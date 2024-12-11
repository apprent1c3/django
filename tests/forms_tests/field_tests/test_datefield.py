import sys
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.forms import DateField, Form, HiddenInput, SelectDateWidget
from django.test import SimpleTestCase
from django.utils import translation


class GetDate(Form):
    mydate = DateField(widget=SelectDateWidget)


class DateFieldTest(SimpleTestCase):
    def test_form_field(self):
        a = GetDate({"mydate_month": "4", "mydate_day": "1", "mydate_year": "2008"})
        self.assertTrue(a.is_valid())
        self.assertEqual(a.cleaned_data["mydate"], date(2008, 4, 1))

        # As with any widget that implements get_value_from_datadict(), we must
        # accept the input from the "as_hidden" rendering as well.
        self.assertHTMLEqual(
            a["mydate"].as_hidden(),
            '<input type="hidden" name="mydate" value="2008-04-01" id="id_mydate">',
        )

        b = GetDate({"mydate": "2008-4-1"})
        self.assertTrue(b.is_valid())
        self.assertEqual(b.cleaned_data["mydate"], date(2008, 4, 1))

        # Invalid dates shouldn't be allowed
        c = GetDate({"mydate_month": "2", "mydate_day": "31", "mydate_year": "2010"})
        self.assertFalse(c.is_valid())
        self.assertEqual(c.errors, {"mydate": ["Enter a valid date."]})

        # label tag is correctly associated with month dropdown
        d = GetDate({"mydate_month": "1", "mydate_day": "1", "mydate_year": "2010"})
        self.assertIn('<label for="id_mydate_month">', d.as_p())

        # Inputs raising an OverflowError.
        e = GetDate(
            {
                "mydate_month": str(sys.maxsize + 1),
                "mydate_day": "31",
                "mydate_year": "2010",
            }
        )
        self.assertIs(e.is_valid(), False)
        self.assertEqual(e.errors, {"mydate": ["Enter a valid date."]})

    @translation.override("nl")
    def test_l10n_date_changed(self):
        """
        DateField.has_changed() with SelectDateWidget works with a localized
        date format (#17165).
        """
        # With Field.show_hidden_initial=False
        b = GetDate(
            {
                "mydate_year": "2008",
                "mydate_month": "4",
                "mydate_day": "1",
            },
            initial={"mydate": date(2008, 4, 1)},
        )
        self.assertFalse(b.has_changed())

        b = GetDate(
            {
                "mydate_year": "2008",
                "mydate_month": "4",
                "mydate_day": "2",
            },
            initial={"mydate": date(2008, 4, 1)},
        )
        self.assertTrue(b.has_changed())

        # With Field.show_hidden_initial=True
        class GetDateShowHiddenInitial(Form):
            mydate = DateField(widget=SelectDateWidget, show_hidden_initial=True)

        b = GetDateShowHiddenInitial(
            {
                "mydate_year": "2008",
                "mydate_month": "4",
                "mydate_day": "1",
                "initial-mydate": HiddenInput().format_value(date(2008, 4, 1)),
            },
            initial={"mydate": date(2008, 4, 1)},
        )
        self.assertFalse(b.has_changed())

        b = GetDateShowHiddenInitial(
            {
                "mydate_year": "2008",
                "mydate_month": "4",
                "mydate_day": "22",
                "initial-mydate": HiddenInput().format_value(date(2008, 4, 1)),
            },
            initial={"mydate": date(2008, 4, 1)},
        )
        self.assertTrue(b.has_changed())

        b = GetDateShowHiddenInitial(
            {
                "mydate_year": "2008",
                "mydate_month": "4",
                "mydate_day": "22",
                "initial-mydate": HiddenInput().format_value(date(2008, 4, 1)),
            },
            initial={"mydate": date(2008, 4, 22)},
        )
        self.assertTrue(b.has_changed())

        b = GetDateShowHiddenInitial(
            {
                "mydate_year": "2008",
                "mydate_month": "4",
                "mydate_day": "22",
                "initial-mydate": HiddenInput().format_value(date(2008, 4, 22)),
            },
            initial={"mydate": date(2008, 4, 1)},
        )
        self.assertFalse(b.has_changed())

    @translation.override("nl")
    def test_l10n_invalid_date_in(self):
        # Invalid dates shouldn't be allowed
        a = GetDate({"mydate_month": "2", "mydate_day": "31", "mydate_year": "2010"})
        self.assertFalse(a.is_valid())
        # 'Geef een geldige datum op.' = 'Enter a valid date.'
        self.assertEqual(a.errors, {"mydate": ["Voer een geldige datum in."]})

    @translation.override("nl")
    def test_form_label_association(self):
        # label tag is correctly associated with first rendered dropdown
        """

        Tests whether the form date field is properly associated with its corresponding label.

        This test case ensures that the label for the day component of a date field
        is correctly linked to the input field, as per HTML accessibility standards.
        It verifies this by checking if the label's 'for' attribute matches the id
        of the day input field in the rendered HTML form.

        The test is performed using a sample date ('2010-01-01') and asserts that
        the expected label is present in the form's paragraph representation.

        """
        a = GetDate({"mydate_month": "1", "mydate_day": "1", "mydate_year": "2010"})
        self.assertIn('<label for="id_mydate_day">', a.as_p())

    def test_datefield_1(self):
        """
        Test that DateField correctly cleans and validates various date formats.

        This test checks the following:

        * It can handle various input formats: date objects, datetime objects, and strings in different formats (YYYY-MM-DD, MM/DD/YYYY, MM/DD/YY, Month DD YYYY, etc.)
        * It can extract the date from a datetime object, ignoring the time component
        * It correctly raises a ValidationError for invalid dates (e.g. February 31, invalid date strings)
        * It correctly raises a ValidationError when the input is None, as this field is required

        Returns:
            None

        Raises:
            ValidationError: if the input is an invalid date or None
        """
        f = DateField()
        self.assertEqual(date(2006, 10, 25), f.clean(date(2006, 10, 25)))
        self.assertEqual(date(2006, 10, 25), f.clean(datetime(2006, 10, 25, 14, 30)))
        self.assertEqual(
            date(2006, 10, 25), f.clean(datetime(2006, 10, 25, 14, 30, 59))
        )
        self.assertEqual(
            date(2006, 10, 25), f.clean(datetime(2006, 10, 25, 14, 30, 59, 200))
        )
        self.assertEqual(date(2006, 10, 25), f.clean("2006-10-25"))
        self.assertEqual(date(2006, 10, 25), f.clean("10/25/2006"))
        self.assertEqual(date(2006, 10, 25), f.clean("10/25/06"))
        self.assertEqual(date(2006, 10, 25), f.clean("Oct 25 2006"))
        self.assertEqual(date(2006, 10, 25), f.clean("October 25 2006"))
        self.assertEqual(date(2006, 10, 25), f.clean("October 25, 2006"))
        self.assertEqual(date(2006, 10, 25), f.clean("25 October 2006"))
        self.assertEqual(date(2006, 10, 25), f.clean("25 October, 2006"))
        with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
            f.clean("2006-4-31")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
            f.clean("200a-10-25")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
            f.clean("25/10/06")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
            f.clean("0-0-0")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)

    def test_datefield_2(self):
        f = DateField(required=False)
        self.assertIsNone(f.clean(None))
        self.assertEqual("None", repr(f.clean(None)))
        self.assertIsNone(f.clean(""))
        self.assertEqual("None", repr(f.clean("")))

    def test_datefield_3(self):
        """

        Tests the validation and cleaning functionality of the DateField.

        The function verifies that DateField correctly validates and cleans different date formats.
        It checks if the field can handle date objects, datetime objects, and string representations of dates.
        Additionally, it ensures that the field raises a ValidationError for invalid date formats.

        The expected output formats and validation rules are based on the input formats specified for the DateField.
        In this case, the field is configured to accept dates in the format '%Y %m %d'.

        The test cases cover a variety of scenarios, including:

        * Valid date objects and datetime objects
        * Valid string representations of dates
        * Invalid date formats that should raise a ValidationError

        """
        f = DateField(input_formats=["%Y %m %d"])
        self.assertEqual(date(2006, 10, 25), f.clean(date(2006, 10, 25)))
        self.assertEqual(date(2006, 10, 25), f.clean(datetime(2006, 10, 25, 14, 30)))
        self.assertEqual(date(2006, 10, 25), f.clean("2006 10 25"))
        with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
            f.clean("2006-10-25")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
            f.clean("10/25/2006")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
            f.clean("10/25/06")

    def test_datefield_4(self):
        # Test whitespace stripping behavior (#5714)
        """

        Tests the functionality of the DateField class for cleaning and validating date inputs.

        Checks that the clean method correctly parses various date formats, including:
            - mm/dd/yyyy
            - mm/dd/yy
            - Month dd yyyy
            - Month dd, yyyy
            - dd Month yyyy

        Verifies that the clean method raises a ValidationError when an empty or invalid date string is provided.

        """
        f = DateField()
        self.assertEqual(date(2006, 10, 25), f.clean(" 10/25/2006 "))
        self.assertEqual(date(2006, 10, 25), f.clean(" 10/25/06 "))
        self.assertEqual(date(2006, 10, 25), f.clean(" Oct 25   2006 "))
        self.assertEqual(date(2006, 10, 25), f.clean(" October  25 2006 "))
        self.assertEqual(date(2006, 10, 25), f.clean(" October 25, 2006 "))
        self.assertEqual(date(2006, 10, 25), f.clean(" 25 October 2006 "))
        with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
            f.clean("   ")

    def test_datefield_5(self):
        # Test null bytes (#18982)
        f = DateField()
        with self.assertRaisesMessage(ValidationError, "'Enter a valid date.'"):
            f.clean("a\x00b")

    def test_datefield_changed(self):
        """
        Tests whether a DateField has changed when the input date matches the stored date.

        Checks that the 'has_changed' method of a DateField returns False when the input date
        and the stored date are the same, when the date is provided in a specific format.

        :param: None
        :return: None (asserts the False condition)
        :raises: AssertionError if the 'has_changed' method returns True when dates are the same
        """
        format = "%d/%m/%Y"
        f = DateField(input_formats=[format])
        d = date(2007, 9, 17)
        self.assertFalse(f.has_changed(d, "17/09/2007"))

    def test_datefield_strptime(self):
        """field.strptime() doesn't raise a UnicodeEncodeError (#16123)"""
        f = DateField()
        try:
            f.strptime("31 мая 2011", "%d-%b-%y")
        except Exception as e:
            # assertIsInstance or assertRaises cannot be used because UnicodeEncodeError
            # is a subclass of ValueError
            self.assertEqual(e.__class__, ValueError)
