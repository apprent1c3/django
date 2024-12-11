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

        Tests the rendering of an if-tag template with a false condition.

        The function verifies that when the condition 'foo' is set to False, 
        the template renders 'no' as the output. This test ensures the 
        correct functionality of the if-tag in the template engine.

        """
        output = self.engine.render_to_string("if-tag02", {"foo": False})
        self.assertEqual(output, "no")

    @setup({"if-tag03": "{% if foo %}yes{% else %}no{% endif %}"})
    def test_if_tag03(self):
        output = self.engine.render_to_string("if-tag03")
        self.assertEqual(output, "no")

    @setup({"if-tag04": "{% if foo %}foo{% elif bar %}bar{% endif %}"})
    def test_if_tag04(self):
        output = self.engine.render_to_string("if-tag04", {"foo": True})
        self.assertEqual(output, "foo")

    @setup({"if-tag05": "{% if foo %}foo{% elif bar %}bar{% endif %}"})
    def test_if_tag05(self):
        output = self.engine.render_to_string("if-tag05", {"bar": True})
        self.assertEqual(output, "bar")

    @setup({"if-tag06": "{% if foo %}foo{% elif bar %}bar{% endif %}"})
    def test_if_tag06(self):
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

        Tests the conditional 'if' tag in template rendering.

        The function checks if the template engine correctly evaluates the 'if' tag when
        the condition 'foo' is True. It expects the output to be 'foo' when 'foo' is
        provided as a context variable.

        The test case covers a basic 'if-elif-else' construct, ensuring the rendering
        engine handles conditional statements as expected.

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

        Render a template with if-elif-else conditional statements and verify the output.

        This test case checks the rendering of a template that includes a chain of if-elif-else conditions.
        The conditional statements check for the presence of 'foo', 'bar', and 'baz' variables, and render the corresponding value if found.
        If none of the conditions are met, it renders the string 'nothing'.
        The function asserts that the rendered output matches the expected result 'nothing', ensuring the correct functionality of the conditional statements in the template.

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
        output = self.engine.render_to_string("if-tag-eq01")
        self.assertEqual(output, "yes")

    @setup({"if-tag-eq02": "{% if foo == bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_eq02(self):
        output = self.engine.render_to_string("if-tag-eq02", {"foo": 1})
        self.assertEqual(output, "no")

    @setup({"if-tag-eq03": "{% if foo == bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_eq03(self):
        output = self.engine.render_to_string("if-tag-eq03", {"foo": 1, "bar": 1})
        self.assertEqual(output, "yes")

    @setup({"if-tag-eq04": "{% if foo == bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_eq04(self):
        """
        Tests the functionality of the if-tag-eq template tag, specifically when the two values being compared are not equal.
        The function verifies that the template engine correctly renders the \"if\" tag when the condition is false, resulting in the \"else\" clause being executed.
        It checks that the output of the rendered template matches the expected string 'no' when 'foo' is not equal to 'bar'.
        """
        output = self.engine.render_to_string("if-tag-eq04", {"foo": 1, "bar": 2})
        self.assertEqual(output, "no")

    @setup({"if-tag-eq05": "{% if foo == '' %}yes{% else %}no{% endif %}"})
    def test_if_tag_eq05(self):
        """
        Tests that an if-tag-eq condition correctly handles an empty string comparison in a template. 

        The test case verifies that when the \"foo\" variable is empty, the if statement returns 'no', indicating the comparison is working as expected.
        """
        output = self.engine.render_to_string("if-tag-eq05")
        self.assertEqual(output, "no")

    # Inequality
    @setup({"if-tag-noteq01": "{% if foo != bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_noteq01(self):
        """

        Tests the functionality of the 'if' tag with 'neq' operator in a templating engine.

        This test case checks if the 'if' tag correctly evaluates the condition when the values are not equal.
        It verifies that the output is as expected when the condition is false.

        """
        output = self.engine.render_to_string("if-tag-noteq01")
        self.assertEqual(output, "no")

    @setup({"if-tag-noteq02": "{% if foo != bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_noteq02(self):
        output = self.engine.render_to_string("if-tag-noteq02", {"foo": 1})
        self.assertEqual(output, "yes")

    @setup({"if-tag-noteq03": "{% if foo != bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_noteq03(self):
        """
        Tests the functionality of the if-tag with the noteq operator.

        This test case verifies that the if-tag correctly handles the 'noteq' operator,
        rendering the content if the given values are not equal, and skipping it otherwise.

        The test renders a template containing an if-tag with the condition 'foo!= bar',
        passing in values where foo equals bar, and checks that the rendered output is 'no' as expected.

        """
        output = self.engine.render_to_string("if-tag-noteq03", {"foo": 1, "bar": 1})
        self.assertEqual(output, "no")

    @setup({"if-tag-noteq04": "{% if foo != bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_noteq04(self):
        output = self.engine.render_to_string("if-tag-noteq04", {"foo": 1, "bar": 2})
        self.assertEqual(output, "yes")

    @setup({"if-tag-noteq05": '{% if foo != "" %}yes{% else %}no{% endif %}'})
    def test_if_tag_noteq05(self):
        output = self.engine.render_to_string("if-tag-noteq05")
        self.assertEqual(output, "yes")

    # Comparison
    @setup({"if-tag-gt-01": "{% if 2 > 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_gt_01(self):
        output = self.engine.render_to_string("if-tag-gt-01")
        self.assertEqual(output, "yes")

    @setup({"if-tag-gt-02": "{% if 1 > 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_gt_02(self):
        output = self.engine.render_to_string("if-tag-gt-02")
        self.assertEqual(output, "no")

    @setup({"if-tag-gte-01": "{% if 1 >= 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_gte_01(self):
        """
        Tests the functionality of the 'if' tag in template rendering when using greater than or equal to (gte) comparison.

        The test case evaluates the condition where the value '1' is compared to check if it is greater than or equal to '1'. 
        The expected output of this evaluation is 'yes' if the condition is met, and 'no' otherwise. 
        The test asserts that the rendered output matches the expected result, ensuring the conditional statement is correctly interpreted and executed by the template engine.
        """
        output = self.engine.render_to_string("if-tag-gte-01")
        self.assertEqual(output, "yes")

    @setup({"if-tag-gte-02": "{% if 1 >= 2 %}yes{% else %}no{% endif %}"})
    def test_if_tag_gte_02(self):
        output = self.engine.render_to_string("if-tag-gte-02")
        self.assertEqual(output, "no")

    @setup({"if-tag-lt-01": "{% if 1 < 2 %}yes{% else %}no{% endif %}"})
    def test_if_tag_lt_01(self):
        """

        Tests the rendering of the 'if' template tag with a less-than comparison.

        Ensures that the 'if' tag correctly evaluates the condition '1 < 2' and 
        renders the 'yes' string when the condition is true.

        """
        output = self.engine.render_to_string("if-tag-lt-01")
        self.assertEqual(output, "yes")

    @setup({"if-tag-lt-02": "{% if 1 < 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_lt_02(self):
        output = self.engine.render_to_string("if-tag-lt-02")
        self.assertEqual(output, "no")

    @setup({"if-tag-lte-01": "{% if 1 <= 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_lte_01(self):
        output = self.engine.render_to_string("if-tag-lte-01")
        self.assertEqual(output, "yes")

    @setup({"if-tag-lte-02": "{% if 2 <= 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_lte_02(self):
        output = self.engine.render_to_string("if-tag-lte-02")
        self.assertEqual(output, "no")

    # Contains
    @setup({"if-tag-in-01": "{% if 1 in x %}yes{% else %}no{% endif %}"})
    def test_if_tag_in_01(self):
        """
        Tests the 'in' operator within an if tag in the templating engine.

        This test case evaluates if the templating engine correctly handles the 'in' operator
        to check if a value is present in a list. It verifies that the 'if' statement returns
        the expected output when the value is found in the list.

        Raises:
            AssertionError: If the rendered output does not match the expected result.

        """
        output = self.engine.render_to_string("if-tag-in-01", {"x": [1]})
        self.assertEqual(output, "yes")

    @setup({"if-tag-in-02": "{% if 2 in x %}yes{% else %}no{% endif %}"})
    def test_if_tag_in_02(self):
        """
        Tests the functionality of the if-tag-in statement when the value is not present in a list.

        This test case checks the rendering of a template with an if-tag-in statement.
        It verifies that the statement correctly evaluates to False when the specified value is not found in the given list.

        The test case supplies a list with a single element, and the if-tag-in statement checks for the presence of a different value.
        It then asserts that the output of the rendered template matches the expected result, which is 'no' in this case.
        """
        output = self.engine.render_to_string("if-tag-in-02", {"x": [1]})
        self.assertEqual(output, "no")

    @setup({"if-tag-not-in-01": "{% if 1 not in x %}yes{% else %}no{% endif %}"})
    def test_if_tag_not_in_01(self):
        output = self.engine.render_to_string("if-tag-not-in-01", {"x": [1]})
        self.assertEqual(output, "no")

    @setup({"if-tag-not-in-02": "{% if 2 not in x %}yes{% else %}no{% endif %}"})
    def test_if_tag_not_in_02(self):
        output = self.engine.render_to_string("if-tag-not-in-02", {"x": [1]})
        self.assertEqual(output, "yes")

    # AND
    @setup({"if-tag-and01": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and01(self):
        """

        Tests the functionality of the 'if' template tag with the 'and' operator.

        The function verifies that when both conditions are True, the template renders the content within the 'if' block.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Note
        ----
        This test case ensures the correct behavior of the 'if' tag when used with the 'and' operator in a template.

        """
        output = self.engine.render_to_string(
            "if-tag-and01", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-and02": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and02(self):
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
        Tests the 'if' tag with 'and' condition when both conditions are False.

        This test case evaluates a template with an 'if' statement that checks if two conditions ('foo' and 'bar') are True.
        It then asserts that the output of the rendered template is 'no', as expected when both conditions are False.

         المفاهيم الأساسية: 
        - CONDITIONAL_STATEMENTS
        - TEMPLATE_RENDERING

        :مكتبات المراجع:
         [@\".Countryconditionals\"]
        """
        output = self.engine.render_to_string(
            "if-tag-and04", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-and05": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and05(self):
        output = self.engine.render_to_string("if-tag-and05", {"foo": False})
        self.assertEqual(output, "no")

    @setup({"if-tag-and06": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and06(self):
        """
        Tests the behavior of the 'if' tag when using the 'and' operator with two variables.
        The test case checks that the 'if' tag correctly evaluates a conditional statement 
        with two conditions and returns the expected output when one of the conditions is False.
        """
        output = self.engine.render_to_string("if-tag-and06", {"bar": False})
        self.assertEqual(output, "no")

    @setup({"if-tag-and07": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and07(self):
        output = self.engine.render_to_string("if-tag-and07", {"foo": True})
        self.assertEqual(output, "no")

    @setup({"if-tag-and08": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and08(self):
        output = self.engine.render_to_string("if-tag-and08", {"bar": True})
        self.assertEqual(output, "no")

    # OR
    @setup({"if-tag-or01": "{% if foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_or01(self):
        output = self.engine.render_to_string("if-tag-or01", {"foo": True, "bar": True})
        self.assertEqual(output, "yes")

    @setup({"if-tag-or02": "{% if foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_or02(self):
        """
        rms the condition where at least one of the variables is True with an 'or' operator. 
        This tag evaluates as true if at least one of the variables is true, otherwise it evaluates as false. 

        :param foo: First variable in the 'or' condition.
        :param bar: Second variable in the 'or' condition.
        :returns: String 'yes' if at least one of the variables is True, otherwise 'no'.
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
        Tests the functionality of the 'if' tag with 'or' condition in template rendering.

        The function verifies that when both conditions in the 'or' statement are False, the 'if' tag correctly renders the 'else' block.
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
        Tests the `if` template tag with the `or` operator to verify that it correctly evaluates the condition when the first variable is not provided and the second variable is False.
        """
        output = self.engine.render_to_string("if-tag-or06", {"bar": False})
        self.assertEqual(output, "no")

    @setup({"if-tag-or07": "{% if foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_or07(self):
        """
        Tests the if tag with 'or' condition functionality in the templating engine.

        Verifies that when at least one of the conditions is met, the if tag evaluates to True and the content under the if block is rendered. In this case, the test checks when 'foo' is True, and 'bar' is implicitly False due to the absence of its value in the context.

        Ensures the correct rendering of the template when the 'or' condition is used within the if tag, returning 'yes' if the condition is met and 'no' otherwise.
        """
        output = self.engine.render_to_string("if-tag-or07", {"foo": True})
        self.assertEqual(output, "yes")

    @setup({"if-tag-or08": "{% if foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_or08(self):
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

        Test the functionality of the if tag with a not condition.

        This test checks if the engine correctly renders a template with an if statement
        that includes a not condition. The test template contains a conditional statement
        that evaluates to 'yes' if the variable 'foo' is true and 'bar' is false, and 'no' otherwise.
        The test asserts that the rendered output is 'no', indicating that the condition
        is correctly evaluated.

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
        """
        Tests the functionality of the 'if-tag-not' template tag with a conditional statement, 
        verifying that it correctly evaluates the 'not' operator within the if statement. 
        The test case checks if the tag renders 'yes' when the first condition is true and the 
        second condition is false, ensuring the 'not' operator is applied as expected.
        """
        output = self.engine.render_to_string(
            "if-tag-not08", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not09": "{% if foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not09(self):
        output = self.engine.render_to_string(
            "if-tag-not09", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not10": "{% if foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not10(self):
        output = self.engine.render_to_string(
            "if-tag-not10", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not11": "{% if not foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not11(self):
        output = self.engine.render_to_string("if-tag-not11")
        self.assertEqual(output, "no")

    @setup({"if-tag-not12": "{% if not foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not12(self):
        """
        Tests the conditional 'if-tag-not12' template tag with a scenario where 'foo' is True and 'bar' is True.
        The function verifies that the rendered template outputs 'no' as expected, correctly handling the conditional logic when both conditions are met.
        """
        output = self.engine.render_to_string(
            "if-tag-not12", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not13": "{% if not foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not13(self):
        """
        Test the functionality of the if-tag-not template tag when the foo variable is True and the bar variable is False, verifying that the rendered output is 'no' as expected.
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
        output = self.engine.render_to_string(
            "if-tag-not15", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not16": "{% if foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not16(self):
        """
        Tests the functionality of the if-tag-not16 template tag, verifying that it correctly evaluates conditional statements with 'or' and 'not' operators, returning 'yes' when the condition is met and 'no' otherwise.
        """
        output = self.engine.render_to_string("if-tag-not16")
        self.assertEqual(output, "yes")

    @setup({"if-tag-not17": "{% if foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not17(self):
        output = self.engine.render_to_string(
            "if-tag-not17", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not18": "{% if foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not18(self):
        output = self.engine.render_to_string(
            "if-tag-not18", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not19": "{% if foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not19(self):
        output = self.engine.render_to_string(
            "if-tag-not19", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not20": "{% if foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not20(self):
        output = self.engine.render_to_string(
            "if-tag-not20", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not21": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not21(self):
        output = self.engine.render_to_string("if-tag-not21")
        self.assertEqual(output, "yes")

    @setup({"if-tag-not22": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not22(self):
        output = self.engine.render_to_string(
            "if-tag-not22", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not23": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not23(self):
        output = self.engine.render_to_string(
            "if-tag-not23", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not24": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not24(self):
        output = self.engine.render_to_string(
            "if-tag-not24", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not25": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not25(self):
        """
        Tests the if-tag-not25 template tag functionality when both foo and bar are False. 
        Verifies that the template engine correctly interprets the conditional statement and renders the expected output.
        """
        output = self.engine.render_to_string(
            "if-tag-not25", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not26": "{% if not foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not26(self):
        output = self.engine.render_to_string("if-tag-not26")
        self.assertEqual(output, "yes")

    @setup({"if-tag-not27": "{% if not foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not27(self):
        output = self.engine.render_to_string(
            "if-tag-not27", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not28": "{% if not foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not28(self):
        """
        Tests the behavior of the if-tag-not operator when one of the conditions is True and the other is False.

        The function renders a template with the if-tag-not operator and checks if the output matches the expected result.
        The template contains a conditional statement that checks if both 'foo' and 'bar' are False, and outputs 'yes' if the condition is met, and 'no' otherwise.

        In this test case, 'foo' is set to True and 'bar' is set to False, so the condition is not met, and the function asserts that the output is 'no'.
        """
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
        output = self.engine.render_to_string(
            "if-tag-not30", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not31": "{% if not foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not31(self):
        output = self.engine.render_to_string("if-tag-not31")
        self.assertEqual(output, "yes")

    @setup({"if-tag-not32": "{% if not foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not32(self):
        """

        Tests the rendering of a template with an if-tag-not condition.

        This test case checks that the template engine correctly handles a conditional
        statement with a 'not' operator and two variables. The condition is {% if not foo or not bar %},
        which should be False when both 'foo' and 'bar' are True. The expected output is 'no'.

        The template is expected to render 'yes' if the condition is met and 'no' otherwise.

        """
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
        Tests the 'if-tag-not35' template tag, which checks if either of two conditions is False.

        This tag is used to conditionally render content based on the absence of one or both of two conditions (foo and bar).
        It returns 'yes' if either foo or bar (or both) is False, and 'no' otherwise.

        The purpose of this test is to ensure the correct functionality of the 'if-tag-not35' template tag in handling conditional logic with False values. 
        """
        output = self.engine.render_to_string(
            "if-tag-not35", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "yes")

    # Various syntax errors
    @setup({"if-tag-error01": "{% if %}yes{% endif %}"})
    def test_if_tag_error01(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error01")

    @setup({"if-tag-error02": "{% if foo and %}yes{% else %}no{% endif %}"})
    def test_if_tag_error02(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-error02", {"foo": True})

    @setup({"if-tag-error03": "{% if foo or %}yes{% else %}no{% endif %}"})
    def test_if_tag_error03(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-error03", {"foo": True})

    @setup({"if-tag-error04": "{% if not foo and %}yes{% else %}no{% endif %}"})
    def test_if_tag_error04(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-error04", {"foo": True})

    @setup({"if-tag-error05": "{% if not foo or %}yes{% else %}no{% endif %}"})
    def test_if_tag_error05(self):
        """
        Tests that a TemplateSyntaxError is raised when using an invalid 'if' tag syntax with a 'not' keyword.

        The function verifies that the template engine correctly handles the case where the 'if' tag is used with an empty 'not' condition, and that it raises a TemplateSyntaxError as expected.

        This test ensures that the template engine enforces proper syntax for conditional statements, preventing potential runtime errors and making it easier to identify and fix issues during development.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-error05", {"foo": True})

    @setup({"if-tag-error06": "{% if abc def %}yes{% endif %}"})
    def test_if_tag_error06(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error06")

    @setup({"if-tag-error07": "{% if not %}yes{% endif %}"})
    def test_if_tag_error07(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error07")

    @setup({"if-tag-error08": "{% if and %}yes{% endif %}"})
    def test_if_tag_error08(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error08")

    @setup({"if-tag-error09": "{% if or %}yes{% endif %}"})
    def test_if_tag_error09(self):
        """
        Tests a template engine's error handling for an if-tag syntax error, specifically when the \"or\" operator is used without a preceding condition, verifying that a TemplateSyntaxError is raised when attempting to parse the template.
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
        Tests that the template engine correctly raises an error when encountering a malformed 'else if' tag in a template.

        The test verifies that the engine raises a TemplateSyntaxError with the expected error message when it encounters an 'else if' tag with an invalid syntax, such as 'else if foo is not bar'. This ensures that the template engine is able to detect and report syntax errors in 'else if' tags.

        The error message is checked to ensure it accurately reports the location and nature of the syntax error, allowing developers to quickly identify and fix issues in their templates.
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
        """
        Tests the if tag with a bad argument (default_if_none filter used with two arguments) to ensure it handles the invalid input correctly.

         The test case verifies that the if tag does not throw an error when the default_if_none filter is used with two arguments, instead rendering an empty string as output.
        """
        output = self.engine.render_to_string("if-tag-badarg02", {"y": 0})
        self.assertEqual(output, "")

    @setup({"if-tag-badarg03": "{% if x|default_if_none:y %}yes{% endif %}"})
    def test_if_tag_badarg03(self):
        """
        Test the if tag with the default_if_none filter to handle None values.

        This test case verifies that the default_if_none filter correctly handles the case when 
        the variable x is None, and provides a default value y instead. The test expects the 
        rendered output to be 'yes' when x is None and y is provided as a default value.

        """
        output = self.engine.render_to_string("if-tag-badarg03", {"y": 1})
        self.assertEqual(output, "yes")

    @setup(
        {"if-tag-badarg04": "{% if x|default_if_none:y %}yes{% else %}no{% endif %}"}
    )
    def test_if_tag_badarg04(self):
        output = self.engine.render_to_string("if-tag-badarg04")
        self.assertEqual(output, "no")

    @setup({"if-tag-single-eq": "{% if foo = bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_single_eq(self):
        # A single equals sign is a syntax error.
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-single-eq", {"foo": 1})

    @setup({"template": "{% if foo is True %}yes{% else %}no{% endif %}"})
    def test_if_is_match(self):
        output = self.engine.render_to_string("template", {"foo": True})
        self.assertEqual(output, "yes")

    @setup({"template": "{% if foo is True %}yes{% else %}no{% endif %}"})
    def test_if_is_no_match(self):
        output = self.engine.render_to_string("template", {"foo": 1})
        self.assertEqual(output, "no")

    @setup({"template": "{% if foo is bar %}yes{% else %}no{% endif %}"})
    def test_if_is_variable_missing(self):
        """
        Tests the templating engine's if-is statement when comparing a variable against another variable.
        The test case checks that if the variable is missing from the context, the comparison will be evaluated as False, resulting in the else branch being executed.
        """
        output = self.engine.render_to_string("template", {"foo": 1})
        self.assertEqual(output, "no")

    @setup({"template": "{% if foo is bar %}yes{% else %}no{% endif %}"})
    def test_if_is_both_variables_missing(self):
        """
        Tests the rendering of a template with an if statement when both variables are missing.

        The function verifies that the template engine correctly handles the case where both 
        variables in an 'is' conditional statement are missing, returning the expected output 
        when the variables are not defined in the rendering context.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the rendered output does not match the expected output.
        """
        output = self.engine.render_to_string("template", {})
        self.assertEqual(output, "yes")

    @setup({"template": "{% if foo is not None %}yes{% else %}no{% endif %}"})
    def test_if_is_not_match(self):
        # For this to act as a regression test, it's important not to use
        # foo=True because True is (not None)
        output = self.engine.render_to_string("template", {"foo": False})
        self.assertEqual(output, "yes")

    @setup({"template": "{% if foo is not None %}yes{% else %}no{% endif %}"})
    def test_if_is_not_no_match(self):
        """

        Tests the rendering of a template with an if statement that checks if a variable is not None.
        The function verifies that when the variable is None, the template renders to 'no', 
        demonstrating the correct handling of None values in if statements within the template engine.

        """
        output = self.engine.render_to_string("template", {"foo": None})
        self.assertEqual(output, "no")

    @setup({"template": "{% if foo is not bar %}yes{% else %}no{% endif %}"})
    def test_if_is_not_variable_missing(self):
        output = self.engine.render_to_string("template", {"foo": False})
        self.assertEqual(output, "yes")

    @setup({"template": "{% if foo is not bar %}yes{% else %}no{% endif %}"})
    def test_if_is_not_both_variables_missing(self):
        output = self.engine.render_to_string("template", {})
        self.assertEqual(output, "no")


class IfNodeTests(SimpleTestCase):
    def test_repr(self):
        node = IfNode(conditions_nodelists=[])
        self.assertEqual(repr(node), "<IfNode>")
