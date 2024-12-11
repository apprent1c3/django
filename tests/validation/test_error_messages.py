from unittest import TestCase

from django.core.exceptions import ValidationError
from django.db import models


class ValidationMessagesTest(TestCase):
    def _test_validation_messages(self, field, value, expected):
        """

        Tests that a validation error is raised with the expected messages when cleaning a field.

        :param field: The field to be tested for validation.
        :param value: The value to test against the field's validation rules.
        :param expected: The expected error messages to be raised.

        This method verifies that the field's validation rules are correctly enforced and 
        that the resulting error messages match the expected output.

        """
        with self.assertRaises(ValidationError) as cm:
            field.clean(value, None)
        self.assertEqual(cm.exception.messages, expected)

    def test_autofield_field_raises_error_message(self):
        """

        Tests that an error message is raised when an invalid value is assigned to an AutoField.

        Verifies that the validation correctly identifies non-integer values and returns an appropriate error message, ensuring data integrity for fields that require integer values.

        """
        f = models.AutoField(primary_key=True)
        self._test_validation_messages(f, "fõo", ["“fõo” value must be an integer."])

    def test_integer_field_raises_error_message(self):
        """

        Tests that an error message is raised when a non-integer value is provided to an IntegerField.

        This test case ensures that the validation mechanism for IntegerField correctly identifies
        and reports invalid input, specifically when a string containing non-integer characters
        is passed to the field. The expected error message confirms that the input value must be
        an integer, providing clear feedback to the user.

        """
        f = models.IntegerField()
        self._test_validation_messages(f, "fõo", ["“fõo” value must be an integer."])

    def test_boolean_field_raises_error_message(self):
        f = models.BooleanField()
        self._test_validation_messages(
            f, "fõo", ["“fõo” value must be either True or False."]
        )

    def test_nullable_boolean_field_raises_error_message(self):
        """
        Tests that a nullable BooleanField raises an error message when provided with an invalid value.

        The function verifies that attempting to validate a BooleanField with a non-Boolean value (in this case, a string) returns an error message instructing the user to provide one of the accepted values: True, False, or None.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the error message is not correctly generated for the invalid input value.
        """
        f = models.BooleanField(null=True)
        self._test_validation_messages(
            f, "fõo", ["“fõo” value must be either True, False, or None."]
        )

    def test_float_field_raises_error_message(self):
        f = models.FloatField()
        self._test_validation_messages(f, "fõo", ["“fõo” value must be a float."])

    def test_decimal_field_raises_error_message(self):
        """
        Tests that a DecimalField raises an appropriate error message when given an invalid decimal value.

        The function verifies that a DecimalField correctly handles non-numeric input and provides a user-friendly error message indicating that the input value must be a decimal number.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the DecimalField does not raise the expected error message for an invalid decimal value.

        Note:
            This test case covers the validation behavior of DecimalField for non-numeric input.

        """
        f = models.DecimalField()
        self._test_validation_messages(
            f, "fõo", ["“fõo” value must be a decimal number."]
        )

    def test_null_boolean_field_raises_error_message(self):
        """

        Tests that a BooleanField with null=True raises an error message when 
        an invalid value is provided. The function checks that passing a string 
        value to the field results in a validation error, with a message 
        indicating that the value must be a boolean (True or False) or None.

        """
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
        Tests the error messages raised when a Date Time Field in a model receives an invalid input.

         The function checks three different scenarios:

         * When the input string has an incorrect format, it should raise an error message specifying the correct format (YYYY-MM-DD HH:MM[:ss[.uuuuuu]][TZ]).
         * When the input string has the correct date format but is an invalid date, it should raise an error message indicating that the date is invalid.
         * When the input string has the correct date and time format but is an invalid date/time, it should raise an error message indicating that the date/time is invalid.

         It ensures that the Date Time Field correctly handles and reports various types of invalid input, providing informative error messages in each case.
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
