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
        Tests that datetime instances are saved and retrieved completely in the database.

        Verifies that date, datetime, and time instances are accurately stored and
        retrieved from the DateTimeModel, ensuring that no information is lost during the
        saving process. The test covers the creation of a DateTimeModel instance with
        various datetime components, its successful retrieval, and the verification that
        the retrieved values match the original ones.
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

        Tests the cleaning functionality of the DateField.

        This test ensures that a string representing a date in the format 'YYYY-MM-DD'
        is correctly converted into a datetime.date object by the DateField's clean method.

        The expected output is a datetime.date object with the specified year, month, and day.

        Verification is done by comparing the cleaned date with a manually created
        datetime.date object representing the same date.

        """
        f = models.DateField()
        self.assertEqual(datetime.date(2008, 10, 10), f.clean("2008-10-10", None))
