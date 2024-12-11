from django.test import SimpleTestCase

from ..utils import setup


class BuiltinsTests(SimpleTestCase):
    @setup({"builtins01": "{{ True }}"})
    def test_builtins01(self):
        """
        .Tests that the Jinja2 engine correctly renders a built-in boolean value.

        This test case verifies that a simple boolean expression is properly evaluated and output as a string.
        The purpose of this test is to ensure the engine can handle basic built-in data types and render them as expected.
        """
        output = self.engine.render_to_string("builtins01")
        self.assertEqual(output, "True")

    @setup({"builtins02": "{{ False }}"})
    def test_builtins02(self):
        """
        Tests the rendering of a template with the 'builtins02' setup, verifying that the output string equals 'False'. This test case ensures that the templating engine correctly handles boolean values in the provided setup.
        """
        output = self.engine.render_to_string("builtins02")
        self.assertEqual(output, "False")

    @setup({"builtins03": "{{ None }}"})
    def test_builtins03(self):
        """
        Tests the rendering of the 'builtins03' template to ensure it correctly outputs the string representation of None when rendered by the engine.
        """
        output = self.engine.render_to_string("builtins03")
        self.assertEqual(output, "None")
