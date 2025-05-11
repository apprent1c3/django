import datetime

from django.core.exceptions import ValidationError
from django.forms import Form, SplitDateTimeField
from django.forms.widgets import SplitDateTimeWidget
from django.test import SimpleTestCase


class SplitDateTimeFieldTest(SimpleTestCase):
    def test_splitdatetimefield_1(self):
        """
        Tests the functionality of a SplitDateTimeField by verifying its widget, validation, and error handling. 

        The test checks that the widget is a SplitDateTimeWidget and that the clean method correctly handles valid and invalid input, including required fields, empty strings, and invalid dates and times.
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

        Tests the cleaning functionality of a SplitDateTimeField.
        Verifies that it correctly handles various input formats, including datetime objects, date and time strings, 
        and empty or invalid inputs, raising ValidationError where necessary.

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
        Checks whether a SplitDateTimeField has changed. This function tests whether the field's current value is different from its initial value, considering various input formats.
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
