from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class VerbatimTagTests(SimpleTestCase):
    @setup({"verbatim-tag01": "{% verbatim %}{{bare   }}{% endverbatim %}"})
    def test_verbatim_tag01(self):
        output = self.engine.render_to_string("verbatim-tag01")
        self.assertEqual(output, "{{bare   }}")

    @setup({"verbatim-tag02": "{% verbatim %}{% endif %}{% endverbatim %}"})
    def test_verbatim_tag02(self):
        """
        Tests the rendering of verbatim tags in templates, specifically the 'verbatim-tag02' case.

        Verifies that the template engine correctly handles the nesting of verbatim and conditional tags, ensuring that the output matches the expected result of '{% endif %}'.

        This test case checks for proper parsing and rendering of template tags, helping to prevent potential errors or unexpected behavior in template rendering.
        """
        output = self.engine.render_to_string("verbatim-tag02")
        self.assertEqual(output, "{% endif %}")

    @setup(
        {"verbatim-tag03": "{% verbatim %}It's the {% verbatim %} tag{% endverbatim %}"}
    )
    def test_verbatim_tag03(self):
        output = self.engine.render_to_string("verbatim-tag03")
        self.assertEqual(output, "It's the {% verbatim %} tag")

    @setup(
        {
            "verbatim-tag04": (
                "{% verbatim %}{% verbatim %}{% endverbatim %}{% endverbatim %}"
            )
        }
    )
    def test_verbatim_tag04(self):
        """
        Tests the rendering of a template containing verbatim tags to ensure proper handling of nested verbatim tags. 

        The test verifies that the template engine correctly raises a TemplateSyntaxError when encountering improperly nested verbatim tags, preventing potential template parsing issues. 

        This test case covers a specific edge case in template syntax, ensuring the engine's robustness and adherence to expected parsing behavior.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("verbatim-tag04")

    @setup(
        {
            "verbatim-tag05": (
                "{% verbatim %}{% endverbatim %}{% verbatim %}{% endverbatim %}"
            )
        }
    )
    def test_verbatim_tag05(self):
        """
        Tests the rendering of a template containing nested verbatim tags.
        The verbatim tag is used to prevent the engine from interpreting the contents of a block.
        This test case checks that the template engine correctly handles nested verbatim tags and renders an empty string as the expected output.
        """
        output = self.engine.render_to_string("verbatim-tag05")
        self.assertEqual(output, "")

    @setup(
        {
            "verbatim-tag06": "{% verbatim special %}"
            "Don't {% endverbatim %} just yet{% endverbatim special %}"
        }
    )
    def test_verbatim_tag06(self):
        """
        Tests the rendering of a template with a verbatim tag that contains a nested template tag, ensuring that the inner tag is not evaluated and is instead treated as literal text. The test verifies that the output matches the expected string, demonstrating the correct behavior of the verbatim tag in this scenario.
        """
        output = self.engine.render_to_string("verbatim-tag06")
        self.assertEqual(output, "Don't {% endverbatim %} just yet")
