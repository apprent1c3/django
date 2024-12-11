from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class WidthRatioTagTests(SimpleTestCase):
    libraries = {"custom": "template_tests.templatetags.custom"}

    @setup({"widthratio01": "{% widthratio a b 0 %}"})
    def test_widthratio01(self):
        """
        Tests that the widthratio template tag correctly calculates a ratio with a result of zero when the first value is less than the second value. 

        This test case verifies that the widthratio tag returns '0' when the first argument (a) is less than the second argument (b), ensuring correct rendering of the template with the given context.
        """
        output = self.engine.render_to_string("widthratio01", {"a": 50, "b": 100})
        self.assertEqual(output, "0")

    @setup({"widthratio02": "{% widthratio a b 100 %}"})
    def test_widthratio02(self):
        """
        Test the widthratio template tag with zero-value inputs.

        This test case checks the output of the widthratio template tag when both the 
        input value and the maximum value are zero. It verifies that the rendered 
        output is '0', ensuring the tag handles this edge case correctly.
        """
        output = self.engine.render_to_string("widthratio02", {"a": 0, "b": 0})
        self.assertEqual(output, "0")

    @setup({"widthratio03": "{% widthratio a b 100 %}"})
    def test_widthratio03(self):
        output = self.engine.render_to_string("widthratio03", {"a": 0, "b": 100})
        self.assertEqual(output, "0")

    @setup({"widthratio04": "{% widthratio a b 100 %}"})
    def test_widthratio04(self):
        """

        Tests the widthratio template tag with the ratio of two values.

        The widthratio tag is used to calculate a ratio of two values and return it as a percentage.
        In this test case, the function verifies that when the input values are 50 and 100,
        the output is '50', which represents 50% of the total value.

        Args:
            None

        Returns:
            None

        Note:
            This test is part of a larger suite to ensure the correct functionality of the widthratio template tag.

        """
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

        Tests that a TemplateSyntaxError is raised when using the widthratio template tag without proper syntax.

        This test case ensures that the templating engine correctly handles invalid template code
        and raises an exception to signal the error, rather than attempting to render the template.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("widthratio08")

    @setup({"widthratio09": "{% widthratio a b %}"})
    def test_widthratio09(self):
        """
        Tests the widthratio template tag with a setup string functionality.

        This test case ensures that the widthratio tag in a template correctly handles a setup string.
        The tag is expected to raise a TemplateSyntaxError when used in this context.

        The test case passes in the values a and b to the template and verifies that the
        expected error is raised, providing validation of the template engine's error handling.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("widthratio09", {"a": 50, "b": 100})

    @setup({"widthratio10": "{% widthratio a b 100.0 %}"})
    def test_widthratio10(self):
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
        Tests the widthratio template tag with a string value for the first argument, and integer values for the ratio and maximum width. 
        Verifies that the template tag handles this edge case by rendering an empty string when the first argument is not a numeric value.
        """
        output = self.engine.render_to_string(
            "widthratio12a", {"a": "a", "c": 100, "b": 100}
        )
        self.assertEqual(output, "")

    @setup({"widthratio12b": "{% widthratio a b c %}"})
    def test_widthratio12b(self):
        output = self.engine.render_to_string(
            "widthratio12b", {"a": None, "c": 100, "b": 100}
        )
        self.assertEqual(output, "")

    @setup({"widthratio13a": "{% widthratio a b c %}"})
    def test_widthratio13a(self):
        output = self.engine.render_to_string(
            "widthratio13a", {"a": 0, "c": 100, "b": "b"}
        )
        self.assertEqual(output, "")

    @setup({"widthratio13b": "{% widthratio a b c %}"})
    def test_widthratio13b(self):
        """

        Tests the widthratio template tag with an undefined denominator.

        Checks that when the denominator (b) is None, the tag returns an empty string.
        This ensures that the template engine handles undefined or missing values correctly and does not raise an error.

        :param none:
        :returns: Result of the test case

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

        Tests the widthratio template tag with equal ratio values.

        The widthratio tag calculates a ratio of the given values and scales it to a given maximum.
        This test checks that the tag correctly handles the case where both values are equal,
        ensuring the calculated ratio is accurately represented as a percentage of the maximum. 

        :raises AssertionError: if the calculated ratio is not correctly represented as a percentage.

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

        Test case to verify that the widthratio template tag raises a TemplateSyntaxError when used with the 'not_as' keyword.

        This test checks the error handling of the template engine when the widthratio tag is used with an invalid syntax.
        It ensures that the engine correctly identifies the 'not_as' keyword as invalid and raises a TemplateSyntaxError.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("widthratio19")

    @setup({"widthratio20": "{% widthratio a b 100 %}"})
    def test_widthratio20(self):
        """
        Tests the widthratio template tag when both input values are infinite.
        Checks if the template engine correctly handles this edge case and returns an empty string as output.
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
        """

        Tests the rendering of a template when using the widthratio filter with zero division.

        This test ensures that when the widthratio filter is used with two zero values,
        it correctly handles the division by zero and returns 0, without raising a ZeroDivisionError.

        It verifies that the output of the template rendering is as expected, 
        i.e., the variable set by the widthratio filter is correctly replaced in the template string.

        """
        output = self.engine.render_to_string("t", {"a": 0, "b": 0})
        self.assertEqual(output, "-0-")

    @setup({"t": "{% widthratio a b c as variable %}-{{ variable }}-"})
    def test_typeerror_as_var(self):
        output = self.engine.render_to_string("t", {"a": "a", "c": 100, "b": 100})
        self.assertEqual(output, "--")
