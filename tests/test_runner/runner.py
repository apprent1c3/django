from django.test.runner import DiscoverRunner


class CustomOptionsTestRunner(DiscoverRunner):
    def __init__(
        self,
        verbosity=1,
        interactive=True,
        failfast=True,
        option_a=None,
        option_b=None,
        option_c=None,
        **kwargs,
    ):
        """
        Initializes the object with various options to control its behavior.

        :param int verbosity: The level of detail to include in output, with higher values producing more verbose output (default: 1)
        :param bool interactive: Whether to run in interactive mode (default: True)
        :param bool failfast: Whether to stop execution as soon as a failure occurs (default: True)
        :param option_a: Custom option a (default: None)
        :param option_b: Custom option b (default: None)
        :param option_c: Custom option c (default: None)
        :param dict kwargs: Additional keyword arguments to pass to the parent class

        The object's behavior can be customized through the provided options, allowing for tailored usage in different scenarios. The custom options (option_a, option_b, option_c) can be used to store additional settings specific to the object's functionality.
        """
        super().__init__(
            verbosity=verbosity, interactive=interactive, failfast=failfast
        )
        self.option_a = option_a
        self.option_b = option_b
        self.option_c = option_c

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument("--option_a", "-a", default="1")
        parser.add_argument("--option_b", "-b", default="2")
        parser.add_argument("--option_c", "-c", default="3")

    def run_tests(self, test_labels, **kwargs):
        print("%s:%s:%s" % (self.option_a, self.option_b, self.option_c))
