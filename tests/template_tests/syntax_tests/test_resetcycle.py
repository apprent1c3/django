from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class ResetCycleTagTests(SimpleTestCase):
    @setup({"resetcycle01": "{% resetcycle %}"})
    def test_resetcycle01(self):
        """
        Tests the behavior of the resetcycle tag when there are no cycles defined in the template.

        Verifies that a TemplateSyntaxError is raised with the expected error message when attempting to reset a non-existent cycle.

        This test ensures the correct handling of edge cases and validates the template engine's behavior in response to invalid or unsupported operations.\"\"\"

         Args:
            self: The test instance.

         Raises:
            TemplateSyntaxError: If no cycles are defined in the template. 

         Note:
            This function utilizes the setup decorator to configure the test template, specifically setting up a resetcycle template snippet.
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
        """
        Tests that the resetcycle template tag properly raises a TemplateSyntaxError when attempting to reset a non-existent cycle. Verifies that the error message contains the name of the undefined cycle.
        """
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
        """
        Tests the resetcycle tag in a template to verify it correctly resets and iterates through a cycle.

        The test case checks the interaction between nested cycles ('abc' and '-' '+', where 'abc' is the main cycle and '-' '+' is nested within it), 
        and the resetcycle tag. This ensures the output string matches the expected sequence after resetting the cycle.

        After rendering the template with a test range of 5, the function asserts the output matches the expected string 'ab-c-a-b-c-'. 

        This test verifies proper functionality and handling of nested cycles with reset, providing assurance the template engine behaves as expected under these conditions.
        """
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

        Tests the resetcycle template tag to ensure it properly resets and cycles through a list of values.

        The test case verifies that the resetcycle tag correctly resets the cycle \"abc\" and another cycle for alternating characters within a loop,
        resulting in the expected output string.

        Args:
            None

        Returns:
            None

        Asserts that the rendered output matches the expected string 'aa-a+a-a+a-'.

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

        Tests the functionality of the resetcycle tag in a nested loop scenario.

        Verifies that the cycle is correctly reset after each iteration of the outer loop,
        resulting in an output string with a repeated pattern of 'a' and 'b' for each inner loop iteration.

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

        Tests the functionality of the resetcycle tag within nested loops.

        The test case verifies that the resetcycle tag correctly resets the cycle iteration 
        after each iteration of the outer loop, ensuring the inner loop cycles start from 
        the beginning in each iteration of the outer loop. 

        The test expects the output to be a string where the cycles 'a' 'b' and 'X' 'Y' 
        are correctly reset and repeated in the specified pattern.

        :param self: The test class instance.
        :returns: None

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

        Tests the resetcycle function in a templating engine.

        This function verifies that the resetcycle function behaves correctly when 
        used with a cycling variable inside a for loop. It checks that the cycle 
        can be reset at a specific point, affecting the sequence of values 
        produced by the cycling variable.

        The test case renders a template with a for loop iterating over a list of 
        numbers, using two cycling variables to generate sequences of characters. 
        The resetcycle function is invoked conditionally within the loop, altering 
        the sequence produced by one of the cycling variables. The rendered output 
        is then compared to an expected result to ensure the correct behavior of 
        the resetcycle function.

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
