from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """
        Adds command line argument parsing functionality to the application.

        This method configures a parser to accept subcommands, specifically adding a 'foo' subcommand with a '--bar' option. The 'foo' subcommand is a required argument, and the '--bar' option allows for additional configuration. The parser is set up to store the selected subcommand in the 'subcommand' destination.
        """
        subparsers = parser.add_subparsers(dest="subcommand", required=True)
        parser_foo = subparsers.add_parser("foo")
        parser_foo.add_argument("--bar")

    def handle(self, *args, **options):
        self.stdout.write(",".join(options))
