from django.template.defaultfilters import first
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class FirstTests(SimpleTestCase):
    @setup({"first01": "{{ a|first }} {{ b|first }}"})
    def test_first01(self):
        """

        Tests the first filter functionality in the templating engine.

        This function verifies that the first filter correctly extracts the first element 
        from a given list. It also checks that the filter handles HTML-escaped strings 
        correctly, ensuring that special characters are properly rendered.

        The test case includes two lists, 'a' and 'b', each containing HTML-escaped and 
        non-escaped strings. The expected output is compared to the actual rendered 
        string to confirm the correctness of the first filter implementation.

        """
        output = self.engine.render_to_string(
            "first01", {"a": ["a&b", "x"], "b": [mark_safe("a&b"), "x"]}
        )
        self.assertEqual(output, "a&amp;b a&b")

    @setup(
        {
            "first02": (
                "{% autoescape off %}{{ a|first }} {{ b|first }}{% endautoescape %}"
            )
        }
    )
    def test_first02(self):
        """

        Tests the Jinja2 'first' filter's behavior in templates, 
        particularly when handling escaped and unescaped string values 
        and HTML-unsafe characters.

        Checks that the filter correctly extracts the first item from 
        lists containing escaped and unescaped strings.

        """
        output = self.engine.render_to_string(
            "first02", {"a": ["a&b", "x"], "b": [mark_safe("a&b"), "x"]}
        )
        self.assertEqual(output, "a&b a&b")


class FunctionTests(SimpleTestCase):
    def test_list(self):
        self.assertEqual(first([0, 1, 2]), 0)

    def test_empty_string(self):
        self.assertEqual(first(""), "")

    def test_string(self):
        self.assertEqual(first("test"), "t")
