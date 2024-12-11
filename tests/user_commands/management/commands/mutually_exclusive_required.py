from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
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
        ..:param args: Additional positional arguments (not used)
        :param options: Options to be processed
        :returns: None
        :rtype: None

        Handles the provided options and prints their values to the standard output, 
        ignoring any options with a value of None. Each option is printed in the format 
        'option=value'.
        """
        for option, value in options.items():
            if value is not None:
                self.stdout.write("%s=%s" % (option, value))
