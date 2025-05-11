from django.test import SimpleTestCase

from ..utils import setup


class InvalidStringTests(SimpleTestCase):
    libraries = {"i18n": "django.templatetags.i18n"}

    @setup({"invalidstr01": '{{ var|default:"Foo" }}'})
    def test_invalidstr01(self):
        """
        Tests the behavior of the templating engine when encountering an invalid string, verifying that it correctly renders either the default value or an \"INVALID\" indicator based on the engine's configuration.
        """
        output = self.engine.render_to_string("invalidstr01")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "Foo")

    @setup({"invalidstr02": '{{ var|default_if_none:"Foo" }}'})
    def test_invalidstr02(self):
        """
        \"testing the behavior of the template engine when rendering an invalid string with a default_if_none filter, verifying that it either outputs 'INVALID' or an empty string depending on the string_if_invalid setting\"
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
        output = self.engine.render_to_string("invalidstr04")
        self.assertEqual(output, "No")

    @setup({"invalidstr04_2": '{% if var|default:"Foo" %}Yes{% else %}No{% endif %}'})
    def test_invalidstr04_2(self):
        output = self.engine.render_to_string("invalidstr04_2")
        self.assertEqual(output, "Yes")

    @setup({"invalidstr05": "{{ var }}"})
    def test_invalidstr05(self):
        """
        Tests rendering behavior when an invalid string is encountered, verifying the output is either 'INVALID' or an empty string depending on the `string_if_invalid` engine setting.
        """
        output = self.engine.render_to_string("invalidstr05")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"invalidstr06": "{{ var.prop }}"})
    def test_invalidstr06(self):
        """

        Tests the behavior of the template engine when rendering a template with an invalid string.
        Verifies that the output matches the expected behavior when the engine is configured to handle invalid strings. 

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
        """
        Tests the rendering of a template string with invalid syntax for internationalization, verifying that the engine handles it correctly by either replacing it with an 'INVALID' marker or an empty string, depending on the engine's configuration.
        """
        output = self.engine.render_to_string("invalidstr07")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")
