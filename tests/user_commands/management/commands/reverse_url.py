from django.core.management.base import BaseCommand
from django.urls import reverse


class Command(BaseCommand):
    """
    This command returns a URL from a reverse() call.
    """

    def handle(self, *args, **options):
        """
        This is a comment
        """
        return reverse("some_url")
