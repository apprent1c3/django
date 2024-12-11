from django.template.defaultfilters import escape
from django.test import SimpleTestCase
from django.utils.functional import Promise, lazy
from django.utils.safestring import mark_safe

from ..utils import setup


class EscapeTests(SimpleTestCase):
    """
    The "escape" filter works the same whether autoescape is on or off,
    but it has no effect on strings already marked as safe.
    """

    @setup({"escape01": "{{ a|escape }} {{ b|escape }}"})
    def test_escape01(self):
        output = self.engine.render_to_string(
            "escape01", {"a": "x&y", "b": mark_safe("x&y")}
        )
        self.assertEqual(output, "x&amp;y x&y")

    @setup(
        {
            "escape02": (
                "{% autoescape off %}{{ a|escape }} {{ b|escape }}{% endautoescape %}"
            )
        }
    )
    def test_escape02(self):
        output = self.engine.render_to_string(
            "escape02", {"a": "x&y", "b": mark_safe("x&y")}
        )
        self.assertEqual(output, "x&amp;y x&y")

    @setup({"escape03": "{% autoescape off %}{{ a|escape|escape }}{% endautoescape %}"})
    def test_escape03(self):
        """
        Tests the autoescaping functionality in templates.

        This test case checks if the autoescape tag behaves correctly when combined with 
        the escape filter. It verifies that the output is properly escaped, even when 
        the autoescape tag is set to off and the escape filter is applied multiple times.

        The test provides an input string containing special characters and checks that 
        the rendered output matches the expected result, ensuring that the escaping is 
        handled correctly.
        """
        output = self.engine.render_to_string("escape03", {"a": "x&y"})
        self.assertEqual(output, "x&amp;y")

    @setup({"escape04": "{{ a|escape|escape }}"})
    def test_escape04(self):
        """
        Tests the double application of the escape filter in a templating engine.

        Verifies that a string containing special characters is correctly escaped when
        the escape filter is applied twice, resulting in the expected HTML-encoded output.

        This test case ensures the templating engine handles repeated escaping correctly
        and produces the desired output without introducing additional encoding artifacts.
        """
        output = self.engine.render_to_string("escape04", {"a": "x&y"})
        self.assertEqual(output, "x&amp;y")

    def test_escape_lazy_string(self):
        """
        Tests the lazy evaluation of string escaping.

        This function verifies that the escape functionality correctly handles
        lazy strings, which are strings that are evaluated only when their values
        are actually needed. In this case, the lazy string contains HTML-special
        characters that need to be escaped. The function checks that the escaped
        string is of the correct type and that the escaping is performed correctly.

        The test covers the scenario where a lazy string is created by adding
        HTML-special characters to an input string and then escaping the result.
        It ensures that the escaping process correctly replaces '<', '>', and '&'
        with their corresponding HTML entity codes.
        """
        add_html = lazy(lambda string: string + "special characters > here", str)
        escaped = escape(add_html("<some html & "))
        self.assertIsInstance(escaped, Promise)
        self.assertEqual(escaped, "&lt;some html &amp; special characters &gt; here")


class FunctionTests(SimpleTestCase):
    def test_non_string_input(self):
        self.assertEqual(escape(123), "123")
