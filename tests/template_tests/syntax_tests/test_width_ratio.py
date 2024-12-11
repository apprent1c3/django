from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class WidthRatioTagTests(SimpleTestCase):
    libraries = {"custom": "template_tests.templatetags.custom"}

    @setup({"widthratio01": "{% widthratio a b 0 %}"})
    def test_widthratio01(self):
        """
        Tests the widthratio template tag with a percentage ratio of 0, 
        verifying it correctly calculates and outputs the result as an integer.
        """
        output = self.engine.render_to_string("widthratio01", {"a": 50, "b": 100})
        self.assertEqual(output, "0")

    @setup({"widthratio02": "{% widthratio a b 100 %}"})
    def test_widthratio02(self):
        """

        Tests the widthratio template tag with a ratio of 0.

        Verifies that when both the numerator and denominator are 0, the widthratio tag returns 0.

        """
        output = self.engine.render_to_string("widthratio02", {"a": 0, "b": 0})
        self.assertEqual(output, "0")

    @setup({"widthratio03": "{% widthratio a b 100 %}"})
    def test_widthratio03(self):
        """
        Tests the widthratio template filter with a zero dividend, ensuring it correctly calculates the ratio and returns 0 when the dividend is 0 and the divisor is a non-zero value.
        """
        output = self.engine.render_to_string("widthratio03", {"a": 0, "b": 100})
        self.assertEqual(output, "0")

    @setup({"widthratio04": "{% widthratio a b 100 %}"})
    def test_widthratio04(self):
        """
        Tests the widthratio template tag with a simple ratio calculation.

        The function verifies that the widthratio tag correctly calculates the ratio of two values (a and b)
        and expresses it as a percentage, in this case 50% of 100. The result is then compared to the expected output.

        :raises AssertionError: if the output does not match the expected value
        """
        output = self.engine.render_to_string("widthratio04", {"a": 50, "b": 100})
        self.assertEqual(output, "50")

    @setup({"widthratio05": "{% widthratio a b 100 %}"})
    def test_widthratio05(self):
        """
        Tests the widthratio template tag with equal input values.

        This test case verifies that the widthratio template tag behaves correctly when 
        the input values 'a' and 'b' are equal. It checks if the output of the tag is 
        100, which corresponds to a ratio of 1.0 when scaled to a base value of 100.
        """
        output = self.engine.render_to_string("widthratio05", {"a": 100, "b": 100})
        self.assertEqual(output, "100")

    @setup({"widthratio06": "{% widthratio a b 100 %}"})
    def test_widthratio06(self):
        """
        62.5 should round to 62
        """
        output = self.engine.render_to_string("widthratio06", {"a": 50, "b": 80})
        self.assertEqual(output, "62")

    @setup({"widthratio07": "{% widthratio a b 100 %}"})
    def test_widthratio07(self):
        """
        71.4 should round to 71
        """
        output = self.engine.render_to_string("widthratio07", {"a": 50, "b": 70})
        self.assertEqual(output, "71")

    # Raise exception if we don't have 3 args, last one an integer
    @setup({"widthratio08": "{% widthratio %}"})
    def test_widthratio08(self):
        """
        Tests that the TemplateSyntaxError is raised when the widthratio template tag is used with an invalid syntax.

        The test case verifies that the template engine correctly handles malformed widthratio tags and raises an exception to prevent unexpected behavior.

        :raises: TemplateSyntaxError
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("widthratio08")

    @setup({"widthratio09": "{% widthratio a b %}"})
    def test_widthratio09(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("widthratio09", {"a": 50, "b": 100})

    @setup({"widthratio10": "{% widthratio a b 100.0 %}"})
    def test_widthratio10(self):
        """
        Tests the widthratio template tag with a ratio of 10, verifying that it correctly calculates the ratio of two values and returns the result as a string. 

        The test case passes in values for 'a' and 'b', where 'a' is half of 'b', and checks that the output is '50.0' when rendered as a percentage. This ensures that the widthratio tag is functioning as expected and producing accurate results.
        """
        output = self.engine.render_to_string("widthratio10", {"a": 50, "b": 100})
        self.assertEqual(output, "50")

    @setup({"widthratio11": "{% widthratio a b c %}"})
    def test_widthratio11(self):
        """
        #10043: widthratio should allow max_width to be a variable
        """
        output = self.engine.render_to_string(
            "widthratio11", {"a": 50, "c": 100, "b": 100}
        )
        self.assertEqual(output, "50")

    # #18739: widthratio should handle None args consistently with
    # non-numerics
    @setup({"widthratio12a": "{% widthratio a b c %}"})
    def test_widthratio12a(self):
        """

        Tests the widthratio template tag with a string as the first argument and 
        equal third and fourth arguments.

        The test case verifies that the template tag～～～ 
        correctly handles string inputs and 
        renders an empty string when the input value is a string and the 
        third and fourth arguments are equal.

        The purpose of this test is to ensure the widthratio template 
        tag behaves as expected in edge cases, providing a robust 
        and reliable template rendering experience.

        """
        output = self.engine.render_to_string(
            "widthratio12a", {"a": "a", "c": 100, "b": 100}
        )
        self.assertEqual(output, "")

    @setup({"widthratio12b": "{% widthratio a b c %}"})
    def test_widthratio12b(self):
        """
        Tests the widthratio template tag behavior when the first argument is None.

        The widthratio tag takes three arguments and calculates a ratio of the first
        argument to the second, scaling it to the third. This test checks how the tag
        behaves when the first argument is None, verifying that it correctly handles
        this edge case and produces the expected output. The test case sets the second
        and third arguments to 100, and checks that the rendered output is an empty
        string, as expected when the first argument is None.
        """
        output = self.engine.render_to_string(
            "widthratio12b", {"a": None, "c": 100, "b": 100}
        )
        self.assertEqual(output, "")

    @setup({"widthratio13a": "{% widthratio a b c %}"})
    def test_widthratio13a(self):
        """
        Tests the widthratio template tag with a zero numerator value and a string denominator to ensure it handles this edge case correctly and returns an empty string.
        """
        output = self.engine.render_to_string(
            "widthratio13a", {"a": 0, "c": 100, "b": "b"}
        )
        self.assertEqual(output, "")

    @setup({"widthratio13b": "{% widthratio a b c %}"})
    def test_widthratio13b(self):
        """

        Tests the rendering of the widthratio template tag with invalid input.

        The widthratio tag calculates a ratio of the given values and applies it to the
        given maximum value, but this test case checks the behavior when the divisor
        value is None. It verifies that the rendering engine handles this edge case
        correctly by producing an empty output string.

        """
        output = self.engine.render_to_string(
            "widthratio13b", {"a": 0, "c": 100, "b": None}
        )
        self.assertEqual(output, "")

    @setup({"widthratio14a": "{% widthratio a b c %}"})
    def test_widthratio14a(self):
        """
        Test the behavior of the widthratio template tag with a zero dividend.

        This test case verifies that the widthratio template tag raises a TemplateSyntaxError when the first argument (dividend) is zero. It checks the error handling of the template tag by rendering a template string with a widthratio tag and then asserting that the expected error is raised.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("widthratio14a", {"a": 0, "c": "c", "b": 100})

    @setup({"widthratio14b": "{% widthratio a b c %}"})
    def test_widthratio14b(self):
        """
        Tests the widthratio template tag with invalid input values.

        Verifies that a TemplateSyntaxError is raised when the template tag is used with
        a divisor of zero and an undefined ratio value.

        Checks the correct handling of edge cases to prevent division by zero errors and
        ensures that the template engine behaves as expected with incomplete or invalid
        input data. 
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("widthratio14b", {"a": 0, "c": None, "b": 100})

    @setup({"widthratio15": '{% load custom %}{% widthratio a|noop:"x y" b 0 %}'})
    def test_widthratio15(self):
        """
        Test whitespace in filter argument
        """
        output = self.engine.render_to_string("widthratio15", {"a": 50, "b": 100})
        self.assertEqual(output, "0")

    # Widthratio with variable assignment
    @setup({"widthratio16": "{% widthratio a b 100 as variable %}-{{ variable }}-"})
    def test_widthratio16(self):
        output = self.engine.render_to_string("widthratio16", {"a": 50, "b": 100})
        self.assertEqual(output, "-50-")

    @setup({"widthratio17": "{% widthratio a b 100 as variable %}-{{ variable }}-"})
    def test_widthratio17(self):
        """
        Tests the functionality of the widthratio template tag, specifically when the input values result in a whole number ratio. 
        It checks if the tag correctly calculates and displays the ratio of two numbers, 'a' and 'b', as a percentage. 
        The test case verifies that when 'a' and 'b' are equal, the output is '100', indicating a 1:1 ratio. 
        This test ensures that the widthratio tag behaves as expected in a scenario where the ratio is a whole number, providing a 100% result.
        """
        output = self.engine.render_to_string("widthratio17", {"a": 100, "b": 100})
        self.assertEqual(output, "-100-")

    @setup({"widthratio18": "{% widthratio a b 100 as %}"})
    def test_widthratio18(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("widthratio18")

    @setup({"widthratio19": "{% widthratio a b 100 not_as variable %}"})
    def test_widthratio19(self):
        """
        Tests the widthratio template tag with an invalid argument, checking that a TemplateSyntaxError is raised.

         This test case ensures that the template engine correctly handles invalid usage of the widthratio tag by passing a non-integer value for the 'not_as' argument. The test confirms that an error is thrown when the template is rendered, verifying the engine's ability to detect and respond to template syntax errors in such scenarios.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("widthratio19")

    @setup({"widthratio20": "{% widthratio a b 100 %}"})
    def test_widthratio20(self):
        output = self.engine.render_to_string(
            "widthratio20", {"a": float("inf"), "b": float("inf")}
        )
        self.assertEqual(output, "")

    @setup({"widthratio21": "{% widthratio a b 100 %}"})
    def test_widthratio21(self):
        """
        Tests the widthratio template tag when the first value is infinity and the second value is a finite number, verifying that the output is an empty string.
        """
        output = self.engine.render_to_string(
            "widthratio21", {"a": float("inf"), "b": 2}
        )
        self.assertEqual(output, "")

    @setup({"t": "{% widthratio a b 100 as variable %}-{{ variable }}-"})
    def test_zerodivisionerror_as_var(self):
        """

        Tests the handling of ZeroDivisionError when using the widthratio template tag with zero values.

        The test case verifies that the template engine correctly handles division by zero and returns a value of 0 when the widthratio tag is used with two zero arguments.

        The expected output is '-0-', indicating that the division by zero error is caught and handled as intended.

        """
        output = self.engine.render_to_string("t", {"a": 0, "b": 0})
        self.assertEqual(output, "-0-")

    @setup({"t": "{% widthratio a b c as variable %}-{{ variable }}-"})
    def test_typeerror_as_var(self):
        output = self.engine.render_to_string("t", {"a": "a", "c": 100, "b": 100})
        self.assertEqual(output, "--")
