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
        \".. function:: handle_app_config(app_config, **options)

           Handles application configuration by generating SQL commands to reset sequences 
           for the given models in the specified database connection. Returns a string 
           containing the SQL commands or an empty string if no sequences are found.\"
        """
        if app_config.models_module is None:
            return
        connection = connections[options["database"]]
        models = app_config.get_models(include_auto_created=True)
        statements = connection.ops.sequence_reset_sql(self.style, models)
        if not statements and options["verbosity"] >= 1:
            self.stderr.write("No sequences found.")
        return "\n".join(statements)
