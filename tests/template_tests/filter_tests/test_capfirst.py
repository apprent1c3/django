from django.template.defaultfilters import capfirst
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class CapfirstTests(SimpleTestCase):
    @setup(
        {
            "capfirst01": (
                "{% autoescape off %}{{ a|capfirst }} {{ b|capfirst }}"
                "{% endautoescape %}"
            )
        }
    )
    def test_capfirst01(self):
        """

        Tests the capfirst template filter when autoescape is turned off.

        This function checks that the capfirst filter correctly capitalizes the first letter of input strings,
        even when the input contains HTML special characters and when the input is marked as safe.

        It verifies that the filter produces the expected output for two different input cases:
        a string with an HTML special character ('>') and a string with an HTML entity ('&gt;') that is marked as safe.

        The function ensures that the capfirst filter works correctly with autoescape turned off,
        producing the expected capitalized output without altering the HTML special characters or entities.

        """
        output = self.engine.render_to_string(
            "capfirst01", {"a": "fred>", "b": mark_safe("fred&gt;")}
        )
        self.assertEqual(output, "Fred> Fred&gt;")

    @setup({"capfirst02": "{{ a|capfirst }} {{ b|capfirst }}"})
    def test_capfirst02(self):
        output = self.engine.render_to_string(
            "capfirst02", {"a": "fred>", "b": mark_safe("fred&gt;")}
        )
        self.assertEqual(output, "Fred&gt; Fred&gt;")


class FunctionTests(SimpleTestCase):
    def test_capfirst(self):
        self.assertEqual(capfirst("hello world"), "Hello world")
