from django.core.exceptions import ValidationError
from django.forms import CharField, HiddenInput, PasswordInput, Textarea, TextInput
from django.test import SimpleTestCase

from . import FormFieldAssertionsMixin


class CharFieldTest(FormFieldAssertionsMixin, SimpleTestCase):
    def test_charfield_1(self):
        """
        Tests the behavior of the CharField, ensuring it properly handles various input types and validates required fields.
        """
        f = CharField()
        self.assertEqual("1", f.clean(1))
        self.assertEqual("hello", f.clean("hello"))
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        self.assertEqual("[1, 2, 3]", f.clean([1, 2, 3]))
        self.assertIsNone(f.max_length)
        self.assertIsNone(f.min_length)

    def test_charfield_2(self):
        """
        Tests the behavior of a CharField with optional input, ensuring it correctly handles various types of input, including integers, strings, None, empty strings, and lists, and verifies that max_length and min_length are not set.
        """
        f = CharField(required=False)
        self.assertEqual("1", f.clean(1))
        self.assertEqual("hello", f.clean("hello"))
        self.assertEqual("", f.clean(None))
        self.assertEqual("", f.clean(""))
        self.assertEqual("[1, 2, 3]", f.clean([1, 2, 3]))
        self.assertIsNone(f.max_length)
        self.assertIsNone(f.min_length)

    def test_charfield_3(self):
        """

        Tests the validation behavior of a CharField with a specified maximum length.
        Verifies that input strings within the allowed length are cleaned successfully,
        while strings exceeding the maximum length raise a ValidationError.

        """
        f = CharField(max_length=10, required=False)
        self.assertEqual("12345", f.clean("12345"))
        self.assertEqual("1234567890", f.clean("1234567890"))
        msg = "'Ensure this value has at most 10 characters (it has 11).'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("1234567890a")
        self.assertEqual(f.max_length, 10)
        self.assertIsNone(f.min_length)

    def test_charfield_4(self):
        """
        Tests the validation behavior of a CharField with minimum length constraint.

        Verifies that the field correctly handles required and non-required input, 
        enforces the minimum length constraint, and raises a ValidationError for 
        input that is too short.
        """
        f = CharField(min_length=10, required=False)
        self.assertEqual("", f.clean(""))
        msg = "'Ensure this value has at least 10 characters (it has 5).'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("12345")
        self.assertEqual("1234567890", f.clean("1234567890"))
        self.assertEqual("1234567890a", f.clean("1234567890a"))
        self.assertIsNone(f.max_length)
        self.assertEqual(f.min_length, 10)

    def test_charfield_5(self):
        """
        Tests the validation behavior of a CharField with minimum length constraint.

        Verifies that the field raises a ValidationError when empty or too short, and
        correctly cleans valid input values.

        """
        f = CharField(min_length=10, required=True)
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        msg = "'Ensure this value has at least 10 characters (it has 5).'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("12345")
        self.assertEqual("1234567890", f.clean("1234567890"))
        self.assertEqual("1234567890a", f.clean("1234567890a"))
        self.assertIsNone(f.max_length)
        self.assertEqual(f.min_length, 10)

    def test_charfield_length_not_int(self):
        """
        Tests that CharField validates its min_length and max_length parameters to ensure they are integers, raising a ValueError for non-integer values and a TypeError for invalid initialization.
        """
        with self.assertRaises(ValueError):
            CharField(min_length="a")
        with self.assertRaises(ValueError):
            CharField(max_length="a")
        msg = "__init__() takes 1 positional argument but 2 were given"
        with self.assertRaisesMessage(TypeError, msg):
            CharField("a")

    def test_charfield_widget_attrs(self):
        """
        Tests that CharField widget attributes are correctly generated based on the field's min_length and max_length properties. Specifically, verifies that minlength and maxlength are included in the widget attrs when the corresponding field properties are set and the widget is not hidden.
        """
        # Return an empty dictionary if max_length and min_length are both None.
        f = CharField()
        self.assertEqual(f.widget_attrs(TextInput()), {})
        self.assertEqual(f.widget_attrs(Textarea()), {})

        # Return a maxlength attribute equal to max_length.
        f = CharField(max_length=10)
        self.assertEqual(f.widget_attrs(TextInput()), {"maxlength": "10"})
        self.assertEqual(f.widget_attrs(PasswordInput()), {"maxlength": "10"})
        self.assertEqual(f.widget_attrs(Textarea()), {"maxlength": "10"})

        # Return a minlength attribute equal to min_length.
        f = CharField(min_length=5)
        self.assertEqual(f.widget_attrs(TextInput()), {"minlength": "5"})
        self.assertEqual(f.widget_attrs(PasswordInput()), {"minlength": "5"})
        self.assertEqual(f.widget_attrs(Textarea()), {"minlength": "5"})

        # Return both maxlength and minlength when both max_length and
        # min_length are set.
        f = CharField(max_length=10, min_length=5)
        self.assertEqual(
            f.widget_attrs(TextInput()), {"maxlength": "10", "minlength": "5"}
        )
        self.assertEqual(
            f.widget_attrs(PasswordInput()), {"maxlength": "10", "minlength": "5"}
        )
        self.assertEqual(
            f.widget_attrs(Textarea()), {"maxlength": "10", "minlength": "5"}
        )
        self.assertEqual(f.widget_attrs(HiddenInput()), {})

    def test_charfield_strip(self):
        """
        Tests that CharField strips leading and trailing whitespace from input values, unless the strip parameter is set to False.
        """
        f = CharField()
        self.assertEqual(f.clean(" 1"), "1")
        self.assertEqual(f.clean("1 "), "1")

        f = CharField(strip=False)
        self.assertEqual(f.clean(" 1"), " 1")
        self.assertEqual(f.clean("1 "), "1 ")

    def test_strip_before_checking_empty(self):
        """
        A whitespace-only value, ' ', is stripped to an empty string and then
        converted to the empty value, None.
        """
        f = CharField(required=False, empty_value=None)
        self.assertIsNone(f.clean(" "))

    def test_clean_non_string(self):
        """
        Tests the clean method of a CharField to ensure non-string values are properly handled, specifically that it calls str() on the value before stripping whitespace.
        """

        class StringWrapper:
            def __init__(self, v):
                self.v = v

            def __str__(self):
                return self.v

        value = StringWrapper(" ")
        f1 = CharField(required=False, empty_value=None)
        self.assertIsNone(f1.clean(value))
        f2 = CharField(strip=False)
        self.assertEqual(f2.clean(value), " ")

    def test_charfield_disabled(self):
        f = CharField(disabled=True)
        self.assertWidgetRendersTo(
            f, '<input type="text" name="f" id="id_f" disabled required>'
        )

    def test_null_characters_prohibited(self):
        f = CharField()
        msg = "Null characters are not allowed."
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("\x00something")
