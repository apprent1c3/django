from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class RandomTests(SimpleTestCase):
    @setup({"random01": "{{ a|random }} {{ b|random }}"})
    def test_random01(self):
        """

        Tests the rendering of a template with random values, ensuring that HTML special characters are properly escaped.

        The test case verifies that the rendered output correctly escapes ampersands (&) to their HTML entity equivalent (&amp;), 
        even when the input values are marked as safe. This ensures that the rendered template produces valid and safe HTML output.

        """
        output = self.engine.render_to_string(
            "random01", {"a": ["a&b", "a&b"], "b": [mark_safe("a&b"), mark_safe("a&b")]}
        )
        self.assertEqual(output, "a&amp;b a&b")

    @setup(
        {
            "random02": (
                "{% autoescape off %}{{ a|random }} {{ b|random }}{% endautoescape %}"
            )
        }
    )
    def test_random02(self):
        """
        ```
        Tests the rendering of the random02 template with HTML-safe strings.

        This test case checks if the rendering engine correctly handles auto-escaping and
        marks the output as safe when necessary, ensuring that special characters are not
        escaped in the final output. It verifies that the rendered string matches the
        expected output without any HTML escaping.
        ```
        """
        output = self.engine.render_to_string(
            "random02", {"a": ["a&b", "a&b"], "b": [mark_safe("a&b"), mark_safe("a&b")]}
        )
        self.assertEqual(output, "a&b a&b")

    @setup({"empty_list": "{{ list|random }}"})
    def test_empty_list(self):
        """

        Tests rendering of an empty list in a template.

        Verifies that when an empty list is passed to the 'empty_list' template,
        the output is an empty string, indicating correct handling of empty data structures.

        """
        output = self.engine.render_to_string("empty_list", {"list": []})
        self.assertEqual(output, "")
