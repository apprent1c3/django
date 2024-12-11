from django.template.defaultfilters import phone2numeric_filter
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class Phone2numericTests(SimpleTestCase):
    @setup({"phone2numeric01": "{{ a|phone2numeric }} {{ b|phone2numeric }}"})
    def test_phone2numeric01(self):
        """

        Tests the 'phone2numeric' filter by rendering a template that applies this filter to two different inputs.
        The filter is expected to convert US-style phone numbers into a standardized numeric format, while preserving HTML safety.
        It checks that the output correctly converts phone numbers to their numeric equivalents, handling both escaped and unescaped HTML input.

        """
        output = self.engine.render_to_string(
            "phone2numeric01",
            {"a": "<1-800-call-me>", "b": mark_safe("<1-800-call-me>")},
        )
        self.assertEqual(output, "&lt;1-800-2255-63&gt; <1-800-2255-63>")

    @setup(
        {
            "phone2numeric02": (
                "{% autoescape off %}{{ a|phone2numeric }} {{ b|phone2numeric }}"
                "{% endautoescape %}"
            )
        }
    )
    def test_phone2numeric02(self):
        """

        Tests the phone2numeric filter by rendering a template with two phone numbers, 
        one marked as safe and the other not, and verifying that both are correctly converted 
        to their numeric equivalents.

        The test case checks that the filter can handle HTML escaped characters and that 
        the output is not affected by the safe status of the input string.

        """
        output = self.engine.render_to_string(
            "phone2numeric02",
            {"a": "<1-800-call-me>", "b": mark_safe("<1-800-call-me>")},
        )
        self.assertEqual(output, "<1-800-2255-63> <1-800-2255-63>")

    @setup({"phone2numeric03": "{{ a|phone2numeric }}"})
    def test_phone2numeric03(self):
        """
        Tests the phone2numeric filter by replacing alphabetic characters with their corresponding numeric equivalent, 
        as found on a standard telephone keypad, and returns the resulting string. 

        This test case checks the filter's ability to replace all alphabetic characters in a given string, ensuring that the output 
        only contains numeric characters and any non-alphabetic characters that were present in the original string. 

        The test verifies that the filter correctly handles a string containing alphabetic characters without any formatting or 
        structuring, resulting in a string that only contains numbers and any non-alphabetic characters from the original string.
        """
        output = self.engine.render_to_string(
            "phone2numeric03",
            {"a": "How razorback-jumping frogs can level six piqued gymnasts!"},
        )
        self.assertEqual(
            output, "469 729672225-5867464 37647 226 53835 749 747833 49662787!"
        )


class FunctionTests(SimpleTestCase):
    def test_phone2numeric(self):
        self.assertEqual(phone2numeric_filter("0800 flowers"), "0800 3569377")
