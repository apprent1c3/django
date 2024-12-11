import datetime
import zoneinfo

from django.test import TestCase
from django.test.utils import override_settings, requires_tz_support
from django.utils import timezone, translation
from django.utils.timesince import timesince, timeuntil
from django.utils.translation import npgettext_lazy


class TimesinceTests(TestCase):
    def setUp(self):
        """
        Set up time-related test data.

        This method initializes a set of time-related attributes, including a base time and various time intervals, 
        ranging from microseconds to years. These attributes are intended to be used in subsequent tests to verify 
        the correctness of time-based functionality.

        Attributes:
            t (datetime): A base time used as a reference point.
            onemicrosecond (timedelta): A time interval of one microsecond.
            onesecond (timedelta): A time interval of one second.
            oneminute (timedelta): A time interval of one minute.
            onehour (timedelta): A time interval of one hour.
            oneday (timedelta): A time interval of one day.
            oneweek (timedelta): A time interval of one week (7 days).
            onemonth (timedelta): A time interval of one month (31 days).
            oneyear (timedelta): A time interval of one year (366 days).

        """
        self.t = datetime.datetime(2007, 8, 14, 13, 46, 0)
        self.onemicrosecond = datetime.timedelta(microseconds=1)
        self.onesecond = datetime.timedelta(seconds=1)
        self.oneminute = datetime.timedelta(minutes=1)
        self.onehour = datetime.timedelta(hours=1)
        self.oneday = datetime.timedelta(days=1)
        self.oneweek = datetime.timedelta(days=7)
        self.onemonth = datetime.timedelta(days=31)
        self.oneyear = datetime.timedelta(days=366)

    def test_equal_datetimes(self):
        """equal datetimes."""
        # NOTE: \xa0 avoids wrapping between value and unit
        self.assertEqual(timesince(self.t, self.t), "0\xa0minutes")

    def test_ignore_microseconds_and_seconds(self):
        """Microseconds and seconds are ignored."""
        self.assertEqual(
            timesince(self.t, self.t + self.onemicrosecond), "0\xa0minutes"
        )
        self.assertEqual(timesince(self.t, self.t + self.onesecond), "0\xa0minutes")

    def test_other_units(self):
        """Test other units."""
        self.assertEqual(timesince(self.t, self.t + self.oneminute), "1\xa0minute")
        self.assertEqual(timesince(self.t, self.t + self.onehour), "1\xa0hour")
        self.assertEqual(timesince(self.t, self.t + self.oneday), "1\xa0day")
        self.assertEqual(timesince(self.t, self.t + self.oneweek), "1\xa0week")
        self.assertEqual(timesince(self.t, self.t + self.onemonth), "1\xa0month")
        self.assertEqual(timesince(self.t, self.t + self.oneyear), "1\xa0year")

    def test_multiple_units(self):
        """Test multiple units."""
        self.assertEqual(
            timesince(self.t, self.t + 2 * self.oneday + 6 * self.onehour),
            "2\xa0days, 6\xa0hours",
        )
        self.assertEqual(
            timesince(self.t, self.t + 2 * self.oneweek + 2 * self.oneday),
            "2\xa0weeks, 2\xa0days",
        )

    def test_display_first_unit(self):
        """
        If the two differing units aren't adjacent, only the first unit is
        displayed.
        """
        self.assertEqual(
            timesince(
                self.t,
                self.t + 2 * self.oneweek + 3 * self.onehour + 4 * self.oneminute,
            ),
            "2\xa0weeks",
        )
        self.assertEqual(
            timesince(self.t, self.t + 4 * self.oneday + 5 * self.oneminute),
            "4\xa0days",
        )

    def test_display_second_before_first(self):
        """
        When the second date occurs before the first, we should always
        get 0 minutes.
        """
        self.assertEqual(
            timesince(self.t, self.t - self.onemicrosecond), "0\xa0minutes"
        )
        self.assertEqual(timesince(self.t, self.t - self.onesecond), "0\xa0minutes")
        self.assertEqual(timesince(self.t, self.t - self.oneminute), "0\xa0minutes")
        self.assertEqual(timesince(self.t, self.t - self.onehour), "0\xa0minutes")
        self.assertEqual(timesince(self.t, self.t - self.oneday), "0\xa0minutes")
        self.assertEqual(timesince(self.t, self.t - self.oneweek), "0\xa0minutes")
        self.assertEqual(timesince(self.t, self.t - self.onemonth), "0\xa0minutes")
        self.assertEqual(timesince(self.t, self.t - self.oneyear), "0\xa0minutes")
        self.assertEqual(
            timesince(self.t, self.t - 2 * self.oneday - 6 * self.onehour),
            "0\xa0minutes",
        )
        self.assertEqual(
            timesince(self.t, self.t - 2 * self.oneweek - 2 * self.oneday),
            "0\xa0minutes",
        )
        self.assertEqual(
            timesince(
                self.t,
                self.t - 2 * self.oneweek - 3 * self.onehour - 4 * self.oneminute,
            ),
            "0\xa0minutes",
        )
        self.assertEqual(
            timesince(self.t, self.t - 4 * self.oneday - 5 * self.oneminute),
            "0\xa0minutes",
        )

    def test_second_before_equal_first_humanize_time_strings(self):
        time_strings = {
            "minute": npgettext_lazy(
                "naturaltime-future",
                "%(num)d minute",
                "%(num)d minutes",
                "num",
            ),
        }
        with translation.override("cs"):
            for now in [self.t, self.t - self.onemicrosecond, self.t - self.oneday]:
                with self.subTest(now):
                    self.assertEqual(
                        timesince(self.t, now, time_strings=time_strings),
                        "0\xa0minut",
                    )

    @requires_tz_support
    def test_different_timezones(self):
        """When using two different timezones."""
        now = datetime.datetime.now()
        now_tz = timezone.make_aware(now, timezone.get_default_timezone())
        now_tz_i = timezone.localtime(now_tz, timezone.get_fixed_timezone(195))

        self.assertEqual(timesince(now), "0\xa0minutes")
        self.assertEqual(timesince(now_tz), "0\xa0minutes")
        self.assertEqual(timesince(now_tz_i), "0\xa0minutes")
        self.assertEqual(timesince(now_tz, now_tz_i), "0\xa0minutes")
        self.assertEqual(timeuntil(now), "0\xa0minutes")
        self.assertEqual(timeuntil(now_tz), "0\xa0minutes")
        self.assertEqual(timeuntil(now_tz_i), "0\xa0minutes")
        self.assertEqual(timeuntil(now_tz, now_tz_i), "0\xa0minutes")

    def test_date_objects(self):
        """Both timesince and timeuntil should work on date objects (#17937)."""
        today = datetime.date.today()
        self.assertEqual(timesince(today + self.oneday), "0\xa0minutes")
        self.assertEqual(timeuntil(today - self.oneday), "0\xa0minutes")

    def test_both_date_objects(self):
        """Timesince should work with both date objects (#9672)"""
        today = datetime.date.today()
        self.assertEqual(timeuntil(today + self.oneday, today), "1\xa0day")
        self.assertEqual(timeuntil(today - self.oneday, today), "0\xa0minutes")
        self.assertEqual(timeuntil(today + self.oneweek, today), "1\xa0week")

    def test_leap_year(self):
        start_date = datetime.date(2016, 12, 25)
        self.assertEqual(timeuntil(start_date + self.oneweek, start_date), "1\xa0week")
        self.assertEqual(timesince(start_date, start_date + self.oneweek), "1\xa0week")

    def test_leap_year_new_years_eve(self):
        """

        Checks the functionality of timesince and timeuntil functions on New Year's Eve of a leap year.

        This test case verifies that the timesince and timeuntil functions correctly calculate the time difference when the given date 
        is one day in the future or past, relative to the current time on December 31st of a leap year. The test ensures that the functions 
        return '0 minutes' when the date is exactly one day ahead or behind the current time.

        """
        t = datetime.date(2016, 12, 31)
        now = datetime.datetime(2016, 12, 31, 18, 0, 0)
        self.assertEqual(timesince(t + self.oneday, now), "0\xa0minutes")
        self.assertEqual(timeuntil(t - self.oneday, now), "0\xa0minutes")

    def test_naive_datetime_with_tzinfo_attribute(self):
        """
        Tests the behavior of the timesince and timeuntil functions when given a datetime object with a tzinfo attribute set to a naive timezone.

        This test case verifies that the functions return the expected output when the input datetime object has a timezone attribute, but the attribute is set to a naive timezone that doesn't provide any offset information.

        The test covers both future and past datetime objects to ensure the functions behave correctly in different scenarios.
        """
        class naive(datetime.tzinfo):
            def utcoffset(self, dt):
                return None

        future = datetime.datetime(2080, 1, 1, tzinfo=naive())
        self.assertEqual(timesince(future), "0\xa0minutes")
        past = datetime.datetime(1980, 1, 1, tzinfo=naive())
        self.assertEqual(timeuntil(past), "0\xa0minutes")

    def test_thousand_years_ago(self):
        t = self.t.replace(year=self.t.year - 1000)
        self.assertEqual(timesince(t, self.t), "1000\xa0years")
        self.assertEqual(timeuntil(self.t, t), "1000\xa0years")

    def test_depth(self):
        """

        Tests the functionality of the :func:`timesince` and :func:`timeuntil` functions,
        which calculate the time difference between two dates.

        The function tests various time intervals, including years, months, weeks, days, and hours,
        with different depths of detail. It verifies that the output matches the expected human-readable
        strings, such as '1 year', '1 year, 1 month', or '1 hour'.

        The tests cover a range of scenarios, including dates in the past and future, to ensure that
        the functions behave correctly in different situations. The function uses a variety of time
        intervals and depths to thoroughly test the functionality of :func:`timesince` and :func:`timeuntil`.

        """
        t = (
            self.t
            + self.oneyear
            + self.onemonth
            + self.oneweek
            + self.oneday
            + self.onehour
        )
        tests = [
            (t, 1, "1\xa0year"),
            (t, 2, "1\xa0year, 1\xa0month"),
            (t, 3, "1\xa0year, 1\xa0month, 1\xa0week"),
            (t, 4, "1\xa0year, 1\xa0month, 1\xa0week, 1\xa0day"),
            (t, 5, "1\xa0year, 1\xa0month, 1\xa0week, 1\xa0day, 1\xa0hour"),
            (t, 6, "1\xa0year, 1\xa0month, 1\xa0week, 1\xa0day, 1\xa0hour"),
            (self.t + self.onehour, 5, "1\xa0hour"),
            (self.t + (4 * self.oneminute), 3, "4\xa0minutes"),
            (self.t + self.onehour + self.oneminute, 1, "1\xa0hour"),
            (self.t + self.oneday + self.onehour, 1, "1\xa0day"),
            (self.t + self.oneweek + self.oneday, 1, "1\xa0week"),
            (self.t + self.onemonth + self.oneweek, 1, "1\xa0month"),
            (self.t + self.oneyear + self.onemonth, 1, "1\xa0year"),
            (self.t + self.oneyear + self.oneweek + self.oneday, 3, "1\xa0year"),
        ]
        for value, depth, expected in tests:
            with self.subTest():
                self.assertEqual(timesince(self.t, value, depth=depth), expected)
                self.assertEqual(timeuntil(value, self.t, depth=depth), expected)

    def test_months_edge(self):
        t = datetime.datetime(2022, 1, 1)
        tests = [
            (datetime.datetime(2022, 1, 31), "4\xa0weeks, 2\xa0days"),
            (datetime.datetime(2022, 2, 1), "1\xa0month"),
            (datetime.datetime(2022, 2, 28), "1\xa0month, 3\xa0weeks"),
            (datetime.datetime(2022, 3, 1), "2\xa0months"),
            (datetime.datetime(2022, 3, 31), "2\xa0months, 4\xa0weeks"),
            (datetime.datetime(2022, 4, 1), "3\xa0months"),
            (datetime.datetime(2022, 4, 30), "3\xa0months, 4\xa0weeks"),
            (datetime.datetime(2022, 5, 1), "4\xa0months"),
            (datetime.datetime(2022, 5, 31), "4\xa0months, 4\xa0weeks"),
            (datetime.datetime(2022, 6, 1), "5\xa0months"),
            (datetime.datetime(2022, 6, 30), "5\xa0months, 4\xa0weeks"),
            (datetime.datetime(2022, 7, 1), "6\xa0months"),
            (datetime.datetime(2022, 7, 31), "6\xa0months, 4\xa0weeks"),
            (datetime.datetime(2022, 8, 1), "7\xa0months"),
            (datetime.datetime(2022, 8, 31), "7\xa0months, 4\xa0weeks"),
            (datetime.datetime(2022, 9, 1), "8\xa0months"),
            (datetime.datetime(2022, 9, 30), "8\xa0months, 4\xa0weeks"),
            (datetime.datetime(2022, 10, 1), "9\xa0months"),
            (datetime.datetime(2022, 10, 31), "9\xa0months, 4\xa0weeks"),
            (datetime.datetime(2022, 11, 1), "10\xa0months"),
            (datetime.datetime(2022, 11, 30), "10\xa0months, 4\xa0weeks"),
            (datetime.datetime(2022, 12, 1), "11\xa0months"),
            (datetime.datetime(2022, 12, 31), "11\xa0months, 4\xa0weeks"),
        ]
        for value, expected in tests:
            with self.subTest():
                self.assertEqual(timesince(t, value), expected)

    def test_depth_invalid(self):
        """
        Tests that the function timesince raises a ValueError when the depth parameter is less than or equal to 0.

        This test case verifies that the function correctly handles invalid input and provides a meaningful error message indicating that the depth must be a positive integer.

        Raises:
            ValueError: If the depth is not greater than 0.

        """
        msg = "depth must be greater than 0."
        with self.assertRaisesMessage(ValueError, msg):
            timesince(self.t, self.t, depth=0)

    @requires_tz_support
    def test_less_than_a_day_with_zoneinfo(self):
        now_with_zoneinfo = timezone.now().astimezone(
            zoneinfo.ZoneInfo(key="Asia/Kathmandu")  # UTC+05:45
        )
        tests = [
            (now_with_zoneinfo, "0\xa0minutes"),
            (now_with_zoneinfo - self.onemicrosecond, "0\xa0minutes"),
            (now_with_zoneinfo - self.onesecond, "0\xa0minutes"),
            (now_with_zoneinfo - self.oneminute, "1\xa0minute"),
            (now_with_zoneinfo - self.onehour, "1\xa0hour"),
        ]
        for value, expected in tests:
            with self.subTest(value):
                self.assertEqual(timesince(value), expected)

    @requires_tz_support
    def test_less_than_a_day_cross_day_with_zoneinfo(self):
        """

        Tests the timesince function for intervals less than a day when crossing day boundaries with zoneinfo.

        This function verifies the correctness of the timesince function when calculating time intervals
        in different time zones, specifically when the interval crosses a day boundary.

        It checks various time intervals, including a few minutes, an hour, a day, and verifies that the
        timesince function returns the expected human-readable string, taking into account the time zone.

        """
        now_with_zoneinfo = timezone.make_aware(
            datetime.datetime(2023, 4, 14, 1, 30, 30),
            zoneinfo.ZoneInfo(key="Asia/Kathmandu"),  # UTC+05:45
        )
        now_utc = now_with_zoneinfo.astimezone(datetime.timezone.utc)
        tests = [
            (now_with_zoneinfo, "0\xa0minutes"),
            (now_with_zoneinfo - self.onemicrosecond, "0\xa0minutes"),
            (now_with_zoneinfo - self.onesecond, "0\xa0minutes"),
            (now_with_zoneinfo - self.oneminute, "1\xa0minute"),
            (now_with_zoneinfo - self.onehour, "1\xa0hour"),
        ]
        for value, expected in tests:
            with self.subTest(value):
                self.assertEqual(timesince(value, now_utc), expected)


@requires_tz_support
@override_settings(USE_TZ=True)
class TZAwareTimesinceTests(TimesinceTests):
    def setUp(self):
        super().setUp()
        self.t = timezone.make_aware(self.t, timezone.get_default_timezone())
