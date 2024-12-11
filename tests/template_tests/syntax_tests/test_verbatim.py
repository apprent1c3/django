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
        output = self.engine.render_to_string("verbatim-tag02")
        self.assertEqual(output, "{% endif %}")

    @setup(
        {"verbatim-tag03": "{% verbatim %}It's the {% verbatim %} tag{% endverbatim %}"}
    )
    def test_verbatim_tag03(self):
        """

        Tests the rendering of the verbatim tag in a template.

        This test ensures that the verbatim tag is properly escaped when rendered,
        allowing it to be displayed as its literal value rather than being interpreted
        as a template tag. The test verifies that the output of the rendering process
        matches the expected string, which includes the verbatim tag itself.

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
        Test the rendering of the verbatim tag with nested tags.

        This test case checks if the template engine correctly handles the verbatim tag 
        when it contains other verbatim tags. The expected output is an empty string, 
        indicating that the verbatim tags are properly escaped and do not interfere 
        with the rendering process.
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
