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
        """
        Tests the timesince filter functionality in a templating engine, verifying that it correctly calculates and displays the time difference between the current time and a given datetime object in a human-readable format.
        """
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
        output = self.engine.render_to_string(
            "timesince03",
            {"a": datetime.now() - timedelta(hours=1, minutes=25, seconds=10)},
        )
        self.assertEqual(output, "1\xa0hour, 25\xa0minutes")

    # Compare to a given parameter
    @setup({"timesince04": "{{ a|timesince:b }}"})
    def test_timesince04(self):
        """

        Render a time difference using the timesince filter.

        The timesince filter calculates the time difference between two dates and returns a human-readable string.
        It takes two arguments, the time to calculate from and the time to calculate to.

        The output will be a string describing the time difference, such as \"1 day\" or \"1 hour\".
        This filter is useful for displaying time differences in a user-friendly format.

        For example, if the current time is 2 days ago, and the reference time is 1 day ago, 
        the filter will output \"1 day\" to indicate the time difference between the two dates.

        """
        output = self.engine.render_to_string(
            "timesince04",
            {"a": self.now - timedelta(days=2), "b": self.now - timedelta(days=1)},
        )
        self.assertEqual(output, "1\xa0day")

    @setup({"timesince05": "{{ a|timesince:b }}"})
    def test_timesince05(self):
        """
        Tests the timesince filter to check if it correctly calculates the time difference in minutes.

        The function renders a template string with the timesince filter, passing two datetime objects as input.
        It then asserts that the output is equal to the expected time difference string, in this case '1 minute'.

        This test case covers the scenario where the time difference is less than an hour, and the output should display the difference in minutes.

        Args:
            a (datetime): The first datetime object.
            b (datetime): The second datetime object.

        Returns:
            str: The rendered template string with the time difference.

        Example:
            The timesince filter can be used in a template as {{ a|timesince:b }} to display the time difference between two datetime objects a and b.
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
        """

        Tests the timesince filter functionality, which calculates the time difference between two dates.

        The filter takes two arguments: the earlier date and the later date, and returns a human-readable string
        representing the time elapsed between them, such as '8 hours'. This test case checks if the filter correctly
        handles time differences in hours.

        """
        output = self.engine.render_to_string(
            "timesince06", {"a": self.now_tz - timedelta(hours=8), "b": self.now_tz}
        )
        self.assertEqual(output, "8\xa0hours")

    # Tests for #7443
    @setup({"timesince07": "{{ earlier|timesince }}"})
    def test_timesince07(self):
        output = self.engine.render_to_string(
            "timesince07", {"earlier": self.now - timedelta(days=7)}
        )
        self.assertEqual(output, "1\xa0week")

    @setup({"timesince08": "{{ earlier|timesince:now }}"})
    def test_timesince08(self):
        """
        Tests the rendering of time differences in a human-readable format, specifically the \"timesince\" filter, with a past date that is one week ago, ensuring it correctly displays as \"1 week\".
        """
        output = self.engine.render_to_string(
            "timesince08", {"now": self.now, "earlier": self.now - timedelta(days=7)}
        )
        self.assertEqual(output, "1\xa0week")

    @setup({"timesince09": "{{ later|timesince }}"})
    def test_timesince09(self):
        output = self.engine.render_to_string(
            "timesince09", {"later": self.now + timedelta(days=7)}
        )
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timesince10": "{{ later|timesince:now }}"})
    def test_timesince10(self):
        """
        Tests the 'timesince' filter by rendering a template string with a future date.

         The 'timesince' filter calculates the time difference between two dates. This test case 
         specifically checks the output when the time difference is less than one hour, 
         verifying that the result is displayed in minutes. 

         :return: None. The test passes if the rendered output matches the expected string '0 minutes', 
                  indicating that the 'timesince' filter functions correctly for time differences 
                  less than one hour.

        """
        output = self.engine.render_to_string(
            "timesince10", {"now": self.now, "later": self.now + timedelta(days=7)}
        )
        self.assertEqual(output, "0\xa0minutes")

    # Differing timezones are calculated correctly.
    @setup({"timesince11": "{{ a|timesince }}"})
    def test_timesince11(self):
        """
        Tests the timesince filter in the templating engine, verifying that it correctly displays the time difference between the current time and a given timestamp, in this case, the current time itself, resulting in an output of '0 minutes'.
        """
        output = self.engine.render_to_string("timesince11", {"a": self.now})
        self.assertEqual(output, "0\xa0minutes")

    @requires_tz_support
    @setup({"timesince12": "{{ a|timesince }}"})
    def test_timesince12(self):
        output = self.engine.render_to_string("timesince12", {"a": self.now_tz})
        self.assertEqual(output, "0\xa0minutes")

    @requires_tz_support
    @setup({"timesince13": "{{ a|timesince }}"})
    def test_timesince13(self):
        output = self.engine.render_to_string("timesince13", {"a": self.now_tz_i})
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timesince14": "{{ a|timesince:b }}"})
    def test_timesince14(self):
        output = self.engine.render_to_string(
            "timesince14", {"a": self.now_tz, "b": self.now_tz_i}
        )
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timesince15": "{{ a|timesince:b }}"})
    def test_timesince15(self):
        output = self.engine.render_to_string(
            "timesince15", {"a": self.now, "b": self.now_tz_i}
        )
        self.assertEqual(output, "")

    @setup({"timesince16": "{{ a|timesince:b }}"})
    def test_timesince16(self):
        """
        Tests the behavior of the timesince filter when the provided date is in the future, relative to the reference date. 

        This test case ensures that when the input date 'a' is later than the reference date 'b', the timesince filter correctly returns an empty string.
        """
        output = self.engine.render_to_string(
            "timesince16", {"a": self.now_tz_i, "b": self.now}
        )
        self.assertEqual(output, "")

    # Tests for #9065 (two date objects).
    @setup({"timesince17": "{{ a|timesince:b }}"})
    def test_timesince17(self):
        output = self.engine.render_to_string(
            "timesince17", {"a": self.today, "b": self.today}
        )
        self.assertEqual(output, "0\xa0minutes")

    @setup({"timesince18": "{{ a|timesince:b }}"})
    def test_timesince18(self):
        """
        Tests the 'timesince' filter with a timestamp that is one day in the future.

        This test case verifies that the 'timesince' filter correctly calculates the time difference
        between two dates and returns the result in a human-readable format.

        It checks that when the time difference is 24 hours, the output is displayed as '1 day'. 
        """
        output = self.engine.render_to_string(
            "timesince18", {"a": self.today, "b": self.today + timedelta(hours=24)}
        )
        self.assertEqual(output, "1\xa0day")

    # Tests for #33879 (wrong results for 11 months + several weeks).
    @setup({"timesince19": "{{ earlier|timesince }}"})
    def test_timesince19(self):
        """

        Tests the timesince filter by rendering a template with a date that is approximately 11 months and 3 weeks prior to the current date.
        The test verifies that the output matches the expected human-readable time difference string.

        :returns: None

        """
        output = self.engine.render_to_string(
            "timesince19", {"earlier": self.today - timedelta(days=358)}
        )
        self.assertEqual(output, "11\xa0months, 3\xa0weeks")

    @setup({"timesince20": "{{ a|timesince:b }}"})
    def test_timesince20(self):
        """

        Tests the timesince filter, which calculates the time difference between two dates.

        The test case verifies that the filter correctly returns a human-readable string
        representing the time elapsed between two dates, taking into account years and months.

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
