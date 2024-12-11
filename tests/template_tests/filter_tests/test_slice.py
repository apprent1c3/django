from django.template.defaultfilters import slice_filter
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class SliceTests(SimpleTestCase):
    @setup({"slice01": '{{ a|slice:"1:3" }} {{ b|slice:"1:3" }}'})
    def test_slice01(self):
        """

        Render the 'slice01' template to test the slice filter.

        This test case checks the functionality of the slice filter by passing two variables 'a' and 'b' 
        with the string 'a&b' to the 'slice01' template. The slice filter is applied to extract a subset 
        of characters from the strings. The test verifies that the output is correctly escaped for 'a' 
        and not escaped for 'b' due to the use of mark_safe, resulting in the expected output '&amp;b &b'.

        """
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
        """

        Test the slice filter in template rendering.

        This function verifies that the slice filter correctly extracts a subset of characters
        from a string, ensuring proper handling of HTML special characters and safe strings.
        The test checks that the filter behaves as expected for both regular strings and
        strings marked as safe from HTML escaping.

        """
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
        Tests that the slice_filter function fails silently when given an invalid slice operation, 
        returning the original object unchanged. This ensures that the function does not raise any 
        exceptions when encountering unexpected input, instead providing a predictable and safe output.
        """
        obj = object()
        self.assertEqual(slice_filter(obj, "0::2"), obj)

    def test_empty_dict(self):
        self.assertEqual(slice_filter({}, "1"), {})
