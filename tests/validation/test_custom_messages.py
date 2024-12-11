from django.test import SimpleTestCase

from . import ValidationAssertions
from .models import CustomMessagesModel


class CustomMessagesTests(ValidationAssertions, SimpleTestCase):
    def test_custom_simple_validator_message(self):
        """

        Tests that a custom simple validator message is correctly raised.

        This test case creates an instance of CustomMessagesModel with an invalid value
        for the 'number' field, and then checks that the full_clean method raises a
        validation error with the expected custom message.

        """
        cmm = CustomMessagesModel(number=12)
        self.assertFieldFailsValidationWithMessage(cmm.full_clean, "number", ["AAARGH"])

    def test_custom_null_message(self):
        """
        Tests that the CustomMessagesModel correctly raises a validation error with a custom null message when the 'number' field is empty. This ensures that the model provides user-friendly feedback when the field is not populated, specifically returning a 'NULL' message instead of a default error message.
        """
        cmm = CustomMessagesModel()
        self.assertFieldFailsValidationWithMessage(cmm.full_clean, "number", ["NULL"])
