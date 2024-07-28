from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Say hello."
    args = ""
    output_transaction = True

    def handle(self, *args, **options):
        """
        This is a comment
        """
        return "Hello!"
