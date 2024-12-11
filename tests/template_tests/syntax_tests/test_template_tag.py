from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class TemplateTagTests(SimpleTestCase):
    @setup({"templatetag01": "{% templatetag openblock %}"})
    def test_templatetag01(self):
        """
        Tests the rendering of the templatetag01, which is expected to output the opening block of a template tag.

        The purpose of this test is to ensure that the templatetag01 is correctly substituted with the opening block syntax, i.e., '{%' when rendered by the template engine.
        """
        output = self.engine.render_to_string("templatetag01")
        self.assertEqual(output, "{%")

    @setup({"templatetag02": "{% templatetag closeblock %}"})
    def test_templatetag02(self):
        output = self.engine.render_to_string("templatetag02")
        self.assertEqual(output, "%}")

    @setup({"templatetag03": "{% templatetag openvariable %}"})
    def test_templatetag03(self):
        output = self.engine.render_to_string("templatetag03")
        self.assertEqual(output, "{{")

    @setup({"templatetag04": "{% templatetag closevariable %}"})
    def test_templatetag04(self):
        """
        Test the rendering of the templatetag to verify it correctly closes a variable.
        The test checks if the output of the templatetag matches the expected string '}}'.
        """
        output = self.engine.render_to_string("templatetag04")
        self.assertEqual(output, "}}")

    @setup({"templatetag05": "{% templatetag %}"})
    def test_templatetag05(self):
        """
        Tests the handling of a malformed templatetag in a template.

        This test checks that the template engine correctly raises a TemplateSyntaxError
        when encountering an improperly formatted templatetag. The test case verifies
        the engine's behavior when the templatetag is not properly closed, ensuring that
        it fails to parse the template and instead throws an exception as expected.

        :raises TemplateSyntaxError: When the template engine encounters a malformed templatetag.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("templatetag05")

    @setup({"templatetag06": "{% templatetag foo %}"})
    def test_templatetag06(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("templatetag06")

    @setup({"templatetag07": "{% templatetag openbrace %}"})
    def test_templatetag07(self):
        """
        Tests the rendering of the templatetag07 template, which contains a custom templatetag.

        Verifies that the engine correctly renders the templatetag as an opening brace ('{').

        Ensures proper functionality of custom templatetags in the template engine, specifically the correct replacement of templatetags with their corresponding output.

        """
        output = self.engine.render_to_string("templatetag07")
        self.assertEqual(output, "{")

    @setup({"templatetag08": "{% templatetag closebrace %}"})
    def test_templatetag08(self):
        """
        Tests the templatetag08 functionality to ensure correct rendering of template tags.
        The function verifies that the template engine properly closes a template tag when encountering a closebrace.
        It checks if the rendered output matches the expected result, which is a single closing brace character.
        """
        output = self.engine.render_to_string("templatetag08")
        self.assertEqual(output, "}")

    @setup({"templatetag09": "{% templatetag openbrace %}{% templatetag openbrace %}"})
    def test_templatetag09(self):
        output = self.engine.render_to_string("templatetag09")
        self.assertEqual(output, "{{")

    @setup(
        {"templatetag10": "{% templatetag closebrace %}{% templatetag closebrace %}"}
    )
    def test_templatetag10(self):
        """
        Tests the rendering of the templatetag closebrace when it appears multiple times in a template, 
        ensuring that it correctly outputs closing braces. The test checks if the output of the template 
        match the expected result, verifying that the template engine handles this edge case properly.
        """
        output = self.engine.render_to_string("templatetag10")
        self.assertEqual(output, "}}")

    @setup({"templatetag11": "{% templatetag opencomment %}"})
    def test_templatetag11(self):
        """
        Tests the rendering of a custom template tag for opening a comment block.

        The function verifies that the template engine correctly replaces the defined
        templatetag with the expected output, which is the opening syntax for a comment
        block. This ensures that the template tag is properly registered and functional,
        allowing for comments to be inserted into templates.
        """
        output = self.engine.render_to_string("templatetag11")
        self.assertEqual(output, "{#")

    @setup({"templatetag12": "{% templatetag closecomment %}"})
    def test_templatetag12(self):
        """
        Tests the rendering of the templatetag12 template to ensure it correctly outputs the close comment tag. 

        The test verifies that the templating engine processes the templatetag properly and produces the expected output. 

        This test case is designed to validate the functionality of the templating engine's handling of the close comment tag, ensuring it is rendered as expected in the final output.
        """
        output = self.engine.render_to_string("templatetag12")
        self.assertEqual(output, "#}")
