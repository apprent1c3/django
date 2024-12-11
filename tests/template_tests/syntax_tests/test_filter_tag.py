from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class FilterTagTests(SimpleTestCase):
    @setup({"filter01": "{% filter upper %}{% endfilter %}"})
    def test_filter01(self):
        output = self.engine.render_to_string("filter01")
        self.assertEqual(output, "")

    @setup({"filter02": "{% filter upper %}django{% endfilter %}"})
    def test_filter02(self):
        """

        Tests the functionality of a template filter to convert text to uppercase.

        This test case verifies that the filter correctly transforms the input string 'django' into 'DJANGO',
        ensuring that the filtering mechanism is working as expected in the template engine.

        """
        output = self.engine.render_to_string("filter02")
        self.assertEqual(output, "DJANGO")

    @setup({"filter03": "{% filter upper|lower %}django{% endfilter %}"})
    def test_filter03(self):
        """

        Tests the usage of multiple filters in a Django template.

        The filter chain applies both 'upper' and 'lower' filters to the input string.
        This test checks if the output is rendered as expected after applying these filters sequentially.

        """
        output = self.engine.render_to_string("filter03")
        self.assertEqual(output, "django")

    @setup({"filter04": "{% filter cut:remove %}djangospam{% endfilter %}"})
    def test_filter04(self):
        output = self.engine.render_to_string("filter04", {"remove": "spam"})
        self.assertEqual(output, "django")

    @setup({"filter05": "{% filter safe %}fail{% endfilter %}"})
    def test_filter05(self):
        """
        Tests that using the 'safe' filter without proper context raises a TemplateSyntaxError.

        This test ensures that the template engine correctly handles the 'safe' filter and raises an error when it is used in an invalid context, preventing potential security vulnerabilities.

        :raises: TemplateSyntaxError
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("filter05")

    @setup({"filter05bis": "{% filter upper|safe %}fail{% endfilter %}"})
    def test_filter05bis(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("filter05bis")

    @setup({"filter06": "{% filter escape %}fail{% endfilter %}"})
    def test_filter06(self):
        """
        Tests that the template engine correctly raises a TemplateSyntaxError when encountering an invalid filter syntax.

        This test case verifies that the template engine properly handles and reports errors when a filter is used incorrectly, ensuring that the template syntax is valid and can be parsed correctly. The test is specifically designed to check the engine's behavior when a filter is used with an invalid syntax, and it checks that the expected error is raised in such cases.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("filter06")

    @setup({"filter06bis": "{% filter upper|escape %}fail{% endfilter %}"})
    def test_filter06bis(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("filter06bis")
