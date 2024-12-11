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

        Tests the spaceless template tag in the templating engine.

        The spaceless tag removes whitespace between HTML tags, ensuring that the output is compact and efficient.
        This test case verifies that the spaceless tag correctly removes newline characters and extra spaces from the template.

        """
        output = self.engine.render_to_string("spaceless02")
        self.assertEqual(output, "<b><i> text </i></b>")

    @setup({"spaceless03": "{% spaceless %}<b><i>text</i></b>{% endspaceless %}"})
    def test_spaceless03(self):
        """
        .. function:: test_spaceless03
            Tests the functionality of the spaceless template tag.

            The spaceless tag is used to remove whitespace between HTML tags in a template.
            This test case verifies that the spaceless tag correctly removes unnecessary whitespace,
            ensuring that the output HTML is compact and efficient.

            It checks if the rendered HTML output matches the expected result, 
            which is the input HTML with all unnecessary whitespace removed.
        """
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
        Tests the functionality of the 'spaceless' template tag in conjunction with HTML escaping.
        The test checks if HTML tags are correctly preserved and rendered, while any excessive whitespace is removed.
        The input string 'This & that' is used, containing an ampersand character that requires proper HTML escaping.
        The expected output is a string containing bold and italic HTML tags with the input text, demonstrating correct rendering and escaping.
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
        output = self.engine.render_to_string("spaceless06", {"text": "This & that"})
        self.assertEqual(output, "<b><i>This & that</i></b>")
