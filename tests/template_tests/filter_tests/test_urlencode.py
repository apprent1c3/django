from django.template.defaultfilters import urlencode
from django.test import SimpleTestCase

from ..utils import setup


class UrlencodeTests(SimpleTestCase):
    @setup({"urlencode01": "{{ url|urlencode }}"})
    def test_urlencode01(self):
        output = self.engine.render_to_string("urlencode01", {"url": '/test&"/me?/'})
        self.assertEqual(output, "/test%26%22/me%3F/")

    @setup({"urlencode02": '/test/{{ urlbit|urlencode:"" }}/'})
    def test_urlencode02(self):
        """
        testName: test_urlencode02
            Tests whether the urlencode filter correctly URL encodes a string containing a slash (/) within a template path.

            The function verifies that the output string matches the expected URL-encoded result, ensuring that special characters are properly escaped.
            It checks for correct replacement of special characters with their corresponding URL-encoded equivalents.
        """
        output = self.engine.render_to_string("urlencode02", {"urlbit": "escape/slash"})
        self.assertEqual(output, "/test/escape%2Fslash/")


class FunctionTests(SimpleTestCase):
    def test_urlencode(self):
        self.assertEqual(urlencode("fran\xe7ois & jill"), "fran%C3%A7ois%20%26%20jill")

    def test_non_string_input(self):
        self.assertEqual(urlencode(1), "1")
