from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test basic commands"
    requires_system_checks = []

    def add_arguments(self, parser):
        """

        Add command line arguments to the parser.

        This method defines the set of command line arguments that can be passed to the application.
        It provides the ability to specify positional arguments and several options that can be used to customize the behavior.

        The available options are:
            - --option_a or -a: specifies the value for option A (default: '1')
            - --option_b or -b: specifies the value for option B (default: '2')
            - --option_c or -c: specifies the value for option C (default: '3')
            - args: zero or more positional arguments that can be used to provide additional input

        The function returns nothing, it modifies the parser object in place.

        """
        parser.add_argument("args", nargs="*")
        parser.add_argument("--option_a", "-a", default="1")
        parser.add_argument("--option_b", "-b", default="2")
        parser.add_argument("--option_c", "-c", default="3")

    def handle(self, *labels, **options):
        print(
            "EXECUTE:BaseCommand labels=%s, options=%s"
            % (labels, sorted(options.items()))
        )
