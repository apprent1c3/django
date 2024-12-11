from django.template.defaultfilters import length
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class LengthTests(SimpleTestCase):
    @setup({"length01": "{{ list|length }}"})
    def test_length01(self):
        """

        Tests the length filter function in the templating engine.

        The length filter calculates the number of elements in a given list. This test case verifies that the filter correctly counts the elements in a list containing various data types, including strings, None values, boolean values, and dictionaries.

        Examples of use cases include rendering the size of a collection or the number of items in a list. The expected output of this test is '4', indicating that the filter correctly counts the elements in the provided list.

        """
        output = self.engine.render_to_string(
            "length01", {"list": ["4", None, True, {}]}
        )
        self.assertEqual(output, "4")

    @setup({"length02": "{{ list|length }}"})
    def test_length02(self):
        """

        Tests the rendering of a template that displays the length of an empty list.

        Verifies that the length filter correctly returns '0' when the input list is empty.

        :raises AssertionError: If the rendered output is not '0'.

        """
        output = self.engine.render_to_string("length02", {"list": []})
        self.assertEqual(output, "0")

    @setup({"length03": "{{ string|length }}"})
    def test_length03(self):
        """

        Tests the length filter by rendering a template with an empty string.

        The function checks if the rendered output correctly represents the length of the input string.
        In this case, it verifies that an empty string yields a length of 0.

        """
        output = self.engine.render_to_string("length03", {"string": ""})
        self.assertEqual(output, "0")

    @setup({"length04": "{{ string|length }}"})
    def test_length04(self):
        """
        Tests the functionality of the length filter in the templating engine.

        This test case verifies that the length filter correctly calculates the number of characters in a given string.

        It renders a template with the string 'django' and checks if the output is the expected length, which is 6.

        This ensures that the length filter is working as expected and can be used to calculate string lengths in templates.
        """
        output = self.engine.render_to_string("length04", {"string": "django"})
        self.assertEqual(output, "6")

    @setup({"length05": "{% if string|length == 6 %}Pass{% endif %}"})
    def test_length05(self):
        output = self.engine.render_to_string(
            "length05", {"string": mark_safe("django")}
        )
        self.assertEqual(output, "Pass")

    # Invalid uses that should fail silently.
    @setup({"length06": "{{ int|length }}"})
    def test_length06(self):
        """
        Test the rendering of a template with a variable length filter.
        The function checks that when a filter is applied to an integer variable, it returns the length of the integer (as a string) which is always a single digit in this case, hence it tests for a specific edge case where the length should be '1' but the test set expects a different length ('0') for the input integer '7'.
        """
        output = self.engine.render_to_string("length06", {"int": 7})
        self.assertEqual(output, "0")

    @setup({"length07": "{{ None|length }}"})
    def test_length07(self):
        """

        Tests the length filter when passed a None value.

        Checks that the rendering engine correctly handles None values and returns a length of 0.

        """
        output = self.engine.render_to_string("length07", {"None": None})
        self.assertEqual(output, "0")


class FunctionTests(SimpleTestCase):
    def test_string(self):
        self.assertEqual(length("1234"), 4)

    def test_safestring(self):
        self.assertEqual(length(mark_safe("1234")), 4)

    def test_list(self):
        self.assertEqual(length([1, 2, 3, 4]), 4)
