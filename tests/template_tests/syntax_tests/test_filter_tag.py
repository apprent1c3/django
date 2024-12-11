from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class FilterTagTests(SimpleTestCase):
    @setup({"filter01": "{% filter upper %}{% endfilter %}"})
    def test_filter01(self):
        """

        Tests the functionality of an empty filter.

        This test case verifies that a filter with no input data returns an empty string.
        It evaluates the template 'filter01' which applies an 'upper' filter without any content,
        and checks if the resulting output is indeed empty.

        """
        output = self.engine.render_to_string("filter01")
        self.assertEqual(output, "")

    @setup({"filter02": "{% filter upper %}django{% endfilter %}"})
    def test_filter02(self):
        output = self.engine.render_to_string("filter02")
        self.assertEqual(output, "DJANGO")

    @setup({"filter03": "{% filter upper|lower %}django{% endfilter %}"})
    def test_filter03(self):
        output = self.engine.render_to_string("filter03")
        self.assertEqual(output, "django")

    @setup({"filter04": "{% filter cut:remove %}djangospam{% endfilter %}"})
    def test_filter04(self):
        """
        Tests the usage of the cut filter for string removal.

        This test case checks if the specified filter can correctly remove a 
        substring from a given string. It verifies that the filtering process 
        produces the expected output string with the specified substring removed.

        :param self: Reference to the instance of the class
        :raises AssertionError: If the output string does not match the expected string
        """
        output = self.engine.render_to_string("filter04", {"remove": "spam"})
        self.assertEqual(output, "django")

    @setup({"filter05": "{% filter safe %}fail{% endfilter %}"})
    def test_filter05(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("filter05")

    @setup({"filter05bis": "{% filter upper|safe %}fail{% endfilter %}"})
    def test_filter05bis(self):
        """
        Test that the template engine raises a TemplateSyntaxError when a filter is used with the 'safe' filter in an invalid order, specifically when 'safe' is applied after 'upper'.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("filter05bis")

    @setup({"filter06": "{% filter escape %}fail{% endfilter %}"})
    def test_filter06(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("filter06")

    @setup({"filter06bis": "{% filter upper|escape %}fail{% endfilter %}"})
    def test_filter06bis(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("filter06bis")
