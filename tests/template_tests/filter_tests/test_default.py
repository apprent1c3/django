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
        output = self.engine.render_to_string("default01", {"a": ""})
        self.assertEqual(output, "x<")

    @setup({"default02": '{% autoescape off %}{{ a|default:"x<" }}{% endautoescape %}'})
    def test_default02(self):
        output = self.engine.render_to_string("default02", {"a": ""})
        self.assertEqual(output, "x<")

    @setup({"default03": '{{ a|default:"x<" }}'})
    def test_default03(self):
        """

        Tests the default filter in a template when the input value is a string that needs to be escaped for HTML safety.

        This test case verifies that the default filter can handle a value marked as safe from HTML escaping.
        The function checks if the rendered output matches the expected result when the input value contains special characters.

        """
        output = self.engine.render_to_string("default03", {"a": mark_safe("x>")})
        self.assertEqual(output, "x>")

    @setup({"default04": '{% autoescape off %}{{ a|default:"x<" }}{% endautoescape %}'})
    def test_default04(self):
        output = self.engine.render_to_string("default04", {"a": mark_safe("x>")})
        self.assertEqual(output, "x>")


class DefaultIfNoneTests(SimpleTestCase):
    @setup({"default_if_none01": '{{ a|default:"x<" }}'})
    def test_default_if_none01(self):
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
        output = self.engine.render_to_string("default_if_none02", {"a": None})
        self.assertEqual(output, "x<")


class FunctionTests(SimpleTestCase):
    def test_value(self):
        self.assertEqual(default("val", "default"), "val")

    def test_none(self):
        self.assertEqual(default(None, "default"), "default")

    def test_empty_string(self):
        self.assertEqual(default("", "default"), "default")
