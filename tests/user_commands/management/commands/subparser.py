from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """
        ``` 
        :param parser: The parser object to extend with sub-commands
        :returns: None
        :description: Extends the provided parser with sub-commands, allowing for more structured and organized command line argument handling.
        :note: Currently, this function adds a single sub-command 'foo' which expects a single integer argument 'bar'.
        ```
        """
        subparsers = parser.add_subparsers()
        parser_foo = subparsers.add_parser("foo")
        parser_foo.add_argument("bar", type=int)

    def handle(self, *args, **options):
        self.stdout.write(",".join(options))
