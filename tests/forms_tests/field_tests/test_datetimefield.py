from datetime import date, datetime, timezone

from django.core.exceptions import ValidationError
from django.forms import DateTimeField
from django.test import SimpleTestCase
from django.utils.timezone import get_fixed_timezone


class DateTimeFieldTest(SimpleTestCase):
    def test_datetimefield_clean(self):
        """

        Tests the cleaning functionality of a DateTimeField.

        This test case checks that the field correctly interprets and converts various date and time formats into a datetime object.
        The formats tested include ISO 8601, American-style date formats with and without time, and formats with varying levels of precision (e.g., seconds, milliseconds).

        The test iterates over a series of input values and expected output datetime objects, verifying that the DateTimeField's clean method produces the expected results.

        """
        tests = [
            (date(2006, 10, 25), datetime(2006, 10, 25, 0, 0)),
            (datetime(2006, 10, 25, 14, 30), datetime(2006, 10, 25, 14, 30)),
            (datetime(2006, 10, 25, 14, 30, 59), datetime(2006, 10, 25, 14, 30, 59)),
            (
                datetime(2006, 10, 25, 14, 30, 59, 200),
                datetime(2006, 10, 25, 14, 30, 59, 200),
            ),
            ("2006-10-25 14:30:45.000200", datetime(2006, 10, 25, 14, 30, 45, 200)),
            ("2006-10-25 14:30:45.0002", datetime(2006, 10, 25, 14, 30, 45, 200)),
            ("2006-10-25 14:30:45", datetime(2006, 10, 25, 14, 30, 45)),
            ("2006-10-25 14:30:00", datetime(2006, 10, 25, 14, 30)),
            ("2006-10-25 14:30", datetime(2006, 10, 25, 14, 30)),
            ("2006-10-25", datetime(2006, 10, 25, 0, 0)),
            ("10/25/2006 14:30:45.000200", datetime(2006, 10, 25, 14, 30, 45, 200)),
            ("10/25/2006 14:30:45", datetime(2006, 10, 25, 14, 30, 45)),
            ("10/25/2006 14:30:00", datetime(2006, 10, 25, 14, 30)),
            ("10/25/2006 14:30", datetime(2006, 10, 25, 14, 30)),
            ("10/25/2006", datetime(2006, 10, 25, 0, 0)),
            ("10/25/06 14:30:45.000200", datetime(2006, 10, 25, 14, 30, 45, 200)),
            ("10/25/06 14:30:45", datetime(2006, 10, 25, 14, 30, 45)),
            ("10/25/06 14:30:00", datetime(2006, 10, 25, 14, 30)),
            ("10/25/06 14:30", datetime(2006, 10, 25, 14, 30)),
            ("10/25/06", datetime(2006, 10, 25, 0, 0)),
            # ISO 8601 formats.
            (
                "2014-09-23T22:34:41.614804",
                datetime(2014, 9, 23, 22, 34, 41, 614804),
            ),
            ("2014-09-23T22:34:41", datetime(2014, 9, 23, 22, 34, 41)),
            ("2014-09-23T22:34", datetime(2014, 9, 23, 22, 34)),
            ("2014-09-23", datetime(2014, 9, 23, 0, 0)),
            ("2014-09-23T22:34Z", datetime(2014, 9, 23, 22, 34, tzinfo=timezone.utc)),
            (
                "2014-09-23T22:34+07:00",
                datetime(2014, 9, 23, 22, 34, tzinfo=get_fixed_timezone(420)),
            ),
            # Whitespace stripping.
            (" 2006-10-25   14:30:45 ", datetime(2006, 10, 25, 14, 30, 45)),
            (" 2006-10-25 ", datetime(2006, 10, 25, 0, 0)),
            (" 10/25/2006 14:30:45 ", datetime(2006, 10, 25, 14, 30, 45)),
            (" 10/25/2006 14:30 ", datetime(2006, 10, 25, 14, 30)),
            (" 10/25/2006 ", datetime(2006, 10, 25, 0, 0)),
            (" 10/25/06 14:30:45 ", datetime(2006, 10, 25, 14, 30, 45)),
            (" 10/25/06 ", datetime(2006, 10, 25, 0, 0)),
            (
                " 2014-09-23T22:34:41.614804 ",
                datetime(2014, 9, 23, 22, 34, 41, 614804),
            ),
            (" 2014-09-23T22:34Z ", datetime(2014, 9, 23, 22, 34, tzinfo=timezone.utc)),
        ]
        f = DateTimeField()
        for value, expected_datetime in tests:
            with self.subTest(value=value):
                self.assertEqual(f.clean(value), expected_datetime)

    def test_datetimefield_clean_invalid(self):
        f = DateTimeField()
        msg = "'Enter a valid date/time.'"
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("hello")
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("2006-10-25 4:30 p.m.")
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("   ")
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("2014-09-23T28:23")
        f = DateTimeField(input_formats=["%Y %m %d %I:%M %p"])
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean("2006.10.25 14:30:45")

    def test_datetimefield_clean_input_formats(self):
        tests = [
            (
                "%Y %m %d %I:%M %p",
                (
                    (date(2006, 10, 25), datetime(2006, 10, 25, 0, 0)),
                    (datetime(2006, 10, 25, 14, 30), datetime(2006, 10, 25, 14, 30)),
                    (
                        datetime(2006, 10, 25, 14, 30, 59),
                        datetime(2006, 10, 25, 14, 30, 59),
                    ),
                    (
                        datetime(2006, 10, 25, 14, 30, 59, 200),
                        datetime(2006, 10, 25, 14, 30, 59, 200),
                    ),
                    ("2006 10 25 2:30 PM", datetime(2006, 10, 25, 14, 30)),
                    # ISO-like formats are always accepted.
                    ("2006-10-25 14:30:45", datetime(2006, 10, 25, 14, 30, 45)),
                ),
            ),
            (
                "%Y.%m.%d %H:%M:%S.%f",
                (
                    (
                        "2006.10.25 14:30:45.0002",
                        datetime(2006, 10, 25, 14, 30, 45, 200),
                    ),
                ),
            ),
        ]
        for input_format, values in tests:
            f = DateTimeField(input_formats=[input_format])
            for value, expected_datetime in values:
                with self.subTest(value=value, input_format=input_format):
                    self.assertEqual(f.clean(value), expected_datetime)

    def test_datetimefield_not_required(self):
        """
        Tests the behavior of a DateTimeField when it is not required.

        Verifies that the field correctly handles None and empty string input, 
        returning None in both cases and ensuring that the repr() method 
        accurately reflects this. This check is essential to validate 
        that the field behaves as expected when it is not mandatory.
        """
        f = DateTimeField(required=False)
        self.assertIsNone(f.clean(None))
        self.assertEqual("None", repr(f.clean(None)))
        self.assertIsNone(f.clean(""))
        self.assertEqual("None", repr(f.clean("")))

    def test_datetimefield_changed(self):
        """
        Checks if a DateTimeField considers a datetime object and a string representation as unchanged.

        This test method creates a DateTimeField with a specified format and uses it to compare a datetime object and its string representation.
        It verifies that the field does not consider the two as having changed if the string can be parsed into the same datetime object.

        Args:
            None

        Returns:
            None

        Note:
            The test method implicitly checks the string representation against the datetime object by using the field's has_changed method.

        """
        f = DateTimeField(input_formats=["%Y %m %d %I:%M %p"])
        d = datetime(2006, 9, 17, 14, 30, 0)
        self.assertFalse(f.has_changed(d, "2006 09 17 2:30 PM"))
