from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class TemplateTagTests(SimpleTestCase):
    @setup({"templatetag01": "{% templatetag openblock %}"})
    def test_templatetag01(self):
        """
        Tests the rendering of the templatetag01 template to verify it produces the correct opening block syntax.

        This test ensures that the template engine correctly replaces the templatetag01 placeholder with the opening block syntax, resulting in the expected output.

        :raises AssertionError: If the rendered output does not match the expected opening block syntax.
        """
        output = self.engine.render_to_string("templatetag01")
        self.assertEqual(output, "{%")

    @setup({"templatetag02": "{% templatetag closeblock %}"})
    def test_templatetag02(self):
        output = self.engine.render_to_string("templatetag02")
        self.assertEqual(output, "%}")

    @setup({"templatetag03": "{% templatetag openvariable %}"})
    def test_templatetag03(self):
        """
        Test that the templatetag03 setup renders the open variable syntax correctly.

        The templatetag03 setup configures the templating engine to use a custom syntax for opening variables, and this test verifies that the rendered output matches the expected result of '{{'. This ensures that the custom syntax is applied correctly during template rendering.
        """
        output = self.engine.render_to_string("templatetag03")
        self.assertEqual(output, "{{")

    @setup({"templatetag04": "{% templatetag closevariable %}"})
    def test_templatetag04(self):
        output = self.engine.render_to_string("templatetag04")
        self.assertEqual(output, "}}")

    @setup({"templatetag05": "{% templatetag %}"})
    def test_templatetag05(self):
        """

        Tests that a TemplateSyntaxError is raised when a template tag is not properly closed.

        The test case verifies that the templating engine correctly handles syntax errors in template tags,
        specifically when a tag is not closed as expected. This ensures that the engine raises an exception
        when encountering malformed template tags, providing a clear indication of the error to the user.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("templatetag05")

    @setup({"templatetag06": "{% templatetag foo %}"})
    def test_templatetag06(self):
        """
        Tests the engine's handling of invalid template tags by attempting to get a template containing a malformed templatetag and asserting that a TemplateSyntaxError is raised.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("templatetag06")

    @setup({"templatetag07": "{% templatetag openbrace %}"})
    def test_templatetag07(self):
        """
        Tests the rendering of the templatetag for an opening brace.
        This test case ensures that the templating engine correctly interprets and renders 
        the `{% templatetag openbrace %}` tag, resulting in the output of a single opening brace character `{`.
        """
        output = self.engine.render_to_string("templatetag07")
        self.assertEqual(output, "{")

    @setup({"templatetag08": "{% templatetag closebrace %}"})
    def test_templatetag08(self):
        output = self.engine.render_to_string("templatetag08")
        self.assertEqual(output, "}")

    @setup({"templatetag09": "{% templatetag openbrace %}{% templatetag openbrace %}"})
    def test_templatetag09(self):
        """
        Tests the functionality of the templatetag when encountering double open bracket syntax.

        Verifies that the templating engine correctly renders the output when faced with nested open bracket template tags, ensuring proper handling and replacement of the tags.

        The expected output of this rendering process is two consecutive open braces, demonstrating the successful resolution of the nested template tags.
        """
        output = self.engine.render_to_string("templatetag09")
        self.assertEqual(output, "{{")

    @setup(
        {"templatetag10": "{% templatetag closebrace %}{% templatetag closebrace %}"}
    )
    def test_templatetag10(self):
        output = self.engine.render_to_string("templatetag10")
        self.assertEqual(output, "}}")

    @setup({"templatetag11": "{% templatetag opencomment %}"})
    def test_templatetag11(self):
        output = self.engine.render_to_string("templatetag11")
        self.assertEqual(output, "{#")

    @setup({"templatetag12": "{% templatetag closecomment %}"})
    def test_templatetag12(self):
        output = self.engine.render_to_string("templatetag12")
        self.assertEqual(output, "#}")
