from django.test import SimpleTestCase

from ..utils import setup


class BuiltinsTests(SimpleTestCase):
    @setup({"builtins01": "{{ True }}"})
    def test_builtins01(self):
        """

        Tests the rendering of a template with a built-in expression that evaluates to True.

        Verifies that the engine correctly renders the template and returns the expected output.

        """
        output = self.engine.render_to_string("builtins01")
        self.assertEqual(output, "True")

    @setup({"builtins02": "{{ False }}"})
    def test_builtins02(self):
        output = self.engine.render_to_string("builtins02")
        self.assertEqual(output, "False")

    @setup({"builtins03": "{{ None }}"})
    def test_builtins03(self):
        """
        .. method:: test_builtins03()

           Tests the rendering of the builtins03 template under specific setup conditions.

           Verifies that when the engine renders the builtins03 template, the output string is 'None', as expected under the given setup where builtins03 is {{ None }}. This ensures the proper handling of the None value within the template rendering process.
        """
        output = self.engine.render_to_string("builtins03")
        self.assertEqual(output, "None")
