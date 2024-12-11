import decimal

from django.core.exceptions import ValidationError
from django.forms import DecimalField, NumberInput, Widget
from django.test import SimpleTestCase, override_settings
from django.utils import formats, translation

from . import FormFieldAssertionsMixin


class DecimalFieldTest(FormFieldAssertionsMixin, SimpleTestCase):
    def test_decimalfield_1(self):
        """

        Test DecimalField validation and rendering.

        This test suite checks the functionality of a DecimalField with specific constraints.
        The DecimalField has a maximum of 4 digits, with 2 of those digits allowed after the decimal point.
        The tests cover various scenarios, including required field validation, cleaning of different input types,
        and validation against the field's constraints.

        The test ensures that:

        * The field is rendered as an HTML number input with the correct attributes.
        * The field raises a ValidationError when not provided (i.e., it is required).
        * The field correctly cleans and converts input values to decimal numbers.
        * The field validates input values against the specified constraints, including maximum digits and decimal places.

        Overall, this test ensures that the DecimalField behaves as expected and provides accurate and helpful error messages.

        """
        f = DecimalField(max_digits=4, decimal_places=2)
        self.assertWidgetRendersTo(
            f, '<input id="id_f" step="0.01" type="number" name="f" required>'
        )
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        self.assertEqual(f.clean("1"), decimal.Decimal("1"))
        self.assertIsInstance(f.clean("1"), decimal.Decimal)
        self.assertEqual(f.clean("23"), decimal.Decimal("23"))
        self.assertEqual(f.clean("3.14"), decimal.Decimal("3.14"))
        self.assertEqual(f.clean(3.14), decimal.Decimal("3.14"))
        self.assertEqual(f.clean(decimal.Decimal("3.14")), decimal.Decimal("3.14"))
        self.assertEqual(f.clean("1.0 "), decimal.Decimal("1.0"))
        self.assertEqual(f.clean(" 1.0"), decimal.Decimal("1.0"))
        self.assertEqual(f.clean(" 1.0 "), decimal.Decimal("1.0"))
        with self.assertRaisesMessage(
            ValidationError, "'Ensure that there are no more than 4 digits in total.'"
        ):
            f.clean("123.45")
        with self.assertRaisesMessage(
            ValidationError, "'Ensure that there are no more than 2 decimal places.'"
        ):
            f.clean("1.234")
        msg = "'Ensure that there are no more than 2 digits before the decimal point.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("123.4")
        self.assertEqual(f.clean("-12.34"), decimal.Decimal("-12.34"))
        with self.assertRaisesMessage(
            ValidationError, "'Ensure that there are no more than 4 digits in total.'"
        ):
            f.clean("-123.45")
        self.assertEqual(f.clean("-.12"), decimal.Decimal("-0.12"))
        self.assertEqual(f.clean("-00.12"), decimal.Decimal("-0.12"))
        self.assertEqual(f.clean("-000.12"), decimal.Decimal("-0.12"))
        with self.assertRaisesMessage(
            ValidationError, "'Ensure that there are no more than 2 decimal places.'"
        ):
            f.clean("-000.123")
        with self.assertRaisesMessage(
            ValidationError, "'Ensure that there are no more than 4 digits in total.'"
        ):
            f.clean("-000.12345")
        self.assertEqual(f.max_digits, 4)
        self.assertEqual(f.decimal_places, 2)
        self.assertIsNone(f.max_value)
        self.assertIsNone(f.min_value)

    def test_enter_a_number_error(self):
        f = DecimalField(max_value=1, max_digits=4, decimal_places=2)
        values = (
            "-NaN",
            "NaN",
            "+NaN",
            "-sNaN",
            "sNaN",
            "+sNaN",
            "-Inf",
            "Inf",
            "+Inf",
            "-Infinity",
            "Infinity",
            "+Infinity",
            "a",
            "łąść",
            "1.0a",
            "--0.12",
        )
        for value in values:
            with (
                self.subTest(value=value),
                self.assertRaisesMessage(ValidationError, "'Enter a number.'"),
            ):
                f.clean(value)

    def test_decimalfield_2(self):
        f = DecimalField(max_digits=4, decimal_places=2, required=False)
        self.assertIsNone(f.clean(""))
        self.assertIsNone(f.clean(None))
        self.assertEqual(f.clean("1"), decimal.Decimal("1"))
        self.assertEqual(f.max_digits, 4)
        self.assertEqual(f.decimal_places, 2)
        self.assertIsNone(f.max_value)
        self.assertIsNone(f.min_value)

    def test_decimalfield_3(self):
        """

        Tests the functionality of a DecimalField with specified constraints.

        This test case covers the rendering of the DecimalField widget as an HTML input
        element with correct attributes, such as step, min, max, and type. It also verifies
        that the field enforces its constraints, including maximum and minimum values,
        through validation. The test checks that valid decimal values are correctly
        parsed and cleaned, while invalid values raise a ValidationError with a
        meaningful error message. Additionally, it ensures that the field's properties,
        such as max_digits, decimal_places, max_value, and min_value, are correctly set
        and accessible.

        The test exercises various input scenarios, including values at the boundaries of
        the allowed range, to guarantee the robustness and correctness of the DecimalField
        implementation.

        """
        f = DecimalField(
            max_digits=4,
            decimal_places=2,
            max_value=decimal.Decimal("1.5"),
            min_value=decimal.Decimal("0.5"),
        )
        self.assertWidgetRendersTo(
            f,
            '<input step="0.01" name="f" min="0.5" max="1.5" type="number" id="id_f" '
            "required>",
        )
        with self.assertRaisesMessage(
            ValidationError, "'Ensure this value is less than or equal to 1.5.'"
        ):
            f.clean("1.6")
        with self.assertRaisesMessage(
            ValidationError, "'Ensure this value is greater than or equal to 0.5.'"
        ):
            f.clean("0.4")
        self.assertEqual(f.clean("1.5"), decimal.Decimal("1.5"))
        self.assertEqual(f.clean("0.5"), decimal.Decimal("0.5"))
        self.assertEqual(f.clean(".5"), decimal.Decimal("0.5"))
        self.assertEqual(f.clean("00.50"), decimal.Decimal("0.50"))
        self.assertEqual(f.max_digits, 4)
        self.assertEqual(f.decimal_places, 2)
        self.assertEqual(f.max_value, decimal.Decimal("1.5"))
        self.assertEqual(f.min_value, decimal.Decimal("0.5"))

    def test_decimalfield_4(self):
        f = DecimalField(decimal_places=2)
        with self.assertRaisesMessage(
            ValidationError, "'Ensure that there are no more than 2 decimal places.'"
        ):
            f.clean("0.00000001")

    def test_decimalfield_5(self):
        f = DecimalField(max_digits=3)
        # Leading whole zeros "collapse" to one digit.
        self.assertEqual(f.clean("0000000.10"), decimal.Decimal("0.1"))
        # But a leading 0 before the . doesn't count toward max_digits
        self.assertEqual(f.clean("0000000.100"), decimal.Decimal("0.100"))
        # Only leading whole zeros "collapse" to one digit.
        self.assertEqual(f.clean("000000.02"), decimal.Decimal("0.02"))
        with self.assertRaisesMessage(
            ValidationError, "'Ensure that there are no more than 3 digits in total.'"
        ):
            f.clean("000000.0002")
        self.assertEqual(f.clean(".002"), decimal.Decimal("0.002"))

    def test_decimalfield_6(self):
        """

        Checks the validation behavior of a DecimalField instance.

        This test ensures that the DecimalField correctly cleans decimal input and raises
        a ValidationError when the input exceeds the maximum allowed digits before the
        decimal point.

        The test covers two scenarios:
            * Successful cleaning of a decimal string with a single digit before the decimal point
            * Raising a ValidationError for input with more digits before the decimal point than allowed

        """
        f = DecimalField(max_digits=2, decimal_places=2)
        self.assertEqual(f.clean(".01"), decimal.Decimal(".01"))
        msg = "'Ensure that there are no more than 0 digits before the decimal point.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("1.1")

    def test_decimalfield_step_size_min_value(self):
        """
        #: Tests the :class:`DecimalField` widget's step size and minimum value validation.
        #: 
        #: Verifies that the widget is rendered with the correct HTML attributes, and that 
        #: it validates user input against the specified step size and minimum value.
        #: 
        #: The step size defines the interval between valid values, and input values that 
        #: are not multiples of this step size raise a :class:`ValidationError`.
        #: 
        #: The function tests both valid and invalid input values, ensuring that the 
        #: widget correctly handles various input scenarios and returns the expected 
        #: errors or cleaned values.
        """
        f = DecimalField(
            step_size=decimal.Decimal("0.3"),
            min_value=decimal.Decimal("-0.4"),
        )
        self.assertWidgetRendersTo(
            f,
            '<input name="f" min="-0.4" step="0.3" type="number" id="id_f" required>',
        )
        msg = (
            "Ensure this value is a multiple of step size 0.3, starting from -0.4, "
            "e.g. -0.4, -0.1, 0.2, and so on."
        )
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("1")
        self.assertEqual(f.clean("0.2"), decimal.Decimal("0.2"))
        self.assertEqual(f.clean(2), decimal.Decimal(2))
        self.assertEqual(f.step_size, decimal.Decimal("0.3"))

    def test_decimalfield_scientific(self):
        f = DecimalField(max_digits=4, decimal_places=2)
        with self.assertRaisesMessage(ValidationError, "Ensure that there are no more"):
            f.clean("1E+2")
        self.assertEqual(f.clean("1E+1"), decimal.Decimal("10"))
        self.assertEqual(f.clean("1E-1"), decimal.Decimal("0.1"))
        self.assertEqual(f.clean("0.546e+2"), decimal.Decimal("54.6"))

    def test_decimalfield_widget_attrs(self):
        f = DecimalField(max_digits=6, decimal_places=2)
        self.assertEqual(f.widget_attrs(Widget()), {})
        self.assertEqual(f.widget_attrs(NumberInput()), {"step": "0.01"})
        f = DecimalField(max_digits=10, decimal_places=0)
        self.assertEqual(f.widget_attrs(NumberInput()), {"step": "1"})
        f = DecimalField(max_digits=19, decimal_places=19)
        self.assertEqual(f.widget_attrs(NumberInput()), {"step": "1e-19"})
        f = DecimalField(max_digits=20)
        self.assertEqual(f.widget_attrs(NumberInput()), {"step": "any"})
        f = DecimalField(max_digits=6, widget=NumberInput(attrs={"step": "0.01"}))
        self.assertWidgetRendersTo(
            f, '<input step="0.01" name="f" type="number" id="id_f" required>'
        )

    def test_decimalfield_localized(self):
        """
        A localized DecimalField's widget renders to a text input without
        number input specific attributes.
        """
        f = DecimalField(localize=True)
        self.assertWidgetRendersTo(f, '<input id="id_f" name="f" type="text" required>')

    def test_decimalfield_changed(self):
        """
        Tests the has_changed method of a DecimalField.

        This test case checks if the has_changed method correctly identifies whether the value of a DecimalField has changed.
        It covers different scenarios, including when the decimal places are the same and when they are different.
        Additionally, it tests the method with localization enabled, ensuring that the comparison is done correctly even when the input is localized.

        """
        f = DecimalField(max_digits=2, decimal_places=2)
        d = decimal.Decimal("0.1")
        self.assertFalse(f.has_changed(d, "0.10"))
        self.assertTrue(f.has_changed(d, "0.101"))

        with translation.override("fr"):
            f = DecimalField(max_digits=2, decimal_places=2, localize=True)
            localized_d = formats.localize_input(d)  # -> '0,1' in French
            self.assertFalse(f.has_changed(d, localized_d))

    @override_settings(DECIMAL_SEPARATOR=",")
    def test_decimalfield_support_decimal_separator(self):
        """
        Tests that a DecimalField correctly handles decimal values with a comma separator.

        The function verifies that the decimal field can parse strings with both comma and dot separators,
        and ensures that the output is a Decimal object with a dot separator.

        The test is performed with the DECIMAL_SEPARATOR setting overridden to use a comma.
        This allows the function to verify that the field behaves correctly in a locale that uses commas as decimal separators.
        The test checks for both localized and non-localized decimal values, ensuring that the field handles both cases correctly.

        """
        with translation.override(None):
            f = DecimalField(localize=True)
            self.assertEqual(f.clean("1001,10"), decimal.Decimal("1001.10"))
            self.assertEqual(f.clean("1001.10"), decimal.Decimal("1001.10"))

    @override_settings(
        DECIMAL_SEPARATOR=",",
        USE_THOUSAND_SEPARATOR=True,
        THOUSAND_SEPARATOR=".",
    )
    def test_decimalfield_support_thousands_separator(self):
        """
        Tests the DecimalField with localization settings to ensure it correctly handles values with thousand separators.

        The function verifies that the DecimalField can parse and validate decimal numbers 
        with thousand separators and decimal points correctly, according to the specified localization settings.

        It also checks that the field raises a ValidationError when the input value is not a valid number.
        """
        with translation.override(None):
            f = DecimalField(localize=True)
            self.assertEqual(f.clean("1.001,10"), decimal.Decimal("1001.10"))
            msg = "'Enter a number.'"
            with self.assertRaisesMessage(ValidationError, msg):
                f.clean("1,001.1")
