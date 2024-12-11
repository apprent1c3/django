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
        """
        Tests the ljust filter with HTML-unsafe and safe input.

        This test case verifies that the ljust filter correctly left-justifies strings 
        within a specified width, ensuring proper handling of HTML-unsafe strings and 
        those marked as safe using mark_safe.

        It checks the output of rendering a template with the ljust filter applied to 
        both an HTML-unsafe string and a string marked as safe, confirming that the 
        resulting output is accurately left-justified and rendered without escaping 
        the safe string. The expected output is a string with the input values 
        left-justified within a field of specified width, surrounded by dots for 
        visibility. 
        """
        output = self.engine.render_to_string(
            "ljust01", {"a": "a&b", "b": mark_safe("a&b")}
        )
        self.assertEqual(output, ".a&b  . .a&b  .")

    @setup({"ljust02": '.{{ a|ljust:"5" }}. .{{ b|ljust:"5" }}.'})
    def test_ljust02(self):
        output = self.engine.render_to_string(
            "ljust02", {"a": "a&b", "b": mark_safe("a&b")}
        )
        self.assertEqual(output, ".a&amp;b  . .a&b  .")


class FunctionTests(SimpleTestCase):
    def test_ljust(self):
        self.assertEqual(ljust("test", 10), "test      ")
        self.assertEqual(ljust("test", 3), "test")

    def test_less_than_string_length(self):
        self.assertEqual(ljust("test", 3), "test")

    def test_non_string_input(self):
        self.assertEqual(ljust(123, 4), "123 ")
