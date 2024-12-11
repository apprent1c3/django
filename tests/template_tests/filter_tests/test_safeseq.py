from django.test import SimpleTestCase

from ..utils import setup


class SafeseqTests(SimpleTestCase):
    @setup({"safeseq01": '{{ a|join:", " }} -- {{ a|safeseq|join:", " }}'})
    def test_safeseq01(self):
        """
        Tests the safeseq filter in a templating engine, verifying it correctly escapes special characters.
        The test case checks if the rendered output properly differentiates between escaped and unescaped sequences of special characters.
        It ensures that special characters like ampersands and less-than signs are correctly replaced with their corresponding HTML entities when the safeseq filter is applied.
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
