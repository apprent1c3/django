from django.test import SimpleTestCase

from ..utils import setup


class TruncatecharsTests(SimpleTestCase):
    @setup({"truncatechars01": "{{ a|truncatechars:3 }}"})
    def test_truncatechars01(self):
        """
        Tests the truncatechars filter with a string input.

        Verifies that the filter correctly truncates a given string to the specified length and appends an ellipsis.

        :raises AssertionError: if the output does not match the expected truncated string
        """
        output = self.engine.render_to_string(
            "truncatechars01", {"a": "Testing, testing"}
        )
        self.assertEqual(output, "Te…")

    @setup({"truncatechars02": "{{ a|truncatechars:7 }}"})
    def test_truncatechars02(self):
        """

        Tests the truncatechars filter functionality with a string length less than the truncate length.

        Verifies that when the input string's length is less than the specified truncate length,
        the output remains unchanged, demonstrating the filter's behavior in such scenarios.

        Args:
            None

        Returns:
            None

        Note:
            This test case is designed to validate the edge case where the input string is shorter than the truncate length.

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
        output = self.engine.render_to_string("truncatechars04", {"a": "abc"})
        self.assertEqual(output, "abc")
