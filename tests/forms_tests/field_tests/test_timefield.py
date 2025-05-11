import datetime

from django.core.exceptions import ValidationError
from django.forms import TimeField
from django.test import SimpleTestCase

from . import FormFieldAssertionsMixin


class TimeFieldTest(FormFieldAssertionsMixin, SimpleTestCase):
    def test_timefield_1(self):
        """
        Tests the functionality of the TimeField class, verifying its ability to correctly clean and validate time input in various formats and raise a ValidationError for invalid input.
        """
        f = TimeField()
        self.assertEqual(datetime.time(14, 25), f.clean(datetime.time(14, 25)))
        self.assertEqual(datetime.time(14, 25, 59), f.clean(datetime.time(14, 25, 59)))
        self.assertEqual(datetime.time(14, 25), f.clean("14:25"))
        self.assertEqual(datetime.time(14, 25, 59), f.clean("14:25:59"))
        with self.assertRaisesMessage(ValidationError, "'Enter a valid time.'"):
            f.clean("hello")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid time.'"):
            f.clean("1:24 p.m.")

    def test_timefield_2(self):
        """

        Tests the TimeField class to ensure it correctly handles and validates time inputs in various formats.

        Verifies that the field can parse and clean time values from both datetime.time objects and string representations,
        using the specified input formats. Also checks that invalid time inputs raise a ValidationError.

        """
        f = TimeField(input_formats=["%I:%M %p"])
        self.assertEqual(datetime.time(14, 25), f.clean(datetime.time(14, 25)))
        self.assertEqual(datetime.time(14, 25, 59), f.clean(datetime.time(14, 25, 59)))
        self.assertEqual(datetime.time(4, 25), f.clean("4:25 AM"))
        self.assertEqual(datetime.time(16, 25), f.clean("4:25 PM"))
        with self.assertRaisesMessage(ValidationError, "'Enter a valid time.'"):
            f.clean("14:30:45")

    def test_timefield_3(self):
        """
        Tests the TimeField's clean method to ensure it correctly parses time strings and raises a ValidationError for invalid input.
        """
        f = TimeField()
        # Test whitespace stripping behavior (#5714)
        self.assertEqual(datetime.time(14, 25), f.clean(" 14:25 "))
        self.assertEqual(datetime.time(14, 25, 59), f.clean(" 14:25:59 "))
        with self.assertRaisesMessage(ValidationError, "'Enter a valid time.'"):
            f.clean("   ")

    def test_timefield_changed(self):
        """
        Checks whether a TimeField has changed based on the input time string and the current time value, considering different time formats.
        """
        t1 = datetime.time(12, 51, 34, 482548)
        t2 = datetime.time(12, 51)
        f = TimeField(input_formats=["%H:%M", "%H:%M %p"])
        self.assertTrue(f.has_changed(t1, "12:51"))
        self.assertFalse(f.has_changed(t2, "12:51"))
        self.assertFalse(f.has_changed(t2, "12:51 PM"))
