from django.core.management import BaseCommand


class Command(BaseCommand):
    help = "Test suppress base options command."
    requires_system_checks = []
    suppressed_base_arguments = {
        "-v",
        "--traceback",
        "--settings",
        "--pythonpath",
        "--no-color",
        "--force-color",
        "--version",
        "file",
    }

    def add_arguments(self, parser):
        """
        Adds command line arguments to the parser, including an optional input file argument.

        Extends the base argument set with a file path parameter, allowing users to specify an input file to be processed.

        :param parser: The argument parser instance to which the arguments will be added

        """
        super().add_arguments(parser)
        self.add_base_argument(parser, "file", nargs="?", help="input file")

    def handle(self, *labels, **options):
        print("EXECUTE:SuppressBaseOptionsCommand options=%s" % sorted(options.items()))
