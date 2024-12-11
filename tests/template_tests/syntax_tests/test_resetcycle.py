from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class ResetCycleTagTests(SimpleTestCase):
    @setup({"resetcycle01": "{% resetcycle %}"})
    def test_resetcycle01(self):
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
        """
        Test that the resetcycle tag raises a TemplateSyntaxError when attempting to reset a cycle that does not exist.

        :raises: TemplateSyntaxError
        """
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

        Tests the behavior of the resetcycle tag in a Jinja2 template.

        The function renders a template containing a for loop with a cycle tag and 
        a resetcycle tag. The cycle tag alternates between two values, but the 
        resetcycle tag resets the cycle after each iteration. The function 
        verifies that the output is as expected, with the first value of the cycle 
        repeating for the entire loop.

        The test case covers the scenario where the resetcycle tag is used within 
        a loop, ensuring that the cycle is properly reset at the end of each 
        iteration.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the rendered output does not match the expected output.

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
        """
        Tests the functionality of resetting a cycle within a for loop.

        This function verifies that the resetcycle tag resets the cycle to its initial state, 
        allowing for proper repetition of the cycle's sequence. The test uses a cycle with 
        three values (a, b, c) and another cycle with two values (-, +) to demonstrate 
        the reset functionality within a loop.

        The expected output is a string where the cycle 'a' 'b' 'c' is reset at each iteration 
        of the loop, resulting in the repetition of the first value 'a' in the cycle, combined 
        with an alternating pattern of '-' and '+' from the second cycle.

        The test passes if the rendered output matches the expected string 'aa-a+a-a+a-'. 
        """
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
        """

        Tests the functionality of resetting a cycle in a nested loop.

        This test case verifies that the resetcycle tag correctly resets the cycle
        at the end of each outer loop iteration, allowing the cycle to start anew
        in the next iteration. The test uses a simple template with two nested loops
        to demonstrate this behavior.

        The expected output is a string where the cycle is correctly reset after each
        outer loop iteration, resulting in a specific output pattern.

        """
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
        Tests the functionality of resetting a cycle within nested loops.

        This test case evaluates how the template engine handles resetting a cycle
        when it's used inside nested loops, ensuring that the cycle is properly reset
        at the end of each outer loop iteration, producing the expected output sequence.

        The test uses two lists, 'outer' and 'inner', with specific lengths to simulate
        the nested loop structure, and verifies that the rendered output matches the
        predicted sequence after the cycle is reset at each iteration of the outer loop.
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

        Tests the functionality of the resetcycle tag with nested cycles.

        The function verifies that the resetcycle tag correctly resets the cycle when a certain condition is met, 
        in this case when the loop counter equals 1. It checks if the output string matches the expected result, 
        ensuring that the cycles are reset and continued as expected.

        :raises AssertionError: If the rendered output does not match the expected string 'XaYbZaXbYc'.

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
