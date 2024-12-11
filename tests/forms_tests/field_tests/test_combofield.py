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

        Tests the functionality of a ComboField instance composed of a CharField and an EmailField.

        This test case validates the following scenarios:
        - Successful cleaning of a valid email address.
        - Validation error for a string exceeding the maximum allowed length.
        - Validation error for an invalid email address.
        - Successful cleaning of empty and None input values.

        Ensures that the ComboField enforces the required validation rules and handles different input types as expected.

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
