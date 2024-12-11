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

        Tests the ComboField with a combination of CharField and EmailField.

        This test case verifies the following scenarios:
            * Successful cleaning of an email address.
            * Validation error for an email address exceeding the maximum character limit.
            * Validation error for an invalid email address.
            * Successful cleaning of empty and None values.

        The test ensures the ComboField correctly applies the validation rules of its constituent fields, 
        providing robust data validation for the form field.

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
