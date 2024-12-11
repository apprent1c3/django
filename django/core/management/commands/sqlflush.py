from django.core.management.base import BaseCommand
from django.core.management.sql import sql_flush
from django.db import DEFAULT_DB_ALIAS, connections


class Command(BaseCommand):
    help = (
        "Returns a list of the SQL statements required to return all tables in "
        "the database to the state they were in just after they were installed."
    )

    output_transaction = True

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            choices=tuple(connections),
            help=(
                'Nominates a database to print the SQL for. Defaults to the "default" '
                "database."
            ),
        )

    def handle(self, **options):
        """

        Handles the flushing of database tables for the given database connection.

        This function generates a set of SQL statements to flush the tables in the specified database.
        If no tables are found and the verbosity level is 1 or higher, it reports that no tables were found.
        The function returns the generated SQL statements as a single string, separated by newlines.

        :param options: A dictionary of options, including 'database' and 'verbosity'
        :return: A string of SQL statements to flush the database tables, or a message if no tables are found

        """
        sql_statements = sql_flush(self.style, connections[options["database"]])
        if not sql_statements and options["verbosity"] >= 1:
            self.stderr.write("No tables found.")
        return "\n".join(sql_statements)
