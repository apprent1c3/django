import sys

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.utils import get_command_line_option
from django.test.runner import get_max_test_processes
from django.test.utils import NullTimeKeeper, TimeKeeper, get_runner


class Command(BaseCommand):
    help = "Discover and run tests in the specified modules or the current directory."

    # DiscoverRunner runs the checks after databases are set up.
    requires_system_checks = []
    test_runner = None

    def run_from_argv(self, argv):
        """
        Pre-parse the command line to extract the value of the --testrunner
        option. This allows a test runner to define additional command line
        arguments.
        """
        self.test_runner = get_command_line_option(argv, "--testrunner")
        super().run_from_argv(argv)

    def add_arguments(self, parser):
        """
        Adds command line arguments to the test management parser. These arguments allow users to specify the tests to run, control interactive input, and select a custom test runner. Additional arguments may be added by the test runner class if it implements the 'add_arguments' method.
        """
        parser.add_argument(
            "args",
            metavar="test_label",
            nargs="*",
            help=(
                "Module paths to test; can be modulename, modulename.TestCase or "
                "modulename.TestCase.test_method"
            ),
        )
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Tells Django to NOT prompt the user for input of any kind.",
        )
        parser.add_argument(
            "--testrunner",
            help="Tells Django to use specified test runner class instead of "
            "the one specified by the TEST_RUNNER setting.",
        )

        test_runner_class = get_runner(settings, self.test_runner)

        if hasattr(test_runner_class, "add_arguments"):
            test_runner_class.add_arguments(parser)

    def handle(self, *test_labels, **options):
        """

        Run tests with the specified labels and options.

        This function is the main entry point for test execution, handling test discovery, 
        execution, and reporting. It supports various options for customizing the test run, 
        such as the test runner, timing, and parallel execution.

        :param test_labels: variable number of test labels to run
        :param options: keyword arguments for customizing the test run

        """
        TestRunner = get_runner(settings, options["testrunner"])

        time_keeper = TimeKeeper() if options.get("timing", False) else NullTimeKeeper()
        parallel = options.get("parallel")
        if parallel == "auto":
            options["parallel"] = get_max_test_processes()
        test_runner = TestRunner(**options)
        with time_keeper.timed("Total run"):
            failures = test_runner.run_tests(test_labels)
        time_keeper.print_results()
        if failures:
            sys.exit(1)
