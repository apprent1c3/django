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
        """
        Tests the HTML escaping functionality of the templating engine.

        This test case verifies that the escape filter correctly escapes special characters in a string, while also ensuring that strings marked as safe are not unnecessarily escaped. The function checks the rendered output of a template against an expected result, validating that the escape filter behaves as expected.
        """
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
        """
        Tests the functionality of autoescaping in templating engine. 

        Verifies that the autoescape tag correctly escapes or unescapes HTML entities within a template. 
        Checks that escaped values are properly converted to HTML entities, and that marked-safe values are not escaped. 
        The test confirms the correct rendering of the template with escaped and unescaped input data.
        """
        output = self.engine.render_to_string(
            "escape02", {"a": "x&y", "b": mark_safe("x&y")}
        )
        self.assertEqual(output, "x&amp;y x&y")

    @setup({"escape03": "{% autoescape off %}{{ a|escape|escape }}{% endautoescape %}"})
    def test_escape03(self):
        """
        Tests the rendering of a template with autoescape disabled and multiple escape filters applied.

        This test case verifies that the |escape filter is applied correctly even when
        autoescaping is turned off, ensuring that special characters in the input are
        properly escaped in the output.

        The test uses a template with a variable 'a' that contains special characters,
        rendered with autoescape disabled and the |escape filter applied twice. The
        expected output is then compared to the actual output to ensure that the
        escaping is correct.
        """
        output = self.engine.render_to_string("escape03", {"a": "x&y"})
        self.assertEqual(output, "x&amp;y")

    @setup({"escape04": "{{ a|escape|escape }}"})
    def test_escape04(self):
        output = self.engine.render_to_string("escape04", {"a": "x&y"})
        self.assertEqual(output, "x&amp;y")

    def test_escape_lazy_string(self):
        add_html = lazy(lambda string: string + "special characters > here", str)
        escaped = escape(add_html("<some html & "))
        self.assertIsInstance(escaped, Promise)
        self.assertEqual(escaped, "&lt;some html &amp; special characters &gt; here")


class FunctionTests(SimpleTestCase):
    def test_non_string_input(self):
        self.assertEqual(escape(123), "123")
