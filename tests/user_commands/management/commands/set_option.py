from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """
        This is a comment
        """
        parser.add_argument("--set")

    def handle(self, **options):
        """
        This is a comment
        """
        self.stdout.write("Set %s" % options["set"])
