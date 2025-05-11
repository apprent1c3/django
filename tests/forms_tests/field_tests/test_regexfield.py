import re

from django.core.exceptions import ValidationError
from django.forms import RegexField
from django.test import SimpleTestCase


class RegexFieldTest(SimpleTestCase):
    def test_regexfield_1(self):
        """
        Tests the validation functionality of the RegexField class.

        Ensures that valid input is accepted, and invalid input raises a ValidationError with the correct error message.

        Validates input against the regular expression '^[0-9][A-F][0-9]$' and checks for required field validation.
        """
        f = RegexField("^[0-9][A-F][0-9]$")
        self.assertEqual("2A2", f.clean("2A2"))
        self.assertEqual("3F3", f.clean("3F3"))
        with self.assertRaisesMessage(ValidationError, "'Enter a valid value.'"):
            f.clean("3G3")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid value.'"):
            f.clean(" 2A2")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid value.'"):
            f.clean("2A2 ")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")

    def test_regexfield_2(self):
        """
        Tests the functionality of RegexField with a custom regular expression.

        This test case ensures that the RegexField correctly validates input strings
        against a predefined pattern, allowing valid strings to pass through while
        raising a ValidationError for invalid ones, and handles empty input when not required.
        """
        f = RegexField("^[0-9][A-F][0-9]$", required=False)
        self.assertEqual("2A2", f.clean("2A2"))
        self.assertEqual("3F3", f.clean("3F3"))
        with self.assertRaisesMessage(ValidationError, "'Enter a valid value.'"):
            f.clean("3G3")
        self.assertEqual("", f.clean(""))

    def test_regexfield_3(self):
        """
        Checks that the RegexField class properly validates input strings against a predefined regular expression, ensuring that valid inputs are cleaned and returned, while invalid inputs raise a ValidationError.
        """
        f = RegexField(re.compile("^[0-9][A-F][0-9]$"))
        self.assertEqual("2A2", f.clean("2A2"))
        self.assertEqual("3F3", f.clean("3F3"))
        with self.assertRaisesMessage(ValidationError, "'Enter a valid value.'"):
            f.clean("3G3")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid value.'"):
            f.clean(" 2A2")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid value.'"):
            f.clean("2A2 ")

    def test_regexfield_4(self):
        """

        Tests the validation of the RegexField for various input values.

        Verifies that the field correctly enforces its minimum and maximum length constraints,
        and that it validates input against a regular expression.

        """
        f = RegexField("^[0-9]+$", min_length=5, max_length=10)
        with self.assertRaisesMessage(
            ValidationError, "'Ensure this value has at least 5 characters (it has 3).'"
        ):
            f.clean("123")
        with self.assertRaisesMessage(
            ValidationError,
            "'Ensure this value has at least 5 characters (it has 3).', "
            "'Enter a valid value.'",
        ):
            f.clean("abc")
        self.assertEqual("12345", f.clean("12345"))
        self.assertEqual("1234567890", f.clean("1234567890"))
        with self.assertRaisesMessage(
            ValidationError,
            "'Ensure this value has at most 10 characters (it has 11).'",
        ):
            f.clean("12345678901")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid value.'"):
            f.clean("12345a")

    def test_regexfield_unicode_characters(self):
        f = RegexField(r"^\w+$")
        self.assertEqual("éèøçÎÎ你好", f.clean("éèøçÎÎ你好"))

    def test_change_regex_after_init(self):
        """

        Verifies that changing the regex pattern of a RegexField instance after initialization 
        correctly validates input values according to the new pattern.

        """
        f = RegexField("^[a-z]+$")
        f.regex = "^[0-9]+$"
        self.assertEqual("1234", f.clean("1234"))
        with self.assertRaisesMessage(ValidationError, "'Enter a valid value.'"):
            f.clean("abcd")

    def test_get_regex(self):
        f = RegexField("^[a-z]+$")
        self.assertEqual(f.regex, re.compile("^[a-z]+$"))

    def test_regexfield_strip(self):
        f = RegexField("^[a-z]+$", strip=True)
        self.assertEqual(f.clean(" a"), "a")
        self.assertEqual(f.clean("a "), "a")

    def test_empty_value(self):
        """
        Tests the behavior of RegexField when encountering empty values, verifying that it correctly handles required and empty_value parameters.
        """
        f = RegexField("", required=False)
        self.assertEqual(f.clean(""), "")
        self.assertEqual(f.clean(None), "")
        f = RegexField("", empty_value=None, required=False)
        self.assertIsNone(f.clean(""))
        self.assertIsNone(f.clean(None))
