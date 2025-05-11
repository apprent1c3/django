from django.core.exceptions import ValidationError
from django.forms import IntegerField, Textarea
from django.test import SimpleTestCase

from . import FormFieldAssertionsMixin


class IntegerFieldTest(FormFieldAssertionsMixin, SimpleTestCase):
    def test_integerfield_1(self):
        """
        Tests the functionality of the IntegerField class.

        Verifies that the field renders correctly as an input of type 'number', requires input,
        and validates that the input is a whole number. Ensures that the field's clean method
        returns an integer, and that invalid inputs (e.g. non-numeric, floating point) raise
        ValidationError with informative messages.
        """
        f = IntegerField()
        self.assertWidgetRendersTo(
            f, '<input type="number" name="f" id="id_f" required>'
        )
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        self.assertEqual(1, f.clean("1"))
        self.assertIsInstance(f.clean("1"), int)
        self.assertEqual(23, f.clean("23"))
        with self.assertRaisesMessage(ValidationError, "'Enter a whole number.'"):
            f.clean("a")
        self.assertEqual(42, f.clean(42))
        with self.assertRaisesMessage(ValidationError, "'Enter a whole number.'"):
            f.clean(3.14)
        self.assertEqual(1, f.clean("1 "))
        self.assertEqual(1, f.clean(" 1"))
        self.assertEqual(1, f.clean(" 1 "))
        with self.assertRaisesMessage(ValidationError, "'Enter a whole number.'"):
            f.clean("1a")
        self.assertIsNone(f.max_value)
        self.assertIsNone(f.min_value)

    def test_integerfield_2(self):
        """

        Tests the functionality of the IntegerField class, verifying it correctly handles 
        different types of input, including empty strings, None, valid integers, and invalid data.

        """
        f = IntegerField(required=False)
        self.assertIsNone(f.clean(""))
        self.assertEqual("None", repr(f.clean("")))
        self.assertIsNone(f.clean(None))
        self.assertEqual("None", repr(f.clean(None)))
        self.assertEqual(1, f.clean("1"))
        self.assertIsInstance(f.clean("1"), int)
        self.assertEqual(23, f.clean("23"))
        with self.assertRaisesMessage(ValidationError, "'Enter a whole number.'"):
            f.clean("a")
        self.assertEqual(1, f.clean("1 "))
        self.assertEqual(1, f.clean(" 1"))
        self.assertEqual(1, f.clean(" 1 "))
        with self.assertRaisesMessage(ValidationError, "'Enter a whole number.'"):
            f.clean("1a")
        self.assertIsNone(f.max_value)
        self.assertIsNone(f.min_value)

    def test_integerfield_3(self):
        """

        Tests the IntegerField form field with a specified max value to ensure correct rendering and validation.

        The test checks for proper HTML rendering, required field validation, and bounds checking. It verifies that
        the field correctly handles integer and string inputs within the specified range and raises validation errors
        for values outside the allowed range.

        """
        f = IntegerField(max_value=10)
        self.assertWidgetRendersTo(
            f, '<input max="10" type="number" name="f" id="id_f" required>'
        )
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        self.assertEqual(1, f.clean(1))
        self.assertEqual(10, f.clean(10))
        with self.assertRaisesMessage(
            ValidationError, "'Ensure this value is less than or equal to 10.'"
        ):
            f.clean(11)
        self.assertEqual(10, f.clean("10"))
        with self.assertRaisesMessage(
            ValidationError, "'Ensure this value is less than or equal to 10.'"
        ):
            f.clean("11")
        self.assertEqual(f.max_value, 10)
        self.assertIsNone(f.min_value)

    def test_integerfield_4(self):
        """

        Tests the functionality of an IntegerField with a minimum value constraint.

        Checks that the field renders correctly in HTML, enforces the minimum value, 
        handles required field validation, and correctly cleans integer values from 
        both integer and string inputs.

        """
        f = IntegerField(min_value=10)
        self.assertWidgetRendersTo(
            f, '<input id="id_f" type="number" name="f" min="10" required>'
        )
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        with self.assertRaisesMessage(
            ValidationError, "'Ensure this value is greater than or equal to 10.'"
        ):
            f.clean(1)
        self.assertEqual(10, f.clean(10))
        self.assertEqual(11, f.clean(11))
        self.assertEqual(10, f.clean("10"))
        self.assertEqual(11, f.clean("11"))
        self.assertIsNone(f.max_value)
        self.assertEqual(f.min_value, 10)

    def test_integerfield_5(self):
        """
        Tests the functionality of an IntegerField with min and max value constraints.

        Verifies that the field renders correctly, raises validation errors for invalid input,
        and correctly cleans valid integer and string inputs within the specified range.
        """
        f = IntegerField(min_value=10, max_value=20)
        self.assertWidgetRendersTo(
            f, '<input id="id_f" max="20" type="number" name="f" min="10" required>'
        )
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        with self.assertRaisesMessage(
            ValidationError, "'Ensure this value is greater than or equal to 10.'"
        ):
            f.clean(1)
        self.assertEqual(10, f.clean(10))
        self.assertEqual(11, f.clean(11))
        self.assertEqual(10, f.clean("10"))
        self.assertEqual(11, f.clean("11"))
        self.assertEqual(20, f.clean(20))
        with self.assertRaisesMessage(
            ValidationError, "'Ensure this value is less than or equal to 20.'"
        ):
            f.clean(21)
        self.assertEqual(f.max_value, 20)
        self.assertEqual(f.min_value, 10)

    def test_integerfield_6(self):
        """
        Tests the functionality of an IntegerField with a specified step size.

        Verifies that the field renders correctly as an HTML input, that validation
        correctly rejects values not matching the step size, and that valid values
        are cleaned and returned as integers.
        """
        f = IntegerField(step_size=3)
        self.assertWidgetRendersTo(
            f,
            '<input name="f" step="3" type="number" id="id_f" required>',
        )
        with self.assertRaisesMessage(
            ValidationError, "'Ensure this value is a multiple of step size 3.'"
        ):
            f.clean("10")
        self.assertEqual(12, f.clean(12))
        self.assertEqual(12, f.clean("12"))
        self.assertEqual(f.step_size, 3)

    def test_integerfield_step_size_min_value(self):
        """

        Tests the IntegerField's step size and minimum value functionality.

        Verifies that the field correctly enforces the minimum value and step size when cleaning input values, 
        and raises a ValidationError for invalid values.

        """
        f = IntegerField(step_size=3, min_value=-1)
        self.assertWidgetRendersTo(
            f,
            '<input name="f" min="-1" step="3" type="number" id="id_f" required>',
        )
        msg = (
            "Ensure this value is a multiple of step size 3, starting from -1, e.g. "
            "-1, 2, 5, and so on."
        )
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("9")
        self.assertEqual(f.clean("2"), 2)
        self.assertEqual(f.clean("-1"), -1)
        self.assertEqual(f.step_size, 3)

    def test_integerfield_localized(self):
        """
        A localized IntegerField's widget renders to a text input without any
        number input specific attributes.
        """
        f1 = IntegerField(localize=True)
        self.assertWidgetRendersTo(
            f1, '<input id="id_f" name="f" type="text" required>'
        )

    def test_integerfield_float(self):
        """
        Tests the cleaning functionality of an IntegerField with float inputs.

        Verifies that the field correctly converts various float representations to integers,
        and raises a ValidationError for non-integer inputs.
        """
        f = IntegerField()
        self.assertEqual(1, f.clean(1.0))
        self.assertEqual(1, f.clean("1.0"))
        self.assertEqual(1, f.clean(" 1.0 "))
        self.assertEqual(1, f.clean("1."))
        self.assertEqual(1, f.clean(" 1. "))
        with self.assertRaisesMessage(ValidationError, "'Enter a whole number.'"):
            f.clean("1.5")
        with self.assertRaisesMessage(ValidationError, "'Enter a whole number.'"):
            f.clean("…")

    def test_integerfield_big_num(self):
        f = IntegerField()
        self.assertEqual(9223372036854775808, f.clean(9223372036854775808))
        self.assertEqual(9223372036854775808, f.clean("9223372036854775808"))
        self.assertEqual(9223372036854775808, f.clean("9223372036854775808.0"))

    def test_integerfield_unicode_number(self):
        f = IntegerField()
        self.assertEqual(50, f.clean("５０"))

    def test_integerfield_subclass(self):
        """
        Class-defined widget is not overwritten by __init__() (#22245).
        """

        class MyIntegerField(IntegerField):
            widget = Textarea

        f = MyIntegerField()
        self.assertEqual(f.widget.__class__, Textarea)
        f = MyIntegerField(localize=True)
        self.assertEqual(f.widget.__class__, Textarea)
