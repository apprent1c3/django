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
        """
        Tests the loading of a template tag from a subpackage using the echo2 tag, verifying that the rendered output matches the expected string.
        """
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
        Tests the functionality of loading a custom tag 'echo2' from the 'subpackage.echo' module and using it to echo a string in a template. 

        This test case verifies that the rendered output of a template containing the loaded tag matches the expected echoed string.
        """
        output = self.engine.render_to_string("load06")
        self.assertEqual(output, "test")

    # {% load %} tag errors
    @setup({"load07": "{% load echo other_echo bad_tag from testtags %}"})
    def test_load07(self):
        msg = "'bad_tag' is not a valid tag or filter in tag library 'testtags'"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("load07")

    @setup({"load08": "{% load echo other_echo bad_tag from %}"})
    def test_load08(self):
        msg = (
            "'echo' is not a registered tag library. Must be one of:\n"
            "subpackage.echo\ntesttags"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("load08")

    @setup({"load09": "{% load from testtags %}"})
    def test_load09(self):
        msg = (
            "'from' is not a registered tag library. Must be one of:\n"
            "subpackage.echo\ntesttags"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("load09")

    @setup({"load10": "{% load echo from bad_library %}"})
    def test_load10(self):
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
