from django.template.defaultfilters import linebreaksbr
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class LinebreaksbrTests(SimpleTestCase):
    """
    The contents in "linebreaksbr" are escaped according to the current
    autoescape setting.
    """

    @setup({"linebreaksbr01": "{{ a|linebreaksbr }} {{ b|linebreaksbr }}"})
    def test_linebreaksbr01(self):
        """
        Tests the linebreaksbr template filter to ensure it correctly replaces newline characters with HTML line breaks.

        The function verifies that the filter properly escapes special characters and handles marked safe input. It checks if the output matches the expected result, which is the input strings with newline characters replaced by HTML line breaks and special characters escaped accordingly. The test covers both regular and marked safe input to ensure the filter works as expected in different scenarios.
        """
        output = self.engine.render_to_string(
            "linebreaksbr01", {"a": "x&\ny", "b": mark_safe("x&\ny")}
        )
        self.assertEqual(output, "x&amp;<br>y x&<br>y")

    @setup(
        {
            "linebreaksbr02": (
                "{% autoescape off %}{{ a|linebreaksbr }} {{ b|linebreaksbr }}"
                "{% endautoescape %}"
            )
        }
    )
    def test_linebreaksbr02(self):
        """

        Tests the linebreaksbr template filter when used with autoescape off and mark_safe.

        This test verifies that linebreaks are correctly replaced with HTML line breaks (<br>) 
        in a Jinja template, regardless of whether the input string is marked as safe or not.

        The test case includes input strings containing both ampersands (&) and newline characters (\n), 
        to ensure proper escaping and line breaking behavior.

        """
        output = self.engine.render_to_string(
            "linebreaksbr02", {"a": "x&\ny", "b": mark_safe("x&\ny")}
        )
        self.assertEqual(output, "x&<br>y x&<br>y")


class FunctionTests(SimpleTestCase):
    def test_newline(self):
        self.assertEqual(linebreaksbr("line 1\nline 2"), "line 1<br>line 2")

    def test_carriage(self):
        self.assertEqual(linebreaksbr("line 1\rline 2"), "line 1<br>line 2")

    def test_carriage_newline(self):
        self.assertEqual(linebreaksbr("line 1\r\nline 2"), "line 1<br>line 2")

    def test_non_string_input(self):
        self.assertEqual(linebreaksbr(123), "123")

    def test_autoescape(self):
        self.assertEqual(
            linebreaksbr("foo\n<a>bar</a>\nbuz"),
            "foo<br>&lt;a&gt;bar&lt;/a&gt;<br>buz",
        )

    def test_autoescape_off(self):
        self.assertEqual(
            linebreaksbr("foo\n<a>bar</a>\nbuz", autoescape=False),
            "foo<br><a>bar</a><br>buz",
        )
