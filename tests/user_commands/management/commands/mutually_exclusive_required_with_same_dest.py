from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--for", dest="until", action="store")
        group.add_argument("--until", action="store")

    def handle(self, *args, **options):
        """
        ..: Handles the given command-line options and prints their corresponding values.

            This function takes in a variable number of arguments and keyword arguments representing command-line options.
            It iterates over the provided options, filtering out those with a value of None, and outputs the remaining options and their values to the standard output.
        """
        for option, value in options.items():
            if value is not None:
                self.stdout.write("%s=%s" % (option, value))
