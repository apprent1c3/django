import datetime

from django.core.exceptions import ValidationError
from django.forms import Form, SplitDateTimeField
from django.forms.widgets import SplitDateTimeWidget
from django.test import SimpleTestCase


class SplitDateTimeFieldTest(SimpleTestCase):
    def test_splitdatetimefield_1(self):
        """
        Tests the functionality of the SplitDateTimeField class.

        This test case verifies the following scenarios:

        * The field uses the correct widget (SplitDateTimeWidget).
        * The field correctly combines date and time components into a single datetime object.
        * The field raises a ValidationError when the input is empty or None.
        * The field raises a ValidationError when the input is a single string value instead of a list.
        * The field raises a ValidationError when the date or time components are invalid.
        * The field raises a ValidationError with specific error messages for different types of invalid input (e.g., invalid date, invalid time).
        """
        f = SplitDateTimeField()
        self.assertIsInstance(f.widget, SplitDateTimeWidget)
        self.assertEqual(
            datetime.datetime(2006, 1, 10, 7, 30),
            f.clean([datetime.date(2006, 1, 10), datetime.time(7, 30)]),
        )
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        with self.assertRaisesMessage(ValidationError, "'Enter a list of values.'"):
            f.clean("hello")
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid date.', 'Enter a valid time.'"
        ):
            f.clean(["hello", "there"])
        with self.assertRaisesMessage(ValidationError, "'Enter a valid time.'"):
            f.clean(["2006-01-10", "there"])
        with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
            f.clean(["hello", "07:30"])

    def test_splitdatetimefield_2(self):
        """
        Tests the SplitDateTimeField class, which is used for splitting date and time into separate fields.

        The field is tested with various input formats and edge cases to ensure it correctly
        validates and returns datetime objects, or raises ValueError with informative messages
        when the input is invalid. It checks for correct parsing of dates and times, 
        empty values, and invalid date/time formats.

        It verifies that the field behaves as expected when given valid input, such as 
        datetime.date and datetime.time objects, or strings in the format 'YYYY-MM-DD' 
        and 'HH:MM'. It also checks that the field correctly handles invalid input, 
        including strings that cannot be parsed into dates or times, and raises 
        ValidationError with the expected error messages.

        The test also ensures that the field returns None for empty input values, 
        such as None, empty strings, or lists containing empty strings.

        """
        f = SplitDateTimeField(required=False)
        self.assertEqual(
            datetime.datetime(2006, 1, 10, 7, 30),
            f.clean([datetime.date(2006, 1, 10), datetime.time(7, 30)]),
        )
        self.assertEqual(
            datetime.datetime(2006, 1, 10, 7, 30), f.clean(["2006-01-10", "07:30"])
        )
        self.assertIsNone(f.clean(None))
        self.assertIsNone(f.clean(""))
        self.assertIsNone(f.clean([""]))
        self.assertIsNone(f.clean(["", ""]))
        with self.assertRaisesMessage(ValidationError, "'Enter a list of values.'"):
            f.clean("hello")
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid date.', 'Enter a valid time.'"
        ):
            f.clean(["hello", "there"])
        with self.assertRaisesMessage(ValidationError, "'Enter a valid time.'"):
            f.clean(["2006-01-10", "there"])
        with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
            f.clean(["hello", "07:30"])
        with self.assertRaisesMessage(ValidationError, "'Enter a valid time.'"):
            f.clean(["2006-01-10", ""])
        with self.assertRaisesMessage(ValidationError, "'Enter a valid time.'"):
            f.clean(["2006-01-10"])
        with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
            f.clean(["", "07:30"])

    def test_splitdatetimefield_changed(self):
        """
        Checks whether the value of a SplitDateTimeField has changed.

        This function takes a current value and a previous value as input and returns True if the two values are different, False otherwise. The comparison is done by converting the previous value into a datetime object based on the input date formats and comparing it to the current value. The function handles different input formats for the date and time parts of the SplitDateTimeField. The main use case for this function is to determine whether a DateTime field has been modified, typically in the context of a form or other data editing workflow.
        """
        f = SplitDateTimeField(input_date_formats=["%d/%m/%Y"])
        self.assertFalse(
            f.has_changed(["11/01/2012", "09:18:15"], ["11/01/2012", "09:18:15"])
        )
        self.assertTrue(
            f.has_changed(
                datetime.datetime(2008, 5, 6, 12, 40, 00), ["2008-05-06", "12:40:00"]
            )
        )
        self.assertFalse(
            f.has_changed(
                datetime.datetime(2008, 5, 6, 12, 40, 00), ["06/05/2008", "12:40"]
            )
        )
        self.assertTrue(
            f.has_changed(
                datetime.datetime(2008, 5, 6, 12, 40, 00), ["06/05/2008", "12:41"]
            )
        )

    def test_form_as_table(self):
        """
        Tests the rendering of a form as an HTML table. 
        This function verifies that a form containing a SplitDateTimeField is correctly formatted into a table structure, 
        with the field label in the table header and the input fields in the table data cell. 
        It checks for the expected HTML output to ensure that the form is displayed as intended.
        """
        class TestForm(Form):
            datetime = SplitDateTimeField()

        f = TestForm()
        self.assertHTMLEqual(
            f.as_table(),
            "<tr><th><label>Datetime:</label></th><td>"
            '<input type="text" name="datetime_0" required id="id_datetime_0">'
            '<input type="text" name="datetime_1" required id="id_datetime_1">'
            "</td></tr>",
        )
