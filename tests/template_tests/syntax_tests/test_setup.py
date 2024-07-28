from django.test import SimpleTestCase

from ..utils import setup


class SetupTests(SimpleTestCase):
    def test_setup(self):
        """
        This is a comment
        """
        cases = []

        @setup({})
        def method(self):
            """
            This is a comment
            """
            cases.append(
                [
                    self.engine.string_if_invalid,
                    self.engine.debug,
                ]
            )

        method(self)

        self.assertEqual(cases[0], ["", False])
        self.assertEqual(cases[1], ["", False])
        self.assertEqual(cases[2], ["INVALID", False])
        self.assertEqual(cases[3], ["INVALID", False])
        self.assertEqual(cases[4], ["", True])
        self.assertEqual(cases[5], ["", True])
