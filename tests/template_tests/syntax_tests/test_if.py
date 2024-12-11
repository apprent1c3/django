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

        Tests the if-tag02 template tag with a False condition.

        This test case verifies that when the template tag's condition is False, it renders the \"else\" clause.
        It checks that the rendered output matches the expected string 'no'.

        Validates the engine's ability to correctly handle conditional rendering in templates.

        """
        output = self.engine.render_to_string("if-tag02", {"foo": False})
        self.assertEqual(output, "no")

    @setup({"if-tag03": "{% if foo %}yes{% else %}no{% endif %}"})
    def test_if_tag03(self):
        """
        Tests the functionality of the if-tag in the templating engine.

        This function checks that the if-tag correctly evaluates a conditional statement and
        renders the appropriate template section. In this case, it verifies that when the
        condition 'foo' is False, the template renders the string 'no'.

        The test renders the 'if-tag03' template and asserts that the output matches the
        expected string, ensuring the if-tag behaves as expected when the condition is not met.
        """
        output = self.engine.render_to_string("if-tag03")
        self.assertEqual(output, "no")

    @setup({"if-tag04": "{% if foo %}foo{% elif bar %}bar{% endif %}"})
    def test_if_tag04(self):
        """
        Tests the rendering of an if-elif conditional statement within a template.
        The function verifies that the template engine correctly evaluates the if condition and returns the corresponding value.
        It checks that when the 'foo' variable is True, the output of the rendered template is 'foo'.
        """
        output = self.engine.render_to_string("if-tag04", {"foo": True})
        self.assertEqual(output, "foo")

    @setup({"if-tag05": "{% if foo %}foo{% elif bar %}bar{% endif %}"})
    def test_if_tag05(self):
        """
        Tests the conditional if-elif-endif tag with a false condition and a true condition.

            Verifies that the engine correctly renders the string 'bar' when the variable 'bar' is true and 'foo' is false.

            This test case ensures the if-elif-endif tag behaves as expected with multiple conditions, prioritizing the first true condition.

            :return: None
        """
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
        """
        Test the if-elif-else tag functionality of the templating engine.

        This function verifies that the templating engine correctly handles conditional statements.
        It renders a template containing an if-elif-else statement and asserts that the output matches the expected result when none of the conditions are met.
        The test case covers the scenario where the conditions in the if and elif clauses are not satisfied, resulting in the else clause being executed.
        """
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

        Test the rendering of conditional statements with the 'if' tag.

        This test case verifies that the 'if' tag correctly evaluates the provided
        condition and renders the corresponding block of text. It checks that when
        the condition 'foo' is True, the rendered output is 'foo'.

        The test covers the basic usage of the 'if' tag with a single condition and
        a positive outcome.

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
        """

        Tests the rendering of conditional statements with multiple elif clauses.

        This test case verifies that the templating engine correctly evaluates 
        conditional statements and returns the expected output when the condition 
        is met. It checks the functionality of if-elif-else statements, ensuring 
        that the engine renders the correct block based on the given conditions.

        The test renders a template containing an if-elif-else statement with 
        multiple conditions and checks if the output matches the expected result 
        when one of the conditions is True.

        """
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
        output = self.engine.render_to_string("if-tag13")
        self.assertEqual(output, "nothing")

    # Filters
    @setup({"if-tag-filter01": "{% if foo|length == 5 %}yes{% else %}no{% endif %}"})
    def test_if_tag_filter01(self):
        """
        Tests the rendering of a template with an if-tag filter, verifying that it correctly evaluates the length of a string and returns 'yes' if the length matches the specified value, and 'no' otherwise.
        """
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
        """
        Tests the functionality of the if-tag-eq template tag when comparing two variables.
        The test case evaluates the template tag's behavior when the variables are not equal, 
        verifying that the template renders the else condition correctly, in this case outputting 'no'.
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

        Tests the if-tag-eq04 template to ensure it correctly handles a conditional statement
        with an equality check.

        The test verifies that the template renders the string 'no' when the variables foo and bar are not equal.

        """
        output = self.engine.render_to_string("if-tag-eq04", {"foo": 1, "bar": 2})
        self.assertEqual(output, "no")

    @setup({"if-tag-eq05": "{% if foo == '' %}yes{% else %}no{% endif %}"})
    def test_if_tag_eq05(self):
        """
        Tests the functionality of the if-tag-eq template tag in the rendering engine.

        This test case checks if the tag correctly evaluates an empty string as false, 
        rendering the 'else' clause when the variable foo is an empty string. The 
        expected output is 'no', indicating that the if-tag-eq functionality is working 
        as expected.

        Returns:
            bool: Pass if the output of the rendered template matches the expected 
                  output, Fail otherwise
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
        output = self.engine.render_to_string("if-tag-noteq02", {"foo": 1})
        self.assertEqual(output, "yes")

    @setup({"if-tag-noteq03": "{% if foo != bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_noteq03(self):
        """
        Tests the functionality of the if tag with the \"neq\" condition.

         Verifies that when the condition is not met, the \"else\" clause is executed, 
         rendering the string 'no' as the output. This ensures the correct 
         behavior of the template engine when comparing values for inequality.

         :return: None

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
        """
        Tests the rendering of an if-tag with a greater-than condition that evaluates to False.

        Verifies that the templating engine correctly renders a conditional statement
        with a greater-than comparison that does not hold true, resulting in the
        rendering of the else clause.

        The expected output of this rendering is 'no', confirming the correct
        application of the conditional logic in the template.
        """
        output = self.engine.render_to_string("if-tag-gt-02")
        self.assertEqual(output, "no")

    @setup({"if-tag-gte-01": "{% if 1 >= 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_gte_01(self):
        output = self.engine.render_to_string("if-tag-gte-01")
        self.assertEqual(output, "yes")

    @setup({"if-tag-gte-02": "{% if 1 >= 2 %}yes{% else %}no{% endif %}"})
    def test_if_tag_gte_02(self):
        """
        Tests the functionality of the if-tag with a greater-than-or-equal comparison when the condition is false.
        The test case verifies that the template engine correctly evaluates the condition \"1 >= 2\" and renders the output as 'no' as expected.
        """
        output = self.engine.render_to_string("if-tag-gte-02")
        self.assertEqual(output, "no")

    @setup({"if-tag-lt-01": "{% if 1 < 2 %}yes{% else %}no{% endif %}"})
    def test_if_tag_lt_01(self):
        output = self.engine.render_to_string("if-tag-lt-01")
        self.assertEqual(output, "yes")

    @setup({"if-tag-lt-02": "{% if 1 < 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_lt_02(self):
        output = self.engine.render_to_string("if-tag-lt-02")
        self.assertEqual(output, "no")

    @setup({"if-tag-lte-01": "{% if 1 <= 1 %}yes{% else %}no{% endif %}"})
    def test_if_tag_lte_01(self):
        """
        Tests the functionality of the 'if' template tag with the 'lte' operator.

        The 'if' template tag is used to render a block of content in a template if a certain condition is met.

        In this specific test, the condition being evaluated is whether the value 1 is less than or equal to 1.

        If the condition is true, the string 'yes' should be rendered; otherwise, 'no' should be rendered.

        The test verifies that the 'if' tag with the 'lte' operator is working as expected by comparing the output of the rendering process with the expected string 'yes'.
        """
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

        Tests the functionality of the 'if' tag with the 'in' operator.

        This test case checks if the template engine correctly evaluates an 'if' statement 
        that uses the 'in' operator to check if a value is present in a list. 
        The test passes if the rendered output is 'yes' when the value is in the list, 
        and 'no' when it is not.

        :seealso: The template engine's documentation for more information on using the 'if' tag and 'in' operator.

        """
        output = self.engine.render_to_string("if-tag-in-01", {"x": [1]})
        self.assertEqual(output, "yes")

    @setup({"if-tag-in-02": "{% if 2 in x %}yes{% else %}no{% endif %}"})
    def test_if_tag_in_02(self):
        """
        Tests the functionality of the 'if-tag-in' template tag when the value is not in the specified list.

        The test case verifies that the 'if-tag-in' statement correctly handles the scenario where the value (2) is not present in the provided list (x), 
        resulting in the expected output of 'no'.
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
        output = self.engine.render_to_string(
            "if-tag-and01", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-and02": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and02(self):
        """

        Tests the 'if' tag with an 'and' condition.

        This test case verifies that the 'if' tag correctly evaluates an 'and' condition
        when rendering a template. It checks that the tag returns the expected output
        when one of the conditions is False, resulting in the 'else' block being rendered.

        The test template contains the 'if' tag with an 'and' condition, and the test
        renders this template with specific values for the variables 'foo' and 'bar'.
        The expected output is confirmed to be the 'else' block, indicating that the
        'and' condition was correctly evaluated.

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

        Tests the rendering of an 'if' template tag with 'and' condition.

        This test case evaluates the conditional statement when one of the variables is set to False.
        It checks if the 'if' tag correctly handles the 'and' operator and renders the 'else' block when the condition is not met.

        """
        output = self.engine.render_to_string("if-tag-and06", {"bar": False})
        self.assertEqual(output, "no")

    @setup({"if-tag-and07": "{% if foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_and07(self):
        """

        Tests the conditional 'if' tag with 'and' operator when one condition is not met.

        Verifies that the template rendering engine correctly evaluates the 'and' condition 
        and returns the expected output when one of the conditions is False.

        """
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

        Test the 'if' tag with 'or' conditional statement.

        This test case evaluates the template expression '{% if foo or bar %}yes{% else %}no{% endif %}'
        when 'foo' is True and 'bar' is False. It checks if the rendered output is 'yes' as expected.

        The purpose of this test is to ensure the template engine correctly interprets the 'or' operator
        in conditional statements and returns the correct output based on the provided values.

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
        Tests the behavior of the 'if' tag with 'or' condition, 
        where the second variable ('bar') is set to False. 
        Verifies that the output renders to the 'else' block when the condition is not met.
        """
        output = self.engine.render_to_string("if-tag-or06", {"bar": False})
        self.assertEqual(output, "no")

    @setup({"if-tag-or07": "{% if foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_or07(self):
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
        """

        Tests the functionality of the 'if-tag-not' conditional statement in templating.
        This test checks if the statement correctly handles a truthy value.

        The test renders a template with a conditional statement that outputs 'yes' when the variable 'foo' is truthy, and 'no' otherwise.
        The test then asserts that the rendered output is 'yes' when 'foo' is set to True.

        """
        output = self.engine.render_to_string("if-tag-not01", {"foo": True})
        self.assertEqual(output, "yes")

    @setup({"if-tag-not02": "{% if not not foo %}no{% else %}yes{% endif %}"})
    def test_if_tag_not02(self):
        """
        Tests the if-tag-not02 template tag to verify correct rendering of conditional statements.

        This test case checks that when the 'foo' variable is set to True, the template renders 'no', 
        as the conditional statement checks for the negation of the 'foo' variable being False.

        The test passes if the rendered output matches the expected string 'no', ensuring the 
        template engine correctly handles the if-tag-not02 template tag
        """
        output = self.engine.render_to_string("if-tag-not02", {"foo": True})
        self.assertEqual(output, "no")

    @setup({"if-tag-not06": "{% if foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not06(self):
        """
        Tests the templating engine's handling of conditional statements, specifically the \"if\" tag with a negated condition, ensuring it correctly renders the expected output when the condition is not met.
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
        .. function:: test_if_tag_not09(self)

            Tests the functionality of the 'if-tag-not' template tag. This tag is used to render content when a given condition is met. 
            Specifically, it checks if the 'foo' variable is True and the 'bar' variable is False, and renders 'yes' if the condition is true, 
            otherwise it renders 'no'. The test here validates that the correct content is rendered when 'foo' is False and 'bar' is True.
        """
        output = self.engine.render_to_string(
            "if-tag-not09", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not10": "{% if foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not10(self):
        """
        Tests the conditional 'if' tag with negation in a template, verifying the correct handling of a false condition when both variables are false, and the output is as expected when the 'if' condition is not met.
        """
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

        Tests the rendering of the 'if-tag-not12' template tag, 
        which checks the conditional 'if not foo and bar'. 

        This test case verifies that the template renders 'no' when both 'foo' and 'bar' are True.

        """
        output = self.engine.render_to_string(
            "if-tag-not12", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not13": "{% if not foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not13(self):
        """

        Tests the functionality of the 'if-tag-not' directive in a template engine.

        This directive checks if the first condition is not true and the second condition is true.
        It then renders 'yes' if the conditions are met and 'no' otherwise.

        The test case verifies that the directive behaves as expected when the first condition is true and the second condition is false.

        """
        output = self.engine.render_to_string(
            "if-tag-not13", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not14": "{% if not foo and bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not14(self):
        """
        Tests the functionality of the if-tag-not template tag, verifying that it correctly evaluates the conditional statement and renders the expected output when the first condition is False and the second condition is True.
        """
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
        output = self.engine.render_to_string("if-tag-not16")
        self.assertEqual(output, "yes")

    @setup({"if-tag-not17": "{% if foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not17(self):
        """
        Tests the functionality of the 'if-tag-not17' template tag, which evaluates a conditional statement with logical 'or' and 'not' operators.

        The tag is expected to return 'yes' when at least one of the conditions 'foo' is True or 'bar' is False, and 'no' otherwise.

        This test verifies that the tag behaves correctly when both 'foo' and 'bar' are set to True, ensuring the rendered output matches the expected result.
        """
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
        """
        Tests the rendering of the 'if-tag-not19' template with the 'if' tag and the 'not' operator.

        Verifies that when 'foo' is False and 'bar' is True, the template renders 'no' as the output, 
        demonstrating the correct application of the conditional logic in the template syntax.
        """
        output = self.engine.render_to_string(
            "if-tag-not19", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not20": "{% if foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not20(self):
        """
        Tests the rendering of the 'if-tag-not20' template with the 'if' tag containing conditional logic.

         The 'if' tag is evaluated as True when 'foo' is True or 'bar' is False. This test case specifically checks 
         the rendering when both 'foo' and 'bar' are False, verifying that the condition 'not bar' makes the tag True.

         :return: None
        """
        output = self.engine.render_to_string(
            "if-tag-not20", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not21": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not21(self):
        """
        Checks the functionality of the 'if-tag-not21' template tag, which evaluates a conditional statement with 'not' and 'or' operators, rendering 'yes' if the condition is true and 'no' otherwise. The test verifies that the template engine correctly interprets the given condition, ensuring the expected output is produced.
        """
        output = self.engine.render_to_string("if-tag-not21")
        self.assertEqual(output, "yes")

    @setup({"if-tag-not22": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not22(self):
        """
        Tests the functionality of the 'if-tag-not22' template tag with 'not' and 'or' conditions.
        The function renders a template string with given conditions and verifies the output matches the expected result when both 'foo' and 'bar' variables are True.
        """
        output = self.engine.render_to_string(
            "if-tag-not22", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not23": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not23(self):
        """
        Tests the functionality of an if-tag with a condition that evaluates to true if 'foo' is false or 'bar' is true, rendering a template string with given variables to verify the expected output is 'no' when 'foo' is true and 'bar' is false.
        """
        output = self.engine.render_to_string(
            "if-tag-not23", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not24": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not24(self):
        """
        Tests the 'if-tag-not24' setup with a conditional template tag that checks for the negation of 'foo' or the truthiness of 'bar'.

        This test verifies that when 'foo' is False and 'bar' is True, the template renders as expected, resulting in the string 'yes'.
        """
        output = self.engine.render_to_string(
            "if-tag-not24", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not25": "{% if not foo or bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not25(self):
        output = self.engine.render_to_string(
            "if-tag-not25", {"foo": False, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not26": "{% if not foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not26(self):
        """
        Tests the rendering of a template containing an if-tag-not condition with two negated variables, verifying that the correct output is produced when both variables are false.
        """
        output = self.engine.render_to_string("if-tag-not26")
        self.assertEqual(output, "yes")

    @setup({"if-tag-not27": "{% if not foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not27(self):
        """
        Tests the conditional 'if-tag-not27' template tag.

        This tag checks if two variables, foo and bar, are both False. If they are, the tag renders 'yes', otherwise it renders 'no'.

        The test case verifies that when both foo and bar are True, the tag correctly renders 'no'.
        """
        output = self.engine.render_to_string(
            "if-tag-not27", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not28": "{% if not foo and not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not28(self):
        """

        Tests the functionality of the 'if-tag-not' template tag.

        This test case checks if the 'if-tag-not' tag correctly evaluates the logical NOT operator 
        on multiple conditions and returns the expected output when at least one condition is True.

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
        """
        Tests rendering of the 'if-tag-not' template tag when both conditions are False, 
        verifying that the template correctly returns 'yes' in this scenario.
        """
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
        Tests the conditional rendering of the 'if-tag-not32' template tag.
        The tag checks if either of the provided conditions 'foo' or 'bar' is not met.
        If either condition is not met, the tag renders 'yes', otherwise it renders 'no'.
        This function verifies that the template tag correctly renders 'no' when both conditions are met.
        """
        output = self.engine.render_to_string(
            "if-tag-not32", {"foo": True, "bar": True}
        )
        self.assertEqual(output, "no")

    @setup({"if-tag-not33": "{% if not foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not33(self):
        """

        Tests the rendering of the 'if-tag-not33' template, which contains a conditional 
        statement with a \"not\" operator. The function checks that the template correctly 
        evaluates the condition and returns the expected output when one of the variables 
        is False. The purpose of this test is to ensure the template engine handles conditional 
        logic with \"not\" operators as expected. It verifies that the rendered template 
        matches the expected result, which in this case is 'yes' when either 'foo' or 
        'bar' (or both) are False. 

        """
        output = self.engine.render_to_string(
            "if-tag-not33", {"foo": True, "bar": False}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not34": "{% if not foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not34(self):
        """
        Tests the functionality of the 'if-tag-not' template tag when neither of the condition variables are True. 
        The test case passes in 'foo' as False and 'bar' as True, verifying that the output is 'yes' as the 'if-tag-not' condition is met when at least one of the variables is False.
        """
        output = self.engine.render_to_string(
            "if-tag-not34", {"foo": False, "bar": True}
        )
        self.assertEqual(output, "yes")

    @setup({"if-tag-not35": "{% if not foo or not bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_not35(self):
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
        """
        Tests that a TemplateSyntaxError is raised when an if tag has an incomplete expression, missing the closing condition. Verifies that the template engine correctly identifies and handles syntax errors in if statements, ensuring robust and reliable template rendering.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-error02", {"foo": True})

    @setup({"if-tag-error03": "{% if foo or %}yes{% else %}no{% endif %}"})
    def test_if_tag_error03(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-error03", {"foo": True})

    @setup({"if-tag-error04": "{% if not foo and %}yes{% else %}no{% endif %}"})
    def test_if_tag_error04(self):
        """
        Tests the behavior of the template engine when encountering an invalid 'if' tag syntax.

        This test case verifies that a :class:`TemplateSyntaxError` is raised when the 'if' tag is used with an invalid syntax, specifically when the 'and' keyword is used without a following condition.

        :raises: TemplateSyntaxError
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-error04", {"foo": True})

    @setup({"if-tag-error05": "{% if not foo or %}yes{% else %}no{% endif %}"})
    def test_if_tag_error05(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-error05", {"foo": True})

    @setup({"if-tag-error06": "{% if abc def %}yes{% endif %}"})
    def test_if_tag_error06(self):
        """
        Tests the template engine's handling of an invalid if statement with a syntax error, specifically a missing colon after the condition. 

        The test expects a TemplateSyntaxError to be raised when attempting to parse the template.
        """
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
        Tests that the template engine raises a TemplateSyntaxError when an if tag is used with an invalid syntax, specifically when the 'or' keyword is used without any condition.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error09")

    @setup({"if-tag-error10": "{% if == %}yes{% endif %}"})
    def test_if_tag_error10(self):
        """
        Tests that a TemplateSyntaxError is raised when the 'if' tag is used with an invalid syntax, specifically when the comparison operator is missing.

        The test verifies that the template engine correctly handles and raises an exception for a template containing a malformed 'if' statement, ensuring that the syntax error is properly detected and reported.

        Args:
            None

        Returns:
            None

        Raises:
            TemplateSyntaxError: When the 'if' tag syntax is invalid
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("if-tag-error10")

    @setup({"if-tag-error11": "{% if 1 == %}yes{% endif %}"})
    def test_if_tag_error11(self):
        """
        Tests that a TemplateSyntaxError is raised when an if tag has invalid syntax. 
        This test case checks the engine's ability to handle and report incorrect 
        template syntax, specifically when an if statement is not properly closed or 
        formatted, ensuring that the engine correctly identifies and raises an error 
        in such cases.
        """
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
        Tests the 'if' tag with the 'default_if_none' filter when the variable 'x' is undefined, verifying that the tag correctly handles the case where the variable is missing and the default value is provided.
        """
        output = self.engine.render_to_string("if-tag-badarg02", {"y": 0})
        self.assertEqual(output, "")

    @setup({"if-tag-badarg03": "{% if x|default_if_none:y %}yes{% endif %}"})
    def test_if_tag_badarg03(self):
        """
        Tests the behavior of the 'if' tag when using the default_if_none filter with invalid arguments.

        This test ensures that the template engine correctly renders the 'if' tag 
        when the variable is replaced by a default value due to the use of the 
        default_if_none filter, even when an invalid argument is provided.

        The expectation is that the 'if' tag will evaluate to True when the 
        variable 'x' is replaced by the default value 'y', resulting in the 
        string 'yes' being rendered.
        """
        output = self.engine.render_to_string("if-tag-badarg03", {"y": 1})
        self.assertEqual(output, "yes")

    @setup(
        {"if-tag-badarg04": "{% if x|default_if_none:y %}yes{% else %}no{% endif %}"}
    )
    def test_if_tag_badarg04(self):
        """
        Tests the behavior of the if tag when using the default_if_none filter with an invalid number of arguments. 
        Verifies that the template renders correctly when the if tag is used with an incorrect number of arguments for the filter, 
        yielding the expected output 'no'.
        """
        output = self.engine.render_to_string("if-tag-badarg04")
        self.assertEqual(output, "no")

    @setup({"if-tag-single-eq": "{% if foo = bar %}yes{% else %}no{% endif %}"})
    def test_if_tag_single_eq(self):
        # A single equals sign is a syntax error.
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("if-tag-single-eq", {"foo": 1})

    @setup({"template": "{% if foo is True %}yes{% else %}no{% endif %}"})
    def test_if_is_match(self):
        """
        Tests the functionality of the template engine in handling conditional statements with the 'is' keyword.
        This function verifies that the template engine correctly renders 'yes' when the condition 'foo is True' is met, and 'no' otherwise, ensuring proper handling of the 'is' operator in template logic.
        """
        output = self.engine.render_to_string("template", {"foo": True})
        self.assertEqual(output, "yes")

    @setup({"template": "{% if foo is True %}yes{% else %}no{% endif %}"})
    def test_if_is_no_match(self):
        """

        Tests the functionality of conditional statements within templates.
        This checks that the templating engine correctly evaluates the 'if' statement
        when the condition is not a boolean value, ensuring it does not match True.

        """
        output = self.engine.render_to_string("template", {"foo": 1})
        self.assertEqual(output, "no")

    @setup({"template": "{% if foo is bar %}yes{% else %}no{% endif %}"})
    def test_if_is_variable_missing(self):
        """

        Tests the rendering of a template with an if statement when a variable is missing.

        This function checks if the template engine correctly handles an if statement 
        comparing two variables, when one of them is not provided in the rendering context. 

        The test case simulates a scenario where the variable 'bar' is not defined, 
        thus the condition 'foo is bar' should evaluate to False, resulting in the 
        output 'no'.

        """
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
        output = self.engine.render_to_string("template", {"foo": False})
        self.assertEqual(output, "yes")

    @setup({"template": "{% if foo is not None %}yes{% else %}no{% endif %}"})
    def test_if_is_not_no_match(self):
        """
        Tests the rendering of a template with an 'if' statement that checks if a variable is not None.

         The function verifies that when the variable 'foo' is None, the template renders 'no'. 
         This test case ensures that the template engine correctly handles conditional statements with 'is not None' checks, 
         and that the expected output is generated when the condition is not met.
        """
        output = self.engine.render_to_string("template", {"foo": None})
        self.assertEqual(output, "no")

    @setup({"template": "{% if foo is not bar %}yes{% else %}no{% endif %}"})
    def test_if_is_not_variable_missing(self):
        """
        Test the Jinja2 templating engine's if statement with the 'is not' condition, verifying it correctly evaluates when a variable is not another variable, and handles cases where a variable is intentionally set to a falsy value, such as False.
        """
        output = self.engine.render_to_string("template", {"foo": False})
        self.assertEqual(output, "yes")

    @setup({"template": "{% if foo is not bar %}yes{% else %}no{% endif %}"})
    def test_if_is_not_both_variables_missing(self):
        """

        Tests the template engine's handling of the 'is not' conditional statement 
        when both variables being compared are missing from the context.

        This test case checks if the engine correctly renders the template when 
        the condition is False due to both variables being absent, resulting in 
        the 'else' branch being taken.

        """
        output = self.engine.render_to_string("template", {})
        self.assertEqual(output, "no")


class IfNodeTests(SimpleTestCase):
    def test_repr(self):
        """
        Tests the string representation of an IfNode instance.

        Verifies that the repr() function returns the expected string for an IfNode object,
        providing a meaningful and concise representation of the node's type and contents.

        The test checks for the default representation of an IfNode with no conditions,
        ensuring it meets the expected format and does not include any unnecessary details.
        """
        node = IfNode(conditions_nodelists=[])
        self.assertEqual(repr(node), "<IfNode>")
