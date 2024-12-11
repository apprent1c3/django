from datetime import date, datetime, timezone

from django.core.exceptions import ValidationError
from django.forms import DateTimeField
from django.test import SimpleTestCase
from django.utils.timezone import get_fixed_timezone


class DateTimeFieldTest(SimpleTestCase):
    def test_datetimefield_clean(self):
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
        """

        Tests the DateTimeField's clean method for handling invalid input.

        This test case verifies that the DateTimeField correctly raises a ValidationError when
        given a variety of invalid date and time formats. The test covers various scenarios,
        including non-date strings, malformed date strings, and whitespace-only input.

        It also checks that the field's input_formats parameter is respected when validating
        input. If the input format does not match any of the specified formats, a ValidationError
        is raised with a message indicating that the input is not a valid date/time.

        """
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
        """
        Tests that the DateTimeField correctly handles clean input for various date and time formats.

        The function verifies that different input formats are correctly parsed and converted into datetime objects. 
        It uses a set of predefined test cases, each with a specific date and time format string and a list of input values along with their expected datetime outputs.
        For each test case, it initializes a DateTimeField with the specified input format and checks if the clean method produces the expected datetime output for each input value.
        """
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
        Tests the functionality of DateTimeField when not required, particularly its handling of None and empty string inputs, ensuring it returns and represents None correctly in both cases.
        """
        f = DateTimeField(required=False)
        self.assertIsNone(f.clean(None))
        self.assertEqual("None", repr(f.clean(None)))
        self.assertIsNone(f.clean(""))
        self.assertEqual("None", repr(f.clean("")))

    def test_datetimefield_changed(self):
        """
        Tests whether a DateTimeField instance correctly detects changes when 
        given a specific date and time and its string representation. 

        The function verifies that when the DateTimeField is initialized with a custom 
        input format, it accurately identifies whether the provided datetime object 
        and its string representation are considered changed or not. 

        Args:
            None

        Returns:
            None

        Note:
            This function is a test case and does not return any values. It uses 
            assertion statements to verify the expected behavior of the DateTimeField 
            instance.

        """
        f = DateTimeField(input_formats=["%Y %m %d %I:%M %p"])
        d = datetime(2006, 9, 17, 14, 30, 0)
        self.assertFalse(f.has_changed(d, "2006 09 17 2:30 PM"))
