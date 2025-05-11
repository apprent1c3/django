from datetime import date, datetime, time

from django import forms
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from django.utils import translation


class LocalizedTimeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        # nl/formats.py has customized TIME_INPUT_FORMATS:
        # ['%H:%M:%S', '%H.%M:%S', '%H.%M', '%H:%M']
        cls.enterClassContext(translation.override("nl"))
        super().setUpClass()

    def test_timeField(self):
        """
        Tests that TimeField correctly parses and cleans time strings in the default 24-hour format, handling both full and partial time specifications, and accurately formats the resulting time value for display.
        """
        f = forms.TimeField()
        # Parse a time in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("1:30:05 PM")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13:30:05")
        self.assertEqual(result, time(13, 30, 5))

        # The parsed result does a round trip
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:05")

        # Parse a time in a valid, but non-default format, get a parsed result
        result = f.clean("13:30")
        self.assertEqual(result, time(13, 30, 0))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:00")

        # ISO formats are accepted, even if not specified in formats.py
        result = f.clean("13:30:05.000155")
        self.assertEqual(result, time(13, 30, 5, 155))

    def test_localized_timeField(self):
        """
        Tests the functionality of localized TimeFields, ensuring they act as unlocalized widgets when localize=True is set, by verifying the correct cleaning and formatting of time input strings in 24-hour format.
        """
        f = forms.TimeField(localize=True)
        # Parse a time in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("1:30:05 PM")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13:30:05")
        self.assertEqual(result, time(13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13:30")
        self.assertEqual(result, time(13, 30, 0))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:00")

    def test_timeField_with_inputformat(self):
        """
        Tests that a TimeField with manually specified input formats correctly accepts 
        and validates those formats, and rejects invalid ones, ensuring proper time parsing 
        and formatting according to the specified input formats.
        """
        f = forms.TimeField(input_formats=["%H.%M.%S", "%H.%M"])
        # Parse a time in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("1:30:05 PM")
        with self.assertRaises(ValidationError):
            f.clean("13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13.30.05")
        self.assertEqual(result, time(13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13.30")
        self.assertEqual(result, time(13, 30, 0))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:00")

    def test_localized_timeField_with_inputformat(self):
        """
        Tests the functionality of TimeField with manually specified input formats in a localized environment.

        This test case verifies that TimeField correctly accepts and validates time inputs
        in the specified formats and rejects invalid formats, ensuring proper time parsing
        and formatting as per the localized settings.
        """
        f = forms.TimeField(input_formats=["%H.%M.%S", "%H.%M"], localize=True)
        # Parse a time in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("1:30:05 PM")
        with self.assertRaises(ValidationError):
            f.clean("13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13.30.05")
        self.assertEqual(result, time(13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13.30")
        self.assertEqual(result, time(13, 30, 0))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:00")


@translation.override(None)
@override_settings(TIME_INPUT_FORMATS=["%I:%M:%S %p", "%I:%M %p"])
class CustomTimeInputFormatsTests(SimpleTestCase):
    def test_timeField(self):
        """
        Tests the functionality of TimeField, ensuring it correctly parses and cleans time inputs in the default format, and verifies that the cleaned values are correctly formatted for output.
        """
        f = forms.TimeField()
        # Parse a time in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("1:30:05 PM")
        self.assertEqual(result, time(13, 30, 5))

        # The parsed result does a round trip
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:05 PM")

        # Parse a time in a valid, but non-default format, get a parsed result
        result = f.clean("1:30 PM")
        self.assertEqual(result, time(13, 30, 0))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:00 PM")

    def test_localized_timeField(self):
        """
        Tests the functionality of a localized TimeField, ensuring it accepts times in the local format and returns the corresponding time object, while rejecting unlocalized input.
        """
        f = forms.TimeField(localize=True)
        # Parse a time in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("1:30:05 PM")
        self.assertEqual(result, time(13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:05 PM")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("01:30 PM")
        self.assertEqual(result, time(13, 30, 0))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:00 PM")

    def test_timeField_with_inputformat(self):
        """
        Tests that TimeField can correctly parse and validate time inputs when custom input formats are specified, ensuring that only the specified formats are accepted.
        """
        f = forms.TimeField(input_formats=["%H.%M.%S", "%H.%M"])
        # Parse a time in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("1:30:05 PM")
        with self.assertRaises(ValidationError):
            f.clean("13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13.30.05")
        self.assertEqual(result, time(13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:05 PM")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13.30")
        self.assertEqual(result, time(13, 30, 0))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:00 PM")

    def test_localized_timeField_with_inputformat(self):
        """
        Tests that a localized TimeField accepts input in the specified formats when the input format is manually defined.
        """
        f = forms.TimeField(input_formats=["%H.%M.%S", "%H.%M"], localize=True)
        # Parse a time in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("1:30:05 PM")
        with self.assertRaises(ValidationError):
            f.clean("13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13.30.05")
        self.assertEqual(result, time(13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:05 PM")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13.30")
        self.assertEqual(result, time(13, 30, 0))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:00 PM")


class SimpleTimeFormatTests(SimpleTestCase):
    def test_timeField(self):
        """
        Verifies that TimeFields correctly parse and format time values in the default format (HH:MM:SS).
        """
        f = forms.TimeField()
        # Parse a time in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("1:30:05 PM")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13:30:05")
        self.assertEqual(result, time(13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:05")

        # Parse a time in a valid, but non-default format, get a parsed result
        result = f.clean("13:30")
        self.assertEqual(result, time(13, 30, 0))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:00")

    def test_localized_timeField(self):
        """
        Tests the behavior of TimeField when localized and unlocalized, verifying 
        that it correctly validates and formats time values in both 12-hour and 24-hour formats.
        """
        f = forms.TimeField()
        # Parse a time in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("1:30:05 PM")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13:30:05")
        self.assertEqual(result, time(13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("13:30")
        self.assertEqual(result, time(13, 30, 0))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:00")

    def test_timeField_with_inputformat(self):
        """
        Tests that a TimeField with manually specified input formats correctly parses and validates input, while also correctly formatting output values.
        """
        f = forms.TimeField(input_formats=["%I:%M:%S %p", "%I:%M %p"])
        # Parse a time in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("1:30:05 PM")
        self.assertEqual(result, time(13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("1:30 PM")
        self.assertEqual(result, time(13, 30, 0))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:00")

    def test_localized_timeField_with_inputformat(self):
        """
        Tests if a localized TimeField can correctly parse and clean time inputs when a specific input format is provided, checking both success and error cases.
        """
        f = forms.TimeField(input_formats=["%I:%M:%S %p", "%I:%M %p"], localize=True)
        # Parse a time in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("1:30:05 PM")
        self.assertEqual(result, time(13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:05")

        # Parse a time in a valid format, get a parsed result
        result = f.clean("1:30 PM")
        self.assertEqual(result, time(13, 30, 0))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "13:30:00")


class LocalizedDateTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(translation.override("de"))
        super().setUpClass()

    def test_dateField(self):
        """
        Tests the functionality of DateField to parse dates in the default format, 
        ensuring it correctly handles clean and formatting operations.
        """
        f = forms.DateField()
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("21/12/2010")

        # ISO formats are accepted, even if not specified in formats.py
        self.assertEqual(f.clean("2010-12-21"), date(2010, 12, 21))

        # Parse a date in a valid format, get a parsed result
        result = f.clean("21.12.2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

        # Parse a date in a valid, but non-default format, get a parsed result
        result = f.clean("21.12.10")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

    def test_localized_dateField(self):
        """
        Tests the functionality of a localized DateField in a form, verifying that it correctly parses and formats dates according to the locale's conventions, and raises a ValidationError for invalid input.
        """
        f = forms.DateField(localize=True)
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("21/12/2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("21.12.2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("21.12.10")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

    def test_dateField_with_inputformat(self):
        """
        Tests the functionality of a DateField when an input format is manually specified.

         Verifies that DateFields only accept the specified input formats and correctly parse dates from those formats.
        """
        f = forms.DateField(input_formats=["%m.%d.%Y", "%m-%d-%Y"])
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("2010-12-21")
        with self.assertRaises(ValidationError):
            f.clean("21/12/2010")
        with self.assertRaises(ValidationError):
            f.clean("21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12.21.2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12-21-2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

    def test_localized_dateField_with_inputformat(self):
        """
        Tests whether a localized DateField with manually specified input formats correctly validates and parses date strings according to those formats, and checks if the field's widget formats the date value as expected.
        """
        f = forms.DateField(input_formats=["%m.%d.%Y", "%m-%d-%Y"], localize=True)
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("2010-12-21")
        with self.assertRaises(ValidationError):
            f.clean("21/12/2010")
        with self.assertRaises(ValidationError):
            f.clean("21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12.21.2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12-21-2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")


@translation.override(None)
@override_settings(DATE_INPUT_FORMATS=["%d.%m.%Y", "%d-%m-%Y"])
class CustomDateInputFormatsTests(SimpleTestCase):
    def test_dateField(self):
        """
        Verifies that a DateField correctly parses and formats dates according to its default settings, ensuring that valid dates are returned and invalid ones raise a ValidationError.
        """
        f = forms.DateField()
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("2010-12-21")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("21.12.2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

        # Parse a date in a valid, but non-default format, get a parsed result
        result = f.clean("21-12-2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

    def test_localized_dateField(self):
        """
        Tests the functionality of a localized DateField in a form, verifying that it correctly handles dates in localized format and raises an error for unlocalized input.
        """
        f = forms.DateField(localize=True)
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("2010-12-21")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("21.12.2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("21-12-2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

    def test_dateField_with_inputformat(self):
        """
        Tests that DateField can correctly parse and format dates according to a manually specified input format, ensuring that only the defined formats are accepted and dates are displayed correctly.
        """
        f = forms.DateField(input_formats=["%m.%d.%Y", "%m-%d-%Y"])
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("21.12.2010")
        with self.assertRaises(ValidationError):
            f.clean("2010-12-21")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12.21.2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12-21-2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

    def test_localized_dateField_with_inputformat(self):
        """
        Tests whether a localized DateField with custom input formats can properly parse and validate dates in those formats.
        """
        f = forms.DateField(input_formats=["%m.%d.%Y", "%m-%d-%Y"], localize=True)
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("21.12.2010")
        with self.assertRaises(ValidationError):
            f.clean("2010-12-21")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12.21.2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12-21-2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010")


class SimpleDateFormatTests(SimpleTestCase):
    def test_dateField(self):
        """
        Verifies that DateField properly handles date parsing and formatting, ensuring it raises an error for invalid formats and correctly parses dates in the default and alternative formats.
        """
        f = forms.DateField()
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("2010-12-21")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21")

        # Parse a date in a valid, but non-default format, get a parsed result
        result = f.clean("12/21/2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21")

    def test_localized_dateField(self):
        """
        Tests that a localized DateField in a non-localized environment behaves as an unlocalized widget, accepting and formatting dates according to the standard format (YYYY-MM-DD).
        """
        f = forms.DateField()
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("2010-12-21")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12/21/2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21")

    def test_dateField_with_inputformat(self):
        """
        Tests DateField functionality with manually specified input formats to ensure correct date parsing and validation.
        """
        f = forms.DateField(input_formats=["%d.%m.%Y", "%d-%m-%Y"])
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("2010-12-21")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("21.12.2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("21-12-2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21")

    def test_localized_dateField_with_inputformat(self):
        """
        Tests that a localized DateField with a manually specified input format correctly accepts and validates date inputs in the specified formats.
        """
        f = forms.DateField(input_formats=["%d.%m.%Y", "%d-%m-%Y"], localize=True)
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("2010-12-21")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("21.12.2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("21-12-2010")
        self.assertEqual(result, date(2010, 12, 21))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21")


class LocalizedDateTimeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(translation.override("de"))
        super().setUpClass()

    def test_dateTimeField(self):
        """
        Tests that DateTimeField correctly parses dates in various formats and raises a ValidationError for invalid dates.
        """
        f = forms.DateTimeField()
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("1:30:05 PM 21/12/2010")

        # ISO formats are accepted, even if not specified in formats.py
        self.assertEqual(
            f.clean("2010-12-21 13:30:05"), datetime(2010, 12, 21, 13, 30, 5)
        )

        # Parse a date in a valid format, get a parsed result
        result = f.clean("21.12.2010 13:30:05")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30, 5))

        # The parsed result does a round trip
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010 13:30:05")

        # Parse a date in a valid, but non-default format, get a parsed result
        result = f.clean("21.12.2010 13:30")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010 13:30:00")

    def test_localized_dateTimeField(self):
        """
        Tests the behavior of a localized DateTimeField, verifying that it raises a ValidationError for unlocalized input and correctly cleans and formats localized input.
        """
        f = forms.DateTimeField(localize=True)
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("1:30:05 PM 21/12/2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("21.12.2010 13:30:05")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010 13:30:05")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("21.12.2010 13:30")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010 13:30:00")

    def test_dateTimeField_with_inputformat(self):
        """
        Tests that DateTimeField with custom input formats correctly validates and cleans input dates, 
        and that the cleaned dates are formatted correctly when rendered as text. 
        Verifies that dates with invalid formats raise a ValidationError.
        """
        f = forms.DateTimeField(input_formats=["%H.%M.%S %m.%d.%Y", "%H.%M %m-%d-%Y"])
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("2010-12-21 13:30:05 13:30:05")
        with self.assertRaises(ValidationError):
            f.clean("1:30:05 PM 21/12/2010")
        with self.assertRaises(ValidationError):
            f.clean("13:30:05 21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("13.30.05 12.21.2010")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010 13:30:05")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("13.30 12-21-2010")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010 13:30:00")

    def test_localized_dateTimeField_with_inputformat(self):
        """
        Verify that a localized DateTimeField accepts manually specified input formats and rejects invalid formats, while also correctly formatting the output value.
        """
        f = forms.DateTimeField(
            input_formats=["%H.%M.%S %m.%d.%Y", "%H.%M %m-%d-%Y"], localize=True
        )
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("2010/12/21 13:30:05")
        with self.assertRaises(ValidationError):
            f.clean("1:30:05 PM 21/12/2010")
        with self.assertRaises(ValidationError):
            f.clean("13:30:05 21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("13.30.05 12.21.2010")
        self.assertEqual(datetime(2010, 12, 21, 13, 30, 5), result)
        # ISO format is always valid.
        self.assertEqual(
            f.clean("2010-12-21 13:30:05"),
            datetime(2010, 12, 21, 13, 30, 5),
        )
        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010 13:30:05")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("13.30 12-21-2010")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "21.12.2010 13:30:00")


@translation.override(None)
@override_settings(DATETIME_INPUT_FORMATS=["%I:%M:%S %p %d/%m/%Y", "%I:%M %p %d-%m-%Y"])
class CustomDateTimeInputFormatsTests(SimpleTestCase):
    def test_dateTimeField(self):
        """
        Tests the DateTimeField's ability to parse dates in various formats and validate input, ensuring correct output and error handling for invalid date strings.
        """
        f = forms.DateTimeField()
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("2010/12/21 13:30:05")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("1:30:05 PM 21/12/2010")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30, 5))

        # The parsed result does a round trip
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:05 PM 21/12/2010")

        # Parse a date in a valid, but non-default format, get a parsed result
        result = f.clean("1:30 PM 21-12-2010")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:00 PM 21/12/2010")

    def test_localized_dateTimeField(self):
        """
        Tests the functionality of a localized DateTimeField, ensuring it correctly handles date and time formatting based on the locale, and raises validation errors for unparseable inputs.
        """
        f = forms.DateTimeField(localize=True)
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("2010/12/21 13:30:05")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("1:30:05 PM 21/12/2010")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:05 PM 21/12/2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("1:30 PM 21-12-2010")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:00 PM 21/12/2010")

    def test_dateTimeField_with_inputformat(self):
        """
        Tests the functionality of a DateTimeField with custom input formats, ensuring it correctly validates and processes dates in the specified formats, and raises validation errors for invalid formats.
        """
        f = forms.DateTimeField(input_formats=["%m.%d.%Y %H:%M:%S", "%m-%d-%Y %H:%M"])
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("13:30:05 21.12.2010")
        with self.assertRaises(ValidationError):
            f.clean("2010/12/21 13:30:05")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12.21.2010 13:30:05")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:05 PM 21/12/2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12-21-2010 13:30")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:00 PM 21/12/2010")

    def test_localized_dateTimeField_with_inputformat(self):
        """
        Tests that a localized DateTimeField can correctly parse dates using manually specified input formats and reject invalid formats.
        """
        f = forms.DateTimeField(
            input_formats=["%m.%d.%Y %H:%M:%S", "%m-%d-%Y %H:%M"], localize=True
        )
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("13:30:05 21.12.2010")
        with self.assertRaises(ValidationError):
            f.clean("2010/12/21 13:30:05")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12.21.2010 13:30:05")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:05 PM 21/12/2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12-21-2010 13:30")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "01:30:00 PM 21/12/2010")


class SimpleDateTimeFormatTests(SimpleTestCase):
    def test_dateTimeField(self):
        """
        Tests the parsing and formatting of DateTimeField in a form. It verifies that 
        the field correctly handles and rejects dates not in the expected format, 
        and that it stores and displays dates in the expected format.
        """
        f = forms.DateTimeField()
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("13:30:05 21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("2010-12-21 13:30:05")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21 13:30:05")

        # Parse a date in a valid, but non-default format, get a parsed result
        result = f.clean("12/21/2010 13:30:05")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30, 5))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21 13:30:05")

    def test_localized_dateTimeField(self):
        """
        Tests the functionality of a DateTimeField in a non-localized environment, verifying its behavior, input validation, and output formatting.
        """
        f = forms.DateTimeField()
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("13:30:05 21.12.2010")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("2010-12-21 13:30:05")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21 13:30:05")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("12/21/2010 13:30:05")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30, 5))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21 13:30:05")

    def test_dateTimeField_with_inputformat(self):
        """
        Tests that a DateTimeField with custom input formats can correctly parse and validate dates in those formats.
        """
        f = forms.DateTimeField(
            input_formats=["%I:%M:%S %p %d.%m.%Y", "%I:%M %p %d-%m-%Y"]
        )
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("2010/12/21 13:30:05")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("1:30:05 PM 21.12.2010")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21 13:30:05")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("1:30 PM 21-12-2010")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21 13:30:00")

    def test_localized_dateTimeField_with_inputformat(self):
        """
        Tests that a DateTimeField with manually specified input formats, when localized, correctly accepts and parses those formats, while rejecting invalid formats.
        """
        f = forms.DateTimeField(
            input_formats=["%I:%M:%S %p %d.%m.%Y", "%I:%M %p %d-%m-%Y"], localize=True
        )
        # Parse a date in an unaccepted format; get an error
        with self.assertRaises(ValidationError):
            f.clean("2010/12/21 13:30:05")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("1:30:05 PM 21.12.2010")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30, 5))

        # The parsed result does a round trip to the same format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21 13:30:05")

        # Parse a date in a valid format, get a parsed result
        result = f.clean("1:30 PM 21-12-2010")
        self.assertEqual(result, datetime(2010, 12, 21, 13, 30))

        # The parsed result does a round trip to default format
        text = f.widget.format_value(result)
        self.assertEqual(text, "2010-12-21 13:30:00")
