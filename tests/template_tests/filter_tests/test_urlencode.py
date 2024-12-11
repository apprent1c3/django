from django.template.defaultfilters import urlencode
from django.test import SimpleTestCase

from ..utils import setup


class UrlencodeTests(SimpleTestCase):
    @setup({"urlencode01": "{{ url|urlencode }}"})
    def test_urlencode01(self):
        """

        Tests the urlencode filter functionality.

        This test verifies that the urlencode filter correctly encodes special characters in a URL string.
        It checks if the filter replaces spaces and special characters with their corresponding escape sequences,
        ensuring the output is a properly encoded URL.

        The test uses a sample URL containing special characters to evaluate the filter's performance.

        """
        output = self.engine.render_to_string("urlencode01", {"url": '/test&"/me?/'})
        self.assertEqual(output, "/test%26%22/me%3F/")

    @setup({"urlencode02": '/test/{{ urlbit|urlencode:"" }}/'})
    def test_urlencode02(self):
        """

        Tests the urlencode filter to ensure it correctly escapes special characters in a URL path.

        The urlencode filter is used to encode a string for use in a URL. This test verifies that the filter 
        correctly replaces special characters, such as forward slashes, with their corresponding escape sequences.

        """
        output = self.engine.render_to_string("urlencode02", {"urlbit": "escape/slash"})
        self.assertEqual(output, "/test/escape%2Fslash/")


class FunctionTests(SimpleTestCase):
    def test_urlencode(self):
        self.assertEqual(urlencode("fran\xe7ois & jill"), "fran%C3%A7ois%20%26%20jill")

    def test_non_string_input(self):
        self.assertEqual(urlencode(1), "1")
