from decimal import Decimal
from sys import float_info

from django.test import SimpleTestCase
from django.utils.numberformat import format as nformat


class TestNumberFormat(SimpleTestCase):
    def test_format_number(self):
        """
        Tests the nformat function for correctly formatting numbers.

        The function nformat is used to format numbers into strings, with options for decimal places, thousand separators, and grouping.
        It handles various cases including integers, floats, and negative numbers.

        The test cases cover different scenarios such as:
        - Formatting numbers with and without decimal places
        - Using thousand separators with or without forced grouping
        - Handling negative numbers
        - Applying locale settings for thousand separators

        These tests ensure that the nformat function behaves as expected in different situations and produces the correct output.
        """
        self.assertEqual(nformat(1234, "."), "1234")
        self.assertEqual(nformat(1234.2, "."), "1234.2")
        self.assertEqual(nformat(1234, ".", decimal_pos=2), "1234.00")
        self.assertEqual(nformat(1234, ".", grouping=2, thousand_sep=","), "1234")
        self.assertEqual(
            nformat(1234, ".", grouping=2, thousand_sep=",", force_grouping=True),
            "12,34",
        )
        self.assertEqual(nformat(-1234.33, ".", decimal_pos=1), "-1234.3")
        # The use_l10n parameter can force thousand grouping behavior.
        with self.settings(USE_THOUSAND_SEPARATOR=True):
            self.assertEqual(
                nformat(1234, ".", grouping=3, thousand_sep=",", use_l10n=False), "1234"
            )
            self.assertEqual(
                nformat(1234, ".", grouping=3, thousand_sep=",", use_l10n=True), "1,234"
            )

    def test_format_string(self):
        self.assertEqual(nformat("1234", "."), "1234")
        self.assertEqual(nformat("1234.2", "."), "1234.2")
        self.assertEqual(nformat("1234", ".", decimal_pos=2), "1234.00")
        self.assertEqual(nformat("1234", ".", grouping=2, thousand_sep=","), "1234")
        self.assertEqual(
            nformat("1234", ".", grouping=2, thousand_sep=",", force_grouping=True),
            "12,34",
        )
        self.assertEqual(nformat("-1234.33", ".", decimal_pos=1), "-1234.3")
        self.assertEqual(
            nformat(
                "10000", ".", grouping=3, thousand_sep="comma", force_grouping=True
            ),
            "10comma000",
        )

    def test_large_number(self):
        """
        Test the formatting of very large numbers.

        This test case checks that the nformat function correctly handles numbers at or near the maximum value that can be represented by the system.

        It verifies the formatted output of several large numbers, including the maximum integer value, the maximum integer value plus one, twice the maximum integer value, and their negative counterparts.

        The test ensures that the formatted output is as expected, with correct handling of leading plus or minus signs and the decimal point.
        """
        most_max = (
            "{}179769313486231570814527423731704356798070567525844996"
            "598917476803157260780028538760589558632766878171540458953"
            "514382464234321326889464182768467546703537516986049910576"
            "551282076245490090389328944075868508455133942304583236903"
            "222948165808559332123348274797826204144723168738177180919"
            "29988125040402618412485836{}"
        )
        most_max2 = (
            "{}35953862697246314162905484746340871359614113505168999"
            "31978349536063145215600570775211791172655337563430809179"
            "07028764928468642653778928365536935093407075033972099821"
            "15310256415249098018077865788815173701691026788460916647"
            "38064458963316171186642466965495956524082894463374763543"
            "61838599762500808052368249716736"
        )
        int_max = int(float_info.max)
        self.assertEqual(nformat(int_max, "."), most_max.format("", "8"))
        self.assertEqual(nformat(int_max + 1, "."), most_max.format("", "9"))
        self.assertEqual(nformat(int_max * 2, "."), most_max2.format(""))
        self.assertEqual(nformat(0 - int_max, "."), most_max.format("-", "8"))
        self.assertEqual(nformat(-1 - int_max, "."), most_max.format("-", "9"))
        self.assertEqual(nformat(-2 * int_max, "."), most_max2.format("-"))

    def test_float_numbers(self):
        """
        परमeters
            ----------
            None

            Returns
            -------
            None

            Tests the number formatting function for floating point numbers.
            It checks that the function correctly formats numbers with various decimal places, 
            including very small and large numbers, with and without thousand separators. 
            The tests cover a range of scenarios, including rounding to a specified number of decimal places, 
            and using thousand separators with forced grouping.
        """
        tests = [
            (9e-10, 10, "0.0000000009"),
            (9e-19, 2, "0.00"),
            (0.00000000000099, 0, "0"),
            (0.00000000000099, 13, "0.0000000000009"),
            (1e16, None, "10000000000000000"),
            (1e16, 2, "10000000000000000.00"),
            # A float without a fractional part (3.) results in a ".0" when no
            # decimal_pos is given. Contrast that with the Decimal('3.') case
            # in test_decimal_numbers which doesn't return a fractional part.
            (3.0, None, "3.0"),
        ]
        for value, decimal_pos, expected_value in tests:
            with self.subTest(value=value, decimal_pos=decimal_pos):
                self.assertEqual(nformat(value, ".", decimal_pos), expected_value)
        # Thousand grouping behavior.
        self.assertEqual(
            nformat(1e16, ".", thousand_sep=",", grouping=3, force_grouping=True),
            "10,000,000,000,000,000",
        )
        self.assertEqual(
            nformat(
                1e16,
                ".",
                decimal_pos=2,
                thousand_sep=",",
                grouping=3,
                force_grouping=True,
            ),
            "10,000,000,000,000,000.00",
        )

    def test_decimal_numbers(self):
        """
        Tests the formatting of decimal numbers using the nformat function.

        Verifies that the function correctly handles various decimal number formats, 
        including integers, floating point numbers, exponential notation, and edge cases.
        Validates the output with and without decimal separators, thousand separators, 
        and different decimal positions. Ensures that the function behaves correctly 
        for negative numbers, zero, and extremely large or small values.

        The tests cover a wide range of scenarios, including:
        - Formatting integers and decimal numbers with and without decimal separators
        - Using thousand separators and differing decimal positions
        - Handling exponential notation and extremely large or small values
        - Formatting negative numbers, zero, and edge cases

        """
        self.assertEqual(nformat(Decimal("1234"), "."), "1234")
        self.assertEqual(nformat(Decimal("1234.2"), "."), "1234.2")
        self.assertEqual(nformat(Decimal("1234"), ".", decimal_pos=2), "1234.00")
        self.assertEqual(
            nformat(Decimal("1234"), ".", grouping=2, thousand_sep=","), "1234"
        )
        self.assertEqual(
            nformat(
                Decimal("1234"), ".", grouping=2, thousand_sep=",", force_grouping=True
            ),
            "12,34",
        )
        self.assertEqual(nformat(Decimal("-1234.33"), ".", decimal_pos=1), "-1234.3")
        self.assertEqual(
            nformat(Decimal("0.00000001"), ".", decimal_pos=8), "0.00000001"
        )
        self.assertEqual(nformat(Decimal("9e-19"), ".", decimal_pos=2), "0.00")
        self.assertEqual(nformat(Decimal(".00000000000099"), ".", decimal_pos=0), "0")
        self.assertEqual(
            nformat(
                Decimal("1e16"), ".", thousand_sep=",", grouping=3, force_grouping=True
            ),
            "10,000,000,000,000,000",
        )
        self.assertEqual(
            nformat(
                Decimal("1e16"),
                ".",
                decimal_pos=2,
                thousand_sep=",",
                grouping=3,
                force_grouping=True,
            ),
            "10,000,000,000,000,000.00",
        )
        self.assertEqual(nformat(Decimal("3."), "."), "3")
        self.assertEqual(nformat(Decimal("3.0"), "."), "3.0")
        # Very large & small numbers.
        tests = [
            ("9e9999", None, "9e+9999"),
            ("9e9999", 3, "9.000e+9999"),
            ("9e201", None, "9e+201"),
            ("9e200", None, "9e+200"),
            ("1.2345e999", 2, "1.23e+999"),
            ("9e-999", None, "9e-999"),
            ("1e-7", 8, "0.00000010"),
            ("1e-8", 8, "0.00000001"),
            ("1e-9", 8, "0.00000000"),
            ("1e-10", 8, "0.00000000"),
            ("1e-11", 8, "0.00000000"),
            ("1" + ("0" * 300), 3, "1.000e+300"),
            ("0.{}1234".format("0" * 299), 3, "0.000"),
        ]
        for value, decimal_pos, expected_value in tests:
            with self.subTest(value=value):
                self.assertEqual(
                    nformat(Decimal(value), ".", decimal_pos), expected_value
                )

    def test_decimal_subclass(self):
        class EuroDecimal(Decimal):
            """
            Wrapper for Decimal which prefixes each amount with the € symbol.
            """

            def __format__(self, specifier, **kwargs):
                """
                Formats the object as a monetary value in Euros, prefixing the amount with the Euro symbol (€). 

                The function takes a format specifier and additional keyword arguments, applies the standard formatting to the object, and then appends the Euro symbol to the result, indicating the amount is in Euros.
                """
                amount = super().__format__(specifier, **kwargs)
                return "€ {}".format(amount)

        price = EuroDecimal("1.23")
        self.assertEqual(nformat(price, ","), "€ 1,23")

    def test_empty(self):
        """
        Tests the handling of empty input values by the nformat function.

        Verifies that an empty string is formatted as an empty string and that a None value is formatted as the string 'None'. This ensures that the function behaves correctly when given empty or undefined input values.
        """
        self.assertEqual(nformat("", "."), "")
        self.assertEqual(nformat(None, "."), "None")
