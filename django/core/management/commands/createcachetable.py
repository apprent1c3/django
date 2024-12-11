from django.conf import settings
from django.core.cache import caches
from django.core.cache.backends.db import BaseDatabaseCache
from django.core.management.base import BaseCommand, CommandError
from django.db import (
    DEFAULT_DB_ALIAS,
    DatabaseError,
    connections,
    models,
    router,
    transaction,
)


class Command(BaseCommand):
    help = "Creates the tables needed to use the SQL cache backend."

    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "args",
            metavar="table_name",
            nargs="*",
            help=(
                "Optional table names. Otherwise, settings.CACHES is used to find "
                "cache tables."
            ),
        )
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            choices=tuple(connections),
            help="Nominates a database onto which the cache tables will be "
            'installed. Defaults to the "default" database.',
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Does not create the table, just prints the SQL that would be run.",
        )

    def handle(self, *tablenames, **options):
        """

        Handle the creation of database tables.

        This function takes in a variable number of table names and optional keyword arguments.
        It iterates over the specified table names and creates the corresponding database tables
        using the specified database connection.

        If no table names are provided, it automatically detects and creates tables for all
        configured database caches.

        The function supports the following optional keyword arguments:

        * database: the database connection to use for creating tables
        * verbosity: the level of detail to display during the creation process
        * dry_run: a flag indicating whether to simulate the creation process without actually
          modifying the database

        The function is typically used to initialize or update the database schema to match
        the requirements of the application.

        """
        db = options["database"]
        self.verbosity = options["verbosity"]
        dry_run = options["dry_run"]
        if tablenames:
            # Legacy behavior, tablename specified as argument
            for tablename in tablenames:
                self.create_table(db, tablename, dry_run)
        else:
            for cache_alias in settings.CACHES:
                cache = caches[cache_alias]
                if isinstance(cache, BaseDatabaseCache):
                    self.create_table(db, cache._table, dry_run)

    def create_table(self, database, tablename, dry_run):
        """
        Create a cache table in the specified database with the given table name.

        The table is created with three fields: cache_key (a unique primary key), value (a text field), and expires (a date/time field with a database index).
        The function checks if the table already exists in the database before attempting to create it.
        If the `dry_run` parameter is True, the function will print the SQL statements that would be used to create the table instead of executing them.
        If the creation is successful, a message will be printed to the standard output with the verbosity level set to 1 or higher.
        If the creation fails, a CommandError will be raised with the error message.

        Args:
            database (str): The name of the database to create the table in.
            tablename (str): The name of the table to create.
            dry_run (bool): Whether to simulate the creation of the table instead of actually creating it.

        Returns:
            None
        """
        cache = BaseDatabaseCache(tablename, {})
        if not router.allow_migrate_model(database, cache.cache_model_class):
            return
        connection = connections[database]

        if tablename in connection.introspection.table_names():
            if self.verbosity > 0:
                self.stdout.write("Cache table '%s' already exists." % tablename)
            return

        fields = (
            # "key" is a reserved word in MySQL, so use "cache_key" instead.
            models.CharField(
                name="cache_key", max_length=255, unique=True, primary_key=True
            ),
            models.TextField(name="value"),
            models.DateTimeField(name="expires", db_index=True),
        )
        table_output = []
        index_output = []
        qn = connection.ops.quote_name
        for f in fields:
            field_output = [
                qn(f.name),
                f.db_type(connection=connection),
                "%sNULL" % ("NOT " if not f.null else ""),
            ]
            if f.primary_key:
                field_output.append("PRIMARY KEY")
            elif f.unique:
                field_output.append("UNIQUE")
            if f.db_index:
                unique = "UNIQUE " if f.unique else ""
                index_output.append(
                    "CREATE %sINDEX %s ON %s (%s);"
                    % (
                        unique,
                        qn("%s_%s" % (tablename, f.name)),
                        qn(tablename),
                        qn(f.name),
                    )
                )
            table_output.append(" ".join(field_output))
        full_statement = ["CREATE TABLE %s (" % qn(tablename)]
        for i, line in enumerate(table_output):
            full_statement.append(
                "    %s%s" % (line, "," if i < len(table_output) - 1 else "")
            )
        full_statement.append(");")

        full_statement = "\n".join(full_statement)

        if dry_run:
            self.stdout.write(full_statement)
            for statement in index_output:
                self.stdout.write(statement)
            return

        with transaction.atomic(
            using=database, savepoint=connection.features.can_rollback_ddl
        ):
            with connection.cursor() as curs:
                try:
                    curs.execute(full_statement)
                except DatabaseError as e:
                    raise CommandError(
                        "Cache table '%s' could not be created.\nThe error was: %s."
                        % (tablename, e)
                    )
                for statement in index_output:
                    curs.execute(statement)

        if self.verbosity > 1:
            self.stdout.write("Cache table '%s' created." % tablename)
