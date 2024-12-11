from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        """

        Adds command line arguments to the parser.

        This method defines a mutually exclusive group of arguments, meaning only one of the arguments in the group can be provided.
        The group includes options to specify a foo id, foo name, or a list of foo ids.
        Additionally, several special action arguments are available, including flags to append a constant value, store a constant value, count the number of occurrences, and set a flag to true or false.

        The arguments in the group are:
            - foo-id: an optional integer id
            - foo-name: an optional string name
            - foo-list: a list of one or more integer ids
            - append-const: appends a constant value to a list
            - const: stores a constant value
            - count: counts the number of occurrences
            - flag_false: sets a flag to false
            - flag_true: sets a flag to true

        Note that at least one of the arguments in the group must be provided.

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
        Handles and outputs the provided options and their corresponding values.

        This function takes in a variable number of keyword arguments and iterates over them.
        For each option with a value that is not None, it writes the option and its value to the standard output.
        The output is formatted as 'option=value', making it easy to parse and understand the provided options.
        """
        for option, value in options.items():
            if value is not None:
                self.stdout.write("%s=%s" % (option, value))
