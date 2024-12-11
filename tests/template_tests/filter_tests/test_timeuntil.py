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
        ..: Tests the timeuntil template filter functionality.

            The timeuntil filter calculates the time difference between the current time and 
            a specified future time. This test ensures that the filter correctly formats 
            the time difference as a human-readable string.

            :return: None
            :raises: AssertionError if the timeuntil filter does not produce the expected output.
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

        Tests the timeuntil filter functionality when the time difference is less than an hour.

        The function provides input times that are 1 minute apart and checks if the output is correctly rendered as '1 minute'.

        :param self: The test instance
        :returns: None

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
        Tests the timeuntil filter when the target time has already passed, verifying that it correctly outputs the time elapsed since the target time, which in this case is 0 minutes.
        """
        output = self.engine.render_to_string(
            "timeuntil06", {"earlier": self.now - timedelta(days=7)}
        )
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timeuntil07": "{{ earlier|timeuntil:now }}"})
    def test_timeuntil07(self):
        output = self.engine.render_to_string(
            "timeuntil07", {"now": self.now, "earlier": self.now - timedelta(days=7)}
        )
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timeuntil08": "{{ later|timeuntil }}"})
    def test_timeuntil08(self):
        output = self.engine.render_to_string(
            "timeuntil08", {"later": self.now + timedelta(days=7, hours=1)}
        )
        self.assertEqual(output, "1\xa0week")

    @setup({"timeuntil09": "{{ later|timeuntil:now }}"})
    def test_timeuntil09(self):
        """
        Tests the timeuntil template filter functionality.

        This test case verifies that the timeuntil filter correctly calculates the time difference
        between two given dates and returns a human-readable string representation of the result.

        The test specifically checks the rendering of a template that uses the timeuntil filter
        with a future date that is one week ahead of the current date. The expected output is
        a string indicating the time difference, in this case '1 week'. 
        """
        output = self.engine.render_to_string(
            "timeuntil09", {"now": self.now, "later": self.now + timedelta(days=7)}
        )
        self.assertEqual(output, "1\xa0week")

    # Differing timezones are calculated correctly.
    @requires_tz_support
    @setup({"timeuntil10": "{{ a|timeuntil }}"})
    def test_timeuntil10(self):
        """
        Tests the timeuntil filter when the input time is the current time.

        Verifies that the filter correctly returns '0 minutes' when the input time is
        the current time, demonstrating proper handling of the \"timeuntil\" filter in
        the templating engine. The test case checks for the expected output when the
        input time has no difference from the current time, ensuring the filter works
        as intended in this edge case.
        """
        output = self.engine.render_to_string("timeuntil10", {"a": self.now_tz})
        self.assertEqual(output, "0\xa0minutes")

    @requires_tz_support
    @setup({"timeuntil11": "{{ a|timeuntil }}"})
    def test_timeuntil11(self):
        """
        Tests the functionality of the timeuntil filter to display the time difference until the current moment, given a datetime object. 

        This test case verifies that when the filter is applied to the current time, it renders the expected output, which is '0 minutes' since there is no time difference. 

        It checks the rendering of the time difference in a human-readable format, ensuring that the filter functions correctly when the input time is the current moment.
        """
        output = self.engine.render_to_string("timeuntil11", {"a": self.now_tz_i})
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timeuntil12": "{{ a|timeuntil:b }}"})
    def test_timeuntil12(self):
        """
        ..: 
            Tests if the timeuntil filter returns the correct output when the two input times are the same.

            The timeuntil filter calculates the difference between two times. In this case, it checks 
            that when both times are equal, the filter returns '0 minutes', indicating no time difference.
        """
        output = self.engine.render_to_string(
            "timeuntil12", {"a": self.now_tz_i, "b": self.now_tz}
        )
        self.assertEqual(output, "0\xa0minutes")

    # Regression for #9065 (two date objects).
    @setup({"timeuntil13": "{{ a|timeuntil:b }}"})
    def test_timeuntil13(self):
        """
        Tests the 'timeuntil' filter when the input times are the same, 
        verifying it correctly calculates the time difference as 0 minutes.
        """
        output = self.engine.render_to_string(
            "timeuntil13", {"a": self.today, "b": self.today}
        )
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timeuntil14": "{{ a|timeuntil:b }}"})
    def test_timeuntil14(self):
        """
        Tests the rendering of time difference using the timeuntil filter, verifying it correctly calculates and displays the time elapsed between two dates.
        """
        output = self.engine.render_to_string(
            "timeuntil14", {"a": self.today, "b": self.today - timedelta(hours=24)}
        )
        self.assertEqual(output, "1\xa0day")

    @setup({"timeuntil15": "{{ a|timeuntil:b }}"})
    def test_naive_aware_type_error(self):
        """

        Tests rendering of the timeuntil template filter with a naive datetime object and an aware datetime object, 
        verifying that a TypeError is handled correctly and an empty string is returned as output.

        """
        output = self.engine.render_to_string(
            "timeuntil15", {"a": self.now, "b": self.now_tz_i}
        )
        self.assertEqual(output, "")

    @setup({"timeuntil16": "{{ a|timeuntil:b }}"})
    def test_aware_naive_type_error(self):
        """
        Tests that a TypeError is implicitly handled when using the 'timeuntil' filter with an aware and a naive datetime object. 
        The test verifies that the filter handles the different object types by rendering an empty string in such cases, thus avoiding potential errors.
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
