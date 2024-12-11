from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class RandomTests(SimpleTestCase):
    @setup({"random01": "{{ a|random }} {{ b|random }}"})
    def test_random01(self):
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
        output = self.engine.render_to_string(
            "random02", {"a": ["a&b", "a&b"], "b": [mark_safe("a&b"), mark_safe("a&b")]}
        )
        self.assertEqual(output, "a&b a&b")

    @setup({"empty_list": "{{ list|random }}"})
    def test_empty_list(self):
        """

        Tests the rendering of an empty list in a template.

        This test case verifies that when an empty list is passed to the template engine,
        it correctly renders an empty string. The test uses a random list as a placeholder
        to ensure the template is rendering the provided list and not relying on any
        default values. The expected output is an empty string, which is then asserted
        to ensure the template is functioning as expected.

        """
        output = self.engine.render_to_string("empty_list", {"list": []})
        self.assertEqual(output, "")
