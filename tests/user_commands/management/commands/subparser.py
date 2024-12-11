from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """
        Adds command line arguments to the application parser.

        This method extends the application parser with a subcommand 'foo' that accepts a required integer argument 'bar'. The 'foo' subcommand can be used to specify an operation that takes an integer value, which can be processed further by the application.
        """
        subparsers = parser.add_subparsers()
        parser_foo = subparsers.add_parser("foo")
        parser_foo.add_argument("bar", type=int)

    def handle(self, *args, **options):
        self.stdout.write(",".join(options))
