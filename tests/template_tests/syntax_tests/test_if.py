from django.template import TemplateSyntaxError
from django.template.defaulttags import IfNode
from django.test import SimpleTestCase

from ..utils import TestObj, setup


class IfTagTests(SimpleTestCase):
    @setup({"if-tag01": "{% if foo %}yes{% else %}no{% endif %}"})
    def test_if_tag01(self):
        output = self.engine.render_to_string("if-tag01", {"foo": True})
        self.assertEqual(output, "yes")

    @setup({"if-tag02": "{% if foo %}yes{% else %}no{% endif %}"})
    def test_if_tag02(self):
        """

        Tests the if-tag02 template tag by verifying its conditional rendering behavior.
        The tag is expected to render 'yes' when the given condition is true and 'no' when it's false.
        This test case specifically checks the 'false' condition scenario, ensuring the output matches the expected result.

        """
        output = self.engine.render_to_string("if-tag02", {"foo": False})
        self.assertEqual(output, "no")

    @setup({"if-tag03": "{% if foo %}yes{% else %}no{% endif %}"})
    def test_if_tag03(self):
        """
        verdadЦеHere is the documentation string for the given function:
        Checks the functionality of the if-tag in the templating engine.
        Tests that a conditional template tag correctly renders to the expected output when the condition is False.
        """
        output = self.engine.render_to_string("if-tag03")
        self.assertEqual(output, "no")

    @setup({"if-tag04": "{% if foo %}foo{% elif bar %}bar{% endif %}"})
    def test_if_tag04(self):
        """
        Tests the rendering of an if-elif-else tag in a template.

        The function verifies that the template engine correctly handles conditional
        statements, rendering the first true condition's content.

        :raises AssertionError: if the rendered output does not match the expected result
        """
        output = self.engine.render_to_string("if-tag04", {"foo": True})
        self.assertEqual(output, "foo")

    @setup({"if-tag05": "{% if foo %}foo{% elif bar %}bar{% endif %}"})
    def test_if_tag05(self):
        """
        Tests the rendering of an if-elif template tag.

        The function checks if the template engine correctly renders the if-elif tag
        based on the provided context. It expects the engine to output 'bar' when
        'bar' is True and 'foo' is not defined, demonstrating the elif condition
        in the if tag.

        :returns: None
        :raises: AssertionError if the output does not match the expected result
        """
        output = self.engine.render_to_string("if-tag05", {"bar": True})
        self.assertEqual(output, "bar")

    @setup({"if-tag06": "{% if foo %}foo{% elif bar %}bar{% endif %}"})
    def test_if_tag06(self):
        """
        Tests the rendering of a template with a conditional if/elif statement when both conditions are false.

        The function verifies that the template engine correctly handles the if/elif/endif syntax when neither the if nor elif conditions are met, resulting in an empty output string.
        """
        output = self.engine.render_to_string("if-tag06")
        self.assertEqual(output, "")

    @setup({"if-tag07": "{% if foo %}foo{% elif bar %}bar{% else %}nothing{% endif %}"})
    def test_if_tag07(self):
        output = self.engine.render_to_string("if-tag07", {"foo": True})
        self.assertEqual(output, "foo")

    @setup({"if-tag08": "{% if foo %}foo{% elif bar %}bar{% else %}nothing{% endif %}"})
    def test_if_tag08(self):
        output = self.engine.render_to_string("if-tag08", {"bar": True})
        self.assertEqual(output, "bar")

    @setup({"if-tag09": "{% if foo %}foo{% elif bar %}bar{% else %}nothing{% endif %}"})
    def test_if_tag09(self):
        output = self.engine.render_to_string("if-tag09")
        self.assertEqual(output, "nothing")

    @setup(
        {
            "if-tag10": (
                "{% if foo %}foo{% elif bar %}bar{% elif baz %}baz{% else %}nothing"
                "{% endif %}"
            )
        }
    )
    def test_if_tag10(self):
        """

        Tests the functionality of the if-else conditional tag in the templating engine.

        This test case checks if the engine correctly evaluates the if-else condition and 
        renders the corresponding value when the first condition is true.

        It verifies that the 'foo' value is rendered when 'foo' is True, 
        regardless of the values of 'bar' and 'baz'.

        """
        output = self.engine.render_to_string("if-tag10", {"foo": True})
        self.assertEqual(output, "foo")

    @setup(
        {
            "if-tag11": (
                "{% if foo %}foo{% elif bar %}bar{% elif baz %}baz{% else %}nothing"
                "{% endif %}"
            )
        }
    )
    def test_if_tag11(self):
        output = self.engine.render_to_string("if-tag11", {"bar": True})
        self.assertEqual(output, "bar")

    @setup(
        {
            "if-tag12": (
                "{% if foo %}foo{% elif bar %}bar{% elif baz %}baz{% else %}nothing"
                "{% endif %}"
            )
        }
    )
    def test_if_tag12(self):
        output = self.engine.render_to_string("if-tag12", {"baz": True})
        self.assertEqual(output, "baz")

    @setup(
        {
            "if-tag13": (
                "{% if foo %}foo{% elif bar %}bar{% elif baz %}baz{% else %}nothing"
                "{% endif %}"
            )
        }
    )
    def test_if_tag13(self):
        """

        Tests the rendering of an if-elif-else template tag with multiple conditions.

        This test case verifies that the template engine correctly evaluates the 
        conditional statements and returns the expected output when none of the 
        initial conditions are met.

        """
        output = self.engine.render_to_string("if-tag13")
        self.assertEqual(output, "nothing")

    # Filters
    @setup({"if-tag-filter01": "{% if foo|length == 5 %}yes{% else %}no{% endif %}"})
    def test_if_tag_filter01(self):
        output = self.engine.render_to_string("if-tag-filter01", {"foo": "abcde"})
        self.assertEqual(output, "yes")

    @setup({"if-tag-filter02": "{% if foo|upper == 'ABC' %}yes{% else %}no{% endif %}"})
    def test_if_tag_filter02(self):
        output = self.engine.render_to_string("if-tag-filter02")
        self.assertEqual(output, "no")

    # Equality
    @setup({"if-tag-eq01": "{% if foo == bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_eq01(self):
        """

        Tests the functionality of the if-tag-eq01 template tag.

        This test case checks if the if-tag-eq01 template tag correctly evaluates
        a conditional statement and outputs the expected result. It verifies that when
        the condition 'foo == bar' is met, the template renders 'yes', and otherwise
        renders 'no'.

        The purpose of this test is to ensure that the template engine correctly
        interprets the conditional statement and produces the desired output.

        """
        output = self.engine.render_to_string("if-tag-eq01")
        self.assertEqual(output, "yes")

    @setup({"if-tag-eq02": "{% if foo == bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_eq02(self):
        """

        Tests the rendering of an if-tag-eq template tag with non-matching values.

        This test case verifies that the if-tag-eq template tag correctly evaluates
        to False when the two values are not equal, resulting in the 'else' branch
        being rendered.

        The expected output is 'no', indicating that the condition 'foo == bar' was
        not met.

        """
        output = self.engine.render_to_string("if-tag-eq02", {"foo": 1})
        self.assertEqual(output, "no")

    @setup({"if-tag-eq03": "{% if foo == bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_eq03(self):
        output = self.engine.render_to_string("if-tag-eq03", {"foo": 1, "bar": 1})
        self.assertEqual(output, "yes")

    @setup({"if-tag-eq04": "{% if foo == bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_eq04(self):
        """

        Tests the functionality of the if-tag-eq directive when comparing two variables.

        This test case evaluates a conditional statement with the if-tag-eq syntax, 
        verifying that the correct output is rendered when the variables are not equal.
        The expected output is 'no' when the variables 'foo' and 'bar' have different values.

        """
        output = self.engine.render_to_string("if-tag-eq04", {"foo": 1, "bar": 2})
        self.assertEqual(output, "no")

    @setup({"if-tag-eq05": "{% if foo == '' %}yes{% else %}no{% endif %}"})
    def test_if_tag_eq05(self):
        """
        Test the if-tag-eq template tag with an empty string comparison.

        The test checks the rendering of a template containing the if-tag-eq template tag when the variable being compared is an empty string.

        :returns: None
        :raises: AssertionError if the rendered template output does not match the expected result.
        """
        output = self.engine.render_to_string("if-tag-eq05")
        self.assertEqual(output, "no")

    # Inequality
    @setup({"if-tag-noteq01": "{% if foo != bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_noteq01(self):
        output = self.engine.render_to_string("if-tag-noteq01")
        self.assertEqual(output, "no")

    @setup({"if-tag-noteq02": "{% if foo != bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_noteq02(self):
        """

        Tests the functionality of the if tag with a 'noteq' condition.

        This function checks if the engine correctly renders a template containing an if tag
        with a 'noteq' (not equal) condition. It verifies that the condition is evaluated as
        expected and the correct output is generated.

        The test case covers a scenario where the 'foo' variable is not equal to 'bar',
        resulting in the string 'yes' being rendered.

        :raises: AssertionError if the rendered output does not match the expected result.

        """
        output = self.engine.render_to_string("if-tag-noteq02", {"foo": 1})
        self.assertEqual(output, "yes")

    @setup({"if-tag-noteq03": "{% if foo != bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_noteq03(self):
        output = self.engine.render_to_string("if-tag-noteq03", {"foo": 1, "bar": 1})
        self.assertEqual(output, "no")

    @setup({"if-tag-noteq04": "{% if foo != bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_noteq04(self):
        output = self.engine.render_to_string("if-tag-noteq04", {"foo": 1, "bar": 2})
        self.assertEqual(output, "yes")

    @setup({"if-tag-noteq05": '{% if foo != "" %}yes{% else %}no{% endif %}'})
    def test_if_tag_noteq05(self):
        """

        Tests the rendering of an if-tag with 'noteq' operator when the conditional variable is not empty.

        Verifies that the if-tag correctly evaluates the 'noteq' condition when the variable 'foo' has a non-empty value, 
        resulting in the expected output 'yes'. 

        """
        output = self.engine.render_to_string("if-tag-noteq05")
        self.assertEqual(output, "yes")

    # Comparison
    @setup({"if-tag-gt-01": "{% if 2 > 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_gt_01(self):
        """
        Tests the functionality of the if-tag greater than operator in template rendering.

            The test case checks if a conditional statement with a greater than comparison returns the expected outcome.

            :return: None
            :rtype: None
            :raises: AssertionError: If the rendered output does not match the expected result.
        """
        output = self.engine.render_to_string("if-tag-gt-01")
        self.assertEqual(output, "yes")

    @setup({"if-tag-gt-02": "{% if 1 > 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_gt_02(self):
        output = self.engine.render_to_string("if-tag-gt-02")
        self.assertEqual(output, "no")

    @setup({"if-tag-gte-01": "{% if 1 >= 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_gte_01(self):
        """

        Tests the rendering of the if-tag with greater than or equal to (gte) condition.

        This test case ensures that the templating engine correctly evaluates an if statement 
        with a condition specifying a greater than or equal to comparison. 

        The expected output is 'yes' when the condition (1 >= 1) is met.

        """
        output = self.engine.render_to_string("if-tag-gte-01")
        self.assertEqual(output, "yes")

    @setup({"if-tag-gte-02": "{% if 1 >= 2 %}yes{% else %}no{% endif %}"})
    def test_if_tag_gte_02(self):
        """

        Tests the 'if' template tag with a greater-than-or-equal comparison ('gte') where 
        the condition is False (1 >= 2). 

        Verifies that the template renders to the expected output when the condition is not met.

        """
        output = self.engine.render_to_string("if-tag-gte-02")
        self.assertEqual(output, "no")

    @setup({"if-tag-lt-01": "{% if 1 < 2 %}yes{% else %}no{% endif %}"})
    def test_if_tag_lt_01(self):
        """
        Checks the functionality of the if-tag with less-than condition.

        This test case verifies that the if-tag correctly evaluates a less-than comparison.
        It renders a template containing an if statement with a less-than condition and 
        then checks if the output matches the expected result, which is 'yes' when the 
        condition is true and 'no' when it's false. The purpose of this test is to ensure 
        that the template engine handles this type of conditional statement correctly.
        """
        output = self.engine.render_to_string("if-tag-lt-01")
        self.assertEqual(output, "yes")

    @setup({"if-tag-lt-02": "{% if 1 < 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_lt_02(self):
        output = self.engine.render_to_string("if-tag-lt-02")
        self.assertEqual(output, "no")

    @setup({"if-tag-lte-01": "{% if 1 <= 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_lte_01(self):
        """
        Tests the if-tag with less-than-or-equal condition in the templating engine.

        Verifies that the templating engine correctly renders an if-tag when the condition is true,
        and that the output matches the expected result.

        The test checks if the rendering of the if-tag with a less-than-or-equal condition
        yields the correct output string, which is 'yes' when the condition 1 <= 1 is met.

        """
        output = self.engine.render_to_string("if-tag-lte-01")
        self.assertEqual(output, "yes")

    @setup({"if-tag-lte-02": "{% if 2 <= 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_lte_02(self):
        """
        Tests the \"if\" template tag with a less than or equal (lte) condition, verifying it correctly evaluates an expression and renders the appropriate template section.

        The test case checks a conditional statement with the expression \"2 <= 1\", which is false, and asserts that the rendered output is \"no\" as expected.
        """
        output = self.engine.render_to_string("if-tag-lte-02")
        self.assertEqual(output, "no")

    # Contains
    @setup({"if-tag-in-01": "{% if 1 in x %}yes{% else %}no{% endif %}"})
    def test_if_tag_in_01(self):
        """
        Tests the \"if in\" tag functionality within the templating engine, verifying that the condition is correctly evaluated when the value is present in a list.
        """
        output = self.engine.render_to_string("if-tag-in-01", {"x": [1]})
        self.assertEqual(output, "yes")

    @setup({"if-tag-in-02": "{% if 2 in x %}yes{% else %}no{% endif %}"})
    def test_if_tag_in_02(self):
        """
        Tests the if tag to check if an element is present in a list.

        This test case verifies that the template engine correctly renders the if tag
        when the list does not contain the specified element. The tag should return 'no'
        if the element is not found in the list.

        :returns: None
        :raises: AssertionError if the output does not match the expected result
        """
        output = self.engine.render_to_string("if-tag-in-02", {"x": [1]})
        self.assertEqual(output, "no")

    @setup({"if-tag-not-in-01": "{% if 1 not in x %}yes{% else %}no{% endif %}"})
    def test_if_tag_not_in_01(self):
        output = self.engine.render_to_string("if-tag-not-in-01", {"x": [1]})
        self.assertEqual(output, "no")

    @setup({"if-tag-not-in-02": "{% if 2 not in x %}yes{% else %}no{% endif %}"})
    def test_if_tag_not_in_02(self):
        """
        Tests the functionality of the 'if not in' conditional statement within a template, 
        specifically checking the condition when the value 2 is not present in a given list.
        This function verifies that the template correctly renders 'yes' when the condition is met.
        """
        output = self.engine.render_to_string("if-tag-not-in-02", {"x": [1]})
        self.assertEqual(output, "yes")

    # AND
    @setup({"if-tag-and01": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and01(self):
        """
        Tests the functionality of the 'if' template tag with 'and' operator.

         The function checks if the template engine correctly renders the conditional 
         statement when both conditions are true. It passes 'foo' and 'bar' as context 
         variables to the template and asserts that the output is 'yes' as expected.
        """
        output = self.engine.render_to_string(
            "if-tag-and01", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-and02": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and02(self):
        """

        Tests the 'if' tag with the 'and' operator, verifying that it correctly renders the 'else' block when one of the conditions is False.

        The test case checks that the template engine correctly evaluates the 'and' condition and returns the expected output when one of the variables is set to False.

        """
        output = self.engine.render_to_string(
            "if-tag-and02", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-and03": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and03(self):
        output = self.engine.render_to_string(
            "if-tag-and03", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-and04": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and04(self):
        """
        Tests the functionality of the if-tag with 'and' condition in the templating engine.
        The test checks if the engine renders 'no' when both conditional variables are set to False, 
        verifying that the templating engine correctly handles the boolean 'and' operation.
        """
        output = self.engine.render_to_string(
            "if-tag-and04", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-and05": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and05(self):
        """

        Tests the if tag with 'and' condition when the first variable is False.

        This test case verifies that the if tag correctly evaluates the 'and' condition 
        when the first variable in the condition is False. It checks that the engine 
        renders the appropriate output based on the condition.

         Args:
             self: The test instance

         Returns:
             None

        """
        output = self.engine.render_to_string("if-tag-and05", {"foo": False})
        self.assertEqual(output, "no")

    @setup({"if-tag-and06": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and06(self):
        output = self.engine.render_to_string("if-tag-and06", {"bar": False})
        self.assertEqual(output, "no")

    @setup({"if-tag-and07": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and07(self):
        """

        Test the if template tag with 'and' operator when one condition is False.

        This test case verifies that the if tag correctly evaluates the 'and' operator
        when one of the conditions is False, resulting in the 'else' clause being rendered.

        :raises AssertionError: if the output does not match the expected result.

        """
        output = self.engine.render_to_string("if-tag-and07", {"foo": True})
        self.assertEqual(output, "no")

    @setup({"if-tag-and08": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and08(self):
        """
        Tests the render_to_string method of the template engine when using the 'if' tag with the 'and' operator.
        The function verifies that if one of the conditions in the 'and' operator is False, the 'if' tag renders the 'else' block.
        """
        output = self.engine.render_to_string("if-tag-and08", {"bar": True})
        self.assertEqual(output, "no")

    # OR
    @setup({"if-tag-or01": "{% if foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_or01(self):
        """
        Tests the functionality of the 'if' tag with 'or' conditional statement in templating engine.

            Verifies that the 'if' tag correctly evaluates the 'or' condition and renders the corresponding output.
            The test case checks if the engine returns 'yes' when both conditions ('foo' and 'bar') are True.

            :return: None
        """
        output = self.engine.render_to_string("if-tag-or01", {"foo": True, "bar": True})
        self.assertEqual(output, "yes")

    @setup({"if-tag-or02": "{% if foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_or02(self):
        """
        Tests the 'if' template tag with 'or' condition.

        This test verifies that the 'if' template tag correctly evaluates an 'or' 
        condition and renders the appropriate block of content. In this case, the 
        tag checks if either 'foo' or 'bar' is true, and renders 'yes' if the 
        condition is met, or 'no' otherwise.

        The test provides a set of input variables, {'foo': True, 'bar': False}, 
        and checks that the rendered output matches the expected result, 'yes'.
        """
        output = self.engine.render_to_string(
            "if-tag-or02", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-or03": "{% if foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_or03(self):
        output = self.engine.render_to_string(
            "if-tag-or03", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-or04": "{% if foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_or04(self):
        """

        Tests the 'if' tag in a template engine to verify its behavior when both conditions in an 'or' statement are False.

        The function evaluates a template that contains an 'if' tag with an 'or' condition, rendering it with a dictionary where both 'foo' and 'bar' are set to False. It then asserts that the rendered output matches the expected result when both conditions are not met.

        This test case ensures the correct functioning of the 'if' tag in logical operations, specifically when no conditions are true.

        """
        output = self.engine.render_to_string(
            "if-tag-or04", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-or05": "{% if foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_or05(self):
        output = self.engine.render_to_string("if-tag-or05", {"foo": False})
        self.assertEqual(output, "no")

    @setup({"if-tag-or06": "{% if foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_or06(self):
        """
        Tests the conditional 'if' tag with an 'or' operator, 
        evaluating the template rendering when one of the conditional 
        variables is False. Verifies that the rendered output is 'no' 
        when the 'bar' variable is set to False, regardless of the 'foo' variable.
        """
        output = self.engine.render_to_string("if-tag-or06", {"bar": False})
        self.assertEqual(output, "no")

    @setup({"if-tag-or07": "{% if foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_or07(self):
        """
        Checks the functionality of the if tag with the 'or' operator in the templating engine, verifying that the condition evaluates to true when at least one of the conditions is met, and returns the expected output string.
        """
        output = self.engine.render_to_string("if-tag-or07", {"foo": True})
        self.assertEqual(output, "yes")

    @setup({"if-tag-or08": "{% if foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_or08(self):
        """
        Tests the functionality of the if-tag with 'or' condition in a template.

        This test case verifies that the if-tag correctly evaluates an 'or' condition and 
        renders the template accordingly. The condition '{% if foo or bar %}' is evaluated 
        to true if either 'foo' or 'bar' (or both) are true, and the string 'yes' is 
        rendered in the output. If neither 'foo' nor 'bar' are true, the string 'no' is 
        rendered instead.

        In this specific test, the template is rendered with 'bar' set to True, and the 
        output is asserted to be 'yes', verifying that the 'or' condition is correctly 
        evaluated.
        """
        output = self.engine.render_to_string("if-tag-or08", {"bar": True})
        self.assertEqual(output, "yes")

    @setup({"if-tag-or09": "{% if foo or bar or baz %}yes{% else %}no{% endif %}"})
    def test_if_tag_or09(self):
        """
        multiple ORs
        """
        output = self.engine.render_to_string("if-tag-or09", {"baz": True})
        self.assertEqual(output, "yes")

    # NOT
    @setup({"if-tag-not01": "{% if not foo %}no{% else %}yes{% endif %}"})
    def test_if_tag_not01(self):
        output = self.engine.render_to_string("if-tag-not01", {"foo": True})
        self.assertEqual(output, "yes")

    @setup({"if-tag-not02": "{% if not not foo %}no{% else %}yes{% endif %}"})
    def test_if_tag_not02(self):
        output = self.engine.render_to_string("if-tag-not02", {"foo": True})
        self.assertEqual(output, "no")

    @setup({"if-tag-not06": "{% if foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not06(self):
        """
        Tests the rendering of an if-tag with a 'not' condition.

        This test case checks that the if-tag correctly handles a condition where the first variable is true and the second variable is also true, thus the 'not' condition makes the whole expression false.

        The expected output of the rendered template is 'no'.
        """
        output = self.engine.render_to_string("if-tag-not06")
        self.assertEqual(output, "no")

    @setup({"if-tag-not07": "{% if foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not07(self):
        output = self.engine.render_to_string(
            "if-tag-not07", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not08": "{% if foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not08(self):
        output = self.engine.render_to_string(
            "if-tag-not08", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not09": "{% if foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not09(self):
        """
        Tests the \"if\" template tag with a \"not\" condition, verifying that it correctly evaluates the negation of a boolean expression and renders the appropriate template block. 

        The function checks that when the \"foo\" variable is False and the \"bar\" variable is True, the template renders \"no\", indicating that the condition \"foo and not bar\" is not met.
        """
        output = self.engine.render_to_string(
            "if-tag-not09", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not10": "{% if foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not10(self):
        """

        Tests the if-tag-not10 Jinja template tag, verifying that it correctly handles
        the logical condition when the 'foo' variable is False and the 'bar' variable is False.
        The expected output is 'no' when the condition 'foo and not bar' is not met.

        """
        output = self.engine.render_to_string(
            "if-tag-not10", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not11": "{% if not foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not11(self):
        """

        Tests the 'if-tag-not' template tag with a conditional statement.

        The function checks if the 'if-tag-not' tag correctly evaluates the condition
        'not foo and bar', where 'foo' is True and 'bar' is True, and renders the 
        expected string output.

        Returns:
            None, but asserts that the rendered output is 'no' if the condition is not met.

        """
        output = self.engine.render_to_string("if-tag-not11")
        self.assertEqual(output, "no")

    @setup({"if-tag-not12": "{% if not foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not12(self):
        output = self.engine.render_to_string(
            "if-tag-not12", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not13": "{% if not foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not13(self):
        """
        Tests the rendering of an 'if' template tag with a 'not' condition when the first condition is True and the second condition is False, verifying that the output is 'no'.
        """
        output = self.engine.render_to_string(
            "if-tag-not13", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not14": "{% if not foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not14(self):
        output = self.engine.render_to_string(
            "if-tag-not14", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not15": "{% if not foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not15(self):
        """
        Tests the rendering of a conditional template tag when both the 'not' condition and the main condition are False.
        The 'if-tag-not15' template checks if 'foo' is False and 'bar' is True, 
        then it returns 'yes', otherwise it returns 'no'. 
        This test ensures the correct output is produced when 'foo' is False and 'bar' is False.
        """
        output = self.engine.render_to_string(
            "if-tag-not15", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not16": "{% if foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not16(self):
        """
        Test the functionality of the if-tag-not16 template tag.

        This test case verifies that the if-tag-not16 template tag correctly evaluates a conditional statement 
        and returns 'yes' when the condition foo is True or bar is False. The test renders a template string 
        containing the if-tag-not16 tag and checks if the output matches the expected result 'yes'.
        """
        output = self.engine.render_to_string("if-tag-not16")
        self.assertEqual(output, "yes")

    @setup({"if-tag-not17": "{% if foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not17(self):
        """

        Tests the functionality of the 'if-tag-not' template tag when a condition is true and the negated condition is false.

        This test case evaluates the 'if-tag-not17' template with variables 'foo' and 'bar' both set to True. 
        It verifies that the template correctly renders 'yes' when 'foo' is True, regardless of the value of 'bar'.

        """
        output = self.engine.render_to_string(
            "if-tag-not17", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not18": "{% if foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not18(self):
        """
        Test the 'if-tag-not18' template tag, specifically when the 'foo' condition is True and the 'bar' condition is False.

        This test case evaluates the conditional logic of the template tag, ensuring that when the 'foo' variable is set to True and the 'bar' variable is set to False, the template renders the expected output string 'yes'. The purpose is to verify the correctness of the conditional rendering based on the provided template and variables. 
        """
        output = self.engine.render_to_string(
            "if-tag-not18", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not19": "{% if foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not19(self):
        """
        Tests the rendering of an if-tag with a condition that includes a negated variable.

         The condition checks if either 'foo' is True or 'bar' is False. If the condition is met, 
         the template should render 'yes', otherwise it should render 'no'. This test case 
         specifically checks the rendering when 'foo' is False and 'bar' is True, expecting 
         the output to be 'no'.
        """
        output = self.engine.render_to_string(
            "if-tag-not19", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not20": "{% if foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not20(self):
        """

        Tests the 'if-tag-not20' template tag logic.

        Verifies that when 'foo' is False and 'bar' is False, the template renders as 'yes'.
        This ensures the correct evaluation of the conditional statement when both conditions are not met.

        """
        output = self.engine.render_to_string(
            "if-tag-not20", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not21": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not21(self):
        """
        Tests the 'if-tag-not21' template tag, verifying that the condition 'not foo or bar' evaluates to True, resulting in the string 'yes' being rendered, when the template is processed by the engine.
        """
        output = self.engine.render_to_string("if-tag-not21")
        self.assertEqual(output, "yes")

    @setup({"if-tag-not22": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not22(self):
        """
        Tests the 'if-tag-not' condition in the templating engine.

        This test case evaluates a conditional statement where the 'if' tag checks for a negated condition.
        It verifies that when the condition is met, the expected output is rendered.

        The test scenario involves two boolean variables being evaluated with a logical 'or' condition.
        The expected output is confirmed with an assertion, ensuring the correctness of the templating engine's evaluation.

        """
        output = self.engine.render_to_string(
            "if-tag-not22", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not23": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not23(self):
        """
        Tests the 'if-tag-not23' template tag with conditional logic.

        The function evaluates a template with an if statement that checks 'foo or bar' condition.
        It passes the rendered output against expected result to ensure correct functionality.

        :returns: None
        :raises AssertionError: If the rendered output does not match the expected result.
        """
        output = self.engine.render_to_string(
            "if-tag-not23", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not24": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not24(self):
        """
        Tests the functionality of the 'if-tag-not' template tag with conditional variables.

        This test case verifies that the 'if-tag-not' tag correctly evaluates a conditional
        statement and returns the expected output when the first variable is False and the
        second variable is True. The function checks the rendered output of the template
        against the expected result to confirm the correct functionality of the tag.
        """
        output = self.engine.render_to_string(
            "if-tag-not24", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not25": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not25(self):
        """
        Tests the rendering of the 'if-tag-not25' template, which contains a conditional statement using the 'if' tag with a negation condition.
        The template renders 'yes' if the 'foo' variable is False or the 'bar' variable is True, and 'no' otherwise.
        This test case specifically checks the scenario where both 'foo' and 'bar' are False, verifying that the template correctly renders 'yes' in this situation.
        """
        output = self.engine.render_to_string(
            "if-tag-not25", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not26": "{% if not foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not26(self):
        """
        Test the functionality of the 'if-tag-not' template tag with variables that are both False.

        This test case verifies that when the 'if-tag-not' template tag is used with two variables that are both False, it correctly evaluates the condition and renders the content within the 'if' block.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Raises
        ------
        AssertionError : If the rendered output does not match the expected output 'yes'.
        """
        output = self.engine.render_to_string("if-tag-not26")
        self.assertEqual(output, "yes")

    @setup({"if-tag-not27": "{% if not foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not27(self):
        """
        Tests the rendering of the 'if-tag-not' template tag with two conditions.
        The function checks if the template engine correctly handles the 'if-tag-not' syntax when both conditions are true, 
        verifying that the expected output 'no' is produced.
        """
        output = self.engine.render_to_string(
            "if-tag-not27", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not28": "{% if not foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not28(self):
        output = self.engine.render_to_string(
            "if-tag-not28", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not29": "{% if not foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not29(self):
        output = self.engine.render_to_string(
            "if-tag-not29", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not30": "{% if not foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not30(self):
        """
        Tests the functionality of the 'if' template tag with a 'not' conditional, ensuring it correctly evaluates to True when both conditions are False, and renders the expected output string.
        """
        output = self.engine.render_to_string(
            "if-tag-not30", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not31": "{% if not foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not31(self):
        """
        Tests the rendering of an 'if not' template tag with two conditions.

        This test case verifies that the 'if not' tag in a template correctly evaluates 
        two conditions and renders the corresponding output. It checks that when either 
        of the conditions is false, the tag renders the 'yes' block, and otherwise 
        renders the 'no' block.

        The expected output of this test is 'yes', indicating that the 'if not' tag 
        works as expected in the given scenario.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the rendered output does not match the expected output.
        """
        output = self.engine.render_to_string("if-tag-not31")
        self.assertEqual(output, "yes")

    @setup({"if-tag-not32": "{% if not foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not32(self):
        output = self.engine.render_to_string(
            "if-tag-not32", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not33": "{% if not foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not33(self):
        output = self.engine.render_to_string(
            "if-tag-not33", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not34": "{% if not foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not34(self):
        output = self.engine.render_to_string(
            "if-tag-not34", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not35": "{% if not foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not35(self):
        """
        Tests the not operator in the if tag when both variables are False.

        This test case verifies that the if tag correctly evaluates to True when neither of the variables are truthy, 
        and thus the template returns the string 'yes'. 

        :returns: None
        :raises: AssertionError if the expected output is not 'yes'
        """
        output = self.engine.render_to_string(
            "if-tag-not35", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "yes")

    # Various syntax errors
    @setup({"if-tag-error01": "{% if %}yes{% endif %}"})
    def test_if_tag_error01(self):
        """
        Test a template engine's error handling when encountering an unclosed if tag.

        The function verifies that a :exc:`TemplateSyntaxError` is raised when the template engine attempts to render a template containing an opening if tag without a corresponding closing endif tag.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error01")

    @setup({"if-tag-error02": "{% if foo and %}yes{% else %}no{% endif %}"})
    def test_if_tag_error02(self):
        """
        Tests the behavior of the template engine when encountering a syntax error in an if-tag, specifically when the tag is not properly closed. 

        It verifies that a TemplateSyntaxError is raised when the engine attempts to render a template containing an if-tag with a missing closing parenthesis. This ensures that the engine correctly handles and reports syntax errors in template definitions.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-error02", {"foo": True})

    @setup({"if-tag-error03": "{% if foo or %}yes{% else %}no{% endif %}"})
    def test_if_tag_error03(self):
        """
        Tests the rendering of an if-template tag with a syntax error, verifying that a TemplateSyntaxError is raised when the tag is parsed. The test case checks the handling of incomplete conditional statements in the template engine.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-error03", {"foo": True})

    @setup({"if-tag-error04": "{% if not foo and %}yes{% else %}no{% endif %}"})
    def test_if_tag_error04(self):
        """
        Test a template rendering scenario where an if-tag is used with an incomplete expression.

        Raises a TemplateSyntaxError when attempting to render a template with an if-tag that lacks a closing tag. The test case validates the error handling behavior of the template engine when encountering malformed if-tag syntax.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-error04", {"foo": True})

    @setup({"if-tag-error05": "{% if not foo or %}yes{% else %}no{% endif %}"})
    def test_if_tag_error05(self):
        """
        Tests that a TemplateSyntaxError is raised when using a conditional statement with an incomplete if condition in a template, specifically when 'or' keyword is used without a condition.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-error05", {"foo": True})

    @setup({"if-tag-error06": "{% if abc def %}yes{% endif %}"})
    def test_if_tag_error06(self):
        """
        Test that a TemplateSyntaxError is raised when the 'if' template tag is used with an invalid syntax, specifically when it contains 'abc def' instead of a valid conditional expression.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error06")

    @setup({"if-tag-error07": "{% if not %}yes{% endif %}"})
    def test_if_tag_error07(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error07")

    @setup({"if-tag-error08": "{% if and %}yes{% endif %}"})
    def test_if_tag_error08(self):
        """
        Test that a TemplateSyntaxError is raised when an if tag is used with the 'and' keyword but no condition is provided, demonstrating incorrect template syntax handling.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error08")

    @setup({"if-tag-error09": "{% if or %}yes{% endif %}"})
    def test_if_tag_error09(self):
        """

        Tests that a TemplateSyntaxError is raised when the 'or' keyword is used incorrectly within an 'if' template tag.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error09")

    @setup({"if-tag-error10": "{% if == %}yes{% endif %}"})
    def test_if_tag_error10(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error10")

    @setup({"if-tag-error11": "{% if 1 == %}yes{% endif %}"})
    def test_if_tag_error11(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error11")

    @setup({"if-tag-error12": "{% if a not b %}yes{% endif %}"})
    def test_if_tag_error12(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error12")

    @setup(
        {
            "else-if-tag-error01": (
                "{% if foo is bar %} yes {% else if foo is not bar %} no {% endif %}"
            )
        }
    )
    def test_else_if_tag_error01(self):
        """
        Tests the error handling for malformed 'else if' template tags.

        This test case checks if the template engine correctly raises a TemplateSyntaxError when an 'else if' tag has an invalid syntax. The test expects the engine to throw an exception with a specific error message indicating the location and nature of the syntax error in the template.

        The test validates the error handling mechanism by verifying that the raised exception contains the expected error message, which includes the line number and the malformed tag syntax that caused the error.

        This test ensures that the template engine properly handles and reports syntax errors in 'else if' tags, allowing developers to identify and correct template errors efficiently.
        """
        error_message = 'Malformed template tag at line 1: "else if foo is not bar"'
        with self.assertRaisesMessage(TemplateSyntaxError, error_message):
            self.engine.get_template("else-if-tag-error01")

    @setup(
        {
            "if-tag-shortcircuit01": (
                "{% if x.is_true or x.is_bad %}yes{% else %}no{% endif %}"
            )
        }
    )
    def test_if_tag_shortcircuit01(self):
        """
        If evaluations are shortcircuited where possible
        """
        output = self.engine.render_to_string("if-tag-shortcircuit01", {"x": TestObj()})
        self.assertEqual(output, "yes")

    @setup(
        {
            "if-tag-shortcircuit02": (
                "{% if x.is_false and x.is_bad %}yes{% else %}no{% endif %}"
            )
        }
    )
    def test_if_tag_shortcircuit02(self):
        """
        The is_bad() function should not be evaluated. If it is, an
        exception is raised.
        """
        output = self.engine.render_to_string("if-tag-shortcircuit02", {"x": TestObj()})
        self.assertEqual(output, "no")

    @setup({"if-tag-badarg01": "{% if x|default_if_none:y %}yes{% endif %}"})
    def test_if_tag_badarg01(self):
        """Nonexistent args"""
        output = self.engine.render_to_string("if-tag-badarg01")
        self.assertEqual(output, "")

    @setup({"if-tag-badarg02": "{% if x|default_if_none:y %}yes{% endif %}"})
    def test_if_tag_badarg02(self):
        output = self.engine.render_to_string("if-tag-badarg02", {"y": 0})
        self.assertEqual(output, "")

    @setup({"if-tag-badarg03": "{% if x|default_if_none:y %}yes{% endif %}"})
    def test_if_tag_badarg03(self):
        """
        Tests the behavior of the if template tag when passed a default value through the default_if_none filter. 
        Verifies that the template renders 'yes' when the 'x' variable is None and a default value 'y' is provided, 
        confirming that the default_if_none filter correctly substitutes the default value.
        """
        output = self.engine.render_to_string("if-tag-badarg03", {"y": 1})
        self.assertEqual(output, "yes")

    @setup(
        {"if-tag-badarg04": "{% if x|default_if_none:y %}yes{% else %}no{% endif %}"}
    )
    def test_if_tag_badarg04(self):
        """

        Tests the behavior of the if tag when the default_if_none filter is used with an incorrect number of arguments.

        The test case checks that the engine correctly handles an invalid if statement and renders the expected output.

        :expected output: 'no'
        :return: None

        """
        output = self.engine.render_to_string("if-tag-badarg04")
        self.assertEqual(output, "no")

    @setup({"if-tag-single-eq": "{% if foo = bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_single_eq(self):
        # A single equals sign is a syntax error.
        """
        Tests that the if tag with a single equals sign raises a TemplateSyntaxError.

        Ensures that a syntax error is raised when the if tag is used with a single equals
        sign for comparison, as this is invalid syntax and should be handled correctly
        by the template engine. The test case passes if a TemplateSyntaxError is raised
        when rendering a template with an if tag that uses a single equals sign for
        comparison, confirming that the template engine properly handles this invalid
        syntax and prevents it from being executed.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-single-eq", {"foo": 1})

    @setup({"template": "{% if foo is True %}yes{% else %}no{% endif %}"})
    def test_if_is_match(self):
        """

        Tests the conditional 'if' statement in the templating engine.

        This function verifies that the templating engine correctly evaluates 
        conditional statements and renders the expected output. It passes a 
        template with an 'if' condition to the engine, along with a context 
        variable 'foo' set to True, and checks that the rendered output matches 
        the expected value.

        :param self: The test instance
        :raises AssertionError: If the rendered output does not match the expected value

        """
        output = self.engine.render_to_string("template", {"foo": True})
        self.assertEqual(output, "yes")

    @setup({"template": "{% if foo is True %}yes{% else %}no{% endif %}"})
    def test_if_is_no_match(self):
        """
        Tests that the if statement in the template engine correctly handles non-boolean true values.

        This function checks that the engine renders a template with the correct output when the condition in an if statement is not a boolean value, but evaluates to true in a boolean context. It verifies that the engine treats non-boolean values as false when checking for an exact match with the boolean value True.

        :raises AssertionError: if the rendered template output does not match the expected output
        """
        output = self.engine.render_to_string("template", {"foo": 1})
        self.assertEqual(output, "no")

    @setup({"template": "{% if foo is bar %}yes{% else %}no{% endif %}"})
    def test_if_is_variable_missing(self):
        output = self.engine.render_to_string("template", {"foo": 1})
        self.assertEqual(output, "no")

    @setup({"template": "{% if foo is bar %}yes{% else %}no{% endif %}"})
    def test_if_is_both_variables_missing(self):
        output = self.engine.render_to_string("template", {})
        self.assertEqual(output, "yes")

    @setup({"template": "{% if foo is not None %}yes{% else %}no{% endif %}"})
    def test_if_is_not_match(self):
        # For this to act as a regression test, it's important not to use
        # foo=True because True is (not None)
        """
        Tests rendering of a template with an 'if' condition that checks for 'not None'.

        This test case verifies that the template engine correctly interprets the 'is not None' condition,
        even when the variable being checked has a value of False.

        The expected output should indicate that the 'if' condition is not met when the variable is False,
        despite it not being None. However, this test currently expects the output 'yes', which may be incorrect
        given the template logic. The actual behavior may vary based on the implementation of the template engine.
        """
        output = self.engine.render_to_string("template", {"foo": False})
        self.assertEqual(output, "yes")

    @setup({"template": "{% if foo is not None %}yes{% else %}no{% endif %}"})
    def test_if_is_not_no_match(self):
        """
        Test if Jinja conditional statement correctly handles \"is not None\" check in template rendering.

        This test case evaluates the output of a template containing a conditional statement 
        that checks if a variable is not None, and verifies that it produces the expected result.
        The function checks the rendered output of a specific template scenario where the variable 'foo' is set to None,
        and asserts that the output matches the expected string 'no'.
        """
        output = self.engine.render_to_string("template", {"foo": None})
        self.assertEqual(output, "no")

    @setup({"template": "{% if foo is not bar %}yes{% else %}no{% endif %}"})
    def test_if_is_not_variable_missing(self):
        """
        Tests the 'is not' conditional statement in a template by rendering a template string with the 'foo' variable set to False and verifying the output is 'yes'.
        """
        output = self.engine.render_to_string("template", {"foo": False})
        self.assertEqual(output, "yes")

    @setup({"template": "{% if foo is not bar %}yes{% else %}no{% endif %}"})
    def test_if_is_not_both_variables_missing(self):
        """

        Tests the behavior of the template engine when rendering an 'if' statement 
        that checks if two variables are not equal, with both variables missing from the context.

        The test verifies that in the absence of both variables, the condition defaults 
        to False, resulting in the 'else' branch being executed and the string 'no' being output.

        """
        output = self.engine.render_to_string("template", {})
        self.assertEqual(output, "no")


class IfNodeTests(SimpleTestCase):
    def test_repr(self):
        """

        Tests the string representation of an IfNode object.

        This test case verifies that the repr function returns a correct and meaningful string representation of the IfNode class.
        It checks if the string representation of an empty IfNode matches the expected format.

        """
        node = IfNode(conditions_nodelists=[])
        self.assertEqual(repr(node), "<IfNode>")
