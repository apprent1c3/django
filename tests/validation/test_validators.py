from django.test import SimpleTestCase

from . import ValidationAssertions
from .models import ModelToValidate


class TestModelsWithValidators(ValidationAssertions, SimpleTestCase):
    def test_custom_validator_passes_for_correct_value(self):
        mtv = ModelToValidate(
            number=10,
            name="Some Name",
            f_with_custom_validator=42,
            f_with_iterable_of_validators=42,
        )
        self.assertIsNone(mtv.full_clean())

    def test_custom_validator_raises_error_for_incorrect_value(self):
        mtv = ModelToValidate(
            number=10,
            name="Some Name",
            f_with_custom_validator=12,
            f_with_iterable_of_validators=42,
        )
        self.assertFailsValidation(mtv.full_clean, ["f_with_custom_validator"])
        self.assertFieldFailsValidationWithMessage(
            mtv.full_clean,
            "f_with_custom_validator",
            ["This is not the answer to life, universe and everything!"],
        )

    def test_field_validators_can_be_any_iterable(self):
        """
        Tests that field validators can be any type of iterable.

        This test case validates a ModelToValidate instance with a field that uses an iterable of custom validators.
        It verifies that the validation fails as expected when the field's value does not meet the validation criteria.
        The test also checks that the correct error message is raised during the validation process, confirming that the iterable validators are properly executed and their messages are displayed.

        The purpose of this test is to ensure that the validation framework can handle and execute any type of iterable, providing flexibility in defining custom validation rules for model fields.
        """
        mtv = ModelToValidate(
            number=10,
            name="Some Name",
            f_with_custom_validator=42,
            f_with_iterable_of_validators=12,
        )
        self.assertFailsValidation(mtv.full_clean, ["f_with_iterable_of_validators"])
        self.assertFieldFailsValidationWithMessage(
            mtv.full_clean,
            "f_with_iterable_of_validators",
            ["This is not the answer to life, universe and everything!"],
        )
