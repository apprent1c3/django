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

        Initialize the object with various options.

        This initializer sets up the object's properties and behavior. It accepts several parameters to customize its operation.

        The following options control the object's behavior:
        - `verbosity`: The level of detail to display during operation (default: 1).
        - `interactive`: Whether to operate in interactive mode (default: True).
        - `failfast`: Whether to stop operation upon encountering an error (default: True).

        Additional options `option_a`, `option_b`, and `option_c` can be specified to further customize the object's behavior.

        Any additional keyword arguments (`**kwargs`) are also accepted and processed by the parent class.

        Returns:
            None

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
