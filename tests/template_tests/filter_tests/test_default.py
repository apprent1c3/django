from django.template.defaultfilters import default
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class DefaultTests(SimpleTestCase):
    """
    Literal string arguments to the default filter are always treated as
    safe strings, regardless of the auto-escaping state.

    Note: we have to use {"a": ""} here, otherwise the invalid template
    variable string interferes with the test result.
    """

    @setup({"default01": '{{ a|default:"x<" }}'})
    def test_default01(self):
        """
        Test the default filter functionality in the template engine.

        The default filter is used to specify a value to return if a variable is empty or undefined.
        This test case checks that the default filter correctly returns the specified default value 'x<' when the variable 'a' is an empty string.
        """
        output = self.engine.render_to_string("default01", {"a": ""})
        self.assertEqual(output, "x<")

    @setup({"default02": '{% autoescape off %}{{ a|default:"x<" }}{% endautoescape %}'})
    def test_default02(self):
        """

        Test the default filter in a template with autoescaping disabled.

        Checks if the default filter correctly substitutes a value when the input is empty,
        and verifies that HTML escaping is not applied to the substituted value.

        """
        output = self.engine.render_to_string("default02", {"a": ""})
        self.assertEqual(output, "x<")

    @setup({"default03": '{{ a|default:"x<" }}'})
    def test_default03(self):
        """

        Render a template string using the 'default' filter with a marked safe input value.

        Tests the handling of marked safe input values when using the 'default' filter.
        The filter is applied to the 'a' variable in the template, which should return the original value if it's not empty or a default value if it is.

        :raises AssertionError: If the rendered output does not match the expected value.

        """
        output = self.engine.render_to_string("default03", {"a": mark_safe("x>")})
        self.assertEqual(output, "x>")

    @setup({"default04": '{% autoescape off %}{{ a|default:"x<" }}{% endautoescape %}'})
    def test_default04(self):
        """

        Tests the default filter with autoescape disabled.

        This test ensures that when using the default filter with autoescape turned off,
        the output is rendered correctly without escaping special characters.

        It verifies that the default value is not used when a safe string is provided as input.

        """
        output = self.engine.render_to_string("default04", {"a": mark_safe("x>")})
        self.assertEqual(output, "x>")


class DefaultIfNoneTests(SimpleTestCase):
    @setup({"default_if_none01": '{{ a|default:"x<" }}'})
    def test_default_if_none01(self):
        """
        Tests the default filter to ensure that it replaces None values with a specified default string.

        This test verifies that when a variable is None, the template engine will output the default string instead of None.

        The test case checks for the correct replacement of None with a default string 'x<' when the variable 'a' is None.

        This test is relevant for ensuring that templates behave as expected when handling missing or undefined variables, providing a default value instead of an empty or None output.
        """
        output = self.engine.render_to_string("default_if_none01", {"a": None})
        self.assertEqual(output, "x<")

    @setup(
        {
            "default_if_none02": (
                '{% autoescape off %}{{ a|default:"x<" }}{% endautoescape %}'
            )
        }
    )
    def test_default_if_none02(self):
        """
        Test the default_if_none filter in a templating engine when the input value is None.

        This function verifies that when the input value 'a' is None, the default_if_none filter 
        returns the specified default value 'x<', ensuring correct template rendering behavior.

        """
        output = self.engine.render_to_string("default_if_none02", {"a": None})
        self.assertEqual(output, "x<")


class FunctionTests(SimpleTestCase):
    def test_value(self):
        self.assertEqual(default("val", "default"), "val")

    def test_none(self):
        self.assertEqual(default(None, "default"), "default")

    def test_empty_string(self):
        self.assertEqual(default("", "default"), "default")
