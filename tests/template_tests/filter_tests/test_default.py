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
        Tests the default filter functionality, ensuring that when an empty value is provided 
        for a variable, the filter returns the specified default value instead of an empty string.
        This test case verifies that the rendered template output matches the expected default value.
        """
        output = self.engine.render_to_string("default01", {"a": ""})
        self.assertEqual(output, "x<")

    @setup({"default02": '{% autoescape off %}{{ a|default:"x<" }}{% endautoescape %}'})
    def test_default02(self):
        """
        Test the default filter in a template with autoescape disabled, 
        verifying that it correctly substitutes a default value when the input is empty.
        """
        output = self.engine.render_to_string("default02", {"a": ""})
        self.assertEqual(output, "x<")

    @setup({"default03": '{{ a|default:"x<" }}'})
    def test_default03(self):
        """
        Renders a template with a default filter and tests that it correctly handles a mark_safe value.

        The function tests the rendering engine's ability to apply the default filter to a variable and ensure the output is correctly escaped or marked as safe.

        It verifies that when the variable is assigned a mark_safe value, the default filter does not interfere with its safe status, resulting in the expected output without any additional escaping.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Examples
        --------
        This function is for internal testing purposes and should not be used directly in user code. It is used to validate the correct behavior of the rendering engine when using the default filter with mark_safe values.
        """
        output = self.engine.render_to_string("default03", {"a": mark_safe("x>")})
        self.assertEqual(output, "x>")

    @setup({"default04": '{% autoescape off %}{{ a|default:"x<" }}{% endautoescape %}'})
    def test_default04(self):
        """

        Test the default filter when autoescape is disabled and the input is marked as safe.

        The test verifies that when the default filter is applied to a variable that has been
        marked as safe, the rendered output does not escape the variable's value, even when
        the variable contains HTML characters.

        This ensures that the default filter behaves correctly in conjunction with the
        autoescape and mark_safe features, allowing for safe and controlled rendering of
        HTML content.

        """
        output = self.engine.render_to_string("default04", {"a": mark_safe("x>")})
        self.assertEqual(output, "x>")


class DefaultIfNoneTests(SimpleTestCase):
    @setup({"default_if_none01": '{{ a|default:"x<" }}'})
    def test_default_if_none01(self):
        """
        Tests the default filter when the input is None.

        Checks if the default filter correctly replaces a None value with a specified default string.
        In this case, it verifies that the string 'x<' is returned when the input 'a' is None.
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
        Tests the default filter in a template when the input variable is None, 
        verifying that the default value is rendered correctly when autoescaping is disabled.
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
