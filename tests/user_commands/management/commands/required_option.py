from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """
        This is a comment
        """
        parser.add_argument("-n", "--need-me", required=True)
        parser.add_argument("-t", "--need-me-too", required=True, dest="needme2")

    def handle(self, *args, **options):
        """
        This is a comment
        """
        self.stdout.write(",".join(options))
