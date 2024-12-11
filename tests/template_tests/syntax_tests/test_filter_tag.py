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
        output = self.engine.render_to_string("filter02")
        self.assertEqual(output, "DJANGO")

    @setup({"filter03": "{% filter upper|lower %}django{% endfilter %}"})
    def test_filter03(self):
        """

        Tests the functionality of combining 'upper' and 'lower' filters in a Django template.
        Verifies that the correct output is produced when a string is filtered with both 'upper' and 'lower' filters.
        The test case ensures the rendered template string is as expected, without the effect of either filter being applied, 
        resulting in the original string 'django'.

        """
        output = self.engine.render_to_string("filter03")
        self.assertEqual(output, "django")

    @setup({"filter04": "{% filter cut:remove %}djangospam{% endfilter %}"})
    def test_filter04(self):
        """

        Tests the 'cut' filter functionality in template rendering.

        This test case checks if the 'cut' filter can correctly remove a specified string from a given input string.
        It verifies that the output of the template render process matches the expected result after applying the filter.

        :param None:
        :returns: None
        :raises: AssertionError if the filter fails to remove the specified string.

        """
        output = self.engine.render_to_string("filter04", {"remove": "spam"})
        self.assertEqual(output, "django")

    @setup({"filter05": "{% filter safe %}fail{% endfilter %}"})
    def test_filter05(self):
        """
        Tests that using the 'safe' filter in a template raises a TemplateSyntaxError when the template engine is configured to restrict its use.
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

        Tests that the template engine correctly raises an exception when encountering a filter syntax error.

        Specifically, this test case checks that a TemplateSyntaxError is raised when a template contains an invalid filter syntax.

        The test verifies that the engine properly parses the template content and detects the filter error, ensuring that the template rendering process is properly halted and an informative error message is provided.

        :raises TemplateSyntaxError: if the template filter syntax is invalid

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("filter06")

    @setup({"filter06bis": "{% filter upper|escape %}fail{% endfilter %}"})
    def test_filter06bis(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("filter06bis")
