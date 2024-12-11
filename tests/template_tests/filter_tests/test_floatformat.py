from decimal import Decimal, localcontext

from django.template.defaultfilters import floatformat
from django.test import SimpleTestCase
from django.utils import translation
from django.utils.safestring import mark_safe

from ..utils import setup


class FloatformatTests(SimpleTestCase):
    @setup(
        {
            "floatformat01": (
                "{% autoescape off %}{{ a|floatformat }} {{ b|floatformat }}"
                "{% endautoescape %}"
            )
        }
    )
    def test_floatformat01(self):
        """

        Tests the floatformat filter in a template.

        This test case checks if the floatformat filter correctly formats floating point numbers.
        It provides two values, one as a string and the other as a marked safe string, to verify
        if the filter works as expected in both cases. The test compares the rendered template
        output with the expected result to ensure the filter is applied correctly.

        """
        output = self.engine.render_to_string(
            "floatformat01", {"a": "1.42", "b": mark_safe("1.42")}
        )
        self.assertEqual(output, "1.4 1.4")

    @setup({"floatformat02": "{{ a|floatformat }} {{ b|floatformat }}"})
    def test_floatformat02(self):
        """
        },{
            :param None: 
            :return: None 
            :raises: AssertionError if the rendered string does not match '1.4 1.4'

            Test the functionality of floatformat filter in a templating engine. This function checks if the floatformat filter 
            correctly formats the given floating point numbers to one decimal place. It also verifies that the filter works with 
            both string and mark_safe inputs. The test case asserts that the formatted output is '1.4 1.4' for the given input 
            values '1.42' and '1.42'.
        """
        output = self.engine.render_to_string(
            "floatformat02", {"a": "1.42", "b": mark_safe("1.42")}
        )
        self.assertEqual(output, "1.4 1.4")


class FunctionTests(SimpleTestCase):
    def test_inputs(self):
        """
        ..: 
            Test the function floatformat with a variety of inputs, including floating point numbers and Decimal objects.
            It covers different cases such as numbers with and without decimal points, negative numbers, and numbers with a large or small number of decimal places.
            The tests include checking the function's behavior with different precision settings and invalid input.
        """
        self.assertEqual(floatformat(7.7), "7.7")
        self.assertEqual(floatformat(7.0), "7")
        self.assertEqual(floatformat(0.7), "0.7")
        self.assertEqual(floatformat(-0.7), "-0.7")
        self.assertEqual(floatformat(0.07), "0.1")
        self.assertEqual(floatformat(-0.07), "-0.1")
        self.assertEqual(floatformat(0.007), "0.0")
        self.assertEqual(floatformat(0.0), "0")
        self.assertEqual(floatformat(7.7, 0), "8")
        self.assertEqual(floatformat(7.7, 3), "7.700")
        self.assertEqual(floatformat(6.000000, 3), "6.000")
        self.assertEqual(floatformat(6.200000, 3), "6.200")
        self.assertEqual(floatformat(6.200000, -3), "6.200")
        self.assertEqual(floatformat(13.1031, -3), "13.103")
        self.assertEqual(floatformat(11.1197, -2), "11.12")
        self.assertEqual(floatformat(11.0000, -2), "11")
        self.assertEqual(floatformat(11.000001, -2), "11.00")
        self.assertEqual(floatformat(8.2798, 3), "8.280")
        self.assertEqual(floatformat(5555.555, 2), "5555.56")
        self.assertEqual(floatformat(001.3000, 2), "1.30")
        self.assertEqual(floatformat(0.12345, 2), "0.12")
        self.assertEqual(floatformat(Decimal("555.555"), 2), "555.56")
        self.assertEqual(floatformat(Decimal("09.000")), "9")
        self.assertEqual(
            floatformat(Decimal("123456.123456789012345678901"), 21),
            "123456.123456789012345678901",
        )
        self.assertEqual(floatformat(13.1031, "bar"), "13.1031")
        self.assertEqual(floatformat(18.125, 2), "18.13")
        self.assertEqual(
            floatformat(-1.323297138040798e35, 2),
            "-132329713804079800000000000000000000.00",
        )
        self.assertEqual(
            floatformat(-1.323297138040798e35, -2),
            "-132329713804079800000000000000000000",
        )
        self.assertEqual(floatformat(1.5e-15, 20), "0.00000000000000150000")
        self.assertEqual(floatformat(1.5e-15, -20), "0.00000000000000150000")
        self.assertEqual(floatformat(1.00000000000000015, 16), "1.0000000000000002")

    def test_invalid_inputs(self):
        """
        Tests the floatformat function with a variety of invalid inputs.

        Checks that the function correctly handles and returns an empty string for different types of invalid input values, including:
        - None and empty data structures (lists, dictionaries)
        - Objects and strings with non-numeric content
        - Strings with unsupported exponential notation
        - Strings containing special characters or Unicode

        The test cases cover various edge cases, ensuring the floatformat function behaves as expected when given malformed or non-numeric input, with and without an optional argument.
        """
        cases = [
            # Non-numeric strings.
            None,
            [],
            {},
            object(),
            "abc123",
            "123abc",
            "foo",
            "error",
            "¿Cómo esta usted?",
            # Scientific notation - missing exponent value.
            "1e",
            "1e+",
            "1e-",
            # Scientific notation - missing base number.
            "e400",
            "e+400",
            "e-400",
            # Scientific notation - invalid exponent value.
            "1e^2",
            "1e2e3",
            "1e2a",
            "1e2.0",
            "1e2,0",
            # Scientific notation - misplaced decimal point.
            "1e.2",
            "1e2.",
            # Scientific notation - misplaced '+' sign.
            "1+e2",
            "1e2+",
        ]
        for value in cases:
            with self.subTest(value=value):
                self.assertEqual(floatformat(value), "")
            with self.subTest(value=value, arg="bar"):
                self.assertEqual(floatformat(value, "bar"), "")

    def test_force_grouping(self):
        with translation.override("en"):
            self.assertEqual(floatformat(10000, "g"), "10,000")
            self.assertEqual(floatformat(66666.666, "1g"), "66,666.7")
            # Invalid suffix.
            self.assertEqual(floatformat(10000, "g2"), "10000")
        with translation.override("de", deactivate=True):
            self.assertEqual(floatformat(10000, "g"), "10.000")
            self.assertEqual(floatformat(66666.666, "1g"), "66.666,7")
            # Invalid suffix.
            self.assertEqual(floatformat(10000, "g2"), "10000")

    def test_unlocalize(self):
        """

        Test the unlocalization of float formatting.

        This test case verifies that the float formatting behaves as expected when the
        locale is overridden or deactivated. It checks the formatting of numbers with and
        without thousand separators, and ensures that the correct decimal and thousand
        separators are used based on the provided format specifiers and system settings.

        The test covers various formatting options, including the use of a decimal point or
        comma as the decimal separator, the handling of thousand separators, and the
        application of number grouping rules. The expected outputs are validated to ensure
        that the float formatting function produces the correct results in different
        scenarios.

        """
        with translation.override("de", deactivate=True):
            self.assertEqual(floatformat(66666.666, "2"), "66666,67")
            self.assertEqual(floatformat(66666.666, "2u"), "66666.67")
            with self.settings(
                USE_THOUSAND_SEPARATOR=True,
                NUMBER_GROUPING=3,
                THOUSAND_SEPARATOR="!",
            ):
                self.assertEqual(floatformat(66666.666, "2gu"), "66!666.67")
                self.assertEqual(floatformat(66666.666, "2ug"), "66!666.67")
            # Invalid suffix.
            self.assertEqual(floatformat(66666.666, "u2"), "66666.666")

    def test_zero_values(self):
        self.assertEqual(floatformat(0, 6), "0.000000")
        self.assertEqual(floatformat(0, 7), "0.0000000")
        self.assertEqual(floatformat(0, 10), "0.0000000000")
        self.assertEqual(
            floatformat(0.000000000000000000015, 20), "0.00000000000000000002"
        )
        self.assertEqual(floatformat("0.00", 0), "0")
        self.assertEqual(floatformat(Decimal("0.00"), 0), "0")
        self.assertEqual(floatformat("0.0000", 2), "0.00")
        self.assertEqual(floatformat(Decimal("0.0000"), 2), "0.00")
        self.assertEqual(floatformat("0.000000", 4), "0.0000")
        self.assertEqual(floatformat(Decimal("0.000000"), 4), "0.0000")

    def test_negative_zero_values(self):
        """
        Tests the functionality of floatformat with negative zero values.

        This test case verifies that the floatformat function correctly handles negative numbers
        close to zero, ensuring that they are formatted as expected with varying numbers of decimal places.

        The test consists of multiple sub-tests, each covering a different scenario where a negative number
        near zero is formatted with a specified number of decimal places, and the result is compared to an
        expected output string. 

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If any of the test cases fail, indicating an issue with the floatformat function's 
            handling of negative zero values.

        """
        tests = [
            (-0.01, -1, "0.0"),
            (-0.001, 2, "0.00"),
            (-0.499, 0, "0"),
        ]
        for num, decimal_places, expected in tests:
            with self.subTest(num=num, decimal_places=decimal_places):
                self.assertEqual(floatformat(num, decimal_places), expected)

    def test_infinity(self):
        pos_inf = float(1e30000)
        neg_inf = float(-1e30000)
        self.assertEqual(floatformat(pos_inf), "inf")
        self.assertEqual(floatformat(neg_inf), "-inf")
        self.assertEqual(floatformat(pos_inf / pos_inf), "nan")

    def test_float_dunder_method(self):
        """

        Tests the float dunder method by creating a custom FloatWrapper class.

        This test case verifies that the floatformat function correctly formats the floating point value 
        encapsulated within the FloatWrapper class, ensuring proper rounding and precision handling.

        The test checks if the floatformat function can correctly extract the floating point value from 
        the custom class and format it to the specified precision, in this case, two decimal places.

        """
        class FloatWrapper:
            def __init__(self, value):
                self.value = value

            def __float__(self):
                return self.value

        self.assertEqual(floatformat(FloatWrapper(11.000001), -2), "11.00")

    def test_low_decimal_precision(self):
        """
        #15789
        """
        with localcontext() as ctx:
            ctx.prec = 2
            self.assertEqual(floatformat(1.2345, 2), "1.23")
            self.assertEqual(floatformat(15.2042, -3), "15.204")
            self.assertEqual(floatformat(1.2345, "2"), "1.23")
            self.assertEqual(floatformat(15.2042, "-3"), "15.204")
            self.assertEqual(floatformat(Decimal("1.2345"), 2), "1.23")
            self.assertEqual(floatformat(Decimal("15.2042"), -3), "15.204")
