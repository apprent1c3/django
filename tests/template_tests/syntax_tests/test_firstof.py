from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class FirstOfTagTests(SimpleTestCase):
    @setup({"firstof01": "{% firstof a b c %}"})
    def test_firstof01(self):
        """
        Tests the behavior of the 'firstof' template tag when all provided values are falsy, 
        verifying that it returns an empty string.
        """
        output = self.engine.render_to_string("firstof01", {"a": 0, "c": 0, "b": 0})
        self.assertEqual(output, "")

    @setup({"firstof02": "{% firstof a b c %}"})
    def test_firstof02(self):
        output = self.engine.render_to_string("firstof02", {"a": 1, "c": 0, "b": 0})
        self.assertEqual(output, "1")

    @setup({"firstof03": "{% firstof a b c %}"})
    def test_firstof03(self):
        output = self.engine.render_to_string("firstof03", {"a": 0, "c": 0, "b": 2})
        self.assertEqual(output, "2")

    @setup({"firstof04": "{% firstof a b c %}"})
    def test_firstof04(self):
        """

        Tests the firstof template tag.

        The firstof tag is used to output the first 'truthy' value of several variables.
        A 'truthy' value in this context means a value that would evaluate to True in a boolean context.

        In this test case, it checks if the firstof tag correctly returns the first non-zero or non-empty value from the provided variables.

        """
        output = self.engine.render_to_string("firstof04", {"a": 0, "c": 3, "b": 0})
        self.assertEqual(output, "3")

    @setup({"firstof05": "{% firstof a b c %}"})
    def test_firstof05(self):
        output = self.engine.render_to_string("firstof05", {"a": 1, "c": 3, "b": 2})
        self.assertEqual(output, "1")

    @setup({"firstof06": "{% firstof a b c %}"})
    def test_firstof06(self):
        output = self.engine.render_to_string("firstof06", {"c": 3, "b": 0})
        self.assertEqual(output, "3")

    @setup({"firstof07": '{% firstof a b "c" %}'})
    def test_firstof07(self):
        """

        Tests the behavior of the 'firstof' template tag when the first argument is falsy.

        This function verifies that the 'firstof' tag returns the first truthy value it encounters.
        If all arguments are falsy, it returns the last argument.

        In this specific test case, 'a' is 0 (which is considered falsy), so the function checks that the output is 'c', which is the last argument.

        """
        output = self.engine.render_to_string("firstof07", {"a": 0})
        self.assertEqual(output, "c")

    @setup({"firstof08": '{% firstof a b "c and d" %}'})
    def test_firstof08(self):
        output = self.engine.render_to_string("firstof08", {"a": 0, "b": 0})
        self.assertEqual(output, "c and d")

    @setup({"firstof09": "{% firstof %}"})
    def test_firstof09(self):
        """
        Tests that using the \"firstof\" template tag without any arguments raises a TemplateSyntaxError. This check ensures that the template engine correctly handles invalid usage of the \"firstof\" tag and provides a meaningful error message instead of failing silently or producing unexpected results.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("firstof09")

    @setup({"firstof10": "{% firstof a %}"})
    def test_firstof10(self):
        """
        Test the functionality of the 'firstof' template tag.

        This test checks that the 'firstof' tag correctly outputs the first
        truthy value from the provided arguments and that HTML special
        characters are properly escaped. It verifies that if the first
        argument is a string containing HTML special characters, they are
        correctly replaced with their corresponding HTML entities.
        """
        output = self.engine.render_to_string("firstof10", {"a": "<"})
        self.assertEqual(output, "&lt;")

    @setup({"firstof11": "{% firstof a b %}"})
    def test_firstof11(self):
        """
        Tests the functionality of the firstof template tag to select the first non-empty or non-false value from a list of arguments and escape special characters if necessary.
        """
        output = self.engine.render_to_string("firstof11", {"a": "<", "b": ">"})
        self.assertEqual(output, "&lt;")

    @setup({"firstof12": "{% firstof a b %}"})
    def test_firstof12(self):
        output = self.engine.render_to_string("firstof12", {"a": "", "b": ">"})
        self.assertEqual(output, "&gt;")

    @setup({"firstof13": "{% autoescape off %}{% firstof a %}{% endautoescape %}"})
    def test_firstof13(self):
        """
        Tests the 'firstof' template tag to ensure it correctly outputs the first non-empty value from a list of variables, while also verifying that auto-escaping is properly disabled when rendering the template.
        """
        output = self.engine.render_to_string("firstof13", {"a": "<"})
        self.assertEqual(output, "<")

    @setup({"firstof14": "{% firstof a|safe b %}"})
    def test_firstof14(self):
        """
        Tests the firstof template tag when the first value contains HTML characters and the safe filter is applied, ensuring that the output is rendered correctly without escaping.
        """
        output = self.engine.render_to_string("firstof14", {"a": "<"})
        self.assertEqual(output, "<")

    @setup({"firstof15": "{% firstof a b c as myvar %}"})
    def test_firstof15(self):
        ctx = {"a": 0, "b": 2, "c": 3}
        output = self.engine.render_to_string("firstof15", ctx)
        self.assertEqual(ctx["myvar"], "2")
        self.assertEqual(output, "")

    @setup({"firstof16": "{% firstof a b c as myvar %}"})
    def test_all_false_arguments_asvar(self):
        """
        Tests the 'firstof' template tag when all arguments are falsey values, with the output assigned to a context variable.

         This function checks the behavior of the 'firstof' template tag with multiple falsey arguments (in this case, 0) and ensures that 
         the assigned context variable ('myvar') and the rendered template output are both empty strings, as expected when all arguments are falsey.
        """
        ctx = {"a": 0, "b": 0, "c": 0}
        output = self.engine.render_to_string("firstof16", ctx)
        self.assertEqual(ctx["myvar"], "")
        self.assertEqual(output, "")
