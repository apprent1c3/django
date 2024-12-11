from django.test import SimpleTestCase

from ..utils import setup


class TruncatecharsTests(SimpleTestCase):
    @setup({"truncatechars01": "{{ a|truncatechars:3 }}"})
    def test_truncatechars01(self):
        """
        Test the truncatechars filter functionality.

        This test verifies that the truncatechars filter correctly truncates a given string to a specified length.
        It checks if the filter replaces the truncated part with an ellipsis, as expected.

        The test case uses a template with the truncatechars filter to render a string 'Testing, testing' truncated to 3 characters.
        The expected output is 'Te…', which is then asserted to ensure the filter works as intended.
        """
        output = self.engine.render_to_string(
            "truncatechars01", {"a": "Testing, testing"}
        )
        self.assertEqual(output, "Te…")

    @setup({"truncatechars02": "{{ a|truncatechars:7 }}"})
    def test_truncatechars02(self):
        """
        Tests the truncatechars template filter with a string length less than the truncation limit.

        The truncatechars filter is expected to return the original string when its length is less than or equal to the specified limit. This test case verifies this behavior by comparing the output of the render_to_string method with the original input string.

        :returns: None
        :raises: AssertionError if the output does not match the expected result
        """
        output = self.engine.render_to_string("truncatechars02", {"a": "Testing"})
        self.assertEqual(output, "Testing")

    @setup({"truncatechars03": "{{ a|truncatechars:'e' }}"})
    def test_fail_silently_incorrect_arg(self):
        output = self.engine.render_to_string(
            "truncatechars03", {"a": "Testing, testing"}
        )
        self.assertEqual(output, "Testing, testing")

    @setup({"truncatechars04": "{{ a|truncatechars:3 }}"})
    def test_truncatechars04(self):
        """

        Tests the truncatechars filter functionality with a string length less than the truncated length.

        This test case verifies that when the input string's length is less than the specified truncate length,
        the original string is returned unchanged. It evaluates the render_to_string method of the engine
        with a template containing the truncatechars filter and checks for the expected output.

        """
        output = self.engine.render_to_string("truncatechars04", {"a": "abc"})
        self.assertEqual(output, "abc")
