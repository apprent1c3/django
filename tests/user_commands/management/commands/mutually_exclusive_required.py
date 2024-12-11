from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """
        Adds command line arguments to a parser.

        This function creates a mutually exclusive group of arguments, meaning only one of the arguments can be provided at a time.
        The group includes arguments for specifying a foo identifier, name, or list, as well as flags for appending constants, storing constants, counting, and setting boolean flags.

        The available arguments are:

        * --foo-id: an integer identifier
        * --foo-name: a string name
        * --foo-list: a list of integers
        * --append_const: appends a constant value
        * --const: stores a constant value
        * --count: counts the number of times the flag is provided
        * --flag_false: sets a flag to False
        * --flag_true: sets a flag to True

        At least one of these arguments is required to be provided. The arguments are added to the parser in a way that allows for flexible and convenient command line input.
        """
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--foo-id", type=int, nargs="?", default=None)
        group.add_argument("--foo-name", type=str, nargs="?", default=None)
        group.add_argument("--foo-list", type=int, nargs="+")
        group.add_argument("--append_const", action="append_const", const=42)
        group.add_argument("--const", action="store_const", const=31)
        group.add_argument("--count", action="count")
        group.add_argument("--flag_false", action="store_false")
        group.add_argument("--flag_true", action="store_true")

    def handle(self, *args, **options):
        """

        Handles command line options and writes their values to the standard output.

        This function takes in arbitrary keyword arguments, checks if their values are not None, 
        and then prints each option and its corresponding value to the console.

        Parameters:
            *args: Variable number of non-keyword arguments (not used in this function)
            **options: Keyword arguments to be processed and printed

        """
        for option, value in options.items():
            if value is not None:
                self.stdout.write("%s=%s" % (option, value))
