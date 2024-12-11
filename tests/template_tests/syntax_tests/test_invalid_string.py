from django.test import SimpleTestCase

from ..utils import setup


class InvalidStringTests(SimpleTestCase):
    libraries = {"i18n": "django.templatetags.i18n"}

    @setup({"invalidstr01": '{{ var|default:"Foo" }}'})
    def test_invalidstr01(self):
        """
        Tests rendering a template variable with an invalid string and a default value.

        The function verifies how the template engine handles a missing variable 'var' 
        by checking the rendered output string. If the engine is configured to 
        display an 'INVALID' string for missing variables, it asserts the output to 
        be 'INVALID'. Otherwise, it checks that the default value 'Foo' is used.
        """
        output = self.engine.render_to_string("invalidstr01")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "Foo")

    @setup({"invalidstr02": '{{ var|default_if_none:"Foo" }}'})
    def test_invalidstr02(self):
        """
        Tests the behavior of the templating engine when rendering a string with a variable that has a default value.

        The function checks the engine's behavior when `string_if_invalid` is enabled or disabled, verifying that the rendered output matches the expected result in either case.
        """
        output = self.engine.render_to_string("invalidstr02")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"invalidstr03": "{% for v in var %}({{ v }}){% endfor %}"})
    def test_invalidstr03(self):
        """
        Tests that rendering a template with an invalid string containing a for loop results in an empty string being output.
        """
        output = self.engine.render_to_string("invalidstr03")
        self.assertEqual(output, "")

    @setup({"invalidstr04": "{% if var %}Yes{% else %}No{% endif %}"})
    def test_invalidstr04(self):
        """
        Tests the rendering of a template string with a conditional statement when the variable is not defined, 
        verifying that the output is 'No' as expected in the absence of the variable.
        """
        output = self.engine.render_to_string("invalidstr04")
        self.assertEqual(output, "No")

    @setup({"invalidstr04_2": '{% if var|default:"Foo" %}Yes{% else %}No{% endif %}'})
    def test_invalidstr04_2(self):
        """
        Tests the rendering of a template string that uses the default filter in an if statement.

        The test verifies that when a variable is defined, the default value is not used, and the condition evaluates to True.

        The expected output of the rendered template string is assertions-checked to be 'Yes'.
        """
        output = self.engine.render_to_string("invalidstr04_2")
        self.assertEqual(output, "Yes")

    @setup({"invalidstr05": "{{ var }}"})
    def test_invalidstr05(self):
        """
        Tests the rendering of a template with an invalid string.

        This test case checks the engine's behavior when a template contains an invalid
        string. It verifies that the rendered output matches the expected result based
        on the engine's configuration for handling invalid strings.

        If the engine is set to replace invalid strings with a specific value, the test
        asserts that the output contains this value. Otherwise, it expects an empty
        string to be returned.

        The test helps ensure that the engine handles invalid strings correctly and
        provides a predictable output in such cases.
        """
        output = self.engine.render_to_string("invalidstr05")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"invalidstr06": "{{ var.prop }}"})
    def test_invalidstr06(self):
        """
        Tests the behavior of the rendering engine when it encounters an invalid string reference.
        It verifies that the engine correctly handles a template string containing a reference to a non-existent property.
        The test checks two possible outcomes: one where the engine is configured to display an 'INVALID' indicator for such references, and another where it is configured to render an empty string instead.
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
        Tests the rendering of a template with an invalid string using the blocktranslate tag.

        Checks if the correct output is produced when the string_if_invalid setting is enabled or disabled.
        The test verifies that the engine renders the template with the expected result, either 'INVALID' when string_if_invalid is True, or an empty string when string_if_invalid is False.
        """
        output = self.engine.render_to_string("invalidstr07")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")
