from django.test import SimpleTestCase

from ..utils import setup


class SafeseqTests(SimpleTestCase):
    @setup({"safeseq01": '{{ a|join:", " }} -- {{ a|safeseq|join:", " }}'})
    def test_safeseq01(self):
        """

        Tests the rendering of a template with safe sequence functionality.

        This test case evaluates the rendering of a sequence of special characters
        when using the 'safeseq' filter. It verifies that the filter correctly
        escapes special characters while rendering the sequence, and then compares
        the escaped output with the expected result.

        The purpose of this test is to ensure that the 'safeseq' filter behaves as
        expected when handling sequences of special characters, and to verify that
        the rendering engine correctly applies this filter to produce the desired
        output.

        """
        output = self.engine.render_to_string("safeseq01", {"a": ["&", "<"]})
        self.assertEqual(output, "&amp;, &lt; -- &, <")

    @setup(
        {
            "safeseq02": (
                '{% autoescape off %}{{ a|join:", " }} -- {{ a|safeseq|join:", " }}'
                "{% endautoescape %}"
            )
        }
    )
    def test_safeseq02(self):
        output = self.engine.render_to_string("safeseq02", {"a": ["&", "<"]})
        self.assertEqual(output, "&, < -- &, <")
