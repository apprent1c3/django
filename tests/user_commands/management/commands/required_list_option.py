from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--foo-list", nargs="+", type=int, required=True)

    def handle(self, *args, **options):
        """
        Handles command execution by printing provided options.

        This method takes in a variable number of arguments and keyword arguments,
        and iterates over the keyword arguments to output each option and its corresponding value.
        The output is written to the standard output stream, making it useful for logging and debugging purposes.

        :arg *args: Variable number of arguments (not used in this implementation)
        :arg **options: Keyword arguments to be processed and printed
        """
        for option, value in options.items():
            self.stdout.write("%s=%s" % (option, value))
