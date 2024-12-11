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
        """

        Tests that an IntegerField raises an error message when a non-integer value is provided.

        Verifies that the field correctly validates input and returns an appropriate error message
        when the input cannot be converted to an integer.

        The expected error message indicates that the input value must be an integer.

        """
        f = models.IntegerField()
        self._test_validation_messages(f, "fõo", ["“fõo” value must be an integer."])

    def test_boolean_field_raises_error_message(self):
        """
        albums): 
            Tests that a BooleanField raises an error message when a non-boolean value is provided.

            The function checks that a validation error is correctly raised when an invalid
            value is assigned to a BooleanField, ensuring that the field only accepts
            boolean values (True or False). The test verifies that the error message
            returned is the expected one, providing a clear indication of the issue.
        """
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
        """
        Tests the DateTimeField's validation error messages.

            This test case ensures that the DateTimeField raises the correct error messages 
            when given invalid input. It checks for the following scenarios:

            - Input with an invalid format
            - Input with a valid date format (YYYY-MM-DD) but an invalid date
            - Input with a valid datetime format (YYYY-MM-DD HH:MM[:ss[.uuuuuu]][TZ]) but an invalid date and time.

            The test verifies that the error messages returned are as expected for each 
            scenario, helping to ensure the field's validation works correctly.
        """
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
