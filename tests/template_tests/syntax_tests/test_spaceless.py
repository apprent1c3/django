from django.test import SimpleTestCase

from ..utils import setup


class SpacelessTagTests(SimpleTestCase):
    @setup(
        {
            "spaceless01": (
                "{% spaceless %} <b>    <i> text </i>    </b> {% endspaceless %}"
            )
        }
    )
    def test_spaceless01(self):
        """
        Tests the functionality of the 'spaceless' template tag. 
        This test case checks whether the tag correctly removes extra whitespace characters from the HTML tags within its block, 
        resulting in clean and compact HTML output.
        """
        output = self.engine.render_to_string("spaceless01")
        self.assertEqual(output, "<b><i> text </i></b>")

    @setup(
        {
            "spaceless02": (
                "{% spaceless %} <b> \n <i> text </i> \n </b> {% endspaceless %}"
            )
        }
    )
    def test_spaceless02(self):
        output = self.engine.render_to_string("spaceless02")
        self.assertEqual(output, "<b><i> text </i></b>")

    @setup({"spaceless03": "{% spaceless %}<b><i>text</i></b>{% endspaceless %}"})
    def test_spaceless03(self):
        output = self.engine.render_to_string("spaceless03")
        self.assertEqual(output, "<b><i>text</i></b>")

    @setup(
        {
            "spaceless04": (
                "{% spaceless %}<b>   <i>{{ text }}</i>  </b>{% endspaceless %}"
            )
        }
    )
    def test_spaceless04(self):
        """
        Tests the spaceless template tag with HTML entities, ensuring that unnecessary whitespace is removed from the output while preserving HTML entity encoding. The test renders a template with a variable containing a string with an ampersand, then asserts that the output is rendered as expected with the ampersand properly escaped to '&amp;'.
        """
        output = self.engine.render_to_string("spaceless04", {"text": "This & that"})
        self.assertEqual(output, "<b><i>This &amp; that</i></b>")

    @setup(
        {
            "spaceless05": "{% autoescape off %}{% spaceless %}"
            "<b>   <i>{{ text }}</i>  </b>{% endspaceless %}"
            "{% endautoescape %}"
        }
    )
    def test_spaceless05(self):
        """
        Tests the functionality of the spaceless template tag with autoescape disabled.

        The spaceless tag removes whitespace between HTML tags, and this test case ensures that 
        it works correctly when autoescaping is turned off. The test verifies that the output 
        of the template rendering matches the expected result, checking that HTML entities 
        like '&' are preserved correctly in the final output.
        """
        output = self.engine.render_to_string("spaceless05", {"text": "This & that"})
        self.assertEqual(output, "<b><i>This & that</i></b>")

    @setup(
        {
            "spaceless06": (
                "{% spaceless %}<b>   <i>{{ text|safe }}</i>  </b>{% endspaceless %}"
            )
        }
    )
    def test_spaceless06(self):
        """
        Tests the 'spaceless' template tag with HTML content.

        This test renders a template that uses the 'spaceless' tag to remove whitespace
        from the HTML output. The template contains an HTML string with an 'i' tag and
        safe text that includes an ampersand character. The test asserts that the
        rendered output has no unnecessary whitespace and the HTML content is rendered
        correctly, including the ampersand character being preserved as is.

        The expected output is HTML with no whitespace between tags, and the 'i' tag
        content being 'This & that', demonstrating the correct application of the
        'spaceless' tag and safe text rendering.
        """
        output = self.engine.render_to_string("spaceless06", {"text": "This & that"})
        self.assertEqual(output, "<b><i>This & that</i></b>")
