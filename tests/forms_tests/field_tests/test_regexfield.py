import re

from django.core.exceptions import ValidationError
from django.forms import RegexField
from django.test import SimpleTestCase


class RegexFieldTest(SimpleTestCase):
    def test_regexfield_1(self):
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
        f = RegexField("^[0-9][A-F][0-9]$", required=False)
        self.assertEqual("2A2", f.clean("2A2"))
        self.assertEqual("3F3", f.clean("3F3"))
        with self.assertRaisesMessage(ValidationError, "'Enter a valid value.'"):
            f.clean("3G3")
        self.assertEqual("", f.clean(""))

    def test_regexfield_3(self):
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

        Tests the functionality of the RegexField class.

        This test case checks the following scenarios:
        - Validation of input with less than the minimum required length
        - Validation of input with non-numeric characters
        - Validation of input with the exact minimum required length
        - Validation of input with the exact maximum allowed length
        - Validation of input with more than the maximum allowed length
        - Validation of input with a mix of numeric and non-numeric characters

        Each scenario verifies that the expected validation error message is raised, or that the input is cleaned and returned without errors if it is valid.

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
        f = RegexField("^[a-z]+$")
        f.regex = "^[0-9]+$"
        self.assertEqual("1234", f.clean("1234"))
        with self.assertRaisesMessage(ValidationError, "'Enter a valid value.'"):
            f.clean("abcd")

    def test_get_regex(self):
        """

        Tests the retrieval of a regex pattern from a RegexField instance.

        Verifies that the regex pattern provided during the creation of the RegexField
        is correctly compiled and stored as an instance attribute.

        The test case checks if the expected regex pattern matches the actual pattern
        stored in the instance, confirming the proper initialization of the RegexField.

        """
        f = RegexField("^[a-z]+$")
        self.assertEqual(f.regex, re.compile("^[a-z]+$"))

    def test_regexfield_strip(self):
        """

        Tests the functionality of the RegexField when the strip parameter is enabled.

        This test case verifies that leading and trailing whitespace is removed from the input string 
        before it is validated against the regular expression pattern. The regular expression pattern 
        used in this test only matches strings consisting of one or more lowercase letters.

        The test confirms that the RegexField's clean method correctly strips whitespace from the input 
        strings and returns the resulting string if it matches the pattern.

        """
        f = RegexField("^[a-z]+$", strip=True)
        self.assertEqual(f.clean(" a"), "a")
        self.assertEqual(f.clean("a "), "a")

    def test_empty_value(self):
        f = RegexField("", required=False)
        self.assertEqual(f.clean(""), "")
        self.assertEqual(f.clean(None), "")
        f = RegexField("", empty_value=None, required=False)
        self.assertIsNone(f.clean(""))
        self.assertIsNone(f.clean(None))
