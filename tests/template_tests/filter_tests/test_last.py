from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class LastTests(SimpleTestCase):
    @setup({"last01": "{{ a|last }} {{ b|last }}"})
    def test_last01(self):
        output = self.engine.render_to_string(
            "last01", {"a": ["x", "a&b"], "b": ["x", mark_safe("a&b")]}
        )
        self.assertEqual(output, "a&amp;b a&b")

    @setup(
        {"last02": "{% autoescape off %}{{ a|last }} {{ b|last }}{% endautoescape %}"}
    )
    def test_last02(self):
        """

        Tests the 'last' filter on list elements with special characters.

        Verifies that the 'last' filter correctly returns the last element of a list,
        even when the element contains special characters such as ampersands, and
        that the output is not autoescaped, allowing for any HTML entities to be rendered
        as is, and that the mark_safe function allows the rendering of strings containing
        special characters without being autoescaped.

        """
        output = self.engine.render_to_string(
            "last02", {"a": ["x", "a&b"], "b": ["x", mark_safe("a&b")]}
        )
        self.assertEqual(output, "a&b a&b")

    @setup({"empty_list": "{% autoescape off %}{{ a|last }}{% endautoescape %}"})
    def test_empty_list(self):
        output = self.engine.render_to_string("empty_list", {"a": []})
        self.assertEqual(output, "")
