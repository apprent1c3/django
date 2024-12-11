from django.template.defaultfilters import upper
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class UpperTests(SimpleTestCase):
    """
    The "upper" filter messes up entities (which are case-sensitive),
    so it's not safe for non-escaping purposes.
    """

    @setup(
        {
            "upper01": (
                "{% autoescape off %}{{ a|upper }} {{ b|upper }}{% endautoescape %}"
            )
        }
    )
    def test_upper01(self):
        """

        Tests the upper filter functionality in template rendering.

        This test case verifies that the upper filter correctly converts strings to
        uppercase while respecting the autoescape and mark_safe parameters.
        It checks the rendering of a template with two variables, one containing
        special characters and the other marked as safe, to ensure proper escaping and
        uppercase conversion.

        The expected output is a string with both variables converted to uppercase,
        while maintaining the original special characters and escaping.

        """
        output = self.engine.render_to_string(
            "upper01", {"a": "a & b", "b": mark_safe("a &amp; b")}
        )
        self.assertEqual(output, "A & B A &AMP; B")

    @setup({"upper02": "{{ a|upper }} {{ b|upper }}"})
    def test_upper02(self):
        """

        Tests the upper filter functionality when rendering a string template.

        The test checks that the upper filter correctly converts strings to uppercase,
        while also ensuring that HTML entities are handled correctly when using
        the mark_safe function to bypass HTML escaping.

        The expected output is a string with both input values converted to uppercase,
        preserving the ampersand and HTML entity (&amp;) as required.

        """
        output = self.engine.render_to_string(
            "upper02", {"a": "a & b", "b": mark_safe("a &amp; b")}
        )
        self.assertEqual(output, "A &amp; B A &amp;AMP; B")


class FunctionTests(SimpleTestCase):
    def test_upper(self):
        self.assertEqual(upper("Mixed case input"), "MIXED CASE INPUT")

    def test_unicode(self):
        # lowercase e umlaut
        self.assertEqual(upper("\xeb"), "\xcb")

    def test_non_string_input(self):
        self.assertEqual(upper(123), "123")
