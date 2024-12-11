from django.template.defaultfilters import force_escape
from django.test import SimpleTestCase
from django.utils.safestring import SafeData

from ..utils import setup


class ForceEscapeTests(SimpleTestCase):
    """
    Force_escape is applied immediately. It can be used to provide
    double-escaping, for example.
    """

    @setup(
        {
            "force-escape01": (
                "{% autoescape off %}{{ a|force_escape }}{% endautoescape %}"
            )
        }
    )
    def test_force_escape01(self):
        """
        Tests the force_escape filter in a template when autoescape is disabled.

        This test case verifies that the force_escape filter correctly escapes special characters 
        in a string, even when autoescape is turned off in the template. It checks that the 
        ampersand (&) character is properly replaced with its HTML entity (&amp;).
        """
        output = self.engine.render_to_string("force-escape01", {"a": "x&y"})
        self.assertEqual(output, "x&amp;y")

    @setup({"force-escape02": "{{ a|force_escape }}"})
    def test_force_escape02(self):
        output = self.engine.render_to_string("force-escape02", {"a": "x&y"})
        self.assertEqual(output, "x&amp;y")

    @setup(
        {
            "force-escape03": (
                "{% autoescape off %}{{ a|force_escape|force_escape }}"
                "{% endautoescape %}"
            )
        }
    )
    def test_force_escape03(self):
        """
        Tests the forced HTML escape functionality when autoescaping is disabled.

        Verifies that applying the force_escape filter twice to a template variable 
        results in the correct double-escaped output, even when template autoescaping 
        is turned off. This ensures that the function properly handles nested escapes 
        and produces the expected HTML-safe string.
        """
        output = self.engine.render_to_string("force-escape03", {"a": "x&y"})
        self.assertEqual(output, "x&amp;amp;y")

    @setup({"force-escape04": "{{ a|force_escape|force_escape }}"})
    def test_force_escape04(self):
        output = self.engine.render_to_string("force-escape04", {"a": "x&y"})
        self.assertEqual(output, "x&amp;amp;y")

    # Because the result of force_escape is "safe", an additional
    # escape filter has no effect.
    @setup(
        {
            "force-escape05": (
                "{% autoescape off %}{{ a|force_escape|escape }}{% endautoescape %}"
            )
        }
    )
    def test_force_escape05(self):
        output = self.engine.render_to_string("force-escape05", {"a": "x&y"})
        self.assertEqual(output, "x&amp;y")

    @setup({"force-escape06": "{{ a|force_escape|escape }}"})
    def test_force_escape06(self):
        """
        Tests the force_escape filter within the template engine to ensure it correctly escapes special characters, specifically the ampersand (&), to produce the expected output 'x&amp;y' when given the input 'x&y'.
        """
        output = self.engine.render_to_string("force-escape06", {"a": "x&y"})
        self.assertEqual(output, "x&amp;y")

    @setup(
        {
            "force-escape07": (
                "{% autoescape off %}{{ a|escape|force_escape }}{% endautoescape %}"
            )
        }
    )
    def test_force_escape07(self):
        """
        Testing the rendering of a template with force escape enabled, verifying that the output correctly escapes special characters. Specifically, this test case checks that the `force_escape` filter properly escapes ampersands (&) in the input string, resulting in the expected HTML-escaped output.
        """
        output = self.engine.render_to_string("force-escape07", {"a": "x&y"})
        self.assertEqual(output, "x&amp;amp;y")

    @setup({"force-escape08": "{{ a|escape|force_escape }}"})
    def test_force_escape08(self):
        """

        Tests the force_escape filter in templating.

        This test case verifies that the force_escape filter correctly escapes special characters, 
        ensuring they are properly encoded for display in HTML.
        The expected output is a string where the ampersand (&) is properly escaped to '&amp;'.

        """
        output = self.engine.render_to_string("force-escape08", {"a": "x&y"})
        self.assertEqual(output, "x&amp;amp;y")


class FunctionTests(SimpleTestCase):
    def test_escape(self):
        """
        Tests the proper escaping of HTML and special characters.

        This test case verifies that the force_escape function correctly replaces special characters with their corresponding HTML entities, 
        resulting in a string that is safe to display in an HTML context. The test also checks that the escaped string is an instance of SafeData, 
        indicating that it has been properly sanitized and marked as safe for display.
        """
        escaped = force_escape("<some html & special characters > here")
        self.assertEqual(escaped, "&lt;some html &amp; special characters &gt; here")
        self.assertIsInstance(escaped, SafeData)

    def test_unicode(self):
        self.assertEqual(
            force_escape("<some html & special characters > here ĐÅ€£"),
            "&lt;some html &amp; special characters &gt; here \u0110\xc5\u20ac\xa3",
        )
