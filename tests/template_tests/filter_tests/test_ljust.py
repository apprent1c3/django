from django.template.defaultfilters import ljust
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class LjustTests(SimpleTestCase):
    @setup(
        {
            "ljust01": (
                '{% autoescape off %}.{{ a|ljust:"5" }}. .{{ b|ljust:"5" }}.'
                "{% endautoescape %}"
            )
        }
    )
    def test_ljust01(self):
        output = self.engine.render_to_string(
            "ljust01", {"a": "a&b", "b": mark_safe("a&b")}
        )
        self.assertEqual(output, ".a&b  . .a&b  .")

    @setup({"ljust02": '.{{ a|ljust:"5" }}. .{{ b|ljust:"5" }}.'})
    def test_ljust02(self):
        """

        Tests the functionality of the ljust filter in template rendering.

        Checks that the filter correctly left-justifies the input strings in a field of specified width.
        The test also verifies the filter's behavior with special characters, ensuring proper escaping and handling of HTML-safe input.

        """
        output = self.engine.render_to_string(
            "ljust02", {"a": "a&b", "b": mark_safe("a&b")}
        )
        self.assertEqual(output, ".a&amp;b  . .a&b  .")


class FunctionTests(SimpleTestCase):
    def test_ljust(self):
        """
        Tests the functionality of the ljust function, which left-justifies a string within a specified width.

        The test cases verify that the function correctly pads the input string with spaces to reach the desired width, 
        and that it returns the original string if the width is less than or equal to the string's length. 

        This ensures that the ljust function behaves as expected in various scenarios, providing confidence in its usage for string formatting tasks.
        """
        self.assertEqual(ljust("test", 10), "test      ")
        self.assertEqual(ljust("test", 3), "test")

    def test_less_than_string_length(self):
        self.assertEqual(ljust("test", 3), "test")

    def test_non_string_input(self):
        self.assertEqual(ljust(123, 4), "123 ")
