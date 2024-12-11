from datetime import datetime, timedelta

from django.template.defaultfilters import timesince_filter
from django.test import SimpleTestCase
from django.test.utils import requires_tz_support

from ..utils import setup
from .timezone_utils import TimezoneTestCase


class TimesinceTests(TimezoneTestCase):
    """
    #20246 - \xa0 in output avoids line-breaks between value and unit
    """

    # Default compare with datetime.now()
    @setup({"timesince01": "{{ a|timesince }}"})
    def test_timesince01(self):
        output = self.engine.render_to_string(
            "timesince01", {"a": datetime.now() + timedelta(minutes=-1, seconds=-10)}
        )
        self.assertEqual(output, "1\xa0minute")

    @setup({"timesince02": "{{ a|timesince }}"})
    def test_timesince02(self):
        output = self.engine.render_to_string(
            "timesince02", {"a": datetime.now() - timedelta(days=1, minutes=1)}
        )
        self.assertEqual(output, "1\xa0day")

    @setup({"timesince03": "{{ a|timesince }}"})
    def test_timesince03(self):
        """
        Tests the timesince filter functionality.

        This test case checks if the timesince filter correctly calculates and formats the time difference between the current time and a given datetime object. The filter should return a human-readable string representing the time difference in hours and minutes.

        Args:
            None

        Returns:
            None

        Asserts that the output of the timesince filter matches the expected string format for a time difference of one hour and twenty-five minutes.
        """
        output = self.engine.render_to_string(
            "timesince03",
            {"a": datetime.now() - timedelta(hours=1, minutes=25, seconds=10)},
        )
        self.assertEqual(output, "1\xa0hour, 25\xa0minutes")

    # Compare to a given parameter
    @setup({"timesince04": "{{ a|timesince:b }}"})
    def test_timesince04(self):
        output = self.engine.render_to_string(
            "timesince04",
            {"a": self.now - timedelta(days=2), "b": self.now - timedelta(days=1)},
        )
        self.assertEqual(output, "1\xa0day")

    @setup({"timesince05": "{{ a|timesince:b }}"})
    def test_timesince05(self):
        """
        .. function:: test_timesince05
           Tests the 'timesince' filter functionality.

           The 'timesince' filter calculates the difference between two dates and returns a human-readable string representing the time that has passed.
           This test case validates that the filter correctly calculates and formats the time difference, outputting a string representing the time elapsed, such as 'X minute' or 'X minutes'.
        """
        output = self.engine.render_to_string(
            "timesince05",
            {
                "a": self.now - timedelta(days=2, minutes=1),
                "b": self.now - timedelta(days=2),
            },
        )
        self.assertEqual(output, "1\xa0minute")

    # Timezone is respected
    @setup({"timesince06": "{{ a|timesince:b }}"})
    def test_timesince06(self):
        output = self.engine.render_to_string(
            "timesince06", {"a": self.now_tz - timedelta(hours=8), "b": self.now_tz}
        )
        self.assertEqual(output, "8\xa0hours")

    # Tests for #7443
    @setup({"timesince07": "{{ earlier|timesince }}"})
    def test_timesince07(self):
        """
        Tests the rendering of a timesince template tag, verifying it correctly calculates and displays the time difference between a given date and the current time, with the expected output being a human-readable duration.
        """
        output = self.engine.render_to_string(
            "timesince07", {"earlier": self.now - timedelta(days=7)}
        )
        self.assertEqual(output, "1\xa0week")

    @setup({"timesince08": "{{ earlier|timesince:now }}"})
    def test_timesince08(self):
        """
        Tests the rendering of a timesince filter with a date in the past, specifically one week ago, to ensure it correctly outputs a human-readable time difference string.
        """
        output = self.engine.render_to_string(
            "timesince08", {"now": self.now, "earlier": self.now - timedelta(days=7)}
        )
        self.assertEqual(output, "1\xa0week")

    @setup({"timesince09": "{{ later|timesince }}"})
    def test_timesince09(self):
        """
        Tests the timesince09 template tag to ensure it correctly calculates the time difference between the current time and a given future time.

        The test case verifies that when the time difference is less than a minute, the output is '0 minutes'. This test helps to ensure the functionality of the timesince template tag when rendering time differences with a level of precision down to minutes.

        :param none:
        :returns: none
        :raises AssertionError: If the rendered output does not match the expected '0 minutes' string.
        """
        output = self.engine.render_to_string(
            "timesince09", {"later": self.now + timedelta(days=7)}
        )
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timesince10": "{{ later|timesince:now }}"})
    def test_timesince10(self):
        """

        Tests the timesince filter in a template, verifying it correctly calculates the time difference between two dates.

        The test renders a template with the timesince filter, passing in two dates: a current date and a future date 7 days later.
        It then asserts that the rendered output is '0 minutes', indicating the filter is working as expected when the input dates are close together.

        """
        output = self.engine.render_to_string(
            "timesince10", {"now": self.now, "later": self.now + timedelta(days=7)}
        )
        self.assertEqual(output, "0\xa0minutes")

    # Differing timezones are calculated correctly.
    @setup({"timesince11": "{{ a|timesince }}"})
    def test_timesince11(self):
        """
        Tests rendering of the timesince filter with the current time as input, verifying that it correctly displays '0 minutes' as the output.
        """
        output = self.engine.render_to_string("timesince11", {"a": self.now})
        self.assertEqual(output, "0\xa0minutes")

    @requires_tz_support
    @setup({"timesince12": "{{ a|timesince }}"})
    def test_timesince12(self):
        """

        Tests the timesince template filter with a timezone-aware datetime object.

        The function verifies that the filter correctly calculates the time difference 
        between the current time and the given datetime object, and that it is rendered 
        as a string in the expected format.

        The test case uses a timezone-aware datetime object to ensure the filter 
        handles timezone information correctly.

        """
        output = self.engine.render_to_string("timesince12", {"a": self.now_tz})
        self.assertEqual(output, "0\xa0minutes")

    @requires_tz_support
    @setup({"timesince13": "{{ a|timesince }}"})
    def test_timesince13(self):
        """
        Test the timesince filter with a Datetime object in the same timezone.

        Verifies that the timesince filter correctly calculates the time difference 
        between the current time and a given Datetime object, returning a humanized 
        string representation of the time elapsed, such as \"X minutes\" or \"X hours\".

        This test ensures the output is as expected when the input Datetime object is 
        in the same timezone as the system time.
        """
        output = self.engine.render_to_string("timesince13", {"a": self.now_tz_i})
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timesince14": "{{ a|timesince:b }}"})
    def test_timesince14(self):
        """
        Tests the \"timesince\" filter functionality to display the time difference between two datetime objects in a human-readable format, specifically when the difference is zero, ensuring the output is correctly formatted as \"0 minutes\".
        """
        output = self.engine.render_to_string(
            "timesince14", {"a": self.now_tz, "b": self.now_tz_i}
        )
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timesince15": "{{ a|timesince:b }}"})
    def test_timesince15(self):
        """
        Tests the timesince filter with two dates in different time zones. 
        It verifies that the filter correctly calculates the time difference 
        between the two dates and returns the expected output when the time difference is zero.
        """
        output = self.engine.render_to_string(
            "timesince15", {"a": self.now, "b": self.now_tz_i}
        )
        self.assertEqual(output, "")

    @setup({"timesince16": "{{ a|timesince:b }}"})
    def test_timesince16(self):
        """
        Tests the timesince filter with a timezone-aware date object and a naive date object as input, verifying that it correctly handles the difference in timezones and returns an empty string as the result.
        """
        output = self.engine.render_to_string(
            "timesince16", {"a": self.now_tz_i, "b": self.now}
        )
        self.assertEqual(output, "")

    # Tests for #9065 (two date objects).
    @setup({"timesince17": "{{ a|timesince:b }}"})
    def test_timesince17(self):
        """
        Test the timesince filter to verify it correctly calculates the time difference between two dates and returns the result in a human-readable format. 

        The test case specifically checks that when the two input dates are the same, the function returns '0 minutes', ensuring it handles this edge case correctly.
        """
        output = self.engine.render_to_string(
            "timesince17", {"a": self.today, "b": self.today}
        )
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timesince18": "{{ a|timesince:b }}"})
    def test_timesince18(self):
        output = self.engine.render_to_string(
            "timesince18", {"a": self.today, "b": self.today + timedelta(hours=24)}
        )
        self.assertEqual(output, "1\xa0day")

    # Tests for #33879 (wrong results for 11 months + several weeks).
    @setup({"timesince19": "{{ earlier|timesince }}"})
    def test_timesince19(self):
        output = self.engine.render_to_string(
            "timesince19", {"earlier": self.today - timedelta(days=358)}
        )
        self.assertEqual(output, "11\xa0months, 3\xa0weeks")

    @setup({"timesince20": "{{ a|timesince:b }}"})
    def test_timesince20(self):
        """
        Return a human-readable representation of a time interval between two dates.

        This function formats the time difference between two dates into a string, using years and months as units, making it easier for users to understand time intervals.

        The output is a string that represents the time difference, such as \"1 year, 11 months\", which is the difference between the provided dates 'a' and 'b'.

        :param a: The base date to calculate the time interval from.
        :param b: The date to calculate the time interval to.
        :return: A human-readable string representing the time interval between 'a' and 'b'.
        """
        now = datetime(2018, 5, 9)
        output = self.engine.render_to_string(
            "timesince20",
            {"a": now, "b": now + timedelta(days=365) + timedelta(days=364)},
        )
        self.assertEqual(output, "1\xa0year, 11\xa0months")


class FunctionTests(SimpleTestCase):
    def test_since_now(self):
        self.assertEqual(timesince_filter(datetime.now() - timedelta(1)), "1\xa0day")

    def test_no_args(self):
        self.assertEqual(timesince_filter(None), "")

    def test_explicit_date(self):
        self.assertEqual(
            timesince_filter(datetime(2005, 12, 29), datetime(2005, 12, 30)), "1\xa0day"
        )
