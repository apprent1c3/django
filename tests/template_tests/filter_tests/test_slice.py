from django.template.defaultfilters import slice_filter
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class SliceTests(SimpleTestCase):
    @setup({"slice01": '{{ a|slice:"1:3" }} {{ b|slice:"1:3" }}'})
    def test_slice01(self):
        output = self.engine.render_to_string(
            "slice01", {"a": "a&b", "b": mark_safe("a&b")}
        )
        self.assertEqual(output, "&amp;b &b")

    @setup(
        {
            "slice02": (
                '{% autoescape off %}{{ a|slice:"1:3" }} {{ b|slice:"1:3" }}'
                "{% endautoescape %}"
            )
        }
    )
    def test_slice02(self):
        output = self.engine.render_to_string(
            "slice02", {"a": "a&b", "b": mark_safe("a&b")}
        )
        self.assertEqual(output, "&b &b")


class FunctionTests(SimpleTestCase):
    def test_zero_length(self):
        self.assertEqual(slice_filter("abcdefg", "0"), "")

    def test_index(self):
        self.assertEqual(slice_filter("abcdefg", "1"), "a")

    def test_index_integer(self):
        self.assertEqual(slice_filter("abcdefg", 1), "a")

    def test_negative_index(self):
        self.assertEqual(slice_filter("abcdefg", "-1"), "abcdef")

    def test_range(self):
        self.assertEqual(slice_filter("abcdefg", "1:2"), "b")

    def test_range_multiple(self):
        self.assertEqual(slice_filter("abcdefg", "1:3"), "bc")

    def test_range_step(self):
        self.assertEqual(slice_filter("abcdefg", "0::2"), "aceg")

    def test_fail_silently(self):
        """
        Tests that the slice_filter function silently fails when an object does not support slicing.

        This test case ensures that when an object is passed to the slice_filter function without a valid slicing attribute, 
        the function returns the original object without raising any exceptions or errors, thus maintaining backwards compatibility 
        and preventing any potential system crashes. The expected output is the original object itself, which is verified using 
        an assertion to guarantee the desired behavior. 
        """
        obj = object()
        self.assertEqual(slice_filter(obj, "0::2"), obj)

    def test_empty_dict(self):
        self.assertEqual(slice_filter({}, "1"), {})
