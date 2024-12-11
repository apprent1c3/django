from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class FirstOfTagTests(SimpleTestCase):
    @setup({"firstof01": "{% firstof a b c %}"})
    def test_firstof01(self):
        """
        Tests that the firstof template tag returns an empty string when all provided values are falsy.
        """
        output = self.engine.render_to_string("firstof01", {"a": 0, "c": 0, "b": 0})
        self.assertEqual(output, "")

    @setup({"firstof02": "{% firstof a b c %}"})
    def test_firstof02(self):
        """

        Tests the functionality of the 'firstof' template tag.

        The 'firstof' tag returns the first variable that is \"truthy\" from the given
        list of variables. A value is considered \"truthy\" if it is not empty, not
        zero, and not False. This test case checks if the tag correctly returns the
        first truthy value from the provided variables.

        The expected behavior is that the function should return the first variable
        that has a truthy value. In this case, the function should return '1',
        since 'a' has a value of 1, which is the first truthy value in the list.

        """
        output = self.engine.render_to_string("firstof02", {"a": 1, "c": 0, "b": 0})
        self.assertEqual(output, "1")

    @setup({"firstof03": "{% firstof a b c %}"})
    def test_firstof03(self):
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
        """
        Tests the firstof template tag functionality when given a falsy value.

        This test case verifies that when the first argument to the firstof tag is falsy,
        the tag returns the first subsequent truthy value it encounters. In this scenario,
        since 'a' is 0 (a falsy value), the tag should return 'c', which is the first truthy value.
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
        Tests the template engine's handling of the firstof tag when it lacks required arguments, ensuring that a TemplateSyntaxError is raised as expected.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("firstof09")

    @setup({"firstof10": "{% firstof a %}"})
    def test_firstof10(self):
        """

        Tests the 'firstof' template tag to ensure it correctly escapes HTML special characters.

        The function verifies that the 'firstof' tag renders the provided input string while applying necessary HTML escaping to prevent potential security vulnerabilities.

        It checks if the rendered output correctly replaces special characters with their corresponding HTML entities, such as replacing '<' with '&lt;'.

        """
        output = self.engine.render_to_string("firstof10", {"a": "<"})
        self.assertEqual(output, "&lt;")

    @setup({"firstof11": "{% firstof a b %}"})
    def test_firstof11(self):
        """

        Tests the 'firstof' template tag with two arguments.

        The 'firstof' tag returns the first argument that is \"truthy\".

        In this case, both arguments 'a' and 'b' are strings, which are considered truthy in a template context.
        However, 'a' is '<', which is an HTML special character that gets escaped to '&lt;'.
        The test verifies that the output of the 'firstof' tag is the escaped version of 'a', which is '&lt;'.

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
        Tests the firstof template tag with an input containing special characters.

        This test case ensures that the firstof tag correctly handles HTML special characters 
        and does not automatically escape them, returning the original input value.
        """
        output = self.engine.render_to_string("firstof13", {"a": "<"})
        self.assertEqual(output, "<")

    @setup({"firstof14": "{% firstof a|safe b %}"})
    def test_firstof14(self):
        output = self.engine.render_to_string("firstof14", {"a": "<"})
        self.assertEqual(output, "<")

    @setup({"firstof15": "{% firstof a b c as myvar %}"})
    def test_firstof15(self):
        """

        Tests the firstof template tag.

        The firstof tag returns the first \"truthy\" value from a list of variables.
        This function checks if the firstof tag correctly sets the variable to the first true value 
        and returns an empty string when no value is provided after the 'as' keyword.

        It verifies the functionality by rendering a template with the firstof tag and 
        asserting that the assigned variable has the expected value.

        """
        ctx = {"a": 0, "b": 2, "c": 3}
        output = self.engine.render_to_string("firstof15", ctx)
        self.assertEqual(ctx["myvar"], "2")
        self.assertEqual(output, "")

    @setup({"firstof16": "{% firstof a b c as myvar %}"})
    def test_all_false_arguments_asvar(self):
        """
        Test the functionality of the 'firstof' template tag with all false arguments when used with the 'as' variable syntax.

        This checks the case where multiple expressions are evaluated as false, and the result is stored in a variable. 

        The test asserts that when all provided arguments evaluate as false, the variable should be set to an empty string and the rendered template should also be empty.
        """
        ctx = {"a": 0, "b": 0, "c": 0}
        output = self.engine.render_to_string("firstof16", ctx)
        self.assertEqual(ctx["myvar"], "")
        self.assertEqual(output, "")
