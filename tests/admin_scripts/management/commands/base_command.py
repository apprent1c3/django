from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test basic commands"
    requires_system_checks = []

    def add_arguments(self, parser):
        """
        Adds command line arguments to the parser, allowing users to customize the behavior of the application.

        The following arguments are supported:
            * Positional arguments (`args`): zero or more arbitrary values
            * Optional arguments:
                + `--option_a` (`-a`): specifies an option with a default value of '1'
                + `--option_b` (`-b`): specifies an option with a default value of '2'
                + `--option_c` (`-c`): specifies an option with a default value of '3'

        These options can be used to modify the application's behavior, with the defaults being used if not explicitly provided.
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
