import datetime

from django.db import models
from django.test import SimpleTestCase, TestCase, override_settings, skipUnlessDBFeature
from django.test.utils import requires_tz_support
from django.utils import timezone

from .models import DateTimeModel


class DateTimeFieldTests(TestCase):
    def test_datetimefield_to_python_microseconds(self):
        """DateTimeField.to_python() supports microseconds."""
        f = models.DateTimeField()
        self.assertEqual(
            f.to_python("2001-01-02 03:04:05.000006"),
            datetime.datetime(2001, 1, 2, 3, 4, 5, 6),
        )
        self.assertEqual(
            f.to_python("2001-01-02 03:04:05.999999"),
            datetime.datetime(2001, 1, 2, 3, 4, 5, 999999),
        )

    def test_timefield_to_python_microseconds(self):
        """TimeField.to_python() supports microseconds."""
        f = models.TimeField()
        self.assertEqual(f.to_python("01:02:03.000004"), datetime.time(1, 2, 3, 4))
        self.assertEqual(f.to_python("01:02:03.999999"), datetime.time(1, 2, 3, 999999))

    def test_datetimes_save_completely(self):
        """

        Tests that datetime, date, and time objects are saved correctly to the database.

        Verifies that a DateTimeModel instance can be created with date, datetime, and time 
        attributes, and that the saved instance has the same attribute values as the 
        original object.

        This test ensures that date, time, and datetime data types are properly persisted 
        and retrieved from the database, maintaining their original values.

        """
        dat = datetime.date(2014, 3, 12)
        datetim = datetime.datetime(2014, 3, 12, 21, 22, 23, 240000)
        tim = datetime.time(21, 22, 23, 240000)
        DateTimeModel.objects.create(d=dat, dt=datetim, t=tim)
        obj = DateTimeModel.objects.first()
        self.assertTrue(obj)
        self.assertEqual(obj.d, dat)
        self.assertEqual(obj.dt, datetim)
        self.assertEqual(obj.t, tim)

    @override_settings(USE_TZ=False)
    def test_lookup_date_without_use_tz(self):
        d = datetime.date(2014, 3, 12)
        dt1 = datetime.datetime(2014, 3, 12, 21, 22, 23, 240000)
        dt2 = datetime.datetime(2014, 3, 11, 21, 22, 23, 240000)
        t = datetime.time(21, 22, 23, 240000)
        m = DateTimeModel.objects.create(d=d, dt=dt1, t=t)
        # Other model with different datetime.
        DateTimeModel.objects.create(d=d, dt=dt2, t=t)
        self.assertEqual(m, DateTimeModel.objects.get(dt__date=d))

    @requires_tz_support
    @skipUnlessDBFeature("has_zoneinfo_database")
    @override_settings(USE_TZ=True, TIME_ZONE="America/Vancouver")
    def test_lookup_date_with_use_tz(self):
        """

        Tests the lookup of a date in a DateTimeField when USE_TZ is True.

        This test ensures that the DateTimeField's date lookup functionality works correctly
        with timezone-aware datetime objects. It creates two DateTimeModel instances with the same date
        but different times and checks that both are returned when filtering by date.
        Additionally, it verifies that the outcome changes when the TIME_ZONE setting is switched to UTC.

        """
        d = datetime.date(2014, 3, 12)
        # The following is equivalent to UTC 2014-03-12 18:34:23.24000.
        dt1 = datetime.datetime(
            2014, 3, 12, 10, 22, 23, 240000, tzinfo=timezone.get_current_timezone()
        )
        # The following is equivalent to UTC 2014-03-13 05:34:23.24000.
        dt2 = datetime.datetime(
            2014, 3, 12, 21, 22, 23, 240000, tzinfo=timezone.get_current_timezone()
        )
        t = datetime.time(21, 22, 23, 240000)
        m1 = DateTimeModel.objects.create(d=d, dt=dt1, t=t)
        m2 = DateTimeModel.objects.create(d=d, dt=dt2, t=t)
        # In Vancouver, we expect both results.
        self.assertCountEqual(
            DateTimeModel.objects.filter(dt__date=d),
            [m1, m2],
        )
        with self.settings(TIME_ZONE="UTC"):
            # But in UTC, the __date only matches one of them.
            self.assertCountEqual(DateTimeModel.objects.filter(dt__date=d), [m1])


class ValidationTest(SimpleTestCase):
    def test_datefield_cleans_date(self):
        """

        Tests the cleaning of a date field to ensure it correctly parses and returns a date object.

        The function verifies that a date string in the standard format (YYYY-MM-DD) is properly cleaned
        and converted into a datetime.date object, regardless of any model instance.

        """
        f = models.DateField()
        self.assertEqual(datetime.date(2008, 10, 10), f.clean("2008-10-10", None))
