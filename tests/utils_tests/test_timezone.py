import datetime
import zoneinfo
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

PARIS_ZI = zoneinfo.ZoneInfo("Europe/Paris")
EAT = timezone.get_fixed_timezone(180)  # Africa/Nairobi
ICT = timezone.get_fixed_timezone(420)  # Asia/Bangkok
UTC = datetime.timezone.utc


class TimezoneTests(SimpleTestCase):
    def test_default_timezone_is_zoneinfo(self):
        self.assertIsInstance(timezone.get_default_timezone(), zoneinfo.ZoneInfo)

    def test_now(self):
        with override_settings(USE_TZ=True):
            self.assertTrue(timezone.is_aware(timezone.now()))
        with override_settings(USE_TZ=False):
            self.assertTrue(timezone.is_naive(timezone.now()))

    def test_localdate(self):
        """
        Return the local date for the given timezone.

        This function takes an optional timezone argument. If no timezone is provided, it
        defaults to the timezone defined by the `timezone.override` context or the system's
        local timezone.

        If a naive datetime (i.e., one without a timezone) is passed, a `ValueError` is
        raised as it cannot be converted to a local date.

        The function returns a `datetime.date` object representing the local date for the
        given datetime and timezone.

        If no datetime is provided, the function returns the local date for the current
        time in the given timezone. The current time can be overridden using the
        `django.utils.timezone.now` function or by using the `timezone.override` context
        manager.

        Examples of usage include getting the local date for a specific datetime and
        timezone, or getting the local date for the current time in a specific timezone.
        The result of this function can be used for date-based calculations and comparisons
        in a timezone-aware manner.
        """
        naive = datetime.datetime(2015, 1, 1, 0, 0, 1)
        with self.assertRaisesMessage(
            ValueError, "localtime() cannot be applied to a naive datetime"
        ):
            timezone.localdate(naive)
        with self.assertRaisesMessage(
            ValueError, "localtime() cannot be applied to a naive datetime"
        ):
            timezone.localdate(naive, timezone=EAT)

        aware = datetime.datetime(2015, 1, 1, 0, 0, 1, tzinfo=ICT)
        self.assertEqual(
            timezone.localdate(aware, timezone=EAT), datetime.date(2014, 12, 31)
        )
        with timezone.override(EAT):
            self.assertEqual(timezone.localdate(aware), datetime.date(2014, 12, 31))

        with mock.patch("django.utils.timezone.now", return_value=aware):
            self.assertEqual(
                timezone.localdate(timezone=EAT), datetime.date(2014, 12, 31)
            )
            with timezone.override(EAT):
                self.assertEqual(timezone.localdate(), datetime.date(2014, 12, 31))

    def test_override(self):
        """

        Tests the override functionality of the timezone module.

        This function verifies that the timezone override works correctly in various scenarios,
        including when the timezone is activated, deactivated, or overridden to None.

        It checks that the current timezone is correctly set to the overridden timezone,
        and that it reverts back to the default or previously active timezone when the override
        is removed or when the timezone is deactivated.

        The test cases cover the following scenarios:
        - Override with a specific timezone (EAT) while a timezone is active (ICT)
        - Override with None while a timezone is active (ICT)
        - Override with a specific timezone (EAT) while no timezone is active
        - Override with None while no timezone is active

        """
        default = timezone.get_default_timezone()
        try:
            timezone.activate(ICT)

            with timezone.override(EAT):
                self.assertIs(EAT, timezone.get_current_timezone())
            self.assertIs(ICT, timezone.get_current_timezone())

            with timezone.override(None):
                self.assertIs(default, timezone.get_current_timezone())
            self.assertIs(ICT, timezone.get_current_timezone())

            timezone.deactivate()

            with timezone.override(EAT):
                self.assertIs(EAT, timezone.get_current_timezone())
            self.assertIs(default, timezone.get_current_timezone())

            with timezone.override(None):
                self.assertIs(default, timezone.get_current_timezone())
            self.assertIs(default, timezone.get_current_timezone())
        finally:
            timezone.deactivate()

    def test_override_decorator(self):
        default = timezone.get_default_timezone()

        @timezone.override(EAT)
        def func_tz_eat():
            self.assertIs(EAT, timezone.get_current_timezone())

        @timezone.override(None)
        def func_tz_none():
            self.assertIs(default, timezone.get_current_timezone())

        try:
            timezone.activate(ICT)

            func_tz_eat()
            self.assertIs(ICT, timezone.get_current_timezone())

            func_tz_none()
            self.assertIs(ICT, timezone.get_current_timezone())

            timezone.deactivate()

            func_tz_eat()
            self.assertIs(default, timezone.get_current_timezone())

            func_tz_none()
            self.assertIs(default, timezone.get_current_timezone())
        finally:
            timezone.deactivate()

    def test_override_string_tz(self):
        with timezone.override("Asia/Bangkok"):
            self.assertEqual(timezone.get_current_timezone_name(), "Asia/Bangkok")

    def test_override_fixed_offset(self):
        """

        Tests the override of the fixed timezone offset.

        This test case verifies that the timezone offset can be successfully overridden
        with a fixed offset, and that the current timezone name is correctly retrieved
        after the override.

        It ensures that the timezone override functionality works as expected, allowing
        for tests to be run in a controlled timezone environment.

        """
        with timezone.override(datetime.timezone(datetime.timedelta(), "tzname")):
            self.assertEqual(timezone.get_current_timezone_name(), "tzname")

    def test_activate_invalid_timezone(self):
        with self.assertRaisesMessage(ValueError, "Invalid timezone: None"):
            timezone.activate(None)

    def test_is_aware(self):
        """
        Test whether datetime objects have timezone awareness, checking both aware and naive datetime instances. 

        The function verifies that the :func:`timezone.is_aware` function correctly identifies timezone-aware dates, such as one with the Eastern Africa Time (EAT) timezone, and timezone-naive dates, which do not have any timezone information associated with them.
        """
        self.assertTrue(
            timezone.is_aware(datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT))
        )
        self.assertFalse(timezone.is_aware(datetime.datetime(2011, 9, 1, 13, 20, 30)))

    def test_is_naive(self):
        self.assertFalse(
            timezone.is_naive(datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT))
        )
        self.assertTrue(timezone.is_naive(datetime.datetime(2011, 9, 1, 13, 20, 30)))

    def test_make_aware(self):
        self.assertEqual(
            timezone.make_aware(datetime.datetime(2011, 9, 1, 13, 20, 30), EAT),
            datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT),
        )
        with self.assertRaises(ValueError):
            timezone.make_aware(
                datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT), EAT
            )

    def test_make_naive(self):
        self.assertEqual(
            timezone.make_naive(
                datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT), EAT
            ),
            datetime.datetime(2011, 9, 1, 13, 20, 30),
        )
        self.assertEqual(
            timezone.make_naive(
                datetime.datetime(2011, 9, 1, 17, 20, 30, tzinfo=ICT), EAT
            ),
            datetime.datetime(2011, 9, 1, 13, 20, 30),
        )

        with self.assertRaisesMessage(
            ValueError, "make_naive() cannot be applied to a naive datetime"
        ):
            timezone.make_naive(datetime.datetime(2011, 9, 1, 13, 20, 30), EAT)

    def test_make_naive_no_tz(self):
        self.assertEqual(
            timezone.make_naive(datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)),
            datetime.datetime(2011, 9, 1, 5, 20, 30),
        )

    def test_make_aware_no_tz(self):
        self.assertEqual(
            timezone.make_aware(datetime.datetime(2011, 9, 1, 13, 20, 30)),
            datetime.datetime(
                2011, 9, 1, 13, 20, 30, tzinfo=timezone.get_fixed_timezone(-300)
            ),
        )

    def test_make_aware2(self):
        """

        Tests the timezone.make_aware function to ensure it correctly assigns a timezone to a naive datetime object.

        The function checks that a naive datetime object is correctly localized to the specified timezone.
        It also verifies that attempting to make a datetime object aware when it already has a timezone raises a ValueError.

        """
        CEST = datetime.timezone(datetime.timedelta(hours=2), "CEST")
        self.assertEqual(
            timezone.make_aware(datetime.datetime(2011, 9, 1, 12, 20, 30), PARIS_ZI),
            datetime.datetime(2011, 9, 1, 12, 20, 30, tzinfo=CEST),
        )
        with self.assertRaises(ValueError):
            timezone.make_aware(
                datetime.datetime(2011, 9, 1, 12, 20, 30, tzinfo=PARIS_ZI), PARIS_ZI
            )

    def test_make_naive_zoneinfo(self):
        """

        Tests the make_naive function in the timezone module, ensuring it correctly removes timezone information from datetime objects while preserving the original date and time values.

        The function is expected to take a datetime object with timezone information and return a naive datetime object (i.e., without timezone information), while maintaining the original timestamp.

        This test covers two scenarios:

        * Removing timezone information from a standard datetime object
        * Preserving the 'fold' attribute when removing timezone information from a datetime object with duplicate timestamps

        """
        self.assertEqual(
            timezone.make_naive(
                datetime.datetime(2011, 9, 1, 12, 20, 30, tzinfo=PARIS_ZI), PARIS_ZI
            ),
            datetime.datetime(2011, 9, 1, 12, 20, 30),
        )

        self.assertEqual(
            timezone.make_naive(
                datetime.datetime(2011, 9, 1, 12, 20, 30, fold=1, tzinfo=PARIS_ZI),
                PARIS_ZI,
            ),
            datetime.datetime(2011, 9, 1, 12, 20, 30, fold=1),
        )

    def test_make_aware_zoneinfo_ambiguous(self):
        # 2:30 happens twice, once before DST ends and once after
        ambiguous = datetime.datetime(2015, 10, 25, 2, 30)

        std = timezone.make_aware(ambiguous.replace(fold=1), timezone=PARIS_ZI)
        dst = timezone.make_aware(ambiguous, timezone=PARIS_ZI)

        self.assertEqual(
            std.astimezone(UTC) - dst.astimezone(UTC), datetime.timedelta(hours=1)
        )
        self.assertEqual(std.utcoffset(), datetime.timedelta(hours=1))
        self.assertEqual(dst.utcoffset(), datetime.timedelta(hours=2))

    def test_make_aware_zoneinfo_non_existent(self):
        # 2:30 never happened due to DST
        """
        Tests the handling of a non-existent time zone date when creating an aware datetime.

        This test case simulates the exact moment when a time zone transitions to daylight saving time, 
        resulting in a \"gap\" in local time where one hour is skipped. It verifies that the 
        timezone.make_aware function correctly interprets the given time in the context of the Paris time zone.

        Specifically, it checks that the time difference between the standard and daylight saving time 
        is one hour, and that the UTC offsets for both cases are correctly determined as one and two hours, respectively.
        """
        non_existent = datetime.datetime(2015, 3, 29, 2, 30)

        std = timezone.make_aware(non_existent, PARIS_ZI)
        dst = timezone.make_aware(non_existent.replace(fold=1), PARIS_ZI)

        self.assertEqual(
            std.astimezone(UTC) - dst.astimezone(UTC), datetime.timedelta(hours=1)
        )
        self.assertEqual(std.utcoffset(), datetime.timedelta(hours=1))
        self.assertEqual(dst.utcoffset(), datetime.timedelta(hours=2))

    def test_get_timezone_name(self):
        """
        The _get_timezone_name() helper must return the offset for fixed offset
        timezones, for usage with Trunc DB functions.

        The datetime.timezone examples show the current behavior.
        """
        tests = [
            # datetime.timezone, fixed offset with and without `name`.
            (datetime.timezone(datetime.timedelta(hours=10)), "UTC+10:00"),
            (
                datetime.timezone(datetime.timedelta(hours=10), name="Etc/GMT-10"),
                "Etc/GMT-10",
            ),
            # zoneinfo, named and fixed offset.
            (zoneinfo.ZoneInfo("Europe/Madrid"), "Europe/Madrid"),
            (zoneinfo.ZoneInfo("Etc/GMT-10"), "+10"),
        ]
        for tz, expected in tests:
            with self.subTest(tz=tz, expected=expected):
                self.assertEqual(timezone._get_timezone_name(tz), expected)

    def test_get_default_timezone(self):
        self.assertEqual(timezone.get_default_timezone_name(), "America/Chicago")

    def test_fixedoffset_timedelta(self):
        """
        Tests the functionality of get_fixed_timezone with a fixed time delta.

        This test case verifies that the get_fixed_timezone function correctly calculates the UTC offset for a given time delta. It ensures that the returned timezone object's utcoffset method returns the expected time delta, which in this case is a fixed offset of one hour.

        The test checks the behavior of the function with a positive time delta and asserts that the result matches the input delta, confirming that the function works as expected for fixed offsets.

        Parameters:
            None

        Returns:
            None

        Raises:
            AssertionError: If the calculated UTC offset does not match the expected time delta.
        """
        delta = datetime.timedelta(hours=1)
        self.assertEqual(timezone.get_fixed_timezone(delta).utcoffset(None), delta)

    def test_fixedoffset_negative_timedelta(self):
        delta = datetime.timedelta(hours=-2)
        self.assertEqual(timezone.get_fixed_timezone(delta).utcoffset(None), delta)
