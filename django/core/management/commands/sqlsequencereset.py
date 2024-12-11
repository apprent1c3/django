from django.core.management.base import AppCommand
from django.db import DEFAULT_DB_ALIAS, connections


class Command(AppCommand):
    help = (
        "Prints the SQL statements for resetting sequences for the given app name(s)."
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

    def handle_app_config(self, app_config, **options):
        """

        Handles the application configuration for sequence resetting.

        This function takes an application configuration and optional keyword arguments,
        then returns a string of SQL statements to reset sequences for the given models.
        If no sequences are found and verbosity is high enough, a message will be written to stderr.
        The function does nothing if the models module is not defined or is None.

        :param app_config: The application configuration to handle.
        :param options: Additional keyword arguments, including 'database' and 'verbosity'.
        :return: A string of SQL statements to reset sequences, or an empty string if no sequences are found.

        """
        if app_config.models_module is None:
            return
        connection = connections[options["database"]]
        models = app_config.get_models(include_auto_created=True)
        statements = connection.ops.sequence_reset_sql(self.style, models)
        if not statements and options["verbosity"] >= 1:
            self.stderr.write("No sequences found.")
        return "\n".join(statements)
