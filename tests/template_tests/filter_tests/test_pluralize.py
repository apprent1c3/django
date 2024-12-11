from decimal import Decimal

from django.template.defaultfilters import pluralize
from django.test import SimpleTestCase

from ..utils import setup


class PluralizeTests(SimpleTestCase):
    def check_values(self, *tests):
        """
        Checks the output of the engine's render_to_string method for multiple test values.

        The function takes in a variable number of tests, where each test is a tuple containing a value and its expected output.
        It renders the template 't' with each test value and asserts that the output matches the expected output.

        This method is useful for testing the engine's rendering behavior with different inputs, and provides detailed information about which test value failed if an assertion fails.

        See Also
        --------
        engine : The engine being tested.
        subTest : A context manager for running subtests.

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
        """
        Tests the pluralize function with integer inputs to ensure correct plural suffixes are applied. 
        The function is expected to return an empty string when the input is 1, indicating a singular form, 
        and 's' for inputs of 0 or any number greater than 1, indicating a plural form.
        """
        self.assertEqual(pluralize(1), "")
        self.assertEqual(pluralize(0), "s")
        self.assertEqual(pluralize(2), "s")

    def test_floats(self):
        self.assertEqual(pluralize(0.5), "s")
        self.assertEqual(pluralize(1.5), "s")

    def test_decimals(self):
        """
        Tests the handling of decimal numbers in the pluralize function.

        This test case checks that decimal numbers are correctly pluralized, 
        verifying that numbers equal to 1 are not pluralized, and all other numbers are.

        It covers the following scenarios:
            - A decimal number equal to 1.
            - A decimal number equal to 0.
            - A decimal number greater than 1.

        """
        self.assertEqual(pluralize(Decimal(1)), "")
        self.assertEqual(pluralize(Decimal(0)), "s")
        self.assertEqual(pluralize(Decimal(2)), "s")

    def test_lists(self):
        """

        Tests the pluralization of lists based on their lengths.

        This test function covers various scenarios to verify the correctness of the pluralize function when dealing with lists.
        It checks for the pluralization rules when the list is empty, contains one element, and contains multiple elements.

        """
        self.assertEqual(pluralize([1]), "")
        self.assertEqual(pluralize([]), "s")
        self.assertEqual(pluralize([1, 2, 3]), "s")

    def test_suffixes(self):
        """
        Test the pluralize function with different suffixes and counts.

        This function checks the behavior of the pluralize function when given various counts and suffix rules.
        It tests the function with simple suffixes, alternative suffixes, and invalid suffix rules to ensure 
        correct behavior in different scenarios. The test cases cover a range of counts, including 1, 0, and 
        2, to verify that the function handles singular and plural forms correctly.

        The function tests the following suffix rules:
        - Simple suffixes (e.g., 'es')
        - Alternative suffixes (e.g., 'y,ies')
        - Invalid suffix rules (e.g., 'y,ies,error')

        By running these tests, we can be confident that the pluralize function behaves as expected and 
        handles different suffix rules and counts correctly.
        """
        self.assertEqual(pluralize(1, "es"), "")
        self.assertEqual(pluralize(0, "es"), "es")
        self.assertEqual(pluralize(2, "es"), "es")
        self.assertEqual(pluralize(1, "y,ies"), "y")
        self.assertEqual(pluralize(0, "y,ies"), "ies")
        self.assertEqual(pluralize(2, "y,ies"), "ies")
        self.assertEqual(pluralize(0, "y,ies,error"), "")

    def test_no_len_type(self):
        """
        Tests that the pluralize function returns an empty string when the input object does not have a __len__ method, regardless of the pluralization rules provided.
        """
        self.assertEqual(pluralize(object(), "y,es"), "")
        self.assertEqual(pluralize(object(), "es"), "")

    def test_value_error(self):
        """
        Tests that the pluralize function raises no errors and returns an empty string when given an empty string as input.

        Args are tested with different pluralization forms to ensure correct handling of empty strings.

        The test checks for the following conditions:
        - An empty string is returned when the input string is empty and the pluralization form includes a comma separator.
        - An empty string is returned when the input string is empty and the pluralization form does not include a comma separator.

        This test case verifies the function's behavior at the boundary of its input domain, ensuring it handles empty strings correctly in various pluralization scenarios.
        """
        self.assertEqual(pluralize("", "y,es"), "")
        self.assertEqual(pluralize("", "es"), "")
