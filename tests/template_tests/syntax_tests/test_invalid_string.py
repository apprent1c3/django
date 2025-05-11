from django.test import SimpleTestCase

from ..utils import setup


class InvalidStringTests(SimpleTestCase):
    libraries = {"i18n": "django.templatetags.i18n"}

    @setup({"invalidstr01": '{{ var|default:"Foo" }}'})
    def test_invalidstr01(self):
        """
        Tests the engine's behavior when rendering an invalid string, verifying that it either outputs 'INVALID' if string_if_invalid is enabled or a default value if not.
        """
        output = self.engine.render_to_string("invalidstr01")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "Foo")

    @setup({"invalidstr02": '{{ var|default_if_none:"Foo" }}'})
    def test_invalidstr02(self):
        """
        Tests the template engine's behavior when encountering an invalid string, specifically verifying that it correctly handles the default_if_none filter and the invalid string replacement setting.
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
        Tests the rendering of an invalid string in a template, verifying that the output is 'INVALID' if string_if_invalid is set, or an empty string otherwise.
        """
        output = self.engine.render_to_string("invalidstr05")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"invalidstr06": "{{ var.prop }}"})
    def test_invalidstr06(self):
        """
        Tests the engine's behavior when rendering an invalid string with undefined variable properties.\"\"\"
        \"\"\" 
            Verifies that the engine correctly handles the case when 'string_if_invalid' 
            is enabled or disabled, and checks the output against the expected values.

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
        Test that the template engine correctly handles an invalid string in a blocktranslate block when rendering a template to a string.
        """
        output = self.engine.render_to_string("invalidstr07")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")
