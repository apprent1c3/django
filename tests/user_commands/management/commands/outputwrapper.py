from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, **options):
        """

        Handle a specific operation.

        This method performs some internal processing and provides output feedback to the user.
        It first indicates that the operation has started, then confirms its completion when finished.

        :param options: Additional options that can be used to customize the operation.

        """
        self.stdout.write("Working...")
        self.stdout.flush()
        self.stdout.write("OK")
