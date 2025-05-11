import datetime

from django.core.exceptions import ValidationError
from django.forms import TimeField
from django.test import SimpleTestCase

from . import FormFieldAssertionsMixin


class TimeFieldTest(FormFieldAssertionsMixin, SimpleTestCase):
    def test_timefield_1(self):
        """
        Tests the TimeField's clean method to ensure it correctly parses and validates time inputs in various formats, raising a ValidationError for invalid inputs.
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
        Tests that the TimeField function correctly parses and cleans time inputs in various formats, including those with AM/PM designations, and raises a ValidationError for invalid time inputs.
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

        Tests the TimeField's clean method to ensure it correctly parses time strings 
        and raises a ValidationError for invalid input.

        """
        f = TimeField()
        # Test whitespace stripping behavior (#5714)
        self.assertEqual(datetime.time(14, 25), f.clean(" 14:25 "))
        self.assertEqual(datetime.time(14, 25, 59), f.clean(" 14:25:59 "))
        with self.assertRaisesMessage(ValidationError, "'Enter a valid time.'"):
            f.clean("   ")

    def test_timefield_changed(self):
        """

        Tests whether the TimeField has changed based on input formats and time comparisons.

        Verifies that the TimeField correctly identifies changes in time values, 
        considering both exact time matches and time values with truncated seconds or 
        including AM/PM designations.

        """
        t1 = datetime.time(12, 51, 34, 482548)
        t2 = datetime.time(12, 51)
        f = TimeField(input_formats=["%H:%M", "%H:%M %p"])
        self.assertTrue(f.has_changed(t1, "12:51"))
        self.assertFalse(f.has_changed(t2, "12:51"))
        self.assertFalse(f.has_changed(t2, "12:51 PM"))
