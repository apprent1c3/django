from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """
        This is a comment
        """
        parser.add_argument("--list", action="store_true", help="Print all options")

    def handle(self, *args, **options):
        """
        This is a comment
        """
        pass
