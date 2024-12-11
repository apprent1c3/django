from django.core.exceptions import ValidationError
from django.forms import EmailField
from django.test import SimpleTestCase

from . import FormFieldAssertionsMixin


class EmailFieldTest(FormFieldAssertionsMixin, SimpleTestCase):
    def test_emailfield_1(self):
        """
        Tests the functionality of the EmailField form field.

        This test case covers the validation and rendering of the EmailField.
        It checks that the field has the expected maximum length, renders correctly as an HTML input element,
        and that it correctly validates and raises errors for empty, invalid, or missing input.
        The test also ensures that the field allows valid email addresses with international domain names (IDNs) to pass validation.

        """
        f = EmailField()
        self.assertEqual(f.max_length, 320)
        self.assertWidgetRendersTo(
            f, '<input type="email" name="f" id="id_f" maxlength="320" required>'
        )
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        self.assertEqual("person@example.com", f.clean("person@example.com"))
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid email address.'"
        ):
            f.clean("foo")
        self.assertEqual(
            "local@domain.with.idn.xyz\xe4\xf6\xfc\xdfabc.part.com",
            f.clean("local@domain.with.idn.xyzäöüßabc.part.com"),
        )

    def test_email_regexp_for_performance(self):
        """
        Tests the performance of the email regular expression in the EmailField.

        This test checks if the email field can efficiently validate and clean an email address.
        It uses an example email address with a long and complex local part, 
        containing special characters and numbers, to test the field's performance.
        The goal of this test is to ensure that the email field can handle such addresses without any issues.
        """
        f = EmailField()
        # Check for runaway regex security problem. This will take a long time
        # if the security fix isn't in place.
        addr = "viewx3dtextx26qx3d@yahoo.comx26latlngx3d15854521645943074058"
        self.assertEqual(addr, f.clean(addr))

    def test_emailfield_not_required(self):
        """
        Tests the behavior of EmailField when it is not required.

        This test case checks that the EmailField correctly handles empty input,
        valid email addresses, and email addresses with leading or trailing whitespace.
        It also verifies that the field raises a ValidationError when an invalid
        email address is provided.

        Validates the following scenarios:
        - Empty input is accepted and cleaned to an empty string
        - Valid email addresses are accepted and cleaned to their original value
        - Email addresses with leading or trailing whitespace are accepted and cleaned
        - Invalid email addresses raise a ValidationError
        """
        f = EmailField(required=False)
        self.assertEqual("", f.clean(""))
        self.assertEqual("", f.clean(None))
        self.assertEqual("person@example.com", f.clean("person@example.com"))
        self.assertEqual(
            "example@example.com", f.clean("      example@example.com  \t   \t ")
        )
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid email address.'"
        ):
            f.clean("foo")

    def test_emailfield_min_max_length(self):
        f = EmailField(min_length=10, max_length=15)
        self.assertWidgetRendersTo(
            f,
            '<input id="id_f" type="email" name="f" maxlength="15" minlength="10" '
            "required>",
        )
        with self.assertRaisesMessage(
            ValidationError,
            "'Ensure this value has at least 10 characters (it has 9).'",
        ):
            f.clean("a@foo.com")
        self.assertEqual("alf@foo.com", f.clean("alf@foo.com"))
        with self.assertRaisesMessage(
            ValidationError,
            "'Ensure this value has at most 15 characters (it has 20).'",
        ):
            f.clean("alf123456788@foo.com")

    def test_emailfield_strip_on_none_value(self):
        """
        ..: Tests that the EmailField strips empty values when the field is not required and the empty value is set to None.

                This test case checks the behavior of the EmailField when it encounters empty or None values, ensuring that the clean method correctly returns None in these scenarios, thus maintaining data consistency and preventing unnecessary whitespace or default values.
        """
        f = EmailField(required=False, empty_value=None)
        self.assertIsNone(f.clean(""))
        self.assertIsNone(f.clean(None))

    def test_emailfield_unable_to_set_strip_kwarg(self):
        """

        .assertRaisesMessage call to test that initializing an EmailField with the 'strip' keyword argument raises a TypeError.

        The test verifies that attempting to set the 'strip' keyword argument on EmailField raises an error due to it being a duplicate keyword argument, with the expected error message indicating multiple values were provided for 'strip'.

        This ensures that EmailField correctly handles and prevents setting the 'strip' argument explicitly.

        """
        msg = "got multiple values for keyword argument 'strip'"
        with self.assertRaisesMessage(TypeError, msg):
            EmailField(strip=False)
