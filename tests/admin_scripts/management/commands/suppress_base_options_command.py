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
        Adds arguments to the parser, including the base argument for specifying an input file.

        This method extends the argument configuration by incorporating the base arguments
        from the parent class and adding a 'file' argument. The 'file' argument is optional
        and allows users to specify an input file for further processing. The parser is
        modified in-place to include these additional arguments.

        :param parser: The parser object to which the arguments will be added.

        """
        super().add_arguments(parser)
        self.add_base_argument(parser, "file", nargs="?", help="input file")

    def handle(self, *labels, **options):
        print("EXECUTE:SuppressBaseOptionsCommand options=%s" % sorted(options.items()))
