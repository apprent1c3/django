from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class ResetCycleTagTests(SimpleTestCase):
    @setup({"resetcycle01": "{% resetcycle %}"})
    def test_resetcycle01(self):
        """

        Tests the TemplateSyntaxError exception raised when attempting to reset a cycle 
        in a template where no cycles are defined.

        Verifies that the get_template method of the engine correctly handles the 
        resetcycle template tag and raises an error with a meaningful message when 
        there are no cycles to reset in the template.

        """
        with self.assertRaisesMessage(TemplateSyntaxError, "No cycles in template."):
            self.engine.get_template("resetcycle01")

    @setup({"resetcycle02": "{% resetcycle undefinedcycle %}"})
    def test_resetcycle02(self):
        with self.assertRaisesMessage(
            TemplateSyntaxError, "Named cycle 'undefinedcycle' does not exist."
        ):
            self.engine.get_template("resetcycle02")

    @setup({"resetcycle03": "{% cycle 'a' 'b' %}{% resetcycle undefinedcycle %}"})
    def test_resetcycle03(self):
        with self.assertRaisesMessage(
            TemplateSyntaxError, "Named cycle 'undefinedcycle' does not exist."
        ):
            self.engine.get_template("resetcycle03")

    @setup({"resetcycle04": "{% cycle 'a' 'b' as ab %}{% resetcycle undefinedcycle %}"})
    def test_resetcycle04(self):
        with self.assertRaisesMessage(
            TemplateSyntaxError, "Named cycle 'undefinedcycle' does not exist."
        ):
            self.engine.get_template("resetcycle04")

    @setup(
        {
            "resetcycle05": (
                "{% for i in test %}{% cycle 'a' 'b' %}{% resetcycle %}{% endfor %}"
            )
        }
    )
    def test_resetcycle05(self):
        """

        Tests the behavior of the 'resetcycle' tag when used within a for loop to reset a cycle.

        The cycle tag is used to cycle over a list of values. In this case, we're testing that the 'resetcycle' tag resets the cycle back to its initial value at each iteration of the loop.

        The expected output is that the cycle will always start from its first value, resulting in a string of identical characters.

        """
        output = self.engine.render_to_string("resetcycle05", {"test": list(range(5))})
        self.assertEqual(output, "aaaaa")

    @setup(
        {
            "resetcycle06": "{% cycle 'a' 'b' 'c' as abc %}"
            "{% for i in test %}"
            "{% cycle abc %}"
            "{% cycle '-' '+' %}"
            "{% resetcycle %}"
            "{% endfor %}"
        }
    )
    def test_resetcycle06(self):
        output = self.engine.render_to_string("resetcycle06", {"test": list(range(5))})
        self.assertEqual(output, "ab-c-a-b-c-")

    @setup(
        {
            "resetcycle07": "{% cycle 'a' 'b' 'c' as abc %}"
            "{% for i in test %}"
            "{% resetcycle abc %}"
            "{% cycle abc %}"
            "{% cycle '-' '+' %}"
            "{% endfor %}"
        }
    )
    def test_resetcycle07(self):
        output = self.engine.render_to_string("resetcycle07", {"test": list(range(5))})
        self.assertEqual(output, "aa-a+a-a+a-")

    @setup(
        {
            "resetcycle08": "{% for i in outer %}"
            "{% for j in inner %}"
            "{% cycle 'a' 'b' %}"
            "{% endfor %}"
            "{% resetcycle %}"
            "{% endfor %}"
        }
    )
    def test_resetcycle08(self):
        output = self.engine.render_to_string(
            "resetcycle08", {"outer": list(range(2)), "inner": list(range(3))}
        )
        self.assertEqual(output, "abaaba")

    @setup(
        {
            "resetcycle09": "{% for i in outer %}"
            "{% cycle 'a' 'b' %}"
            "{% for j in inner %}"
            "{% cycle 'X' 'Y' %}"
            "{% endfor %}"
            "{% resetcycle %}"
            "{% endfor %}"
        }
    )
    def test_resetcycle09(self):
        """

        Tests the functionality of nested cycles and their reset in templating.

        Verifies that the resetcycle tag correctly resets the cycle state in nested loops.
        The test renders a template with two nested loops, using the cycle tag to alternate
        between 'a' and 'b' in the outer loop, and 'X' and 'Y' in the inner loop. The
        resetcycle tag is used to reset the outer cycle at the end of each iteration.

        The function checks that the rendered output matches the expected result, ensuring
        that the cycles are correctly reset and the template is rendered as expected.

        """
        output = self.engine.render_to_string(
            "resetcycle09", {"outer": list(range(2)), "inner": list(range(3))}
        )
        self.assertEqual(output, "aXYXbXYX")

    @setup(
        {
            "resetcycle10": "{% for i in test %}"
            "{% cycle 'X' 'Y' 'Z' as XYZ %}"
            "{% cycle 'a' 'b' 'c' as abc %}"
            "{% if i == 1 %}"
            "{% resetcycle abc %}"
            "{% endif %}"
            "{% endfor %}"
        }
    )
    def test_resetcycle10(self):
        """

        Test the resetcycle tag functionality.

        This function ensures that the resetcycle tag behaves correctly when resetting a named cycle.
        The test checks that the cycle is properly reset and restarts from the beginning of the cycle sequence.
        It verifies that the output matches the expected result after rendering the template with the given input data.

        The main goal of this test is to validate the functionality of resetting cycles within a template,
        which is essential for maintaining the desired output when working with cycles in templating engines.

        """
        output = self.engine.render_to_string("resetcycle10", {"test": list(range(5))})
        self.assertEqual(output, "XaYbZaXbYc")

    @setup(
        {
            "resetcycle11": "{% for i in test %}"
            "{% cycle 'X' 'Y' 'Z' as XYZ %}"
            "{% cycle 'a' 'b' 'c' as abc %}"
            "{% if i == 1 %}"
            "{% resetcycle XYZ %}"
            "{% endif %}"
            "{% endfor %}"
        }
    )
    def test_resetcycle11(self):
        output = self.engine.render_to_string("resetcycle11", {"test": list(range(5))})
        self.assertEqual(output, "XaYbXcYaZb")
