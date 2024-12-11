from django.core.exceptions import ValidationError
from django.forms import CharField, ComboField, EmailField
from django.test import SimpleTestCase


class ComboFieldTest(SimpleTestCase):
    def test_combofield_1(self):
        f = ComboField(fields=[CharField(max_length=20), EmailField()])
        self.assertEqual("test@example.com", f.clean("test@example.com"))
        with self.assertRaisesMessage(
            ValidationError,
            "'Ensure this value has at most 20 characters (it has 28).'",
        ):
            f.clean("longemailaddress@example.com")
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid email address.'"
        ):
            f.clean("not an email")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)

    def test_combofield_2(self):
        """

        Tests the functionality of ComboField with a combination of character and email fields.

        This test case verifies the following scenarios:
        - Successful validation of a valid email address
        - Validation error when the input exceeds the maximum allowed characters
        - Validation error when the input is not a valid email address
        - Successful cleaning of empty and None input values, returning an empty string in both cases.

        The test ensures that the ComboField behaves as expected when handling different types of input, providing error messages for invalid data and handling empty or null values correctly.

        """
        f = ComboField(fields=[CharField(max_length=20), EmailField()], required=False)
        self.assertEqual("test@example.com", f.clean("test@example.com"))
        with self.assertRaisesMessage(
            ValidationError,
            "'Ensure this value has at most 20 characters (it has 28).'",
        ):
            f.clean("longemailaddress@example.com")
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid email address.'"
        ):
            f.clean("not an email")
        self.assertEqual("", f.clean(""))
        self.assertEqual("", f.clean(None))
