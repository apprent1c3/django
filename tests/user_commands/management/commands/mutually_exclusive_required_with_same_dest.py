from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--for", dest="until", action="store")
        group.add_argument("--until", action="store")

    def handle(self, *args, **options):
        """
        Handle and display provided command options.

        This function processes the given options and their corresponding values, 
        then writes each non-null option-value pair to the standard output.

        :param args: Variable number of positional arguments (not used in this implementation)
        :param options: Keyword arguments representing command options and their values

        """
        for option, value in options.items():
            if value is not None:
                self.stdout.write("%s=%s" % (option, value))
