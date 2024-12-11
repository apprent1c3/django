import math
from decimal import Decimal

from django.core import validators
from django.core.exceptions import ValidationError
from django.db import models
from django.test import TestCase

from .models import BigD, Foo


class DecimalFieldTests(TestCase):
    def test_to_python(self):
        """

        Tests the conversion of input values to Python Decimal objects using the to_python method.

        This method ensures that various input types, including integers and strings, are correctly converted to Decimal objects with the specified number of decimal places.

        The test cases cover a range of scenarios, including:

        * Integer inputs
        * String inputs in the form of decimal numbers
        * Floating point inputs with varying levels of precision

        The expected output is a Decimal object with the input value rounded to the specified number of decimal places.

        """
        f = models.DecimalField(max_digits=4, decimal_places=2)
        self.assertEqual(f.to_python(3), Decimal("3"))
        self.assertEqual(f.to_python("3.14"), Decimal("3.14"))
        # to_python() converts floats and honors max_digits.
        self.assertEqual(f.to_python(3.1415926535897), Decimal("3.142"))
        self.assertEqual(f.to_python(2.4), Decimal("2.400"))
        # Uses default rounding of ROUND_HALF_EVEN.
        self.assertEqual(f.to_python(2.0625), Decimal("2.062"))
        self.assertEqual(f.to_python(2.1875), Decimal("2.188"))

    def test_invalid_value(self):
        """

        Tests the validation of a DecimalField instance to ensure it correctly identifies and raises an error for invalid input values.

        The function attempts to clean a variety of invalid inputs, including empty collections, non-numeric strings, byte-strings, and complex numbers, and verifies that a ValidationError is raised with the expected error message for each case.

        """
        field = models.DecimalField(max_digits=4, decimal_places=2)
        msg = "“%s” value must be a decimal number."
        tests = [
            (),
            [],
            {},
            set(),
            object(),
            complex(),
            "non-numeric string",
            b"non-numeric byte-string",
        ]
        for value in tests:
            with self.subTest(value):
                with self.assertRaisesMessage(ValidationError, msg % (value,)):
                    field.clean(value, None)

    def test_default(self):
        f = models.DecimalField(default=Decimal("0.00"))
        self.assertEqual(f.get_default(), Decimal("0.00"))

    def test_get_prep_value(self):
        f = models.DecimalField(max_digits=5, decimal_places=1)
        self.assertIsNone(f.get_prep_value(None))
        self.assertEqual(f.get_prep_value("2.4"), Decimal("2.4"))

    def test_filter_with_strings(self):
        """
        Should be able to filter decimal fields using strings (#8023).
        """
        foo = Foo.objects.create(a="abc", d=Decimal("12.34"))
        self.assertEqual(list(Foo.objects.filter(d="12.34")), [foo])

    def test_save_without_float_conversion(self):
        """
        Ensure decimals don't go through a corrupting float conversion during
        save (#5079).
        """
        bd = BigD(d="12.9")
        bd.save()
        bd = BigD.objects.get(pk=bd.pk)
        self.assertEqual(bd.d, Decimal("12.9"))

    def test_save_nan_invalid(self):
        """

        Tests that an attempt to save a BigD object with an invalid 'nan' (not a number) value raises a ValidationError.

        The function checks that the 'nan' value is valid by attempting to create a BigD object with different representations of 'nan', 
        including float('nan'), math.nan, and the string 'nan'. It verifies that a ValidationError is raised with the expected message 
        in each case, ensuring that only valid decimal numbers are accepted.

        """
        msg = "“nan” value must be a decimal number."
        for value in [float("nan"), math.nan, "nan"]:
            with self.subTest(value), self.assertRaisesMessage(ValidationError, msg):
                BigD.objects.create(d=value)

    def test_save_inf_invalid(self):
        msg = "“inf” value must be a decimal number."
        for value in [float("inf"), math.inf, "inf"]:
            with self.subTest(value), self.assertRaisesMessage(ValidationError, msg):
                BigD.objects.create(d=value)
        msg = "“-inf” value must be a decimal number."
        for value in [float("-inf"), -math.inf, "-inf"]:
            with self.subTest(value), self.assertRaisesMessage(ValidationError, msg):
                BigD.objects.create(d=value)

    def test_fetch_from_db_without_float_rounding(self):
        """
        Tests the retrieval of a BigD object from the database without losing precision due to floating point rounding.

         Verifies that the decimal value stored in the database is accurately fetched and matches the original value, including very small decimal places.
        """
        big_decimal = BigD.objects.create(d=Decimal(".100000000000000000000000000005"))
        big_decimal.refresh_from_db()
        self.assertEqual(big_decimal.d, Decimal(".100000000000000000000000000005"))

    def test_lookup_really_big_value(self):
        """
        Really big values can be used in a filter statement.
        """
        # This should not crash.
        self.assertSequenceEqual(Foo.objects.filter(d__gte=100000000000), [])

    def test_lookup_decimal_larger_than_max_digits(self):
        self.assertSequenceEqual(Foo.objects.filter(d__lte=Decimal("123456")), [])

    def test_max_digits_validation(self):
        field = models.DecimalField(max_digits=2)
        expected_message = validators.DecimalValidator.messages["max_digits"] % {
            "max": 2
        }
        with self.assertRaisesMessage(ValidationError, expected_message):
            field.clean(100, None)

    def test_max_decimal_places_validation(self):
        """
        Tests validation of DecimalField with max_decimal_places constraint.

        Verifies that a ValidationError is raised when the input value exceeds the 
        defined maximum number of decimal places. It checks that the error message 
        returned matches the expected message, providing the correct maximum decimal 
        places value. This ensures the validation rule is applied correctly and 
        provides informative error messages to users.
        """
        field = models.DecimalField(decimal_places=1)
        expected_message = validators.DecimalValidator.messages[
            "max_decimal_places"
        ] % {"max": 1}
        with self.assertRaisesMessage(ValidationError, expected_message):
            field.clean(Decimal("0.99"), None)

    def test_max_whole_digits_validation(self):
        """
        .Tests whether a DecimalField with a specified maximum number of whole digits correctly raises a ValidationError when the input value exceeds the allowed number of digits before the decimal point. 

        The validation checks for values where the number of whole digits is greater than the max_digits minus decimal_places threshold, ensuring it matches the expected error message.
        """
        field = models.DecimalField(max_digits=3, decimal_places=1)
        expected_message = validators.DecimalValidator.messages["max_whole_digits"] % {
            "max": 2
        }
        with self.assertRaisesMessage(ValidationError, expected_message):
            field.clean(Decimal("999"), None)

    def test_roundtrip_with_trailing_zeros(self):
        """Trailing zeros in the fractional part aren't truncated."""
        obj = Foo.objects.create(a="bar", d=Decimal("8.320"))
        obj.refresh_from_db()
        self.assertEqual(obj.d.compare_total(Decimal("8.320")), Decimal("0"))
