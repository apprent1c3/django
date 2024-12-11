from django.test import SimpleTestCase

from ..utils import setup


class CommentSyntaxTests(SimpleTestCase):
    @setup({"comment-syntax01": "{# this is hidden #}hello"})
    def test_comment_syntax01(self):
        """

        Tests the rendering of a template with a comment syntax that hides content.

        This test case verifies that comments in the template, defined by the syntax {# comment #},
        are properly removed from the rendered output, ensuring that only the intended
        content is displayed.

        The expected output of this test is the string 'hello', which confirms that the
        comment syntax is correctly handled and the comment is effectively hidden.

        """
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
        output = self.engine.render_to_string("comment-syntax05")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax06": "foo{# {% #}"})
    def test_comment_syntax06(self):
        output = self.engine.render_to_string("comment-syntax06")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax07": "foo{# %} #}"})
    def test_comment_syntax07(self):
        """
        Tests the comment syntax for template engine.

        This test case verifies that the template engine correctly handles comments 
        in templates, specifically those using the syntax 'foo{# %} #}'. It 
        renders a template named 'comment-syntax07' and checks if the output is 
        as expected, ensuring that the comment is properly removed and only the 
        content 'foo' is rendered. 

        The purpose of this test is to ensure the engine's ability to ignore 
        template comments while processing templates, allowing designers and 
        developers to include notes and comments in their template code without 
        them being displayed in the final output.
        """
        output = self.engine.render_to_string("comment-syntax07")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax08": "foo{# %} #}bar"})
    def test_comment_syntax08(self):
        output = self.engine.render_to_string("comment-syntax08")
        self.assertEqual(output, "foobar")

    @setup({"comment-syntax09": "foo{# {{ #}"})
    def test_comment_syntax09(self):
        output = self.engine.render_to_string("comment-syntax09")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax10": "foo{# }} #}"})
    def test_comment_syntax10(self):
        """
        Tests the rendering of a template with a custom comment syntax.

        This test case verifies that the templating engine can correctly interpret and 
        render a template where the comment syntax is defined as 'foo{# }} #}'.

        The test checks if the rendered output matches the expected string 'foo', 
        indicating that the comment has been properly removed.

        :raises AssertionError: If the rendered output does not match the expected string.

        """
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
        """

        Tests the rendering of a template with comment tags.

        Verifies that content enclosed within comment tags is correctly removed from the output, 
        while content outside of these tags is preserved. This ensures that comment tags are 
        properly parsed and ignored during the rendering process, resulting in the expected output.

        """
        output = self.engine.render_to_string("comment-tag02")
        self.assertEqual(output, "hello")

    @setup({"comment-tag03": "foo{% comment %} {% if %} {% endcomment %}"})
    def test_comment_tag03(self):
        """
        Tests the rendering of a template with a comment tag containing invalid syntax.

        This test case verifies that the template engine correctly handles a comment tag
        that includes invalid template syntax, such as an if statement, and ensures that
        the comment is properly removed from the output.

        The expected output is a string with the comment removed, resulting in the string 'foo'.
        """
        output = self.engine.render_to_string("comment-tag03")
        self.assertEqual(output, "foo")

    @setup({"comment-tag04": "foo{% comment %} {% endblock %} {% endcomment %}"})
    def test_comment_tag04(self):
        """

        Tests the rendering of a template containing a comment tag.

        This test case checks that the comment tag is properly handled by the template engine,
        ensuring that the content inside the tag is ignored and not included in the rendered output.

        The test verifies that the expected output is produced, which in this case is 'foo',
        indicating that the comment tag is correctly processed and its contents are discarded.

        """
        output = self.engine.render_to_string("comment-tag04")
        self.assertEqual(output, "foo")

    @setup({"comment-tag05": "foo{% comment %} {% somerandomtag %} {% endcomment %}"})
    def test_comment_tag05(self):
        output = self.engine.render_to_string("comment-tag05")
        self.assertEqual(output, "foo")
