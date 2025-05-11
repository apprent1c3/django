from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """
        Adds subcommands and arguments to a parser, creating a nested structure for foo_1 and foo_2 subcommands with a required --bar argument for foo_2.
        """
        subparsers_1 = parser.add_subparsers(dest="subcommand_1")
        parser_foo_1 = subparsers_1.add_parser("foo_1")
        subparsers_2 = parser_foo_1.add_subparsers(dest="subcommand_2")
        parser_foo_2 = subparsers_2.add_parser("foo_2")
        parser_foo_2.add_argument("--bar", required=True)

    def handle(self, *args, **options):
        self.stdout.write(",".join(options))
