from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """
        Adds command-line arguments to a parser.

        The arguments added are:
            * --append_const: appends a constant value to a list
            * --const: sets a constant value
            * --count: counts the number of occurrences
            * --flag_false: sets a flag to False
            * --flag_true: sets a flag to True

        All arguments are required.
        """
        parser.add_argument(
            "--append_const",
            action="append_const",
            const=42,
            required=True,
        )
        parser.add_argument("--const", action="store_const", const=31, required=True)
        parser.add_argument("--count", action="count", required=True)
        parser.add_argument("--flag_false", action="store_false", required=True)
        parser.add_argument("--flag_true", action="store_true", required=True)

    def handle(self, *args, **options):
        for option, value in options.items():
            if value is not None:
                self.stdout.write("%s=%s" % (option, value))
