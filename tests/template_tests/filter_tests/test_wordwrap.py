from django.template.defaultfilters import wordwrap
from django.test import SimpleTestCase
from django.utils.functional import lazystr
from django.utils.safestring import mark_safe

from ..utils import setup


class WordwrapTests(SimpleTestCase):
    @setup(
        {
            "wordwrap01": (
                '{% autoescape off %}{{ a|wordwrap:"3" }} {{ b|wordwrap:"3" }}'
                "{% endautoescape %}"
            )
        }
    )
    def test_wordwrap01(self):
        """
        Tests the wordwrap filter with autoescaped and mark_safe input.

        This test case checks the rendering of a template that applies the wordwrap filter
        to two input strings. The first string is autoescaped while the second is marked
        as safe, allowing for the comparison of the filter's behavior in different escaping
        contexts. The test verifies that the output is correctly wordwrapped and that the
        escaping of special characters is handled as expected.

        The expected output is a string with the input text wrapped at a specified width,
        with special characters treated accordingly based on their escaping status.
        """
        output = self.engine.render_to_string(
            "wordwrap01", {"a": "a & b", "b": mark_safe("a & b")}
        )
        self.assertEqual(output, "a &\nb a &\nb")

    @setup({"wordwrap02": '{{ a|wordwrap:"3" }} {{ b|wordwrap:"3" }}'})
    def test_wordwrap02(self):
        output = self.engine.render_to_string(
            "wordwrap02", {"a": "a & b", "b": mark_safe("a & b")}
        )
        self.assertEqual(output, "a &amp;\nb a &\nb")


class FunctionTests(SimpleTestCase):
    def test_wrap(self):
        self.assertEqual(
            wordwrap(
                "this is a long paragraph of text that really needs to be wrapped I'm "
                "afraid",
                14,
            ),
            "this is a long\nparagraph of\ntext that\nreally needs\nto be wrapped\n"
            "I'm afraid",
        )

    def test_indent(self):
        self.assertEqual(
            wordwrap(
                "this is a short paragraph of text.\n  But this line should be "
                "indented",
                14,
            ),
            "this is a\nshort\nparagraph of\ntext.\n  But this\nline should be\n"
            "indented",
        )

    def test_indent2(self):
        self.assertEqual(
            wordwrap(
                "this is a short paragraph of text.\n  But this line should be "
                "indented",
                15,
            ),
            "this is a short\nparagraph of\ntext.\n  But this line\nshould be\n"
            "indented",
        )

    def test_non_string_input(self):
        self.assertEqual(wordwrap(123, 2), "123")

    def test_wrap_lazy_string(self):
        self.assertEqual(
            wordwrap(
                lazystr(
                    "this is a long paragraph of text that really needs to be wrapped "
                    "I'm afraid"
                ),
                14,
            ),
            "this is a long\nparagraph of\ntext that\nreally needs\nto be wrapped\n"
            "I'm afraid",
        )
