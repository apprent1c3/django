from decimal import Decimal

from django.template.defaultfilters import pluralize
from django.test import SimpleTestCase

from ..utils import setup


class PluralizeTests(SimpleTestCase):
    def check_values(self, *tests):
        """
        Checks that the rendered output of the engine matches the expected values.

        This method takes in a variable number of tests, where each test is a tuple of 
        two values: the value to be rendered and the expected output. It iterates over 
        each test, renders the value using the engine, and asserts that the rendered 
        output matches the expected output. If any of the tests fail, it will be 
        reported separately, allowing for easier identification of the problematic 
        values. The test uses a subTest context to provide more detailed information 
        about the failed test cases. 

        :param tests: A variable number of tuples, where each tuple contains a value 
                      to be rendered and the expected output.

        """
        for value, expected in tests:
            with self.subTest(value=value):
                output = self.engine.render_to_string("t", {"value": value})
                self.assertEqual(output, expected)

    @setup({"t": "vote{{ value|pluralize }}"})
    def test_no_arguments(self):
        self.check_values(("0", "votes"), ("1", "vote"), ("2", "votes"))

    @setup({"t": 'class{{ value|pluralize:"es" }}'})
    def test_suffix(self):
        self.check_values(("0", "classes"), ("1", "class"), ("2", "classes"))

    @setup({"t": 'cand{{ value|pluralize:"y,ies" }}'})
    def test_singular_and_plural_suffix(self):
        self.check_values(("0", "candies"), ("1", "candy"), ("2", "candies"))


class FunctionTests(SimpleTestCase):
    def test_integers(self):
        self.assertEqual(pluralize(1), "")
        self.assertEqual(pluralize(0), "s")
        self.assertEqual(pluralize(2), "s")

    def test_floats(self):
        """
        ..: Tests the pluralize function with floating point numbers to ensure correct plural suffix is returned. 

            The test checks that the pluralize function correctly handles decimal numbers, 
            returning the plural suffix 's' for both numbers less than 1 and greater than 1.
        """
        self.assertEqual(pluralize(0.5), "s")
        self.assertEqual(pluralize(1.5), "s")

    def test_decimals(self):
        """
        Tests the pluralize function with decimal numbers to ensure correct plural suffixes are applied, covering the cases for singular (1) and plural (0, 2 or more) values.
        """
        self.assertEqual(pluralize(Decimal(1)), "")
        self.assertEqual(pluralize(Decimal(0)), "s")
        self.assertEqual(pluralize(Decimal(2)), "s")

    def test_lists(self):
        self.assertEqual(pluralize([1]), "")
        self.assertEqual(pluralize([]), "s")
        self.assertEqual(pluralize([1, 2, 3]), "s")

    def test_suffixes(self):
        self.assertEqual(pluralize(1, "es"), "")
        self.assertEqual(pluralize(0, "es"), "es")
        self.assertEqual(pluralize(2, "es"), "es")
        self.assertEqual(pluralize(1, "y,ies"), "y")
        self.assertEqual(pluralize(0, "y,ies"), "ies")
        self.assertEqual(pluralize(2, "y,ies"), "ies")
        self.assertEqual(pluralize(0, "y,ies,error"), "")

    def test_no_len_type(self):
        """
        Tests the behavior of the pluralize function when the input object does not have a length.

         Verifies that when the input object does not support len() and is thus considered not to have a length,
         the function returns an empty string for plural forms 'y,es' and 'es'.
        """
        self.assertEqual(pluralize(object(), "y,es"), "")
        self.assertEqual(pluralize(object(), "es"), "")

    def test_value_error(self):
        """
        Checks the handling of empty strings by the pluralize function, verifying that it correctly returns an empty string when given no input value and various pluralization rules.
        """
        self.assertEqual(pluralize("", "y,es"), "")
        self.assertEqual(pluralize("", "es"), "")
