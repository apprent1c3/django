from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class EscapeseqTests(SimpleTestCase):
    """
    The "escapeseq" filter works the same whether autoescape is on or off,
    and has no effect on strings already marked as safe.
    """

    @setup(
        {
            "escapeseq_basic": (
                '{{ a|escapeseq|join:", " }} -- {{ b|escapeseq|join:", " }}'
            ),
        }
    )
    def test_basic(self):
        """

        Tests the basic functionality of the escapeseq filter.

        This test verifies that the escapeseq filter correctly escapes special characters in a list of strings, 
        and that it does not escape strings that have been marked as safe.

        The test checks that the filter replaces special characters with their corresponding HTML entities, 
        such as '&' with '&amp;' and '<' with '&lt;'. It also checks that the filter does not modify strings 
        that have been explicitly marked as safe, allowing them to be rendered as is.

        """
        output = self.engine.render_to_string(
            "escapeseq_basic",
            {"a": ["x&y", "<p>"], "b": [mark_safe("x&y"), mark_safe("<p>")]},
        )
        self.assertEqual(output, "x&amp;y, &lt;p&gt; -- x&y, <p>")

    @setup(
        {
            "escapeseq_autoescape_off": (
                '{% autoescape off %}{{ a|escapeseq|join:", " }}'
                " -- "
                '{{ b|escapeseq|join:", "}}{% endautoescape %}'
            )
        }
    )
    def test_autoescape_off(self):
        """

        Tests the autoescape off functionality in templating.

        This function verifies that autoescape is correctly disabled, allowing HTML characters
        to be rendered as is, while also ensuring that the escapeseq filter still escapes
        special characters in the output.

        It checks the rendering of two lists of strings, one of which contains marked safe
        strings, to ensure that the expected output is produced when autoescape is turned off.

        """
        output = self.engine.render_to_string(
            "escapeseq_autoescape_off",
            {"a": ["x&y", "<p>"], "b": [mark_safe("x&y"), mark_safe("<p>")]},
        )
        self.assertEqual(output, "x&amp;y, &lt;p&gt; -- x&y, <p>")

    @setup({"escapeseq_join": '{{ a|escapeseq|join:"<br/>" }}'})
    def test_chain_join(self):
        """

        Tests the rendering of a template that escapes special characters and joins a list into a string.

        The function verifies that the 'escapeseq' filter correctly escapes special characters in the list elements and 
        the 'join' filter concatenates the elements with the specified separator, '<br/>'.
        The expected output is a string where all special characters are properly escaped and the list elements are joined with the separator.

        """
        output = self.engine.render_to_string("escapeseq_join", {"a": ["x&y", "<p>"]})
        self.assertEqual(output, "x&amp;y<br/>&lt;p&gt;")

    @setup(
        {
            "escapeseq_join_autoescape_off": (
                '{% autoescape off %}{{ a|escapeseq|join:"<br/>" }}{% endautoescape %}'
            ),
        }
    )
    def test_chain_join_autoescape_off(self):
        """

        Tests the behavior of the escapeseq and join filters when autoescape is turned off.
        Verifies that the output is correctly escaped and joined, without being influenced by the surrounding autoescape context.

        The test checks if a list of strings containing special characters is properly escaped
        and then joined with a specified separator. The expected output should have the special
        characters correctly escaped and the strings joined as expected.

        """
        output = self.engine.render_to_string(
            "escapeseq_join_autoescape_off", {"a": ["x&y", "<p>"]}
        )
        self.assertEqual(output, "x&amp;y<br/>&lt;p&gt;")
