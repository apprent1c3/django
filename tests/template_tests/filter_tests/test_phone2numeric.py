from django.template.defaultfilters import phone2numeric_filter
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class Phone2numericTests(SimpleTestCase):
    @setup({"phone2numeric01": "{{ a|phone2numeric }} {{ b|phone2numeric }}"})
    def test_phone2numeric01(self):
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

        Tests the phone2numeric template filter by rendering a template string 
        with HTML-unsafe and safe input values and asserting the output is correct.

        The filter is expected to convert the input phone numbers to their numeric 
        equivalents, ignoring HTML tags and other non-numeric characters.

        The test covers two cases: one with a string containing HTML tags and 
        another with a string marked as safe, to ensure the filter behaves as 
        expected in both scenarios.

        """
        output = self.engine.render_to_string(
            "phone2numeric02",
            {"a": "<1-800-call-me>", "b": mark_safe("<1-800-call-me>")},
        )
        self.assertEqual(output, "<1-800-2255-63> <1-800-2255-63>")

    @setup({"phone2numeric03": "{{ a|phone2numeric }}"})
    def test_phone2numeric03(self):
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
