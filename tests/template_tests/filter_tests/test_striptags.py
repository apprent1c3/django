from django.template.defaultfilters import striptags
from django.test import SimpleTestCase
from django.utils.functional import lazystr
from django.utils.safestring import mark_safe

from ..utils import setup


class StriptagsTests(SimpleTestCase):
    @setup({"striptags01": "{{ a|striptags }} {{ b|striptags }}"})
    def test_striptags01(self):
        output = self.engine.render_to_string(
            "striptags01",
            {
                "a": "<a>x</a> <p><b>y</b></p>",
                "b": mark_safe("<a>x</a> <p><b>y</b></p>"),
            },
        )
        self.assertEqual(output, "x y x y")

    @setup(
        {
            "striptags02": (
                "{% autoescape off %}{{ a|striptags }} {{ b|striptags }}"
                "{% endautoescape %}"
            )
        }
    )
    def test_striptags02(self):
        """

        Test the striptags template filter functionality.

        This function verifies that the striptags filter correctly removes HTML tags from input strings.
        It checks the filter's behavior with both regular strings and strings marked as safe using 
        the mark_safe function, ensuring that tags are stripped in both cases.

        The test expects the filter to output plain text with all HTML tags removed.

        """
        output = self.engine.render_to_string(
            "striptags02",
            {
                "a": "<a>x</a> <p><b>y</b></p>",
                "b": mark_safe("<a>x</a> <p><b>y</b></p>"),
            },
        )
        self.assertEqual(output, "x y x y")


class FunctionTests(SimpleTestCase):
    def test_strip(self):
        self.assertEqual(
            striptags(
                'some <b>html</b> with <script>alert("You smell")</script> disallowed '
                "<img /> tags"
            ),
            'some html with alert("You smell") disallowed  tags',
        )

    def test_non_string_input(self):
        self.assertEqual(striptags(123), "123")

    def test_strip_lazy_string(self):
        self.assertEqual(
            striptags(
                lazystr(
                    'some <b>html</b> with <script>alert("Hello")</script> disallowed '
                    "<img /> tags"
                )
            ),
            'some html with alert("Hello") disallowed  tags',
        )
