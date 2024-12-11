from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--foo-list", nargs="+", type=int, required=True)

    def handle(self, *args, **options):
        """
        Handles incoming options and writes their values to the standard output.

        This function iterates over the provided keyword arguments (options), 
        displaying each option name and its corresponding value. It can be used 
        to echo or log command-line options and their values for debugging or 
        informational purposes.

        :arg args: Variable number of positional arguments (not used in this implementation)
        :arg options: Keyword arguments to be handled and displayed
        """
        for option, value in options.items():
            self.stdout.write("%s=%s" % (option, value))
