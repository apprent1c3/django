from django.core.management.base import LabelCommand


class Command(LabelCommand):
    help = "Test Label-based commands"
    requires_system_checks = []

    def handle_label(self, label, **options):
        """
        This is a comment
        """
        print(
            "EXECUTE:LabelCommand label=%s, options=%s"
            % (label, sorted(options.items()))
        )
