from django.test import SimpleTestCase

from ..utils import setup


class CommentSyntaxTests(SimpleTestCase):
    @setup({"comment-syntax01": "{# this is hidden #}hello"})
    def test_comment_syntax01(self):
        output = self.engine.render_to_string("comment-syntax01")
        self.assertEqual(output, "hello")

    @setup({"comment-syntax02": "{# this is hidden #}hello{# foo #}"})
    def test_comment_syntax02(self):
        output = self.engine.render_to_string("comment-syntax02")
        self.assertEqual(output, "hello")

    @setup({"comment-syntax03": "foo{#  {% if %}  #}"})
    def test_comment_syntax03(self):
        output = self.engine.render_to_string("comment-syntax03")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax04": "foo{#  {% endblock %}  #}"})
    def test_comment_syntax04(self):
        output = self.engine.render_to_string("comment-syntax04")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax05": "foo{#  {% somerandomtag %}  #}"})
    def test_comment_syntax05(self):
        """
        Test the syntax for comments in templates.

        This test checks that comments within templates are handled correctly, ensuring they are not rendered in the output.
        The test verifies that comments are properly removed from the template, resulting in the expected output.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Assertions
        ----------
        The test asserts that the rendered template output matches the expected string 'foo', confirming correct comment syntax handling.
        """
        output = self.engine.render_to_string("comment-syntax05")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax06": "foo{# {% #}"})
    def test_comment_syntax06(self):
        """

        Tests the template engine's comment syntax for a specific format.

        This test case verifies that the template engine correctly interprets and removes
        comments that start with '{# %' and end with the corresponding closing syntax,
        ensuring that the rendered output matches the expected result.

        """
        output = self.engine.render_to_string("comment-syntax06")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax07": "foo{# %} #}"})
    def test_comment_syntax07(self):
        output = self.engine.render_to_string("comment-syntax07")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax08": "foo{# %} #}bar"})
    def test_comment_syntax08(self):
        """

        Tests the syntax for comments in templates.

        This test case verifies that comments are correctly parsed and removed from the output.
        It checks that the rendering engine properly handles comments and produces the expected output.

        The test uses a template with a comment to ensure that the comment is not included in the rendered string.
        The expected output is a string without the comment, demonstrating that the comment syntax is correctly handled.

        """
        output = self.engine.render_to_string("comment-syntax08")
        self.assertEqual(output, "foobar")

    @setup({"comment-syntax09": "foo{# {{ #}"})
    def test_comment_syntax09(self):
        output = self.engine.render_to_string("comment-syntax09")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax10": "foo{# }} #}"})
    def test_comment_syntax10(self):
        output = self.engine.render_to_string("comment-syntax10")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax11": "foo{# { #}"})
    def test_comment_syntax11(self):
        output = self.engine.render_to_string("comment-syntax11")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax12": "foo{# } #}"})
    def test_comment_syntax12(self):
        """
        Tests the rendering of the 'comment-syntax12' template with a specific comment syntax.

        The function verifies that the output of the template rendering matches the expected result, 
        which is 'foo', after the comment syntax 'foo{# } #' has been applied.

        This test case ensures that the template engine correctly handles comments in the template 
        and produces the expected output, thus validating the functionality of the 'comment-syntax12' setup.

        """
        output = self.engine.render_to_string("comment-syntax12")
        self.assertEqual(output, "foo")

    @setup({"comment-tag01": "{% comment %}this is hidden{% endcomment %}hello"})
    def test_comment_tag01(self):
        output = self.engine.render_to_string("comment-tag01")
        self.assertEqual(output, "hello")

    @setup(
        {
            "comment-tag02": "{% comment %}this is hidden{% endcomment %}"
            "hello{% comment %}foo{% endcomment %}"
        }
    )
    def test_comment_tag02(self):
        """
        Tests the functionality of the comment tag to ensure it properly removes commented content from the rendered output. 

        The comment tag is expected to hide its enclosed content, so only the content outside of the comment tags should be visible in the final rendered string. This test verifies that the rendering engine correctly interprets and removes the commented sections, resulting in the expected output.
        """
        output = self.engine.render_to_string("comment-tag02")
        self.assertEqual(output, "hello")

    @setup({"comment-tag03": "foo{% comment %} {% if %} {% endcomment %}"})
    def test_comment_tag03(self):
        """

        Tests the rendering of a template containing a comment tag with nested template tags.

        The function verifies that the comment tag correctly removes its contents, including any nested template tags, from the rendered output.

        """
        output = self.engine.render_to_string("comment-tag03")
        self.assertEqual(output, "foo")

    @setup({"comment-tag04": "foo{% comment %} {% endblock %} {% endcomment %}"})
    def test_comment_tag04(self):
        output = self.engine.render_to_string("comment-tag04")
        self.assertEqual(output, "foo")

    @setup({"comment-tag05": "foo{% comment %} {% somerandomtag %} {% endcomment %}"})
    def test_comment_tag05(self):
        output = self.engine.render_to_string("comment-tag05")
        self.assertEqual(output, "foo")
