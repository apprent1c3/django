from django.template.defaultfilters import iriencode, urlencode
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class IriencodeTests(SimpleTestCase):
    """
    Ensure iriencode keeps safe strings.
    """

    @setup({"iriencode01": "{{ url|iriencode }}"})
    def test_iriencode01(self):
        """
        Tests the iriencode filter to ensure it properly encodes URLs by replacing special characters with their corresponding HTML entities.

        The filter is applied to a URL string containing special characters, and the output is compared to the expected HTML-encoded string. This test verifies that the filter correctly replaces ampersands (&) with their HTML entity equivalent (&amp;), ensuring the URL is properly encoded for use in HTML contexts.
        """
        output = self.engine.render_to_string("iriencode01", {"url": "?test=1&me=2"})
        self.assertEqual(output, "?test=1&amp;me=2")

    @setup(
        {"iriencode02": "{% autoescape off %}{{ url|iriencode }}{% endautoescape %}"}
    )
    def test_iriencode02(self):
        """
        Tests the iriencode filter when rendering a template with the 'iriencode' tag, verifying that the filter correctly encodes special characters in a URL query string.
        """
        output = self.engine.render_to_string("iriencode02", {"url": "?test=1&me=2"})
        self.assertEqual(output, "?test=1&me=2")

    @setup({"iriencode03": "{{ url|iriencode }}"})
    def test_iriencode03(self):
        """
        Tests that the iriencode filter correctly encodes an Internationalized Resource Identifier (IRI) without modifying its query parameters. 
        The function verifies that the output of the iriencode filter matches the expected output when passed a URL with query parameters, ensuring proper handling and encoding of special characters in URLs.
        """
        output = self.engine.render_to_string(
            "iriencode03", {"url": mark_safe("?test=1&me=2")}
        )
        self.assertEqual(output, "?test=1&me=2")

    @setup(
        {"iriencode04": "{% autoescape off %}{{ url|iriencode }}{% endautoescape %}"}
    )
    def test_iriencode04(self):
        """
        Tests that the iriencode filter properly handles URL query strings when autoescaping is disabled, ensuring that the output matches the expected result without any unwanted character encoding.
        """
        output = self.engine.render_to_string(
            "iriencode04", {"url": mark_safe("?test=1&me=2")}
        )
        self.assertEqual(output, "?test=1&me=2")


class FunctionTests(SimpleTestCase):
    def test_unicode(self):
        self.assertEqual(iriencode("S\xf8r-Tr\xf8ndelag"), "S%C3%B8r-Tr%C3%B8ndelag")

    def test_urlencoded(self):
        self.assertEqual(
            iriencode(urlencode("fran\xe7ois & jill")), "fran%C3%A7ois%20%26%20jill"
        )
