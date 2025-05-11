from django.test import SimpleTestCase

from ..utils import setup


class SetupTests(SimpleTestCase):
    def test_setup(self):
        """

        Tests that the setup method runs cases in the correct order, 
        specifically verifying the expected values of string_if_invalid and debug attributes.

        """
        cases = []

        @setup({})
        def method(self):
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
