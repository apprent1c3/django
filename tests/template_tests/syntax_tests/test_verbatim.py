from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class VerbatimTagTests(SimpleTestCase):
    @setup({"verbatim-tag01": "{% verbatim %}{{bare   }}{% endverbatim %}"})
    def test_verbatim_tag01(self):
        """
        Tests the rendering of the verbatim tag in a template.

        Verifies that the verbatim tag correctly escapes its contents, preventing any templating engine syntax within the tag from being interpreted.

        The test case checks if the output of the rendering process matches the expected literal content, ensuring that the verbatim tag functions as expected.
        """
        output = self.engine.render_to_string("verbatim-tag01")
        self.assertEqual(output, "{{bare   }}")

    @setup({"verbatim-tag02": "{% verbatim %}{% endif %}{% endverbatim %}"})
    def test_verbatim_tag02(self):
        output = self.engine.render_to_string("verbatim-tag02")
        self.assertEqual(output, "{% endif %}")

    @setup(
        {"verbatim-tag03": "{% verbatim %}It's the {% verbatim %} tag{% endverbatim %}"}
    )
    def test_verbatim_tag03(self):
        """
        Tests rendering of the verbatim tag within a template to ensure it correctly escapes templating syntax and prevents the enclosed content from being interpreted as template code. Validates that the verbatim tag is handled properly by comparing the rendered output to the expected string, ensuring that the tag itself is included in the output without being executed.
        """
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

        Tests the rendering of the verbatim tag in a template.

        This test case checks if the verbatim tag correctly escapes its contents,
        preventing any templating syntax within the tag from being interpreted.
        The test verifies that the output of the template rendering is empty,
        indicating that the verbatim tag is handled as expected.

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
        output = self.engine.render_to_string("verbatim-tag06")
        self.assertEqual(output, "Don't {% endverbatim %} just yet")
