from django.test import SimpleTestCase

from ..utils import SafeClass, UnsafeClass, setup


class AutoescapeStringfilterTests(SimpleTestCase):
    """
    Filters decorated with stringfilter still respect is_safe.
    """

    @setup({"autoescape-stringfilter01": "{{ unsafe|capfirst }}"})
    def test_autoescape_stringfilter01(self):
        output = self.engine.render_to_string(
            "autoescape-stringfilter01", {"unsafe": UnsafeClass()}
        )
        self.assertEqual(output, "You &amp; me")

    @setup(
        {
            "autoescape-stringfilter02": (
                "{% autoescape off %}{{ unsafe|capfirst }}{% endautoescape %}"
            )
        }
    )
    def test_autoescape_stringfilter02(self):
        output = self.engine.render_to_string(
            "autoescape-stringfilter02", {"unsafe": UnsafeClass()}
        )
        self.assertEqual(output, "You & me")

    @setup({"autoescape-stringfilter03": "{{ safe|capfirst }}"})
    def test_autoescape_stringfilter03(self):
        """
        Test autoescape functionality with string filter capfirst.

        Verifies that the autoescape mechanism properly escapes HTML special characters
        in a string, even when the capfirst filter is applied to the string.
        The expected output should have the greater-than symbol replaced with its HTML entity ('&gt;').

        This test ensures that the rendering engine correctly handles the combination of
        autoescaping and string filtering, resulting in a safe and properly formatted output string.
        """
        output = self.engine.render_to_string(
            "autoescape-stringfilter03", {"safe": SafeClass()}
        )
        self.assertEqual(output, "You &gt; me")

    @setup(
        {
            "autoescape-stringfilter04": (
                "{% autoescape off %}{{ safe|capfirst }}{% endautoescape %}"
            )
        }
    )
    def test_autoescape_stringfilter04(self):
        """
        Tests the functionality of autoescape in templating engine when used in conjunction with a string filter.

        The test case verifies that the autoescape feature is properly turned off within a block,
        allowing HTML-special characters to be rendered correctly after passing through a string filter.
        In this instance, the string filter applies the capfirst operation, but the autoescape feature
        is still responsible for handling special characters. The expected output is compared with
        the rendered template string to ensure correct functionality.
        """
        output = self.engine.render_to_string(
            "autoescape-stringfilter04", {"safe": SafeClass()}
        )
        self.assertEqual(output, "You &gt; me")
