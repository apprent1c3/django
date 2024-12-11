from django.template.defaultfilters import center
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class CenterTests(SimpleTestCase):
    @setup(
        {
            "center01": (
                '{% autoescape off %}.{{ a|center:"5" }}. .{{ b|center:"5" }}.'
                "{% endautoescape %}"
            )
        }
    )
    def test_center01(self):
        output = self.engine.render_to_string(
            "center01", {"a": "a&b", "b": mark_safe("a&b")}
        )
        self.assertEqual(output, ". a&b . . a&b .")

    @setup({"center02": '.{{ a|center:"5" }}. .{{ b|center:"5" }}.'})
    def test_center02(self):
        """

        Tests the center template filter with ampersand (&) characters.

        This test case verifies that the center filter correctly handles ampersand characters in the input string,
        escaping them when necessary to ensure proper HTML rendering. The test checks two scenarios:
        one where the input string is not marked as safe, and another where it is marked as safe using the mark_safe function.

        """
        output = self.engine.render_to_string(
            "center02", {"a": "a&b", "b": mark_safe("a&b")}
        )
        self.assertEqual(output, ". a&amp;b . . a&b .")


class FunctionTests(SimpleTestCase):
    def test_center(self):
        self.assertEqual(center("test", 6), " test ")

    def test_non_string_input(self):
        self.assertEqual(center(123, 5), " 123 ")
