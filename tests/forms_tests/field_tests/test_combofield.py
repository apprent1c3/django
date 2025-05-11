from django.core.exceptions import ValidationError
from django.forms import CharField, ComboField, EmailField
from django.test import SimpleTestCase


class ComboFieldTest(SimpleTestCase):
    def test_combofield_1(self):
        """
        Tests the ComboField class with a combination of character and email fields, 
        ensuring it correctly validates input lengths and email addresses, and raises 
        appropriate validation errors for invalid or missing input.
        """
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

        Validates the functionality of a ComboField instance composed of a character field and an email field.

        This test case ensures that the ComboField properly validates input data, 
        allowing valid email addresses while rejecting those that exceed the maximum character limit or are invalid.

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
