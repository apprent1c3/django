from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """
        ..: Add command-line arguments to the parser for subcommands.

            This function configures a parser to accept subcommands, specifically adding a subcommand named \"foo\". 
            The \"foo\" subcommand has an option '--bar' that can be provided when invoking the \"foo\" subcommand. 
            The subcommand to be executed is stored in the 'subcommand' destination, and a subcommand must be provided when using the parser.
        """
        subparsers = parser.add_subparsers(dest="subcommand", required=True)
        parser_foo = subparsers.add_parser("foo")
        parser_foo.add_argument("--bar")

    def handle(self, *args, **options):
        self.stdout.write(",".join(options))
