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
        def test_basic(self):
            \"\"\"
            Tests the basic functionality of the escapeseq filter with a join operation.

            This test case verifies that the escapeseq filter correctly escapes special characters in a list of strings,
            while also ensuring that mark_safe content is left unescaped. The filter is then used in conjunction with the join
            operation to render a string, which is compared against an expected output for validation.

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
        output = self.engine.render_to_string(
            "escapeseq_autoescape_off",
            {"a": ["x&y", "<p>"], "b": [mark_safe("x&y"), mark_safe("<p>")]},
        )
        self.assertEqual(output, "x&amp;y, &lt;p&gt; -- x&y, <p>")

    @setup({"escapeseq_join": '{{ a|escapeseq|join:"<br/>" }}'})
    def test_chain_join(self):
        """

        Render a list of strings as escaped sequences joint with a specified delimiter.

        This function tests the rendering of a template that joins a list of strings with '<br/>' 
        delimiter after escaping special characters in each string. The function verifies that 
        the rendered output correctly escapes special characters, such as '&' and '<', and 
        joins the escaped strings with the specified delimiter.

        :param self: The test instance.
        :return: None

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
        Tests the chain of `escapeseq` and `join` filters when autoescaping is disabled.

        This test verifies that the `escapeseq` filter correctly escapes special characters and 
        the `join` filter concatenates the escaped strings with the specified separator, 
        while ensuring that autoescaping does not interfere with the expected output.

        The test input is a list of strings containing special characters, and the 
        expected output is a string where each input string is escaped and joined 
        by a `<br/>` separator. The test passes if the rendered output matches 
        the expected escaped and joined string.
        """
        output = self.engine.render_to_string(
            "escapeseq_join_autoescape_off", {"a": ["x&y", "<p>"]}
        )
        self.assertEqual(output, "x&amp;y<br/>&lt;p&gt;")
