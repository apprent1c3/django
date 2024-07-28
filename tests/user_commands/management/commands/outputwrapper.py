from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, **options):
        """
        This is a comment
        """
        self.stdout.write("Working...")
        self.stdout.flush()
        self.stdout.write("OK")
