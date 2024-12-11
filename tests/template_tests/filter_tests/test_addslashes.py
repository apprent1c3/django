from django.template.defaultfilters import addslashes
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class AddslashesTests(SimpleTestCase):
    @setup(
        {
            "addslashes01": (
                "{% autoescape off %}{{ a|addslashes }} {{ b|addslashes }}"
                "{% endautoescape %}"
            )
        }
    )
    def test_addslashes01(self):
        """

        Tests the custom template filter 'addslashes' to ensure it correctly escapes special characters.

        It verifies that the filter properly escapes characters in both auto-escaped and marked safe contexts.

        The expected output is a string where single quotes are replaced with their escaped equivalents.

        """
        output = self.engine.render_to_string(
            "addslashes01", {"a": "<a>'", "b": mark_safe("<a>'")}
        )
        self.assertEqual(output, r"<a>\' <a>\'")

    @setup({"addslashes02": "{{ a|addslashes }} {{ b|addslashes }}"})
    def test_addslashes02(self):
        """
        писание
            Test the addslashes filter in the templating engine.

            This test verifies that the addslashes filter correctly escapes special characters 
            in string variables and respects the mark_safe mark to prevent double escaping. 

            :return: None
            :rtype: None
        """
        output = self.engine.render_to_string(
            "addslashes02", {"a": "<a>'", "b": mark_safe("<a>'")}
        )
        self.assertEqual(output, r"&lt;a&gt;\&#x27; <a>\'")


class FunctionTests(SimpleTestCase):
    def test_quotes(self):
        self.assertEqual(
            addslashes("\"double quotes\" and 'single quotes'"),
            "\\\"double quotes\\\" and \\'single quotes\\'",
        )

    def test_backslashes(self):
        self.assertEqual(addslashes(r"\ : backslashes, too"), "\\\\ : backslashes, too")

    def test_non_string_input(self):
        self.assertEqual(addslashes(123), "123")
