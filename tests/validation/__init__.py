from django.core.exceptions import ValidationError


class ValidationAssertions:
    def assertFailsValidation(self, clean, failed_fields, **kwargs):
        """
        Asserts that a validation function fails with the expected error fields.

        This function checks that a given validation function (`clean`) raises a 
        `ValidationError` exception when executed with the provided keyword arguments. 
        It then verifies that the error fields contained in the exception match the 
        expected `failed_fields`.

        :param clean: The validation function to test.
        :param failed_fields: A list of field names that are expected to fail validation.
        :param kwargs: Additional keyword arguments to pass to the `clean` function.

        """
        with self.assertRaises(ValidationError) as cm:
            clean(**kwargs)
        self.assertEqual(sorted(failed_fields), sorted(cm.exception.message_dict))

    def assertFieldFailsValidationWithMessage(self, clean, field_name, message):
        """

        Asserts that a validation on a specific field fails with a given error message.

        This method checks that a validation error is raised when calling the provided 
        clean function. It verifies that the validation error is associated with the 
        specified field and that the error message matches the expected message.

        :param clean: A function to call to trigger the validation.
        :param field_name: The name of the field that is expected to fail validation.
        :param message: The expected error message for the failed validation.

        """
        with self.assertRaises(ValidationError) as cm:
            clean()
        self.assertIn(field_name, cm.exception.message_dict)
        self.assertEqual(message, cm.exception.message_dict[field_name])
