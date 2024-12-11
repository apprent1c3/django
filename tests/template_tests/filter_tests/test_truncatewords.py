from django.template.defaultfilters import truncatewords
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class TruncatewordsTests(SimpleTestCase):
    @setup(
        {
            "truncatewords01": (
                '{% autoescape off %}{{ a|truncatewords:"2" }} {{ b|truncatewords:"2"}}'
                "{% endautoescape %}"
            )
        }
    )
    def test_truncatewords01(self):
        """
        Tests the truncatewords filter by rendering a template that applies the filter to two different strings.

        The test checks if the filter correctly truncates the input strings to the specified number of words and handles HTML entities properly.

        Args:
            None

        Returns:
            None

        Asserts that the rendered template output matches the expected truncated string.
        """
        output = self.engine.render_to_string(
            "truncatewords01",
            {"a": "alpha & bravo", "b": mark_safe("alpha &amp; bravo")},
        )
        self.assertEqual(output, "alpha & … alpha &amp; …")

    @setup({"truncatewords02": '{{ a|truncatewords:"2" }} {{ b|truncatewords:"2"}}'})
    def test_truncatewords02(self):
        """

        Tests the truncatewords template filter with two input strings.
        The filter truncates each string to a specified number of words, 
        appending an ellipsis if the string is longer than the limit. 

        In this case, the test renders a template with two variables, 
        'a' and 'b', which are truncated to 2 words each. 

        The expected output is compared to the actual rendered string 
        to ensure the filter is working correctly with both escaped 
        and unescaped HTML entities. 

        """
        output = self.engine.render_to_string(
            "truncatewords02",
            {"a": "alpha & bravo", "b": mark_safe("alpha &amp; bravo")},
        )
        self.assertEqual(output, "alpha &amp; … alpha &amp; …")


class FunctionTests(SimpleTestCase):
    def test_truncate(self):
        self.assertEqual(truncatewords("A sentence with a few words in it", 1), "A …")

    def test_truncate2(self):
        self.assertEqual(
            truncatewords("A sentence with a few words in it", 5),
            "A sentence with a few …",
        )

    def test_overtruncate(self):
        self.assertEqual(
            truncatewords("A sentence with a few words in it", 100),
            "A sentence with a few words in it",
        )

    def test_invalid_number(self):
        self.assertEqual(
            truncatewords("A sentence with a few words in it", "not a number"),
            "A sentence with a few words in it",
        )

    def test_non_string_input(self):
        self.assertEqual(truncatewords(123, 2), "123")
