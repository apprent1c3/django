from django.test import SimpleTestCase

from ..utils import setup


class BuiltinsTests(SimpleTestCase):
    @setup({"builtins01": "{{ True }}"})
    def test_builtins01(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("builtins01")
        self.assertEqual(output, "True")

    @setup({"builtins02": "{{ False }}"})
    def test_builtins02(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("builtins02")
        self.assertEqual(output, "False")

    @setup({"builtins03": "{{ None }}"})
    def test_builtins03(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("builtins03")
        self.assertEqual(output, "None")
