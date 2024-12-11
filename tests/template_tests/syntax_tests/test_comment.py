from django.test import SimpleTestCase

from ..utils import setup


class CommentSyntaxTests(SimpleTestCase):
    @setup({"comment-syntax01": "{# this is hidden #}hello"})
    def test_comment_syntax01(self):
        """
        Tests the comment syntax by rendering a template and verifying that the output matches the expected result, with all content within the comment syntax correctly hidden from the output. The comment syntax is used to exclude a section of text from being rendered in the final output, and this test ensures that the rendering engine correctly interprets and handles this syntax.
        """
        output = self.engine.render_to_string("comment-syntax01")
        self.assertEqual(output, "hello")

    @setup({"comment-syntax02": "{# this is hidden #}hello{# foo #}"})
    def test_comment_syntax02(self):
        """

        Tests the syntax for comments in the templating engine.

        Verifies that comments enclosed in '{# #}' are properly removed from the output,
        leaving only the visible text. This ensures that commenting functionality works
        as expected, allowing template authors to embed hidden notes or metadata.

        """
        output = self.engine.render_to_string("comment-syntax02")
        self.assertEqual(output, "hello")

    @setup({"comment-syntax03": "foo{#  {% if %}  #}"})
    def test_comment_syntax03(self):
        output = self.engine.render_to_string("comment-syntax03")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax04": "foo{#  {% endblock %}  #}"})
    def test_comment_syntax04(self):
        """
        Test the rendering of a template with a comment syntax that includes a block statement.

        This function verifies that the template engine correctly handles comments containing block statements, 
        by checking if the rendered output matches the expected result, omitting the comment and its contents.
        """
        output = self.engine.render_to_string("comment-syntax04")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax05": "foo{#  {% somerandomtag %}  #}"})
    def test_comment_syntax05(self):
        """
        Tests the comment syntax by rendering a template with a comment tag.

        This test case checks if the engine correctly handles a comment tag
        embedded within a string, ensuring that the comment is properly removed
        from the output. The expected output should be the string without the
        comment tag, verifying the correct functionality of the comment syntax.
        """
        output = self.engine.render_to_string("comment-syntax05")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax06": "foo{# {% #}"})
    def test_comment_syntax06(self):
        """

        Tests the rendering of a template with a specific comment syntax.

        This test case verifies that the templating engine correctly interprets and removes comments 
        from the template, resulting in the expected output. The test expects the string 'foo' as 
        the rendered output when the template 'comment-syntax06' is processed with the specified 
        comment syntax ('foo{# {% #}'). 

        The purpose of this test is to ensure that the templating engine handles comments correctly 
        and produces the desired output.

        """
        output = self.engine.render_to_string("comment-syntax06")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax07": "foo{# %} #}"})
    def test_comment_syntax07(self):
        """
        Tests the comment syntax 'foo{# %} #}' to ensure it correctly removes comments from the output.

        This test case verifies that the templating engine properly interprets and removes the specific comment syntax,
        resulting in a clean output string without the comment section.

        The expected output of this test is 'foo', indicating that the comments have been successfully removed.
        """
        output = self.engine.render_to_string("comment-syntax07")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax08": "foo{# %} #}bar"})
    def test_comment_syntax08(self):
        """
        Tests the rendering of templates with custom comment syntax.

        This test case verifies that the template engine correctly handles comments 
        defined with the syntax 'foo{# %} #}bar'. It checks if the engine removes 
        comments from the template output, resulting in the expected rendered string.

        :raises AssertionError: If the rendered output does not match the expected result.
        """
        output = self.engine.render_to_string("comment-syntax08")
        self.assertEqual(output, "foobar")

    @setup({"comment-syntax09": "foo{# {{ #}"})
    def test_comment_syntax09(self):
        output = self.engine.render_to_string("comment-syntax09")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax10": "foo{# }} #}"})
    def test_comment_syntax10(self):
        """

        Tests the syntax for comments in templates.

        This test case verifies that the comment syntax 'foo{# }} #}' is correctly interpreted by the template engine,
        resulting in the output 'foo'. The test checks for proper parsing and removal of comments, ensuring that only the
        intended content is rendered.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the rendered output does not match the expected output.

        """
        output = self.engine.render_to_string("comment-syntax10")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax11": "foo{# { #}"})
    def test_comment_syntax11(self):
        """

        Tests the rendering of a template with custom comment syntax.

        This test case specifically checks if the templating engine correctly handles 
        a template comment that uses the syntax 'foo{# { #}' and removes the comment 
        from the rendered output, resulting in the expected 'foo' string.

        The test verifies that the custom comment syntax is properly parsed and ignored 
        during the rendering process, ensuring that only the desired content is included 
        in the final output.

        """
        output = self.engine.render_to_string("comment-syntax11")
        self.assertEqual(output, "foo")

    @setup({"comment-syntax12": "foo{# } #}"})
    def test_comment_syntax12(self):
        """
        Tests the rendering of a template with a custom comment syntax.

        This test case verifies that the templating engine correctly handles a specific
        comment syntax, ensuring that comments are properly removed from the rendered output.
        The custom syntax 'foo{# } #}' is used to define the comment block, and the test
        asserts that the resulting output is 'foo', indicating that the comment has been
        successfully stripped from the template.
        """
        output = self.engine.render_to_string("comment-syntax12")
        self.assertEqual(output, "foo")

    @setup({"comment-tag01": "{% comment %}this is hidden{% endcomment %}hello"})
    def test_comment_tag01(self):
        """

        Tests the functionality of the comment tag in the templating engine.

        This test case verifies that the content within a comment tag is removed from the output.
        The comment tag is defined as {% comment %}...{% endcomment %}, and any content within this block should be hidden from the final rendered string.

        The test checks if the engine correctly renders the template with the comment tag, 
        by comparing the output string with the expected result, which should be the content outside of the comment tag.

        """
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

        Tests that comments defined by the template tag '{% comment %}' are removed from the rendered template output.

        The purpose of this test is to verify that the templating engine correctly identifies and omits content enclosed within the comment tags, ensuring that only the intended visible content is rendered.

        The test case checks if the output string 'hello' is correctly produced after removing comments from the input string.

        """
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
