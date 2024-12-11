from django.core.management.commands.startproject import Command as BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """
        Adds command line arguments to the parser, extending the base set of arguments.

        The following additional argument is supported:
            --extra: An arbitrary extra value that is passed to the context, allowing for additional customization or data to be provided.
        """
        super().add_arguments(parser)
        parser.add_argument(
            "--extra", help="An arbitrary extra value passed to the context"
        )
