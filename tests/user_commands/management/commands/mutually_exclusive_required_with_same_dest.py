from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--for", dest="until", action="store")
        group.add_argument("--until", action="store")

    def handle(self, *args, **options):
        """
        hexdigest 
        Handle function arguments and options, printing non-null option values to the standard output.

        Args:
            *args: Variable length non-keyword arguments, not utilized in this function.
            **options: Arbitrary keyword arguments, where each key-value pair is printed if the value is not None.

        Note:
            This function iterates through the provided keyword arguments, checking each value. If a value is not None, it writes the corresponding key-value pair to the standard output in the format 'key=value'.
        """
        for option, value in options.items():
            if value is not None:
                self.stdout.write("%s=%s" % (option, value))
