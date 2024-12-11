from unittest import TestCase

from django.core.exceptions import ValidationError
from django.db import models


class ValidationMessagesTest(TestCase):
    def _test_validation_messages(self, field, value, expected):
        with self.assertRaises(ValidationError) as cm:
            field.clean(value, None)
        self.assertEqual(cm.exception.messages, expected)

    def test_autofield_field_raises_error_message(self):
        f = models.AutoField(primary_key=True)
        self._test_validation_messages(f, "fõo", ["“fõo” value must be an integer."])

    def test_integer_field_raises_error_message(self):
        f = models.IntegerField()
        self._test_validation_messages(f, "fõo", ["“fõo” value must be an integer."])

    def test_boolean_field_raises_error_message(self):
        f = models.BooleanField()
        self._test_validation_messages(
            f, "fõo", ["“fõo” value must be either True or False."]
        )

    def test_nullable_boolean_field_raises_error_message(self):
        f = models.BooleanField(null=True)
        self._test_validation_messages(
            f, "fõo", ["“fõo” value must be either True, False, or None."]
        )

    def test_float_field_raises_error_message(self):
        f = models.FloatField()
        self._test_validation_messages(f, "fõo", ["“fõo” value must be a float."])

    def test_decimal_field_raises_error_message(self):
        """
        Tests that a DecimalField raises an appropriate error message when a non-decimal value is provided. 

        The test case checks that the field correctly identifies and reports invalid input, 
        specifically when a string containing non-numeric characters is passed, 
        ensuring that the expected validation error message is generated.
        """
        f = models.DecimalField()
        self._test_validation_messages(
            f, "fõo", ["“fõo” value must be a decimal number."]
        )

    def test_null_boolean_field_raises_error_message(self):
        f = models.BooleanField(null=True)
        self._test_validation_messages(
            f, "fõo", ["“fõo” value must be either True, False, or None."]
        )

    def test_date_field_raises_error_message(self):
        f = models.DateField()
        self._test_validation_messages(
            f,
            "fõo",
            [
                "“fõo” value has an invalid date format. It must be in YYYY-MM-DD "
                "format."
            ],
        )
        self._test_validation_messages(
            f,
            "aaaa-10-10",
            [
                "“aaaa-10-10” value has an invalid date format. It must be in "
                "YYYY-MM-DD format."
            ],
        )
        self._test_validation_messages(
            f,
            "2011-13-10",
            [
                "“2011-13-10” value has the correct format (YYYY-MM-DD) but it is an "
                "invalid date."
            ],
        )
        self._test_validation_messages(
            f,
            "2011-10-32",
            [
                "“2011-10-32” value has the correct format (YYYY-MM-DD) but it is an "
                "invalid date."
            ],
        )

    def test_datetime_field_raises_error_message(self):
        f = models.DateTimeField()
        # Wrong format
        self._test_validation_messages(
            f,
            "fõo",
            [
                "“fõo” value has an invalid format. It must be in "
                "YYYY-MM-DD HH:MM[:ss[.uuuuuu]][TZ] format."
            ],
        )
        # Correct format but invalid date
        self._test_validation_messages(
            f,
            "2011-10-32",
            [
                "“2011-10-32” value has the correct format (YYYY-MM-DD) but it is an "
                "invalid date."
            ],
        )
        # Correct format but invalid date/time
        self._test_validation_messages(
            f,
            "2011-10-32 10:10",
            [
                "“2011-10-32 10:10” value has the correct format "
                "(YYYY-MM-DD HH:MM[:ss[.uuuuuu]][TZ]) but it is an invalid date/time."
            ],
        )

    def test_time_field_raises_error_message(self):
        """
        Tests that the TimeField raises an error message with invalid input values.

            The function checks two scenarios: 
            1. When the input value has an incorrect format, it verifies that the error message indicates the required format (HH:MM[:ss[.uuuuuu]]).
            2. When the input value has the correct format but represents an invalid time, it checks that the error message reports the time as invalid. 

            This ensures that the TimeField validation provides informative and accurate feedback for different types of invalid input.
        """
        f = models.TimeField()
        # Wrong format
        self._test_validation_messages(
            f,
            "fõo",
            [
                "“fõo” value has an invalid format. It must be in HH:MM[:ss[.uuuuuu]] "
                "format."
            ],
        )
        # Correct format but invalid time
        self._test_validation_messages(
            f,
            "25:50",
            [
                "“25:50” value has the correct format (HH:MM[:ss[.uuuuuu]]) but it is "
                "an invalid time."
            ],
        )
