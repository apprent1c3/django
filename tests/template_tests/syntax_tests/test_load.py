from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class LoadTagTests(SimpleTestCase):
    libraries = {
        "subpackage.echo": "template_tests.templatetags.subpackage.echo",
        "testtags": "template_tests.templatetags.testtags",
    }

    @setup(
        {
            "load01": (
                '{% load testtags subpackage.echo %}{% echo test %} {% echo2 "test" %}'
            )
        }
    )
    def test_load01(self):
        output = self.engine.render_to_string("load01")
        self.assertEqual(output, "test test")

    @setup({"load02": '{% load subpackage.echo %}{% echo2 "test" %}'})
    def test_load02(self):
        output = self.engine.render_to_string("load02")
        self.assertEqual(output, "test")

    # {% load %} tag, importing individual tags
    @setup({"load03": "{% load echo from testtags %}{% echo this that theother %}"})
    def test_load03(self):
        """
        Tests the template loading of a custom tag named 'echo' from the 'testtags' module.

        This function checks if the 'echo' tag correctly outputs the parameters 'this', 'that', and 'theother' when loaded into a template using the {% load %} syntax.

        The test renders a template string containing the loaded 'echo' tag and verifies that the output matches the expected result, ensuring the tag functions as intended.
        """
        output = self.engine.render_to_string("load03")
        self.assertEqual(output, "this that theother")

    @setup(
        {
            "load04": "{% load echo other_echo from testtags %}"
            "{% echo this that theother %} {% other_echo and another thing %}"
        }
    )
    def test_load04(self):
        """
        Tests the loading of custom template tags from a testtags module.

        Verifies that the `echo` and `other_echo` tags are successfully loaded and
        rendered within a template, resulting in the expected output string.

        The test case covers the functionality of loading multiple tags and using them
        to generate content in a template, ensuring that the output matches the
        anticipated result.
        """
        output = self.engine.render_to_string("load04")
        self.assertEqual(output, "this that theother and another thing")

    @setup(
        {
            "load05": "{% load echo upper from testtags %}"
            "{% echo this that theother %} {{ statement|upper }}"
        }
    )
    def test_load05(self):
        output = self.engine.render_to_string("load05", {"statement": "not shouting"})
        self.assertEqual(output, "this that theother NOT SHOUTING")

    @setup({"load06": '{% load echo2 from subpackage.echo %}{% echo2 "test" %}'})
    def test_load06(self):
        """

        Tests the {% load %} template tag with a custom tag from the 'subpackage.echo' module.

        Verifies that loading the 'echo2' template tag and using it to echo a string
        results in the correct output.

        Raises:
            AssertionError: If the rendered output does not match the expected output.

        """
        output = self.engine.render_to_string("load06")
        self.assertEqual(output, "test")

    # {% load %} tag errors
    @setup({"load07": "{% load echo other_echo bad_tag from testtags %}"})
    def test_load07(self):
        """

        Test the handling of an invalid tag in a load statement.

        This test case checks that a TemplateSyntaxError is raised when the 'load'
        statement attempts to load a tag library that includes a non-existent tag.
        The error message should specifically mention the invalid tag 'bad_tag' and
        indicate that it is not a valid tag or filter in the 'testtags' library.

        """
        msg = "'bad_tag' is not a valid tag or filter in tag library 'testtags'"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("load07")

    @setup({"load08": "{% load echo other_echo bad_tag from %}"})
    def test_load08(self):
        """

        Tests that a TemplateSyntaxError is raised when attempting to load an unregistered tag library.

        The test case covers the scenario where a template tries to load a tag library that is not registered in the template engine.
        The expected error message includes a list of available tag libraries, providing helpful feedback for troubleshooting.

        """
        msg = (
            "'echo' is not a registered tag library. Must be one of:\n"
            "subpackage.echo\ntesttags"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("load08")

    @setup({"load09": "{% load from testtags %}"})
    def test_load09(self):
        """

        Tests that an error is raised when attempting to load a non-existent or unregistered template tag library.

        This test verifies that the template engine correctly handles invalid 'load' tag syntax by raising a TemplateSyntaxError with a descriptive error message.

        """
        msg = (
            "'from' is not a registered tag library. Must be one of:\n"
            "subpackage.echo\ntesttags"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("load09")

    @setup({"load10": "{% load echo from bad_library %}"})
    def test_load10(self):
        """
        Tests the Template Engine's handling of a non-registered tag library in a load statement.

        This test case checks that the engine raises a TemplateSyntaxError when attempting to load a tag library that is not registered. The test expects the error message to contain the names of the registered tag libraries, indicating that the engine is aware of the available libraries but the specified one is not among them.
        """
        msg = (
            "'bad_library' is not a registered tag library. Must be one of:\n"
            "subpackage.echo\ntesttags"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("load10")

    @setup({"load12": "{% load subpackage.missing %}"})
    def test_load12(self):
        """
        Tests that a TemplateSyntaxError is raised when attempting to load a non-existent template tag library, 'subpackage.missing', using the {% load %} template tag. 
        The test expects an error message specifying that 'subpackage.missing' is not a registered tag library, and instead provides a list of valid tag libraries, in this case 'subpackage.echo' and 'testtags'.
        """
        msg = (
            "'subpackage.missing' is not a registered tag library. Must be one of:\n"
            "subpackage.echo\ntesttags"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("load12")
