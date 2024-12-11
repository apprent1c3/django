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

        Tests the escape functionality in the template engine.

        This function evaluates the rendering of a template string that contains two variables, 
        one marked as safe and the other not, after being passed through the escape filter.
        It checks that the variable not marked as safe is properly escaped and the safe variable is not.

        The test ensures that the output of the rendered template matches the expected result, 
        verifying that the escape functionality works as intended.

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
        Tests the rendering of a template with autoescaping turned off.

        This function verifies that when autoescaping is disabled, the rendering of 
        templates with escaped and unescaped variables behaves as expected. It 
        checks that the escaped variable is rendered with HTML entities, while 
        the unescaped variable is rendered as is, without any escaping.

        :raises AssertionError: If the rendered output does not match the expected result.
        """
        output = self.engine.render_to_string(
            "escape02", {"a": "x&y", "b": mark_safe("x&y")}
        )
        self.assertEqual(output, "x&amp;y x&y")

    @setup({"escape03": "{% autoescape off %}{{ a|escape|escape }}{% endautoescape %}"})
    def test_escape03(self):
        """
        Tests the autoescape mechanism in templates, specifically the interaction between the autoescape tag and the escape filter. 
        Verifies that the escape filter correctly escapes special characters, resulting in the expected output, even when autoescaping is disabled.
        """
        output = self.engine.render_to_string("escape03", {"a": "x&y"})
        self.assertEqual(output, "x&amp;y")

    @setup({"escape04": "{{ a|escape|escape }}"})
    def test_escape04(self):
        output = self.engine.render_to_string("escape04", {"a": "x&y"})
        self.assertEqual(output, "x&amp;y")

    def test_escape_lazy_string(self):
        """
        Tests the functionality of escaping lazy string objects, ensuring they are properly converted to their string representation and HTML special characters are escaped when processed by the escape function, resulting in a Promise object with the expected escaped string value.
        """
        add_html = lazy(lambda string: string + "special characters > here", str)
        escaped = escape(add_html("<some html & "))
        self.assertIsInstance(escaped, Promise)
        self.assertEqual(escaped, "&lt;some html &amp; special characters &gt; here")


class FunctionTests(SimpleTestCase):
    def test_non_string_input(self):
        self.assertEqual(escape(123), "123")
