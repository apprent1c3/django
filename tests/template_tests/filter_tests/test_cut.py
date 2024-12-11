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
        """

        Tests the behavior of the cut filter when applied to string values with HTML entities.
        It verifies that the filter correctly removes the specified substring and handles HTML escaping.

        Args:
            self (object): The test instance.

        Returns:
            None

        """
        output = self.engine.render_to_string(
            "cut01", {"a": "x&y", "b": mark_safe("x&amp;y")}
        )
        self.assertEqual(output, "&y &amp;y")

    @setup({"cut02": '{{ a|cut:"x" }} {{ b|cut:"x" }}'})
    def test_cut02(self):
        """

        Remove specified characters from string values using the cut filter.

        This function tests the behavior of the cut filter when applied to string values.
        It verifies that the filter correctly removes the specified characters from the input strings,
        regardless of whether the input strings contain HTML-escaped characters.

        The test case renders a template with two string variables, 'a' and 'b', which contain
        the character to be cut. The function then asserts that the output matches the expected result,
        where the character 'x' has been removed from both strings, and any HTML-escaped characters
        are preserved and rendered correctly.

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

        Test the functionality of the cut filter with autoescaping disabled.

        This test verifies that the cut filter correctly removes specified characters
        from a string, and that autoescaping does not interfere with this process.
        The test checks two cases: one where the input string contains an unescaped
        ampersand, and one where the input string contains an escaped ampersand.

        """
        output = self.engine.render_to_string(
            "cut03", {"a": "x&y", "b": mark_safe("x&amp;y")}
        )
        self.assertEqual(output, "xy xamp;y")

    @setup({"cut04": '{{ a|cut:"&" }} {{ b|cut:"&" }}'})
    def test_cut04(self):
        """

        Tests the cut template filter with the '&' character.

        This test case verifies that the cut filter correctly removes the '&' character 
        from the input strings 'a' and 'b', and that it handles HTML-escaped ampersands 
        correctly. The test checks that the output of the rendering process matches the 
        expected result after applying the cut filter.

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
