from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """
        This is a comment
        """
        subparsers = parser.add_subparsers(dest="subcommand", required=True)
        parser_foo = subparsers.add_parser("foo")
        parser_foo.add_argument("--bar")

    def handle(self, *args, **options):
        """
        This is a comment
        """
        self.stdout.write(",".join(options))
