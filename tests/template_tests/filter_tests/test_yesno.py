from django.template.defaultfilters import yesno
from django.test import SimpleTestCase

from ..utils import setup


class YesNoTests(SimpleTestCase):
    @setup({"t": '{{ var|yesno:"yup,nup,mup" }} {{ var|yesno }}'})
    def test_true(self):
        output = self.engine.render_to_string("t", {"var": True})
        self.assertEqual(output, "yup yes")


class FunctionTests(SimpleTestCase):
    def test_true(self):
        self.assertEqual(yesno(True), "yes")

    def test_false(self):
        self.assertEqual(yesno(False), "no")

    def test_none(self):
        self.assertEqual(yesno(None), "maybe")

    def test_true_arguments(self):
        self.assertEqual(yesno(True, "certainly,get out of town,perhaps"), "certainly")

    def test_false_arguments(self):
        self.assertEqual(
            yesno(False, "certainly,get out of town,perhaps"), "get out of town"
        )

    def test_none_two_arguments(self):
        self.assertEqual(yesno(None, "certainly,get out of town"), "get out of town")

    def test_none_three_arguments(self):
        self.assertEqual(yesno(None, "certainly,get out of town,perhaps"), "perhaps")

    def test_invalid_value(self):
        """

        Tests the behavior of the yesno function with invalid values.

        This test case checks how the function handles inputs that do not match the expected 'yes' or 'no' values, 
        including boolean true and false, and null input.

        It verifies that the function correctly handles these edge cases and returns the expected results:
        - Returns True when the input matches 'yes'
        - Returns False when the input does not match 'yes'
        - Returns None for a null input.

        """
        self.assertIs(yesno(True, "yes"), True)
        self.assertIs(yesno(False, "yes"), False)
        self.assertIsNone(yesno(None, "yes"))
