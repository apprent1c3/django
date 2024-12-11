from django.template.defaultfilters import cut
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class CutTests(SimpleTestCase):
    @setup(
        {
            "cut01": (
                '{% autoescape off %}{{ a|cut:"x" }} {{ b|cut:"x" }}{% endautoescape %}'
            )
        }
    )
    def test_cut01(self):
        output = self.engine.render_to_string(
            "cut01", {"a": "x&y", "b": mark_safe("x&amp;y")}
        )
        self.assertEqual(output, "&y &amp;y")

    @setup({"cut02": '{{ a|cut:"x" }} {{ b|cut:"x" }}'})
    def test_cut02(self):
        """

        Test the cut filter with HTML entities.

        This test case verifies that the cut filter correctly removes the specified
        string from the input values, while also ensuring that HTML entities are
        handled properly.

        Args:
            None

        Returns:
            None

        Note:
            This test checks the rendering of a template with the cut filter applied
            to two input values: one containing a plain string and the other containing
            an HTML entity.

        """
        output = self.engine.render_to_string(
            "cut02", {"a": "x&y", "b": mark_safe("x&amp;y")}
        )
        self.assertEqual(output, "&amp;y &amp;y")

    @setup(
        {
            "cut03": (
                '{% autoescape off %}{{ a|cut:"&" }} {{ b|cut:"&" }}{% endautoescape %}'
            )
        }
    )
    def test_cut03(self):
        """
        Tests the cut filter when autoescaping is disabled.

        This test case verifies that the cut filter correctly removes specified characters
        from input strings, even when the input strings contain HTML entities.
        It ensures that the filter behaves as expected when rendering a template with
        autoescaping turned off, and that the output is as expected for both escaped
        and unescaped input strings.

        The test checks the filter's behavior with two input strings: one containing an
        ampersand (&) character, and another containing the HTML entity &amp;.
        The expected output is a string with the ampersand characters removed from the
        first input string, and the HTML entity preserved in the second input string.

        """
        output = self.engine.render_to_string(
            "cut03", {"a": "x&y", "b": mark_safe("x&amp;y")}
        )
        self.assertEqual(output, "xy xamp;y")

    @setup({"cut04": '{{ a|cut:"&" }} {{ b|cut:"&" }}'})
    def test_cut04(self):
        """

        Tests the functionality of the cut filter with ampersand (&) character.

        This test case verifies that the cut filter correctly removes the specified
        character from the input strings. It checks the filter's behavior with both
        normal and HTML-escaped ampersand characters.

        Two input strings are provided: one with an unescaped ampersand and another
        with an HTML-escaped ampersand. The test ensures that the filter correctly
        removes the ampersand from the first string and leaves the escaped ampersand
        intact in the second string.

        """
        output = self.engine.render_to_string(
            "cut04", {"a": "x&y", "b": mark_safe("x&amp;y")}
        )
        self.assertEqual(output, "xy xamp;y")

    # Passing ';' to cut can break existing HTML entities, so those strings
    # are auto-escaped.
    @setup(
        {
            "cut05": (
                '{% autoescape off %}{{ a|cut:";" }} {{ b|cut:";" }}{% endautoescape %}'
            )
        }
    )
    def test_cut05(self):
        output = self.engine.render_to_string(
            "cut05", {"a": "x&y", "b": mark_safe("x&amp;y")}
        )
        self.assertEqual(output, "x&y x&ampy")

    @setup({"cut06": '{{ a|cut:";" }} {{ b|cut:";" }}'})
    def test_cut06(self):
        """

        Test the cut filter to ensure it correctly truncates strings at the specified delimiter.

        The filter is applied to two input strings: one containing an ampersand (&) and another containing a HTML-encoded ampersand (&amp;).
        The expected output is checked to ensure that the filter properly truncates the strings at the delimiter (;) and handles HTML encoding correctly.

        """
        output = self.engine.render_to_string(
            "cut06", {"a": "x&y", "b": mark_safe("x&amp;y")}
        )
        self.assertEqual(output, "x&amp;y x&amp;ampy")


class FunctionTests(SimpleTestCase):
    def test_character(self):
        self.assertEqual(cut("a string to be mangled", "a"), " string to be mngled")

    def test_characters(self):
        self.assertEqual(cut("a string to be mangled", "ng"), "a stri to be maled")

    def test_non_matching_string(self):
        self.assertEqual(
            cut("a string to be mangled", "strings"), "a string to be mangled"
        )

    def test_non_string_input(self):
        self.assertEqual(cut(123, "2"), "13")
