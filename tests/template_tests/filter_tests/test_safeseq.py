from django.test import SimpleTestCase

from ..utils import setup


class SafeseqTests(SimpleTestCase):
    @setup({"safeseq01": '{{ a|join:", " }} -- {{ a|safeseq|join:", " }}'})
    def test_safeseq01(self):
        """
        This is a comment
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
        """
        This is a comment
        """
        output = self.engine.render_to_string("safeseq02", {"a": ["&", "<"]})
        self.assertEqual(output, "&, < -- &, <")
