from datetime import datetime, time

from django.template.defaultfilters import date
from django.test import SimpleTestCase
from django.utils import timezone, translation

from ..utils import setup
from .timezone_utils import TimezoneTestCase


class DateTests(TimezoneTestCase):
    @setup({"date01": '{{ d|date:"m" }}'})
    def test_date01(self):
        """
        Tests the rendering of a date object as a month string.

        This test case verifies that the date object is correctly formatted as a two-digit month string.
        It checks if the rendered output matches the expected month value when the date object is January 1, 2008.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Notes
        -----
        This test is part of the setup for testing date-related functionality in the templating engine.

        """
        output = self.engine.render_to_string("date01", {"d": datetime(2008, 1, 1)})
        self.assertEqual(output, "01")

    @setup({"date02": "{{ d|date }}"})
    def test_date02(self):
        """
        Tests the rendering of a date object using the date filter.

        The function verifies that a datetime object is correctly formatted as a string
        when passed through the date filter. It checks that the output matches the expected
        format 'Month. Day, Year'.

        :raises AssertionError: if the rendered date string does not match the expected output.
        """
        output = self.engine.render_to_string("date02", {"d": datetime(2008, 1, 1)})
        self.assertEqual(output, "Jan. 1, 2008")

    @setup({"date02_l10n": "{{ d|date }}"})
    def test_date02_l10n(self):
        """Without arg, the active language's DATE_FORMAT is used."""
        with translation.override("fr"):
            output = self.engine.render_to_string(
                "date02_l10n", {"d": datetime(2008, 1, 1)}
            )
        self.assertEqual(output, "1 janvier 2008")

    @setup({"date03": '{{ d|date:"m" }}'})
    def test_date03(self):
        """
        #9520: Make sure |date doesn't blow up on non-dates
        """
        output = self.engine.render_to_string("date03", {"d": "fail_string"})
        self.assertEqual(output, "")

    # ISO date formats
    @setup({"date04": '{{ d|date:"o" }}'})
    def test_date04(self):
        """
        Tests rendering of a date in the 'o' format, which represents the ISO-8601 year.


        This test ensures that when a date is rendered, the year calculated according to the ISO week date system is correctly displayed.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the rendered date string does not match the expected output.

        Note:
            The date used for testing (December 29, 2008) is near the end of the year and 
            thus is part of the first week of the following year according to the ISO 
            week date system, which is why the rendered year should be 2009.
        """
        output = self.engine.render_to_string("date04", {"d": datetime(2008, 12, 29)})
        self.assertEqual(output, "2009")

    @setup({"date05": '{{ d|date:"o" }}'})
    def test_date05(self):
        output = self.engine.render_to_string("date05", {"d": datetime(2010, 1, 3)})
        self.assertEqual(output, "2009")

    # Timezone name
    @setup({"date06": '{{ d|date:"e" }}'})
    def test_date06(self):
        output = self.engine.render_to_string(
            "date06",
            {"d": datetime(2009, 3, 12, tzinfo=timezone.get_fixed_timezone(30))},
        )
        self.assertEqual(output, "+0030")

    @setup({"date07": '{{ d|date:"e" }}'})
    def test_date07(self):
        """
        Tests date filtering of a date object with an invalid format specifier.

        The function verifies that rendering a template with a date object and an invalid format specifier results in an empty string.

        :param self: The test instance
        :raises AssertionError: If the rendered output does not match the expected empty string
        """
        output = self.engine.render_to_string("date07", {"d": datetime(2009, 3, 12)})
        self.assertEqual(output, "")

    # #19370: Make sure |date doesn't blow up on a midnight time object
    @setup({"date08": '{{ t|date:"H:i" }}'})
    def test_date08(self):
        """

        Tests the rendering of a date string in the format \"H:i\" using the Jinja2 templating engine.

        The test case verifies that the date object is correctly formatted as a string in 24-hour format with hours and minutes.

        """
        output = self.engine.render_to_string("date08", {"t": time(0, 1)})
        self.assertEqual(output, "00:01")

    @setup({"date09": '{{ t|date:"H:i" }}'})
    def test_date09(self):
        """

        Test the date formatting functionality to ensure it produces the expected output.

        Specifically, this test verifies that the 'date09' template is correctly rendered
        with a time object, formatted as hours and minutes in 24-hour format ('H:i').
        The expected output is a string representing the time '00:00'.

        """
        output = self.engine.render_to_string("date09", {"t": time(0, 0)})
        self.assertEqual(output, "00:00")

    @setup({"datelazy": '{{ t|date:_("H:i") }}'})
    def test_date_lazy(self):
        output = self.engine.render_to_string("datelazy", {"t": time(0, 0)})
        self.assertEqual(output, "00:00")


class FunctionTests(SimpleTestCase):
    def test_date(self):
        self.assertEqual(date(datetime(2005, 12, 29), "d F Y"), "29 December 2005")

    def test_no_args(self):
        self.assertEqual(date(""), "")
        self.assertEqual(date(None), "")

    def test_escape_characters(self):
        self.assertEqual(date(datetime(2005, 12, 29), r"jS \o\f F"), "29th of December")
