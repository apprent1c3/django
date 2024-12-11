from datetime import datetime, timedelta

from django.template.defaultfilters import timeuntil_filter
from django.test import SimpleTestCase
from django.test.utils import requires_tz_support

from ..utils import setup
from .timezone_utils import TimezoneTestCase


class TimeuntilTests(TimezoneTestCase):
    # Default compare with datetime.now()
    @setup({"timeuntil01": "{{ a|timeuntil }}"})
    def test_timeuntil01(self):
        """
        Tests the timeuntil function to ensure it correctly calculates the time difference until a given datetime object and formats it as a human-readable string, specifically verifying that it omits seconds from the output when the time difference is in minutes.
        """
        output = self.engine.render_to_string(
            "timeuntil01", {"a": datetime.now() + timedelta(minutes=2, seconds=10)}
        )
        self.assertEqual(output, "2\xa0minutes")

    @setup({"timeuntil02": "{{ a|timeuntil }}"})
    def test_timeuntil02(self):
        output = self.engine.render_to_string(
            "timeuntil02", {"a": (datetime.now() + timedelta(days=1, seconds=10))}
        )
        self.assertEqual(output, "1\xa0day")

    @setup({"timeuntil03": "{{ a|timeuntil }}"})
    def test_timeuntil03(self):
        output = self.engine.render_to_string(
            "timeuntil03",
            {"a": (datetime.now() + timedelta(hours=8, minutes=10, seconds=10))},
        )
        self.assertEqual(output, "8\xa0hours, 10\xa0minutes")

    # Compare to a given parameter
    @setup({"timeuntil04": "{{ a|timeuntil:b }}"})
    def test_timeuntil04(self):
        output = self.engine.render_to_string(
            "timeuntil04",
            {"a": self.now - timedelta(days=1), "b": self.now - timedelta(days=2)},
        )
        self.assertEqual(output, "1\xa0day")

    @setup({"timeuntil05": "{{ a|timeuntil:b }}"})
    def test_timeuntil05(self):
        """

        Tests the timeuntil template filter, verifying that it correctly calculates the time difference between two datetime objects.

        The function checks the filter's output when the input datetimes have a difference of one minute, ensuring the result is displayed in the expected format.

        """
        output = self.engine.render_to_string(
            "timeuntil05",
            {
                "a": self.now - timedelta(days=2),
                "b": self.now - timedelta(days=2, minutes=1),
            },
        )
        self.assertEqual(output, "1\xa0minute")

    # Regression for #7443
    @setup({"timeuntil06": "{{ earlier|timeuntil }}"})
    def test_timeuntil06(self):
        """
        Tests the timeuntil template filter to ensure it returns the correct time difference when the provided date is 7 days in the past. The test verifies that the output is rounded down to the nearest minute and does not display any hours or days when the time difference is less than 1 hour.
        """
        output = self.engine.render_to_string(
            "timeuntil06", {"earlier": self.now - timedelta(days=7)}
        )
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timeuntil07": "{{ earlier|timeuntil:now }}"})
    def test_timeuntil07(self):
        """
        Tests the timeuntil filter with a time in the past.

        This test case checks that when the input time is 7 days earlier than the current time,
        the timeuntil filter returns '0 minutes', indicating that the time has already passed.

        Args:
            None

        Returns:
            None

        Asserts that the timeuntil filter behaves correctly with past times.
        """
        output = self.engine.render_to_string(
            "timeuntil07", {"now": self.now, "earlier": self.now - timedelta(days=7)}
        )
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timeuntil08": "{{ later|timeuntil }}"})
    def test_timeuntil08(self):
        """
        Tests the timeuntil filter functionality in the template engine, specifically when the difference is one week. It verifies that the output is correctly rendered as '1 week'.
        """
        output = self.engine.render_to_string(
            "timeuntil08", {"later": self.now + timedelta(days=7, hours=1)}
        )
        self.assertEqual(output, "1\xa0week")

    @setup({"timeuntil09": "{{ later|timeuntil:now }}"})
    def test_timeuntil09(self):
        output = self.engine.render_to_string(
            "timeuntil09", {"now": self.now, "later": self.now + timedelta(days=7)}
        )
        self.assertEqual(output, "1\xa0week")

    # Differing timezones are calculated correctly.
    @requires_tz_support
    @setup({"timeuntil10": "{{ a|timeuntil }}"})
    def test_timeuntil10(self):
        """
        Tests the timeuntil template filter when the time difference is less than 10 minutes.

        The function verifies that when the time until a given time is less than 10 minutes, 
        the filter renders the time difference as '0 minutes'. It checks the output of the 
        engine render_to_string method with the current time in the timezone and 
        compares it with the expected string '0 minutes'.
        """
        output = self.engine.render_to_string("timeuntil10", {"a": self.now_tz})
        self.assertEqual(output, "0\xa0minutes")

    @requires_tz_support
    @setup({"timeuntil11": "{{ a|timeuntil }}"})
    def test_timeuntil11(self):
        """
        Tests the timeuntil filter to verify it correctly displays the time until a given datetime object.

        This test case utilizes a template with the timeuntil filter, passing in a datetime object, and checks if the rendered output matches the expected result, confirming the filter's functionality in displaying elapsed time as \"0 minutes\" when the input datetime object is the same as the current time.
        """
        output = self.engine.render_to_string("timeuntil11", {"a": self.now_tz_i})
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timeuntil12": "{{ a|timeuntil:b }}"})
    def test_timeuntil12(self):
        output = self.engine.render_to_string(
            "timeuntil12", {"a": self.now_tz_i, "b": self.now_tz}
        )
        self.assertEqual(output, "0\xa0minutes")

    # Regression for #9065 (two date objects).
    @setup({"timeuntil13": "{{ a|timeuntil:b }}"})
    def test_timeuntil13(self):
        output = self.engine.render_to_string(
            "timeuntil13", {"a": self.today, "b": self.today}
        )
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timeuntil14": "{{ a|timeuntil:b }}"})
    def test_timeuntil14(self):
        output = self.engine.render_to_string(
            "timeuntil14", {"a": self.today, "b": self.today - timedelta(hours=24)}
        )
        self.assertEqual(output, "1\xa0day")

    @setup({"timeuntil15": "{{ a|timeuntil:b }}"})
    def test_naive_aware_type_error(self):
        output = self.engine.render_to_string(
            "timeuntil15", {"a": self.now, "b": self.now_tz_i}
        )
        self.assertEqual(output, "")

    @setup({"timeuntil16": "{{ a|timeuntil:b }}"})
    def test_aware_naive_type_error(self):
        """

        Tests that rendering the timeuntil template filter with an aware datetime object and a naive datetime object raises a TypeError.

        The test verifies that the engine correctly handles the case where the input dates have different timezone awareness, and that it produces an empty output when the dates cannot be compared.

        """
        output = self.engine.render_to_string(
            "timeuntil16", {"a": self.now_tz_i, "b": self.now}
        )
        self.assertEqual(output, "")


class FunctionTests(SimpleTestCase):
    def test_until_now(self):
        self.assertEqual(timeuntil_filter(datetime.now() + timedelta(1, 1)), "1\xa0day")

    def test_no_args(self):
        self.assertEqual(timeuntil_filter(None), "")

    def test_explicit_date(self):
        self.assertEqual(
            timeuntil_filter(datetime(2005, 12, 30), datetime(2005, 12, 29)), "1\xa0day"
        )
