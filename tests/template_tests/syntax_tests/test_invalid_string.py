from django.test import SimpleTestCase

from ..utils import setup


class InvalidStringTests(SimpleTestCase):
    libraries = {"i18n": "django.templatetags.i18n"}

    @setup({"invalidstr01": '{{ var|default:"Foo" }}'})
    def test_invalidstr01(self):
        output = self.engine.render_to_string("invalidstr01")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "Foo")

    @setup({"invalidstr02": '{{ var|default_if_none:"Foo" }}'})
    def test_invalidstr02(self):
        """
        Test the behavior of the template engine when rendering a string with an invalid variable.

        This test checks how the engine handles a template that uses the `default_if_none` filter on a variable that does not exist. The expected output can vary depending on the engine's configuration, specifically the `string_if_invalid` setting.

        If `string_if_invalid` is enabled, the test verifies that the engine renders the string 'INVALID'. Otherwise, it checks that the engine renders an empty string.
        """
        output = self.engine.render_to_string("invalidstr02")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"invalidstr03": "{% for v in var %}({{ v }}){% endfor %}"})
    def test_invalidstr03(self):
        output = self.engine.render_to_string("invalidstr03")
        self.assertEqual(output, "")

    @setup({"invalidstr04": "{% if var %}Yes{% else %}No{% endif %}"})
    def test_invalidstr04(self):
        """
        Tests the rendering of a template containing an if statement with an undefined variable, verifying that the else clause is executed when the variable is not defined.
        """
        output = self.engine.render_to_string("invalidstr04")
        self.assertEqual(output, "No")

    @setup({"invalidstr04_2": '{% if var|default:"Foo" %}Yes{% else %}No{% endif %}'})
    def test_invalidstr04_2(self):
        """
        Tests the rendering of a template string with a default variable value. 

        The test case verifies that when a variable is passed through a default filter in a conditional statement and the variable evaluates to a truthy value, the template renders the string 'Yes'. 

        This test ensures that the templating engine correctly handles default values in conditional statements and returns the expected output when the variable is defined.
        """
        output = self.engine.render_to_string("invalidstr04_2")
        self.assertEqual(output, "Yes")

    @setup({"invalidstr05": "{{ var }}"})
    def test_invalidstr05(self):
        output = self.engine.render_to_string("invalidstr05")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"invalidstr06": "{{ var.prop }}"})
    def test_invalidstr06(self):
        """

        Tests the behavior of the templating engine when encountering an invalid string.

        Verifies that the engine correctly handles a template string containing an
        expression with an undefined property. The test checks the output of the
        templating engine, comparing it to the expected result based on the engine's
        configuration for handling invalid strings.

        When the engine is configured to replace invalid strings with a specific
        value, this test checks that the output matches the expected replacement value.
        Otherwise, it checks that the output is an empty string.

        """
        output = self.engine.render_to_string("invalidstr06")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup(
        {
            "invalidstr07": (
                "{% load i18n %}{% blocktranslate %}{{ var }}{% endblocktranslate %}"
            )
        }
    )
    def test_invalidstr07(self):
        output = self.engine.render_to_string("invalidstr07")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")
