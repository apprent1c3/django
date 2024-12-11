from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """

        Add required command-line arguments to the parser.

        This function configures the parser to expect two mandatory arguments:
        - need-me: a required argument that can be specified using either the '-n' or '--need-me' flag.
        - need-me-too: a required argument that can be specified using either the '-t' or '--need-me-too' flag, and is stored under the 'needme2' destination.

        """
        parser.add_argument("-n", "--need-me", required=True)
        parser.add_argument("-t", "--need-me-too", required=True, dest="needme2")

    def handle(self, *args, **options):
        self.stdout.write(",".join(options))
