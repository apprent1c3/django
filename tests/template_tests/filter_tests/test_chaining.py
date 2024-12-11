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
        """
        Tests the chaining of filters in templates, specifically the capfirst and center filters.

           Verifies that the filters are applied correctly to string variables, 
           including those that may contain HTML special characters, and that the output 
           is rendered as expected, without any unintended escaping or formatting issues.

           The test case covers both a regular string variable and a variable marked as safe,
           to ensure the filters behave consistently in both scenarios.

           :return: None if the test passes, otherwise an assertion error is raised
        """
        output = self.engine.render_to_string(
            "chaining02", {"a": "a < b", "b": mark_safe("a < b")}
        )
        self.assertEqual(output, " A < b . A < b ")

    # Using a filter that forces a string back to unsafe:
    @setup({"chaining03": '{{ a|cut:"b"|capfirst }}.{{ b|cut:"b"|capfirst }}'})
    def test_chaining03(self):
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
        """
        Test the chaining of escape and capfirst filters in a Jinja2 template.

        This test case checks if Jinja2 template engine correctly handles the chaining of filters when rendering a template. The expectation is that the string 'a < b' should be first escaped to replace special characters with their corresponding HTML entities, and then the 'capfirst' filter should capitalize the first letter of the resulting string, resulting in the output 'A &lt; b'. The test verifies that the output matches this expected outcome.
        """
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
        """

        Tests the chaining of the 'force_escape' and 'cut' filters in a template.

        The test case verifies that the 'force_escape' filter is applied to the input string,
        transforming any HTML special characters into their corresponding escape sequences,
        before the 'cut' filter is applied to remove any specified characters.
        The test asserts that the output string is correctly escaped and filtered.

        """
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

        Tests the chaining of filters in a template, ensuring that the output is correctly escaped.

        This test case verifies that when the 'cut' and 'force_escape' filters are applied sequentially,
        the resulting output is properly escaped, replacing special characters with their corresponding HTML entities.

        """
        output = self.engine.render_to_string("chaining10", {"a": "a < b"})
        self.assertEqual(output, "a &lt; b")

    @setup({"chaining11": '{{ a|cut:"b"|safe }}'})
    def test_chaining11(self):
        """
        Tests the chaining of filters in template rendering, specifically the 'cut' filter followed by the 'safe' filter.

        This test case checks if the 'cut' filter correctly removes the specified substring and the 'safe' filter prevents HTML escaping, resulting in the expected output string.

        :param None:
        :returns: None
        :raises AssertionError: If the rendered output does not match the expected string
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
        """
        Tests the chaining of multiple filters in a template, specifically the application of both the \"safe\" and \"force_escape\" filters to a variable. 

        This test case verifies that the \"force_escape\" filter, which typically converts special characters into HTML-safe equivalents, is applied even when the \"safe\" filter, which marks a string as safe to display without escaping, is also present in the chain. 

        The expected outcome is that the special character \"<\" in the input string is correctly escaped to \"&lt;\" in the output.
        """
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
        Tests that the chaining of the 'safe' and 'force_escape' filters produces the expected output.

         The 'safe' filter is used to mark a string as safe HTML, while the 'force_escape' filter escapes any special characters.

         This test case checks that when a string is first marked as safe and then escaped, it results in the original string being escaped correctly.

         :return: None
        """
        output = self.engine.render_to_string("chaining14", {"a": "a < b"})
        self.assertEqual(output, "a &lt; b")
