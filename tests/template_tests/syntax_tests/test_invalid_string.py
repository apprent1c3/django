from django.test import SimpleTestCase

from ..utils import setup


class InvalidStringTests(SimpleTestCase):
    libraries = {"i18n": "django.templatetags.i18n"}

    @setup({"invalidstr01": '{{ var|default:"Foo" }}'})
    def test_invalidstr01(self):
        """

        Tests the behavior of the template engine when rendering a string with an invalid variable.

        This test case checks how the engine handles a template containing a variable that
        is not defined. It verifies that the output is either the default value specified
        in the template or the engine's configured string to display when a variable is invalid.

        """
        output = self.engine.render_to_string("invalidstr01")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "Foo")

    @setup({"invalidstr02": '{{ var|default_if_none:"Foo" }}'})
    def test_invalidstr02(self):
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

        Tests the rendering of a template containing an invalid string.

        When the template engine encounters an invalid string, this test checks two possible outcomes:
        - If the engine is configured to render an error message when encountering an invalid string, the test verifies that the rendered output contains the error message.
        - If the engine is configured to render an empty string when encountering an invalid string, the test verifies that the rendered output is indeed empty.

        The test covers the behavior of the template engine in handling invalid strings, ensuring that it behaves as expected based on its configuration.

        """
        output = self.engine.render_to_string("invalidstr05")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"invalidstr06": "{{ var.prop }}"})
    def test_invalidstr06(self):
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
