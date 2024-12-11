from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Dance around like a madman."
    args = ""
    requires_system_checks = "__all__"

    def add_arguments(self, parser):
        parser.add_argument("integer", nargs="?", type=int, default=0)
        parser.add_argument("-s", "--style", default="Rock'n'Roll")
        parser.add_argument("-x", "--example")
        parser.add_argument("--opt-3", action="store_true", dest="option3")

    def handle(self, *args, **options):
        """

        Handles a command with optional arguments and keyword options.

        This function accepts variable arguments and keyword options. It first checks the value of the 'example' option and raises a CommandError if it is set to 'raise'. 

        It then checks the verbosity level and writes messages to the standard output if verbosity is greater than 0. The messages include a styled text and a comma-separated list of options.

        Finally, it checks if an integer option is provided and greater than 0, and writes a message to the standard output indicating the integer value passed as a positional argument.

        :param args: variable positional arguments
        :param options: keyword options, including 'example', 'verbosity', 'style', and 'integer'
        :raises CommandError: if 'example' option is set to 'raise'

        """
        example = options["example"]
        if example == "raise":
            raise CommandError(returncode=3)
        if options["verbosity"] > 0:
            self.stdout.write("I don't feel like dancing %s." % options["style"])
            self.stdout.write(",".join(options))
        if options["integer"] > 0:
            self.stdout.write(
                "You passed %d as a positional argument." % options["integer"]
            )
