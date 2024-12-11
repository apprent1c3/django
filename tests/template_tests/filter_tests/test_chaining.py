from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class ChainingTests(SimpleTestCase):
    """
    Chaining safeness-preserving filters should not alter the safe status.
    """

    @setup({"chaining01": '{{ a|capfirst|center:"7" }}.{{ b|capfirst|center:"7" }}'})
    def test_chaining01(self):
        output = self.engine.render_to_string(
            "chaining01", {"a": "a < b", "b": mark_safe("a < b")}
        )
        self.assertEqual(output, " A &lt; b . A < b ")

    @setup(
        {
            "chaining02": (
                '{% autoescape off %}{{ a|capfirst|center:"7" }}.'
                '{{ b|capfirst|center:"7" }}{% endautoescape %}'
            )
        }
    )
    def test_chaining02(self):
        output = self.engine.render_to_string(
            "chaining02", {"a": "a < b", "b": mark_safe("a < b")}
        )
        self.assertEqual(output, " A < b . A < b ")

    # Using a filter that forces a string back to unsafe:
    @setup({"chaining03": '{{ a|cut:"b"|capfirst }}.{{ b|cut:"b"|capfirst }}'})
    def test_chaining03(self):
        """
        Tests rendering of a template string with chained filters, specifically the 'cut' and 'capfirst' filters, to ensure correct output when rendering a template with less-than signs. The test verifies that the filters are applied correctly and HTML special characters are escaped as expected.
        """
        output = self.engine.render_to_string(
            "chaining03", {"a": "a < b", "b": mark_safe("a < b")}
        )
        self.assertEqual(output, "A &lt; .A < ")

    @setup(
        {
            "chaining04": (
                '{% autoescape off %}{{ a|cut:"b"|capfirst }}.{{ b|cut:"b"|capfirst }}'
                "{% endautoescape %}"
            )
        }
    )
    def test_chaining04(self):
        output = self.engine.render_to_string(
            "chaining04", {"a": "a < b", "b": mark_safe("a < b")}
        )
        self.assertEqual(output, "A < .A < ")

    # Using a filter that forces safeness does not lead to double-escaping
    @setup({"chaining05": "{{ a|escape|capfirst }}"})
    def test_chaining05(self):
        output = self.engine.render_to_string("chaining05", {"a": "a < b"})
        self.assertEqual(output, "A &lt; b")

    @setup(
        {"chaining06": "{% autoescape off %}{{ a|escape|capfirst }}{% endautoescape %}"}
    )
    def test_chaining06(self):
        output = self.engine.render_to_string("chaining06", {"a": "a < b"})
        self.assertEqual(output, "A &lt; b")

    # Force to safe, then back (also showing why using force_escape too
    # early in a chain can lead to unexpected results).
    @setup({"chaining07": '{{ a|force_escape|cut:";" }}'})
    def test_chaining07(self):
        output = self.engine.render_to_string("chaining07", {"a": "a < b"})
        self.assertEqual(output, "a &amp;lt b")

    @setup(
        {
            "chaining08": (
                '{% autoescape off %}{{ a|force_escape|cut:";" }}{% endautoescape %}'
            )
        }
    )
    def test_chaining08(self):
        output = self.engine.render_to_string("chaining08", {"a": "a < b"})
        self.assertEqual(output, "a &lt b")

    @setup({"chaining09": '{{ a|cut:";"|force_escape }}'})
    def test_chaining09(self):
        output = self.engine.render_to_string("chaining09", {"a": "a < b"})
        self.assertEqual(output, "a &lt; b")

    @setup(
        {
            "chaining10": (
                '{% autoescape off %}{{ a|cut:";"|force_escape }}{% endautoescape %}'
            )
        }
    )
    def test_chaining10(self):
        """
        Tests the end-to-end behavior of the templating engine's autoescape and force_escape functionality
        when applied in a sequence to user-provided input. Specifically, it verifies that HTML special characters
        are correctly escaped, preventing potential XSS vulnerabilities, while allowing the template to 
        temporarily bypass autoescaping and then reapply it to ensure safe output
        """
        output = self.engine.render_to_string("chaining10", {"a": "a < b"})
        self.assertEqual(output, "a &lt; b")

    @setup({"chaining11": '{{ a|cut:"b"|safe }}'})
    def test_chaining11(self):
        """
        Render a template string with chained filters to test the output.

        The function verifies that the 'cut' filter correctly removes the specified substring 
        and the 'safe' filter prevents HTML escaping, resulting in the expected output string.

        :raises AssertionError: If the rendered output does not match the expected string.

        """
        output = self.engine.render_to_string("chaining11", {"a": "a < b"})
        self.assertEqual(output, "a < ")

    @setup(
        {"chaining12": '{% autoescape off %}{{ a|cut:"b"|safe }}{% endautoescape %}'}
    )
    def test_chaining12(self):
        output = self.engine.render_to_string("chaining12", {"a": "a < b"})
        self.assertEqual(output, "a < ")

    @setup({"chaining13": "{{ a|safe|force_escape }}"})
    def test_chaining13(self):
        output = self.engine.render_to_string("chaining13", {"a": "a < b"})
        self.assertEqual(output, "a &lt; b")

    @setup(
        {
            "chaining14": (
                "{% autoescape off %}{{ a|safe|force_escape }}{% endautoescape %}"
            )
        }
    )
    def test_chaining14(self):
        """
        Tests the behavior of chaining filters in template rendering, specifically the interaction between the 'safe' and 'force_escape' filters. This test case verifies that when the 'autoescape' directive is disabled and the 'safe' filter is applied, subsequent application of the 'force_escape' filter correctly escapes the output to prevent XSS vulnerabilities.
        """
        output = self.engine.render_to_string("chaining14", {"a": "a < b"})
        self.assertEqual(output, "a &lt; b")
