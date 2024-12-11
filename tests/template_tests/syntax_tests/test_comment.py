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
        Tests the rendering of a template with a comment syntax that spans multiple lines.

        The function checks that the template engine correctly interprets a comment block 
        that contains a template tag and ignores its contents, producing the expected output.

        The test case verifies that the comment syntax '{#  {% somerandomtag %}  #}' 
        is properly handled and does not affect the output of the rendered template.
        """
        output = self.engine.render_to_string("comment-syntax05")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax06": "foo{# {% #}"})
    def test_comment_syntax06(self):
        output = self.engine.render_to_string("comment-syntax06")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax07": "foo{# %} #}"})
    def test_comment_syntax07(self):
        output = self.engine.render_to_string("comment-syntax07")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax08": "foo{# %} #}bar"})
    def test_comment_syntax08(self):
        """
        Tests the comment syntax using a custom delimiter '{# %} #}'.

        This test case verifies that the templating engine correctly ignores comments
        defined by the custom syntax and renders the expected output.

        The expected output is a string 'foobar', indicating that the comments have been
        successfully removed from the template.

        The test covers the setup and rendering of a template with custom comment syntax,
        providing assurance that the templating engine handles comments as intended.
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
        output = self.engine.render_to_string("comment-tag02")
        self.assertEqual(output, "hello")

    @setup({"comment-tag03": "foo{% comment %} {% if %} {% endcomment %}"})
    def test_comment_tag03(self):
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
