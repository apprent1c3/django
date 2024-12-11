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
        output = self.engine.render_to_string(
            "addslashes01", {"a": "<a>'", "b": mark_safe("<a>'")}
        )
        self.assertEqual(output, r"<a>\' <a>\'")

    @setup({"addslashes02": "{{ a|addslashes }} {{ b|addslashes }}"})
    def test_addslashes02(self):
        """
        ंदरRender a template string using the addslashes filter to escape special characters.

        The function tests the correct application of the addslashes filter on two input strings, one of which is marked as safe. It verifies that the output string has the expected special characters escaped, while the marked safe string is not modified.
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
