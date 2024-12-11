from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class ChainingTests(SimpleTestCase):
    """
    Chaining safeness-preserving filters should not alter the safe status.
    """

    @setup({"chaining01": '{{ a|capfirst|center:"7" }}.{{ b|capfirst|center:"7" }}'})
    def test_chaining01(self):
        """

        Render a template string with chained filters and safe HTML.

        This function tests the rendering of a template string that applies multiple
        filters to input variables, including capitalizing the first letter and centering
        the string within a specified width. The function also verifies that HTML entities
        are handled correctly, escaping them when necessary and preserving them when
        marked as safe.

        """
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
        Tests the chaining of filters in a template, specifically the capfirst and center filters.

         Verifies that these filters can be applied to variables that contain HTML markup, and that 
         the autoescape tag correctly handles the rendering of these variables. The test checks for 
         the correct output when rendering the template with variables 'a' and 'b', ensuring that 
         the capfirst filter capitalizes the first letter and the center filter aligns the text as 
         expected, while also handling the HTML markup in 'b' due to mark_safe().
        """
        output = self.engine.render_to_string(
            "chaining02", {"a": "a < b", "b": mark_safe("a < b")}
        )
        self.assertEqual(output, " A < b . A < b ")

    # Using a filter that forces a string back to unsafe:
    @setup({"chaining03": '{{ a|cut:"b"|capfirst }}.{{ b|cut:"b"|capfirst }}'})
    def test_chaining03(self):
        """
        Test the chaining of templating filters, specifically the 'cut' and 'capfirst' filters, 
        in conjunction with HTML escaping. This checks if the filters are applied correctly 
        and if the output is properly escaped, resulting in the expected rendered string.
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
        """

        Tests the chaining of template filters, specifically the cut and capfirst filters, 
        with the autoescape option turned off. Verifies that the output is rendered correctly, 
        removing the specified substring and capitalizing the first letter of the resulting string.

        """
        output = self.engine.render_to_string(
            "chaining04", {"a": "a < b", "b": mark_safe("a < b")}
        )
        self.assertEqual(output, "A < .A < ")

    # Using a filter that forces safeness does not lead to double-escaping
    @setup({"chaining05": "{{ a|escape|capfirst }}"})
    def test_chaining05(self):
        """
        Tests the chaining of template filters, specifically the escape and capfirst filters.

        Ensures that the capfirst filter properly capitalizes the first letter of a string, 
        while the escape filter correctly escapes any special characters, 
        resulting in a safely formatted and capitalized output string.
        """
        output = self.engine.render_to_string("chaining05", {"a": "a < b"})
        self.assertEqual(output, "A &lt; b")

    @setup(
        {"chaining06": "{% autoescape off %}{{ a|escape|capfirst }}{% endautoescape %}"}
    )
    def test_chaining06(self):
        """
        Tests the chaining of multiple filters in a template, specifically the escape and capfirst filters, to verify correct output and HTML escaping.
        """
        output = self.engine.render_to_string("chaining06", {"a": "a < b"})
        self.assertEqual(output, "A &lt; b")

    # Force to safe, then back (also showing why using force_escape too
    # early in a chain can lead to unexpected results).
    @setup({"chaining07": '{{ a|force_escape|cut:";" }}'})
    def test_chaining07(self):
        """

        Tests the chaining of template filters, specifically the force_escape and cut filters.

        Verifies that the force_escape filter correctly escapes special characters in a string,
        and the cut filter trims the string to the desired length.

        This test case checks the output when the input string 'a < b' is passed through these filters,
        expecting the output to be 'a &lt b', which demonstrates the correct application of HTML escaping.

        """
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
        """
        Tests the chaining of template filters to escape special characters.

        This test case verifies that the rendering engine correctly escapes special characters
        in a string by applying a sequence of filters. It checks if the escaping of special
        characters, such as '<', is performed correctly when chaining filters like 'cut' and
        'force_escape'.

        The test expects the output string to be properly escaped, replacing '<' with its
        HTML entity equivalent '&lt;'. This ensures the rendered output is safe for inclusion
        in HTML documents without introducing potential security vulnerabilities or breaking
        the document structure.
        """
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
        Tests the chaining of template filters to ensure proper HTML escaping.

        This test verifies that applying multiple filters in sequence, specifically the 
        'cut' and 'force_escape' filters, produces the expected output. The 'cut' filter 
        removes a specified character from the input string, and the 'force_escape' filter 
        ensures that any special characters are properly escaped for safe inclusion in HTML.

        The test case uses the template string '{{ a|cut:\";\"|force_escape }}' and checks 
        that the rendered output, when the input 'a' is 'a < b', results in the string 
        'a &lt; b', demonstrating correct HTML escaping of the '<' character.
        """
        output = self.engine.render_to_string("chaining10", {"a": "a < b"})
        self.assertEqual(output, "a &lt; b")

    @setup({"chaining11": '{{ a|cut:"b"|safe }}'})
    def test_chaining11(self):
        """

        Render a template with a chained filter to sanitize a string by removing a specified substring and then marking the output as safe.

        This function tests the chaining of filters to clean and format a template variable.
        The template 'chaining11' is rendered with a variable 'a' that contains a string with HTML characters.
        The output is then compared to the expected result to ensure the template is rendered correctly.

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
        Tests the chaining of multiple filters in a template, specifically the interaction between the 'safe' and 'force_escape' filters.

        The purpose of this test is to verify that the output is correctly escaped when both filters are applied in sequence.

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
        Tests that template chaining works correctly with safe and force escape filters.

        The function tests the templating engine's rendering of a string with HTML special 
        characters, ensuring that the output is properly escaped. It verifies that the 
        engine correctly handles the combination of the safe and force_escape filters, 
        producing the expected HTML-escaped output.
        """
        output = self.engine.render_to_string("chaining14", {"a": "a < b"})
        self.assertEqual(output, "a &lt; b")
