from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class WidthRatioTagTests(SimpleTestCase):
    libraries = {"custom": "template_tests.templatetags.custom"}

    @setup({"widthratio01": "{% widthratio a b 0 %}"})
    def test_widthratio01(self):
        """
        Tests the widthratio template tag with a value of zero when the ratio of 'a' to 'b' is less than one. 

        Verifies that the function correctly calculates and returns the expected ratio as a string, represented as a whole number.
        """
        output = self.engine.render_to_string("widthratio01", {"a": 50, "b": 100})
        self.assertEqual(output, "0")

    @setup({"widthratio02": "{% widthratio a b 100 %}"})
    def test_widthratio02(self):
        """

        Tests the(widthratio template tag with a zero division case.

        This test ensures that the template tag correctly handles the case where both
        the numerator and denominator are zero, returning the expected output.

        """
        output = self.engine.render_to_string("widthratio02", {"a": 0, "b": 0})
        self.assertEqual(output, "0")

    @setup({"widthratio03": "{% widthratio a b 100 %}"})
    def test_widthratio03(self):
        """
        Tests the widthratio template filter with a zero numerator value, ensuring it correctly renders as '0' when the input values are at the extremes of the ratio range.
        """
        output = self.engine.render_to_string("widthratio03", {"a": 0, "b": 100})
        self.assertEqual(output, "0")

    @setup({"widthratio04": "{% widthratio a b 100 %}"})
    def test_widthratio04(self):
        output = self.engine.render_to_string("widthratio04", {"a": 50, "b": 100})
        self.assertEqual(output, "50")

    @setup({"widthratio05": "{% widthratio a b 100 %}"})
    def test_widthratio05(self):
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
        Tests the widthratio template tag to ensure it raises a TemplateSyntaxError when used incorrectly, specifically when the tag is used as a string '{{% widthratio %}}' instead of as a template tag. This test case verifies that the template engine properly handles and reports syntax errors in the widthratio tag.
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
        Tests the widthratio template tag with a ratio that results in a value less than 100.
        The function verifies that the widthratio template tag correctly calculates a ratio of two values and returns the result as a string.
        It checks if the output of the template tag is equal to the expected result, ensuring the functionality of the tag in calculating proportions.
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

        Tests the widthratio template tag with input values for \"a\" and \"b\" both set to 100, 
        and \"c\" also set to 100, where \"a\" is a non-numeric string. 

        This test case verifies that the template engine correctly handles a non-numeric value for the 
        first argument in the widthratio tag.

        """
        output = self.engine.render_to_string(
            "widthratio12a", {"a": "a", "c": 100, "b": 100}
        )
        self.assertEqual(output, "")

    @setup({"widthratio12b": "{% widthratio a b c %}"})
    def test_widthratio12b(self):
        """
        Tests the widthratio template tag with a None value for the first argument, 
        ensuring it renders an empty string when the input is invalid.
        """
        output = self.engine.render_to_string(
            "widthratio12b", {"a": None, "c": 100, "b": 100}
        )
        self.assertEqual(output, "")

    @setup({"widthratio13a": "{% widthratio a b c %}"})
    def test_widthratio13a(self):
        """
        Tests the widthratio template tag with a ratio of 0 when the first value is 0, 
        verifying it renders an empty string.
        """
        output = self.engine.render_to_string(
            "widthratio13a", {"a": 0, "c": 100, "b": "b"}
        )
        self.assertEqual(output, "")

    @setup({"widthratio13b": "{% widthratio a b c %}"})
    def test_widthratio13b(self):
        """
        Tests the widthratio template tag with a None value for the 'b' parameter to ensure it returns an empty string. This check covers a specific edge case where the denominator in the width ratio calculation is undefined.
        """
        output = self.engine.render_to_string(
            "widthratio13b", {"a": 0, "c": 100, "b": None}
        )
        self.assertEqual(output, "")

    @setup({"widthratio14a": "{% widthratio a b c %}"})
    def test_widthratio14a(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("widthratio14a", {"a": 0, "c": "c", "b": 100})

    @setup({"widthratio14b": "{% widthratio a b c %}"})
    def test_widthratio14b(self):
        """
        Tests the raising of a TemplateSyntaxError when using the widthratio template tag with an invalid value for the number of parts, specifically a null value for the variable c. This test ensures that the template engine correctly handles and reports invalid input.
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
        Tests the widthratio17 template tag by rendering a template with a widthratio statement and verifying the output is as expected. The widthratio tag calculates a ratio of two values, a and b, scaled to a given maximum value, in this case 100. This test case checks the functionality of the widthratio tag when a and b are equal, ensuring it returns the correct scaled value.
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

        Tests the widthratio template tag to ensure it raises a TemplateSyntaxError when used with an unsupported argument type.

        The test case verifies that the template engine correctly handles invalid input by raising an exception.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("widthratio19")

    @setup({"widthratio20": "{% widthratio a b 100 %}"})
    def test_widthratio20(self):
        """
        Tests the behavior of the widthratio template tag when both input values are infinity, ensuring it renders an empty string.
        """
        output = self.engine.render_to_string(
            "widthratio20", {"a": float("inf"), "b": float("inf")}
        )
        self.assertEqual(output, "")

    @setup({"widthratio21": "{% widthratio a b 100 %}"})
    def test_widthratio21(self):
        output = self.engine.render_to_string(
            "widthratio21", {"a": float("inf"), "b": 2}
        )
        self.assertEqual(output, "")

    @setup({"t": "{% widthratio a b 100 as variable %}-{{ variable }}-"})
    def test_zerodivisionerror_as_var(self):
        output = self.engine.render_to_string("t", {"a": 0, "b": 0})
        self.assertEqual(output, "-0-")

    @setup({"t": "{% widthratio a b c as variable %}-{{ variable }}-"})
    def test_typeerror_as_var(self):
        """
        Test the rendering behavior when a TypeError occurs while assigning the result of the widthratio template tag to a variable.

        The test checks that the template engine correctly handles the TypeError by rendering the variable as an empty string, resulting in the expected output. This test ensures that the template engine prevents the TypeError from propagating and instead provides a more controlled and predictable rendering outcome.
        """
        output = self.engine.render_to_string("t", {"a": "a", "c": 100, "b": 100})
        self.assertEqual(output, "--")
