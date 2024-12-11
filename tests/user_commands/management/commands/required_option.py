from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """

        Add required command line arguments to an argument parser.

        This method extends an ArgumentParser instance with two required command line arguments:
        - need-me: a required argument, accessible via the '-n' or '--need-me' flags
        - need-me-too: a required argument, accessible via the '-t' or '--need-me-too' flags, stored under the 'needme2' destination

        Both arguments must be provided when using the parser to successfully parse the command line.

        """
        parser.add_argument("-n", "--need-me", required=True)
        parser.add_argument("-t", "--need-me-too", required=True, dest="needme2")

    def handle(self, *args, **options):
        self.stdout.write(",".join(options))
