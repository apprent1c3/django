from django.test import SimpleTestCase

from ..utils import setup


class BuiltinsTests(SimpleTestCase):
    @setup({"builtins01": "{{ True }}"})
    def test_builtins01(self):
        """

        Tests the rendering of built-in variables in the template engine.

        This test case verifies that the template engine correctly evaluates and renders
        built-in variables, such as boolean values, in a template. It checks that the
        rendered output matches the expected result.

        :param self: The test instance.
        :raises AssertionError: If the rendered output does not match the expected result.

        """
        output = self.engine.render_to_string("builtins01")
        self.assertEqual(output, "True")

    @setup({"builtins02": "{{ False }}"})
    def test_builtins02(self):
        output = self.engine.render_to_string("builtins02")
        self.assertEqual(output, "False")

    @setup({"builtins03": "{{ None }}"})
    def test_builtins03(self):
        output = self.engine.render_to_string("builtins03")
        self.assertEqual(output, "None")
