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

        Tests the timesince template filter.

        This function checks if the timesince filter correctly calculates the time difference
        between the current time and a given datetime object, and formats it as a human-readable string.

        The test case verifies that a time difference of one minute and ten seconds is rendered as '1 minute'.

        :returns: None

        """
        output = self.engine.render_to_string(
            "timesince01", {"a": datetime.now() + timedelta(minutes=-1, seconds=-10)}
        )
        self.assertEqual(output, "1\xa0minute")

    @setup({"timesince02": "{{ a|timesince }}"})
    def test_timesince02(self):
        """
        Tests the timesince filter functionality.

        The timesince filter calculates the time difference between the current time
        and a given datetime object, and outputs a human-readable string representing
        this difference. This test case renders a template with the timesince filter
        applied to a datetime object that is one day and one minute in the past, and
        verifies that the output matches the expected result.

        :param None:
        :raises AssertionError: if the output does not match the expected result.
        :return: None
        """
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

        Render a time difference in a human-readable format using the timesince filter.

        The timesince filter calculates the difference between two datetime objects and 
        returns a string representing the time interval in a human-readable format, 
        such as \"1 day\" or \"2 hours\".

        :param a: The earlier datetime object.
        :param b: The later datetime object.
        :return: A string representing the time interval between a and b.

        """
        output = self.engine.render_to_string(
            "timesince04",
            {"a": self.now - timedelta(days=2), "b": self.now - timedelta(days=1)},
        )
        self.assertEqual(output, "1\xa0day")

    @setup({"timesince05": "{{ a|timesince:b }}"})
    def test_timesince05(self):
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

        Tests the timesince filter by checking if it correctly calculates the time difference between two datetime objects.

        The function renders a template string that uses the timesince filter to calculate the time elapsed between two dates.
        It then asserts that the output is as expected, which in this case is '8 hours'.

        This test case covers the scenario where the time difference is in hours, ensuring the filter handles this unit correctly.

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

        Tests the functionality of the timesince filter when the input time is in the future, 
        approximately 10 minutes or less from the current time.

        The test case verifies that the filter correctly calculates the time difference 
        between two dates and returns a human-readable string, even when the future time 
        is near the current time.

        The expected output is a string indicating the time difference in minutes, 
        taking into account the correct handling of edges cases such as negligible time 
        differences, resulting in an output of '0 minutes'.

        """
        output = self.engine.render_to_string(
            "timesince10", {"now": self.now, "later": self.now + timedelta(days=7)}
        )
        self.assertEqual(output, "0\xa0minutes")

    # Differing timezones are calculated correctly.
    @setup({"timesince11": "{{ a|timesince }}"})
    def test_timesince11(self):
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
        """
        Tests the timesince filter with a timezone aware and naive datetime.

        This test case verifies that the timesince filter correctly handles the difference
        between a timezone aware datetime object and a naive datetime object, 
        resulting in an empty string when both dates are the same.

        :param: None
        :returns: None

        """
        output = self.engine.render_to_string(
            "timesince15", {"a": self.now, "b": self.now_tz_i}
        )
        self.assertEqual(output, "")

    @setup({"timesince16": "{{ a|timesince:b }}"})
    def test_timesince16(self):
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
