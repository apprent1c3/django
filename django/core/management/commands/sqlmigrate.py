from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.loader import AmbiguityError, MigrationLoader


class Command(BaseCommand):
    help = "Prints the SQL statements for the named migration."

    output_transaction = True

    def add_arguments(self, parser):
        parser.add_argument(
            "app_label", help="App label of the application containing the migration."
        )
        parser.add_argument(
            "migration_name", help="Migration name to print the SQL for."
        )
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            choices=tuple(connections),
            help=(
                'Nominates a database to create SQL for. Defaults to the "default" '
                "database."
            ),
        )
        parser.add_argument(
            "--backwards",
            action="store_true",
            help="Creates SQL to unapply the migration, rather than to apply it",
        )

    def execute(self, *args, **options):
        # sqlmigrate doesn't support coloring its output but we need to force
        # no_color=True so that the BEGIN/COMMIT statements added by
        # output_transaction don't get colored either.
        options["no_color"] = True
        return super().execute(*args, **options)

    def handle(self, *args, **options):
        # Get the database we're operating from
        """
        Handles migration operations for a specified application and migration name.

        This function takes in the application label and migration name as options, 
        loads the migration, and generates the necessary SQL statements for the operation.
        It checks if the application has migrations and if the specified migration exists, 
        resolving any ambiguities or errors that may occur.

        If the operation is successful, it returns the SQL statements as a string. 
        Otherwise, it raises a CommandError with an informative error message.

        The function also considers the verbosity level and outputs messages accordingly.
        It handles both forward and backward migration operations, depending on the provided options.

        :param app_label: The label of the application for which to handle the migration.
        :param migration_name: The name of the migration to handle.
        :param database: The database connection to use for the migration.
        :param backwards: Whether to apply the migration in reverse.
        :param verbosity: The level of verbosity for output messages.
        :return: A string of SQL statements for the migration operation, or an empty string if no operations are found.

        """
        connection = connections[options["database"]]

        # Load up a loader to get all the migration data, but don't replace
        # migrations.
        loader = MigrationLoader(connection, replace_migrations=False)

        # Resolve command-line arguments into a migration
        app_label, migration_name = options["app_label"], options["migration_name"]
        # Validate app_label
        try:
            apps.get_app_config(app_label)
        except LookupError as err:
            raise CommandError(str(err))
        if app_label not in loader.migrated_apps:
            raise CommandError("App '%s' does not have migrations" % app_label)
        try:
            migration = loader.get_migration_by_prefix(app_label, migration_name)
        except AmbiguityError:
            raise CommandError(
                "More than one migration matches '%s' in app '%s'. Please be more "
                "specific." % (migration_name, app_label)
            )
        except KeyError:
            raise CommandError(
                "Cannot find a migration matching '%s' from app '%s'. Is it in "
                "INSTALLED_APPS?" % (migration_name, app_label)
            )
        target = (app_label, migration.name)

        # Show begin/end around output for atomic migrations, if the database
        # supports transactional DDL.
        self.output_transaction = (
            migration.atomic and connection.features.can_rollback_ddl
        )

        # Make a plan that represents just the requested migrations and show SQL
        # for it
        plan = [(loader.graph.nodes[target], options["backwards"])]
        sql_statements = loader.collect_sql(plan)
        if not sql_statements and options["verbosity"] >= 1:
            self.stderr.write("No operations found.")
        return "\n".join(sql_statements)
