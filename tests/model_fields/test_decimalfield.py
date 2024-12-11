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
        Tests the to_python method of a DecimalField.

        This method checks that the to_python method correctly converts various input types
        to a Decimal object, with the correct rounding and precision.

        It verifies that integer, string and float inputs are properly converted to Decimal,
        with a maximum of 4 digits and 2 decimal places, and that the rounding is done
        correctly.

        The test cases cover various scenarios, including integers, strings representing
        decimal numbers, and floating point numbers with different numbers of decimal places.

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
        Tests the validation of DecimalField with invalid input values.

        This function checks that the DecimalField correctly raises a ValidationError when
        given invalid input, such as non-numeric strings, bytes, collections, and other
        object types. It verifies that the error message includes the invalid input value,
        providing informative error messages for users.

        The test covers a variety of invalid input types, ensuring the field's validation
        is robust and handles different types of incorrect data.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Raises
        ------
        ValidationError: if the input value is not a valid decimal number.

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

        Tests the validation behavior when attempting to save a BigD object with an invalid \"nan\" value.

        Verifies that different representations of \"not a number\" (NaN) values, including float('nan'), math.nan, and the string 'nan', 
        are rejected and raise a ValidationError with a specific error message indicating that the \"nan\" value must be a decimal number.

        """
        msg = "“nan” value must be a decimal number."
        for value in [float("nan"), math.nan, "nan"]:
            with self.subTest(value), self.assertRaisesMessage(ValidationError, msg):
                BigD.objects.create(d=value)

    def test_save_inf_invalid(self):
        """
        Tests the creation of BigD objects with invalid infinity values.

        This test checks that creating a BigD object with 'inf' or '-inf' as the value of 'd'
        raises a ValidationError, regardless of whether the value is provided as a float,
        math.inf, or a string. It ensures that only decimal numbers are accepted as valid
        values for 'd'.

        The test covers the following invalid input values:
        - Positive infinity (float('inf'), math.inf, 'inf')
        - Negative infinity (float('-inf'), -math.inf, '-inf')

        It verifies that a ValidationError is raised with the expected error message for each
        invalid input value.
        """
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
        Tests the ability to fetch a decimal value from the database without losing precision due to float rounding.

        Verifies that a BigD object created with a high-precision decimal value can be successfully retrieved from the database
        and its original value is preserved, ensuring that no rounding occurs during the fetch process.

        The test covers scenarios where decimal values have a large number of digits, ensuring that the database and application
        can handle these cases accurately without introducing rounding errors.
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
        Tests the validation of a DecimalField with a maximum number of decimal places. 

        Checks if a ValidationError is raised when a decimal value with more than the specified number of decimal places is cleaned. 

        The test verifies that the error message matches the expected format for max decimal places validation, ensuring that the validation is working correctly and providing the correct feedback to the user.
        """
        field = models.DecimalField(decimal_places=1)
        expected_message = validators.DecimalValidator.messages[
            "max_decimal_places"
        ] % {"max": 1}
        with self.assertRaisesMessage(ValidationError, expected_message):
            field.clean(Decimal("0.99"), None)

    def test_max_whole_digits_validation(self):
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
