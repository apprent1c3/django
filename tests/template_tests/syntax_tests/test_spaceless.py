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

        Tests the spaceless template tag functionality.

        The spaceless tag is used to remove whitespace from a block of HTML code.
        This test case verifies that the spaceless tag effectively removes extra spaces 
        between HTML tags, ensuring the output is clean and compact.

        The test expectation is that the input string containing HTML tags with 
        surrounding whitespace is rendered as a string without the extra spaces.

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
        """

        Tests the spaceless template tag to remove extra whitespace from HTML tags.

        The spaceless tag is used to remove extra whitespace between HTML tags, 
        resulting in more compact and efficient HTML output. This test case 
        verifies that the tag correctly removes newline characters and extra 
        whitespace from the rendered template, ensuring that the output matches 
        the expected HTML string without unnecessary whitespace.

        """
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

        Tests the spaceless template tag with HTML content.

        This test verifies that the spaceless tag correctly removes unnecessary whitespace from
        the HTML content while preserving HTML entities. The function renders a template with
        the spaceless tag and checks if the output matches the expected result.

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
        Tests that the Django template engine's `spaceless` tag correctly removes whitespace 
        from the HTML content while preserving HTML entities, ensuring that the output 
        contains the expected HTML structure and content.
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
        Tests the spaceless template tag in conjunction with the safe filter.

        The spaceless tag removes whitespace between HTML tags, while the safe filter
        prevents the escaping of HTML characters in the template output. This test case
        verifies that the spaceless tag correctly removes unnecessary whitespace and
        the safe filter prevents HTML encoding of special characters, such as ampersands.

        It checks if the rendered output matches the expected HTML string without any
        extra whitespace between the HTML tags, and that the special characters are
        preserved as is.
        """
        output = self.engine.render_to_string("spaceless06", {"text": "This & that"})
        self.assertEqual(output, "<b><i>This & that</i></b>")
