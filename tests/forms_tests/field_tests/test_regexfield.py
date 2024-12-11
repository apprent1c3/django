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
        """
        Tests the RegexField's handling of unicode characters.

        This test checks whether the RegexField correctly validates and cleans strings
        containing non-ASCII characters, ensuring that it allows the passage of valid
        unicode characters without modification or corruption.

        The test case specifically targets the regular expression pattern '^\\w+$',
        which matches any word character (alphanumeric plus underscore), and verifies
        that the field correctly handles a string containing a mix of European and
        non-European unicode characters.

        The test asserts that the cleaned output matches the original input, demonstrating
        that the RegexField preserves the integrity of unicode characters during the
        validation and cleaning process.
        """
        f = RegexField(r"^\w+$")
        self.assertEqual("éèøçÎÎ你好", f.clean("éèøçÎÎ你好"))

    def test_change_regex_after_init(self):
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
        f = RegexField("", required=False)
        self.assertEqual(f.clean(""), "")
        self.assertEqual(f.clean(None), "")
        f = RegexField("", empty_value=None, required=False)
        self.assertIsNone(f.clean(""))
        self.assertIsNone(f.clean(None))
