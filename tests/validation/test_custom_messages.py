from django.test import SimpleTestCase

from . import ValidationAssertions
from .models import CustomMessagesModel


class CustomMessagesTests(ValidationAssertions, SimpleTestCase):
    def test_custom_simple_validator_message(self):
        """
        Tests the custom validation message for the `number` field.

        Verifies that a custom error message is raised when the `number` field fails validation.
        The test checks if the error message matches the expected custom message 'AAARGH'.
        """
        cmm = CustomMessagesModel(number=12)
        self.assertFieldFailsValidationWithMessage(cmm.full_clean, "number", ["AAARGH"])

    def test_custom_null_message(self):
        """

        Tests that a custom null message is correctly returned when the 'number' field fails validation.

        Verifies that the 'number' field properly handles null values and returns the expected custom error message when validation is performed using the full_clean method of the CustomMessagesModel.

        """
        cmm = CustomMessagesModel()
        self.assertFieldFailsValidationWithMessage(cmm.full_clean, "number", ["NULL"])
