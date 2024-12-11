from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class FirstOfTagTests(SimpleTestCase):
    @setup({"firstof01": "{% firstof a b c %}"})
    def test_firstof01(self):
        """
        Tests the firstof template tag when all variables are falsy.

        This test case verifies that when all variables passed to the firstof tag are considered falsy in a Python context (e.g., zero, empty string, etc.),
        the resulting output of the tag is an empty string, indicating that none of the provided values were considered truthy by the tag.

        The expected behavior is that since all variables 'a', 'b', and 'c' are set to 0 (a falsy value), the rendered template should not output any of these values,
        resulting in an empty string as the final output, confirming the tag's behavior in handling falsy values as input.
        """
        output = self.engine.render_to_string("firstof01", {"a": 0, "c": 0, "b": 0})
        self.assertEqual(output, "")

    @setup({"firstof02": "{% firstof a b c %}"})
    def test_firstof02(self):
        output = self.engine.render_to_string("firstof02", {"a": 1, "c": 0, "b": 0})
        self.assertEqual(output, "1")

    @setup({"firstof03": "{% firstof a b c %}"})
    def test_firstof03(self):
        """

        Test the 'firstof' template tag functionality with multiple values.

        This function evaluates the 'firstof' tag with three variables (a, b, c) 
        passed to the template engine. The 'firstof' tag returns the first 
        \"truthy\" value it encounters, which in this case is expected to be 2 
        from variable 'b', since 'a' and 'c' are both set to 0 (falsy values).

        The function verifies that the rendered output matches the expected 
        result, ensuring correct behavior of the 'firstof' template tag.

        """
        output = self.engine.render_to_string("firstof03", {"a": 0, "c": 0, "b": 2})
        self.assertEqual(output, "2")

    @setup({"firstof04": "{% firstof a b c %}"})
    def test_firstof04(self):
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
        output = self.engine.render_to_string("firstof07", {"a": 0})
        self.assertEqual(output, "c")

    @setup({"firstof08": '{% firstof a b "c and d" %}'})
    def test_firstof08(self):
        output = self.engine.render_to_string("firstof08", {"a": 0, "b": 0})
        self.assertEqual(output, "c and d")

    @setup({"firstof09": "{% firstof %}"})
    def test_firstof09(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("firstof09")

    @setup({"firstof10": "{% firstof a %}"})
    def test_firstof10(self):
        output = self.engine.render_to_string("firstof10", {"a": "<"})
        self.assertEqual(output, "&lt;")

    @setup({"firstof11": "{% firstof a b %}"})
    def test_firstof11(self):
        output = self.engine.render_to_string("firstof11", {"a": "<", "b": ">"})
        self.assertEqual(output, "&lt;")

    @setup({"firstof12": "{% firstof a b %}"})
    def test_firstof12(self):
        output = self.engine.render_to_string("firstof12", {"a": "", "b": ">"})
        self.assertEqual(output, "&gt;")

    @setup({"firstof13": "{% autoescape off %}{% firstof a %}{% endautoescape %}"})
    def test_firstof13(self):
        output = self.engine.render_to_string("firstof13", {"a": "<"})
        self.assertEqual(output, "<")

    @setup({"firstof14": "{% firstof a|safe b %}"})
    def test_firstof14(self):
        output = self.engine.render_to_string("firstof14", {"a": "<"})
        self.assertEqual(output, "<")

    @setup({"firstof15": "{% firstof a b c as myvar %}"})
    def test_firstof15(self):
        """

        Test the 'firstof' template tag to assign the first true value from a list of variables.

        This function checks if the 'firstof' tag correctly assigns the first variable with a truthy value to the given variable.
        In this case, it verifies that when 'a' is falsy and 'b' is truthy, 'b' is assigned to 'myvar'.
        The function also checks that the rendered template output is empty, as expected when using the 'as' keyword with 'firstof'.

        """
        ctx = {"a": 0, "b": 2, "c": 3}
        output = self.engine.render_to_string("firstof15", ctx)
        self.assertEqual(ctx["myvar"], "2")
        self.assertEqual(output, "")

    @setup({"firstof16": "{% firstof a b c as myvar %}"})
    def test_all_false_arguments_asvar(self):
        """
        Tests the firstof template tag with all false arguments when used with the 'as' variable syntax.

            The function verifies that when all arguments passed to the firstof tag are false, 
            the assigned variable is set to an empty string, and the rendered output is also empty. 
            It creates a context with all arguments set to false, renders the template, 
            and then asserts that both the assigned variable 'myvar' and the template output are empty strings.
        """
        ctx = {"a": 0, "b": 0, "c": 0}
        output = self.engine.render_to_string("firstof16", ctx)
        self.assertEqual(ctx["myvar"], "")
        self.assertEqual(output, "")
