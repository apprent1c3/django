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
        """
        Tests the rendering of a template that includes a custom tag using the load tag from the subpackage.echo module.

        Verifies that the.echo and.echo2 custom tags are correctly loaded and rendered, 
        producing the expected output when the template is rendered to a string.
        """
        output = self.engine.render_to_string("load01")
        self.assertEqual(output, "test test")

    @setup({"load02": '{% load subpackage.echo %}{% echo2 "test" %}'})
    def test_load02(self):
        output = self.engine.render_to_string("load02")
        self.assertEqual(output, "test")

    # {% load %} tag, importing individual tags
    @setup({"load03": "{% load echo from testtags %}{% echo this that theother %}"})
    def test_load03(self):
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

        Tests the functionality of loading custom template tags and using them to render a string.

        This test case verifies that the 'echo' and 'other_echo' tags from the 'testtags' module are correctly loaded and applied to the template, resulting in the expected output string.

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
        """
        Tests the functionality of loading custom template tags in a template.

        This test case verifies that the 'echo' and 'upper' template tags are properly loaded and utilized 
        in a template, and that the 'upper' filter correctly converts a string to uppercase. The test 
        renders a template with the custom tags and filter, and asserts that the output matches the 
        expected result, confirming the correct functionality of the loaded tags and filter.
        """
        output = self.engine.render_to_string("load05", {"statement": "not shouting"})
        self.assertEqual(output, "this that theother NOT SHOUTING")

    @setup({"load06": '{% load echo2 from subpackage.echo %}{% echo2 "test" %}'})
    def test_load06(self):
        output = self.engine.render_to_string("load06")
        self.assertEqual(output, "test")

    # {% load %} tag errors
    @setup({"load07": "{% load echo other_echo bad_tag from testtags %}"})
    def test_load07(self):
        """

        Tests the behavior of the template engine when loading a template with an invalid tag.
        The test checks that the engine raises a TemplateSyntaxError with a descriptive message
        when encountering a tag that is not a valid tag or filter in the loaded library.

        """
        msg = "'bad_tag' is not a valid tag or filter in tag library 'testtags'"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("load07")

    @setup({"load08": "{% load echo other_echo bad_tag from %}"})
    def test_load08(self):
        """
        Tests that using the {% load %} template tag with an unregistered tag library raises a TemplateSyntaxError.
        The error message includes the list of registered tag libraries.
        Verifies that the templating engine correctly validates tag library names and provides informative error messages for invalid libraries.
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
        Tests that the template engine raises a TemplateSyntaxError when attempting to load a non-existent tag library using the 'load' template tag.
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
        Tests the behavior when attempting to load a non-existent template tag library.

        The function verifies that a TemplateSyntaxError is raised with a descriptive error message when the template engine is instructed to load a tag library that is not registered. The error message should include the name of the invalid library and a list of valid registered libraries.
        """
        msg = (
            "'bad_library' is not a registered tag library. Must be one of:\n"
            "subpackage.echo\ntesttags"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("load10")

    @setup({"load12": "{% load subpackage.missing %}"})
    def test_load12(self):
        msg = (
            "'subpackage.missing' is not a registered tag library. Must be one of:\n"
            "subpackage.echo\ntesttags"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("load12")
