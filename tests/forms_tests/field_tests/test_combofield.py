from django.core.exceptions import ValidationError
from django.forms import CharField, ComboField, EmailField
from django.test import SimpleTestCase


class ComboFieldTest(SimpleTestCase):
    def test_combofield_1(self):
        """
        Tests the ComboField's cleaning functionality, ensuring it validates input data against a combination of character limit and email format requirements, raising specific validation errors for invalid inputs.
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

        Checks the functionality of a ComboField with multiple validation rules.

        The ComboField is tested with a combination of a character field (max length 20) and an email field.
        The tests cover cases such as valid emails, emails exceeding the maximum allowed length, 
        invalid email formats, and empty or null input values.

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
