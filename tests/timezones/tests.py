import datetime
import re
import sys
import zoneinfo
from contextlib import contextmanager
from unittest import SkipTest, skipIf
from xml.dom.minidom import parseString

from django.contrib.auth.models import User
from django.core import serializers
from django.db import connection
from django.db.models import F, Max, Min
from django.db.models.functions import Now
from django.http import HttpRequest
from django.template import (
    Context,
    RequestContext,
    Template,
    TemplateSyntaxError,
    context_processors,
)
from django.test import (
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    override_settings,
    skipIfDBFeature,
    skipUnlessDBFeature,
)
from django.test.utils import requires_tz_support
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.timezone import timedelta

from .forms import (
    EventForm,
    EventLocalizedForm,
    EventLocalizedModelForm,
    EventModelForm,
    EventSplitForm,
)
from .models import (
    AllDayEvent,
    DailyEvent,
    Event,
    MaybeEvent,
    Session,
    SessionEvent,
    Timestamp,
)

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# These tests use the EAT (Eastern Africa Time) and ICT (Indochina Time)
# who don't have daylight saving time, so we can represent them easily
# with fixed offset timezones and use them directly as tzinfo in the
# constructors.

# settings.TIME_ZONE is forced to EAT. Most tests use a variant of
# datetime.datetime(2011, 9, 1, 13, 20, 30), which translates to
# 10:20:30 in UTC and 17:20:30 in ICT.

UTC = datetime.timezone.utc
EAT = timezone.get_fixed_timezone(180)  # Africa/Nairobi
ICT = timezone.get_fixed_timezone(420)  # Asia/Bangkok


@contextmanager
def override_database_connection_timezone(timezone):
    """

    Temporarily overrides the database connection timezone.

    This context manager changes the timezone of the database connection to the specified timezone for the duration of the context block, 
    restoring the original timezone when the block is exited.

    :param timezone: The timezone to use for the database connection.

    """
    try:
        orig_timezone = connection.settings_dict["TIME_ZONE"]
        connection.settings_dict["TIME_ZONE"] = timezone
        # Clear cached properties, after first accessing them to ensure they exist.
        connection.timezone
        del connection.timezone
        connection.timezone_name
        del connection.timezone_name
        yield
    finally:
        connection.settings_dict["TIME_ZONE"] = orig_timezone
        # Clear cached properties, after first accessing them to ensure they exist.
        connection.timezone
        del connection.timezone
        connection.timezone_name
        del connection.timezone_name


@override_settings(TIME_ZONE="Africa/Nairobi", USE_TZ=False)
class LegacyDatabaseTests(TestCase):
    def test_naive_datetime(self):
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    def test_naive_datetime_with_microsecond(self):
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, 405060)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    @skipUnlessDBFeature("supports_timezones")
    def test_aware_datetime_in_local_timezone(self):
        """
        Tests the behavior of saving an aware datetime in the local timezone, verifying that the timezone information is lost upon retrieval but the original datetime value is preserved.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertIsNone(event.dt.tzinfo)
        # interpret the naive datetime in local time to get the correct value
        self.assertEqual(event.dt.replace(tzinfo=EAT), dt)

    @skipUnlessDBFeature("supports_timezones")
    def test_aware_datetime_in_local_timezone_with_microsecond(self):
        """
        Tests the behavior of storing and retrieving an aware datetime object 
        in the local timezone with microseconds, verifying its timezone info 
        is correctly lost and can be restored.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, 405060, tzinfo=EAT)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertIsNone(event.dt.tzinfo)
        # interpret the naive datetime in local time to get the correct value
        self.assertEqual(event.dt.replace(tzinfo=EAT), dt)

    @skipUnlessDBFeature("supports_timezones")
    def test_aware_datetime_in_utc(self):
        """
        Tests that an aware datetime in UTC is correctly stored and retrieved without timezone info, and can be restored to its original timezone-aware state.
        """
        dt = datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertIsNone(event.dt.tzinfo)
        # interpret the naive datetime in local time to get the correct value
        self.assertEqual(event.dt.replace(tzinfo=EAT), dt)

    @skipUnlessDBFeature("supports_timezones")
    def test_aware_datetime_in_other_timezone(self):
        """
        Tests the handling of timezone-aware datetime objects.

        Verifies that datetime objects with timezone information are properly
        stored and retrieved, and that the timezone information is lost in the process.

        """
        dt = datetime.datetime(2011, 9, 1, 17, 20, 30, tzinfo=ICT)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertIsNone(event.dt.tzinfo)
        # interpret the naive datetime in local time to get the correct value
        self.assertEqual(event.dt.replace(tzinfo=EAT), dt)

    @skipIfDBFeature("supports_timezones")
    def test_aware_datetime_unsupported(self):
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)
        msg = "backend does not support timezone-aware datetimes when USE_TZ is False."
        with self.assertRaisesMessage(ValueError, msg):
            Event.objects.create(dt=dt)

    def test_auto_now_and_auto_now_add(self):
        """
        Tests that the auto_now and auto_now_add fields in the Timestamp model are correctly populated with the current date and time upon object creation.
        """
        now = datetime.datetime.now()
        past = now - datetime.timedelta(seconds=2)
        future = now + datetime.timedelta(seconds=2)
        Timestamp.objects.create()
        ts = Timestamp.objects.get()
        self.assertLess(past, ts.created)
        self.assertLess(past, ts.updated)
        self.assertGreater(future, ts.updated)
        self.assertGreater(future, ts.updated)

    def test_query_filter(self):
        """
        Tests the filter functionality of the Event model, specifically the usage of greater than or equal to (`__gte`) and greater than (`__gt`) query filters on the 'dt' field.
        """
        dt1 = datetime.datetime(2011, 9, 1, 12, 20, 30)
        dt2 = datetime.datetime(2011, 9, 1, 14, 20, 30)
        Event.objects.create(dt=dt1)
        Event.objects.create(dt=dt2)
        self.assertEqual(Event.objects.filter(dt__gte=dt1).count(), 2)
        self.assertEqual(Event.objects.filter(dt__gt=dt1).count(), 1)
        self.assertEqual(Event.objects.filter(dt__gte=dt2).count(), 1)
        self.assertEqual(Event.objects.filter(dt__gt=dt2).count(), 0)

    def test_query_datetime_lookups(self):
        """
        Tests datetime lookup functionality in Event model queries.

        Verifies that various datetime field lookups (year, month, day, week day, iso week day, hour, minute, second) 
        correctly filter Event objects based on their 'dt' datetime field.
        """
        Event.objects.create(dt=datetime.datetime(2011, 1, 1, 1, 30, 0))
        Event.objects.create(dt=datetime.datetime(2011, 1, 1, 4, 30, 0))
        self.assertEqual(Event.objects.filter(dt__year=2011).count(), 2)
        self.assertEqual(Event.objects.filter(dt__month=1).count(), 2)
        self.assertEqual(Event.objects.filter(dt__day=1).count(), 2)
        self.assertEqual(Event.objects.filter(dt__week_day=7).count(), 2)
        self.assertEqual(Event.objects.filter(dt__iso_week_day=6).count(), 2)
        self.assertEqual(Event.objects.filter(dt__hour=1).count(), 1)
        self.assertEqual(Event.objects.filter(dt__minute=30).count(), 2)
        self.assertEqual(Event.objects.filter(dt__second=0).count(), 2)

    def test_query_aggregation(self):
        # Only min and max make sense for datetimes.
        """
        Tests aggregation of datetime fields by creating sample Event objects and verifying the minimum and maximum datetime values returned by the aggregate method.
        """
        Event.objects.create(dt=datetime.datetime(2011, 9, 1, 23, 20, 20))
        Event.objects.create(dt=datetime.datetime(2011, 9, 1, 13, 20, 30))
        Event.objects.create(dt=datetime.datetime(2011, 9, 1, 3, 20, 40))
        result = Event.objects.aggregate(Min("dt"), Max("dt"))
        self.assertEqual(
            result,
            {
                "dt__min": datetime.datetime(2011, 9, 1, 3, 20, 40),
                "dt__max": datetime.datetime(2011, 9, 1, 23, 20, 20),
            },
        )

    def test_query_annotation(self):
        # Only min and max make sense for datetimes.
        """
        Tests the query annotation functionality by creating sessions and events, 
        then checks if the minimum date for each session is correctly annotated 
        and filtered in various queries.
        """
        morning = Session.objects.create(name="morning")
        afternoon = Session.objects.create(name="afternoon")
        SessionEvent.objects.create(
            dt=datetime.datetime(2011, 9, 1, 23, 20, 20), session=afternoon
        )
        SessionEvent.objects.create(
            dt=datetime.datetime(2011, 9, 1, 13, 20, 30), session=afternoon
        )
        SessionEvent.objects.create(
            dt=datetime.datetime(2011, 9, 1, 3, 20, 40), session=morning
        )
        morning_min_dt = datetime.datetime(2011, 9, 1, 3, 20, 40)
        afternoon_min_dt = datetime.datetime(2011, 9, 1, 13, 20, 30)
        self.assertQuerySetEqual(
            Session.objects.annotate(dt=Min("events__dt")).order_by("dt"),
            [morning_min_dt, afternoon_min_dt],
            transform=lambda d: d.dt,
        )
        self.assertQuerySetEqual(
            Session.objects.annotate(dt=Min("events__dt")).filter(
                dt__lt=afternoon_min_dt
            ),
            [morning_min_dt],
            transform=lambda d: d.dt,
        )
        self.assertQuerySetEqual(
            Session.objects.annotate(dt=Min("events__dt")).filter(
                dt__gte=afternoon_min_dt
            ),
            [afternoon_min_dt],
            transform=lambda d: d.dt,
        )

    def test_query_datetimes(self):
        """
        Tests the functionality of the datetimes method of the Event.objects manager, verifying it correctly truncates datetime objects to the specified unit of time (year, month, day, hour, minute, second).
        """
        Event.objects.create(dt=datetime.datetime(2011, 1, 1, 1, 30, 0))
        Event.objects.create(dt=datetime.datetime(2011, 1, 1, 4, 30, 0))
        self.assertSequenceEqual(
            Event.objects.datetimes("dt", "year"),
            [datetime.datetime(2011, 1, 1, 0, 0, 0)],
        )
        self.assertSequenceEqual(
            Event.objects.datetimes("dt", "month"),
            [datetime.datetime(2011, 1, 1, 0, 0, 0)],
        )
        self.assertSequenceEqual(
            Event.objects.datetimes("dt", "day"),
            [datetime.datetime(2011, 1, 1, 0, 0, 0)],
        )
        self.assertSequenceEqual(
            Event.objects.datetimes("dt", "hour"),
            [
                datetime.datetime(2011, 1, 1, 1, 0, 0),
                datetime.datetime(2011, 1, 1, 4, 0, 0),
            ],
        )
        self.assertSequenceEqual(
            Event.objects.datetimes("dt", "minute"),
            [
                datetime.datetime(2011, 1, 1, 1, 30, 0),
                datetime.datetime(2011, 1, 1, 4, 30, 0),
            ],
        )
        self.assertSequenceEqual(
            Event.objects.datetimes("dt", "second"),
            [
                datetime.datetime(2011, 1, 1, 1, 30, 0),
                datetime.datetime(2011, 1, 1, 4, 30, 0),
            ],
        )

    def test_raw_sql(self):
        # Regression test for #17755
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30)
        event = Event.objects.create(dt=dt)
        self.assertEqual(
            list(
                Event.objects.raw("SELECT * FROM timezones_event WHERE dt = %s", [dt])
            ),
            [event],
        )

    def test_cursor_execute_accepts_naive_datetime(self):
        """
        Tests that the database cursor can execute queries using naive datetime objects.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30)
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO timezones_event (dt) VALUES (%s)", [dt])
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    def test_cursor_execute_returns_naive_datetime(self):
        """
        Tests that the database cursor executes a query and returns a naive datetime object correctly, ensuring consistent date and time data retrieval.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30)
        Event.objects.create(dt=dt)
        with connection.cursor() as cursor:
            cursor.execute("SELECT dt FROM timezones_event WHERE dt = %s", [dt])
            self.assertEqual(cursor.fetchall()[0][0], dt)

    def test_filter_date_field_with_aware_datetime(self):
        # Regression test for #17742
        day = datetime.date(2011, 9, 1)
        AllDayEvent.objects.create(day=day)
        # This is 2011-09-02T01:30:00+03:00 in EAT
        dt = datetime.datetime(2011, 9, 1, 22, 30, 0, tzinfo=UTC)
        self.assertTrue(AllDayEvent.objects.filter(day__gte=dt).exists())


@override_settings(TIME_ZONE="Africa/Nairobi", USE_TZ=True)
class NewDatabaseTests(TestCase):
    naive_warning = "DateTimeField Event.dt received a naive datetime"

    @skipIfDBFeature("supports_timezones")
    def test_aware_time_unsupported(self):
        t = datetime.time(13, 20, 30, tzinfo=EAT)
        msg = "backend does not support timezone-aware times."
        with self.assertRaisesMessage(ValueError, msg):
            DailyEvent.objects.create(time=t)

    @requires_tz_support
    def test_naive_datetime(self):
        """

        Tests the creation of an event with a naive datetime object, ensuring a warning is raised and the datetime is successfully localized to the expected timezone.

        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30)
        with self.assertWarnsMessage(RuntimeWarning, self.naive_warning):
            Event.objects.create(dt=dt)
        event = Event.objects.get()
        # naive datetimes are interpreted in local time
        self.assertEqual(event.dt, dt.replace(tzinfo=EAT))

    @requires_tz_support
    def test_datetime_from_date(self):
        """
        Tests that creating an Event object with a naive datetime.date object results in a warning and the date being converted to a timezone-aware datetime object with the EAT timezone.
        """
        dt = datetime.date(2011, 9, 1)
        with self.assertWarnsMessage(RuntimeWarning, self.naive_warning):
            Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertEqual(event.dt, datetime.datetime(2011, 9, 1, tzinfo=EAT))

    @requires_tz_support
    def test_filter_unbound_datetime_with_naive_date(self):
        dt = datetime.date(2011, 9, 1)
        msg = "DateTimeField (unbound) received a naive datetime"
        with self.assertWarnsMessage(RuntimeWarning, msg):
            Event.objects.annotate(unbound_datetime=Now()).filter(unbound_datetime=dt)

    @requires_tz_support
    def test_naive_datetime_with_microsecond(self):
        """
        Test creation of an Event with a naive datetime containing microseconds, 
        verifying a warning is raised and the datetime is properly converted to the 
        project's timezone.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, 405060)
        with self.assertWarnsMessage(RuntimeWarning, self.naive_warning):
            Event.objects.create(dt=dt)
        event = Event.objects.get()
        # naive datetimes are interpreted in local time
        self.assertEqual(event.dt, dt.replace(tzinfo=EAT))

    def test_aware_datetime_in_local_timezone(self):
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    def test_aware_datetime_in_local_timezone_with_microsecond(self):
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, 405060, tzinfo=EAT)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    def test_aware_datetime_in_utc(self):
        dt = datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    def test_aware_datetime_in_other_timezone(self):
        dt = datetime.datetime(2011, 9, 1, 17, 20, 30, tzinfo=ICT)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    def test_auto_now_and_auto_now_add(self):
        """
        Tests that Timestamp model's auto_now and auto_now_add fields are correctly set to the current time when an instance is created and updated.
        """
        now = timezone.now()
        past = now - datetime.timedelta(seconds=2)
        future = now + datetime.timedelta(seconds=2)
        Timestamp.objects.create()
        ts = Timestamp.objects.get()
        self.assertLess(past, ts.created)
        self.assertLess(past, ts.updated)
        self.assertGreater(future, ts.updated)
        self.assertGreater(future, ts.updated)

    def test_query_filter(self):
        """

        Tests the filtering of events by date and time using Django's ORM query API.

        Verifies that the filtering by greater than or equal to and greater than 
        date/time criteria returns the correct number of events.

        """
        dt1 = datetime.datetime(2011, 9, 1, 12, 20, 30, tzinfo=EAT)
        dt2 = datetime.datetime(2011, 9, 1, 14, 20, 30, tzinfo=EAT)
        Event.objects.create(dt=dt1)
        Event.objects.create(dt=dt2)
        self.assertEqual(Event.objects.filter(dt__gte=dt1).count(), 2)
        self.assertEqual(Event.objects.filter(dt__gt=dt1).count(), 1)
        self.assertEqual(Event.objects.filter(dt__gte=dt2).count(), 1)
        self.assertEqual(Event.objects.filter(dt__gt=dt2).count(), 0)

    def test_query_filter_with_timezones(self):
        """
        Tests filtering of events by datetime with timezone, ensuring correct handling of exact, in and range queries when using timezone aware datetime objects.
        """
        tz = zoneinfo.ZoneInfo("Europe/Paris")
        dt = datetime.datetime(2011, 9, 1, 12, 20, 30, tzinfo=tz)
        Event.objects.create(dt=dt)
        next = dt + datetime.timedelta(seconds=3)
        prev = dt - datetime.timedelta(seconds=3)
        self.assertEqual(Event.objects.filter(dt__exact=dt).count(), 1)
        self.assertEqual(Event.objects.filter(dt__exact=next).count(), 0)
        self.assertEqual(Event.objects.filter(dt__in=(prev, next)).count(), 0)
        self.assertEqual(Event.objects.filter(dt__in=(prev, dt, next)).count(), 1)
        self.assertEqual(Event.objects.filter(dt__range=(prev, next)).count(), 1)

    def test_query_convert_timezones(self):
        # Connection timezone is equal to the current timezone, datetime
        # shouldn't be converted.
        """
        Tests the conversion of timezones when querying events by date.

        Verifies that events are correctly retrieved when the database connection timezone is overridden, 
        ensuring that date-based queries work correctly across different timezones.
        """
        with override_database_connection_timezone("Africa/Nairobi"):
            event_datetime = datetime.datetime(2016, 1, 2, 23, 10, 11, 123, tzinfo=EAT)
            event = Event.objects.create(dt=event_datetime)
            self.assertEqual(
                Event.objects.filter(dt__date=event_datetime.date()).first(), event
            )
        # Connection timezone is not equal to the current timezone, datetime
        # should be converted (-4h).
        with override_database_connection_timezone("Asia/Bangkok"):
            event_datetime = datetime.datetime(2016, 1, 2, 3, 10, 11, tzinfo=ICT)
            event = Event.objects.create(dt=event_datetime)
            self.assertEqual(
                Event.objects.filter(dt__date=datetime.date(2016, 1, 1)).first(), event
            )

    @requires_tz_support
    def test_query_filter_with_naive_datetime(self):
        """
        Test that querying with a naive datetime object (i.e., one without timezone information) raises a warning and produces the correct results for exact, less-than-or-equal, and greater-than comparisons.
        """
        dt = datetime.datetime(2011, 9, 1, 12, 20, 30, tzinfo=EAT)
        Event.objects.create(dt=dt)
        dt = dt.replace(tzinfo=None)
        # naive datetimes are interpreted in local time
        with self.assertWarnsMessage(RuntimeWarning, self.naive_warning):
            self.assertEqual(Event.objects.filter(dt__exact=dt).count(), 1)
        with self.assertWarnsMessage(RuntimeWarning, self.naive_warning):
            self.assertEqual(Event.objects.filter(dt__lte=dt).count(), 1)
        with self.assertWarnsMessage(RuntimeWarning, self.naive_warning):
            self.assertEqual(Event.objects.filter(dt__gt=dt).count(), 0)

    @skipUnlessDBFeature("has_zoneinfo_database")
    def test_query_datetime_lookups(self):
        """
        Tests datetime field lookups on model instances.

        Verifies that various datetime lookup types (e.g. year, month, day, hour)
        correctly filter objects based on their datetime fields.

        """
        Event.objects.create(dt=datetime.datetime(2011, 1, 1, 1, 30, 0, tzinfo=EAT))
        Event.objects.create(dt=datetime.datetime(2011, 1, 1, 4, 30, 0, tzinfo=EAT))
        self.assertEqual(Event.objects.filter(dt__year=2011).count(), 2)
        self.assertEqual(Event.objects.filter(dt__month=1).count(), 2)
        self.assertEqual(Event.objects.filter(dt__day=1).count(), 2)
        self.assertEqual(Event.objects.filter(dt__week_day=7).count(), 2)
        self.assertEqual(Event.objects.filter(dt__iso_week_day=6).count(), 2)
        self.assertEqual(Event.objects.filter(dt__hour=1).count(), 1)
        self.assertEqual(Event.objects.filter(dt__minute=30).count(), 2)
        self.assertEqual(Event.objects.filter(dt__second=0).count(), 2)

    @skipUnlessDBFeature("has_zoneinfo_database")
    def test_query_datetime_lookups_in_other_timezone(self):
        """
        Tests datetime lookup functions in a different timezone, ensuring they correctly query data when the timezone is overridden.
        """
        Event.objects.create(dt=datetime.datetime(2011, 1, 1, 1, 30, 0, tzinfo=EAT))
        Event.objects.create(dt=datetime.datetime(2011, 1, 1, 4, 30, 0, tzinfo=EAT))
        with timezone.override(UTC):
            # These two dates fall in the same day in EAT, but in different days,
            # years and months in UTC.
            self.assertEqual(Event.objects.filter(dt__year=2011).count(), 1)
            self.assertEqual(Event.objects.filter(dt__month=1).count(), 1)
            self.assertEqual(Event.objects.filter(dt__day=1).count(), 1)
            self.assertEqual(Event.objects.filter(dt__week_day=7).count(), 1)
            self.assertEqual(Event.objects.filter(dt__iso_week_day=6).count(), 1)
            self.assertEqual(Event.objects.filter(dt__hour=22).count(), 1)
            self.assertEqual(Event.objects.filter(dt__minute=30).count(), 2)
            self.assertEqual(Event.objects.filter(dt__second=0).count(), 2)

    def test_query_aggregation(self):
        # Only min and max make sense for datetimes.
        """
        Test the aggregation functionality of the Event model by creating events with different timestamps and verifying that the Min and Max aggregations return the correct minimum and maximum datetimes.
        """
        Event.objects.create(dt=datetime.datetime(2011, 9, 1, 23, 20, 20, tzinfo=EAT))
        Event.objects.create(dt=datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT))
        Event.objects.create(dt=datetime.datetime(2011, 9, 1, 3, 20, 40, tzinfo=EAT))
        result = Event.objects.aggregate(Min("dt"), Max("dt"))
        self.assertEqual(
            result,
            {
                "dt__min": datetime.datetime(2011, 9, 1, 3, 20, 40, tzinfo=EAT),
                "dt__max": datetime.datetime(2011, 9, 1, 23, 20, 20, tzinfo=EAT),
            },
        )

    def test_query_annotation(self):
        # Only min and max make sense for datetimes.
        """

        Tests the query annotation on Session objects by creating sessions and events,
        then verifying that the minimum datetime of events for each session is correctly
        annotated and filtered.

        """
        morning = Session.objects.create(name="morning")
        afternoon = Session.objects.create(name="afternoon")
        SessionEvent.objects.create(
            dt=datetime.datetime(2011, 9, 1, 23, 20, 20, tzinfo=EAT), session=afternoon
        )
        SessionEvent.objects.create(
            dt=datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT), session=afternoon
        )
        SessionEvent.objects.create(
            dt=datetime.datetime(2011, 9, 1, 3, 20, 40, tzinfo=EAT), session=morning
        )
        morning_min_dt = datetime.datetime(2011, 9, 1, 3, 20, 40, tzinfo=EAT)
        afternoon_min_dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)
        self.assertQuerySetEqual(
            Session.objects.annotate(dt=Min("events__dt")).order_by("dt"),
            [morning_min_dt, afternoon_min_dt],
            transform=lambda d: d.dt,
        )
        self.assertQuerySetEqual(
            Session.objects.annotate(dt=Min("events__dt")).filter(
                dt__lt=afternoon_min_dt
            ),
            [morning_min_dt],
            transform=lambda d: d.dt,
        )
        self.assertQuerySetEqual(
            Session.objects.annotate(dt=Min("events__dt")).filter(
                dt__gte=afternoon_min_dt
            ),
            [afternoon_min_dt],
            transform=lambda d: d.dt,
        )

    @skipUnlessDBFeature("has_zoneinfo_database")
    def test_query_datetimes(self):
        """
        Test the datetimes method of a Django ORM query, ensuring it correctly truncates datetime objects to the specified interval (year, month, day, hour, minute, second).
        """
        Event.objects.create(dt=datetime.datetime(2011, 1, 1, 1, 30, 0, tzinfo=EAT))
        Event.objects.create(dt=datetime.datetime(2011, 1, 1, 4, 30, 0, tzinfo=EAT))
        self.assertSequenceEqual(
            Event.objects.datetimes("dt", "year"),
            [datetime.datetime(2011, 1, 1, 0, 0, 0, tzinfo=EAT)],
        )
        self.assertSequenceEqual(
            Event.objects.datetimes("dt", "month"),
            [datetime.datetime(2011, 1, 1, 0, 0, 0, tzinfo=EAT)],
        )
        self.assertSequenceEqual(
            Event.objects.datetimes("dt", "day"),
            [datetime.datetime(2011, 1, 1, 0, 0, 0, tzinfo=EAT)],
        )
        self.assertSequenceEqual(
            Event.objects.datetimes("dt", "hour"),
            [
                datetime.datetime(2011, 1, 1, 1, 0, 0, tzinfo=EAT),
                datetime.datetime(2011, 1, 1, 4, 0, 0, tzinfo=EAT),
            ],
        )
        self.assertSequenceEqual(
            Event.objects.datetimes("dt", "minute"),
            [
                datetime.datetime(2011, 1, 1, 1, 30, 0, tzinfo=EAT),
                datetime.datetime(2011, 1, 1, 4, 30, 0, tzinfo=EAT),
            ],
        )
        self.assertSequenceEqual(
            Event.objects.datetimes("dt", "second"),
            [
                datetime.datetime(2011, 1, 1, 1, 30, 0, tzinfo=EAT),
                datetime.datetime(2011, 1, 1, 4, 30, 0, tzinfo=EAT),
            ],
        )

    @skipUnlessDBFeature("has_zoneinfo_database")
    def test_query_datetimes_in_other_timezone(self):
        """
        Tests the datetimes method of a QuerySet when the datetime field is in a different timezone than the active timezone. It verifies that the datetimes are correctly converted to the active timezone.
        """
        Event.objects.create(dt=datetime.datetime(2011, 1, 1, 1, 30, 0, tzinfo=EAT))
        Event.objects.create(dt=datetime.datetime(2011, 1, 1, 4, 30, 0, tzinfo=EAT))
        with timezone.override(UTC):
            self.assertSequenceEqual(
                Event.objects.datetimes("dt", "year"),
                [
                    datetime.datetime(2010, 1, 1, 0, 0, 0, tzinfo=UTC),
                    datetime.datetime(2011, 1, 1, 0, 0, 0, tzinfo=UTC),
                ],
            )
            self.assertSequenceEqual(
                Event.objects.datetimes("dt", "month"),
                [
                    datetime.datetime(2010, 12, 1, 0, 0, 0, tzinfo=UTC),
                    datetime.datetime(2011, 1, 1, 0, 0, 0, tzinfo=UTC),
                ],
            )
            self.assertSequenceEqual(
                Event.objects.datetimes("dt", "day"),
                [
                    datetime.datetime(2010, 12, 31, 0, 0, 0, tzinfo=UTC),
                    datetime.datetime(2011, 1, 1, 0, 0, 0, tzinfo=UTC),
                ],
            )
            self.assertSequenceEqual(
                Event.objects.datetimes("dt", "hour"),
                [
                    datetime.datetime(2010, 12, 31, 22, 0, 0, tzinfo=UTC),
                    datetime.datetime(2011, 1, 1, 1, 0, 0, tzinfo=UTC),
                ],
            )
            self.assertSequenceEqual(
                Event.objects.datetimes("dt", "minute"),
                [
                    datetime.datetime(2010, 12, 31, 22, 30, 0, tzinfo=UTC),
                    datetime.datetime(2011, 1, 1, 1, 30, 0, tzinfo=UTC),
                ],
            )
            self.assertSequenceEqual(
                Event.objects.datetimes("dt", "second"),
                [
                    datetime.datetime(2010, 12, 31, 22, 30, 0, tzinfo=UTC),
                    datetime.datetime(2011, 1, 1, 1, 30, 0, tzinfo=UTC),
                ],
            )

    def test_raw_sql(self):
        # Regression test for #17755
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)
        event = Event.objects.create(dt=dt)
        self.assertSequenceEqual(
            list(
                Event.objects.raw("SELECT * FROM timezones_event WHERE dt = %s", [dt])
            ),
            [event],
        )

    @skipUnlessDBFeature("supports_timezones")
    def test_cursor_execute_accepts_aware_datetime(self):
        """

        Tests if a database cursor can execute a query with an aware datetime object.

        Verifies that the datetime object is correctly inserted and retrieved from the database,
        without losing its timezone information.

        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO timezones_event (dt) VALUES (%s)", [dt])
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    @skipIfDBFeature("supports_timezones")
    def test_cursor_execute_accepts_naive_datetime(self):
        """
        Tests that cursor.execute can handle naive datetime objects, ensuring they are correctly stored and retrieved despite database timezone support being unavailable.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)
        utc_naive_dt = timezone.make_naive(dt, datetime.timezone.utc)
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO timezones_event (dt) VALUES (%s)", [utc_naive_dt]
            )
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    @skipUnlessDBFeature("supports_timezones")
    def test_cursor_execute_returns_aware_datetime(self):
        """

        Tests that the database cursor correctly handles and returns timezone-aware datetime objects when executing a query.

        This test case verifies that the datetime value retrieved from the database matches the original aware datetime object used in the query.

        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)
        Event.objects.create(dt=dt)
        with connection.cursor() as cursor:
            cursor.execute("SELECT dt FROM timezones_event WHERE dt = %s", [dt])
            self.assertEqual(cursor.fetchall()[0][0], dt)

    @skipIfDBFeature("supports_timezones")
    def test_cursor_execute_returns_naive_datetime(self):
        """
        Tests that a cursor execute operation returns naive datetime objects.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)
        utc_naive_dt = timezone.make_naive(dt, datetime.timezone.utc)
        Event.objects.create(dt=dt)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT dt FROM timezones_event WHERE dt = %s", [utc_naive_dt]
            )
            self.assertEqual(cursor.fetchall()[0][0], utc_naive_dt)

    @skipUnlessDBFeature("supports_timezones")
    def test_cursor_explicit_time_zone(self):
        """
        Tests if the cursor correctly uses an explicit time zone when executing a query. 
        Verifies that the timezone from the database connection is applied to the results.
        """
        with override_database_connection_timezone("Europe/Paris"):
            with connection.cursor() as cursor:
                cursor.execute("SELECT CURRENT_TIMESTAMP")
                now = cursor.fetchone()[0]
                self.assertEqual(str(now.tzinfo), "Europe/Paris")

    @requires_tz_support
    def test_filter_date_field_with_aware_datetime(self):
        # Regression test for #17742
        day = datetime.date(2011, 9, 1)
        AllDayEvent.objects.create(day=day)
        # This is 2011-09-02T01:30:00+03:00 in EAT
        dt = datetime.datetime(2011, 9, 1, 22, 30, 0, tzinfo=UTC)
        self.assertFalse(AllDayEvent.objects.filter(day__gte=dt).exists())

    def test_null_datetime(self):
        # Regression test for #17294
        e = MaybeEvent.objects.create()
        self.assertIsNone(e.dt)

    def test_update_with_timedelta(self):
        """
        Tests that the Event model's datetime field can be updated with a timedelta value, verifying the correct offset is applied to the initial datetime value.
        """
        initial_dt = timezone.now().replace(microsecond=0)
        event = Event.objects.create(dt=initial_dt)
        Event.objects.update(dt=F("dt") + timedelta(hours=2))
        event.refresh_from_db()
        self.assertEqual(event.dt, initial_dt + timedelta(hours=2))


@override_settings(TIME_ZONE="Africa/Nairobi", USE_TZ=True)
class ForcedTimeZoneDatabaseTests(TransactionTestCase):
    """
    Test the TIME_ZONE database configuration parameter.

    Since this involves reading and writing to the same database through two
    connections, this is a TransactionTestCase.
    """

    available_apps = ["timezones"]

    @classmethod
    def setUpClass(cls):
        # @skipIfDBFeature and @skipUnlessDBFeature cannot be chained. The
        # outermost takes precedence. Handle skipping manually instead.
        """

        Ensures the test database setup is compatible with the test requirements.

        Skips the test if the database supports timezones or does not allow multiple connections.

        """
        if connection.features.supports_timezones:
            raise SkipTest("Database has feature(s) supports_timezones")
        if not connection.features.test_db_allows_multiple_connections:
            raise SkipTest(
                "Database doesn't support feature(s): "
                "test_db_allows_multiple_connections"
            )

        super().setUpClass()

    def test_read_datetime(self):
        """
        Tests that datetime fields are correctly read and converted to the database connection's timezone.\"\"\"
        ```
        """
        fake_dt = datetime.datetime(2011, 9, 1, 17, 20, 30, tzinfo=UTC)
        Event.objects.create(dt=fake_dt)

        with override_database_connection_timezone("Asia/Bangkok"):
            event = Event.objects.get()
            dt = datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC)
        self.assertEqual(event.dt, dt)

    def test_write_datetime(self):
        """
        Tests that datetime values are correctly written to the database, taking into account the timezone override.
        """
        dt = datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC)
        with override_database_connection_timezone("Asia/Bangkok"):
            Event.objects.create(dt=dt)

        event = Event.objects.get()
        fake_dt = datetime.datetime(2011, 9, 1, 17, 20, 30, tzinfo=UTC)
        self.assertEqual(event.dt, fake_dt)


@override_settings(TIME_ZONE="Africa/Nairobi")
class SerializationTests(SimpleTestCase):
    # Backend-specific notes:
    # - JSON supports only milliseconds, microseconds will be truncated.
    # - PyYAML dumps the UTC offset correctly for timezone-aware datetimes.
    #   When PyYAML < 5.3 loads this representation, it subtracts the offset
    #   and returns a naive datetime object in UTC. PyYAML 5.3+ loads timezones
    #   correctly.
    # Tests are adapted to take these quirks into account.

    def assert_python_contains_datetime(self, objects, dt):
        self.assertEqual(objects[0]["fields"]["dt"], dt)

    def assert_json_contains_datetime(self, json, dt):
        self.assertIn('"fields": {"dt": "%s"}' % dt, json)

    def assert_xml_contains_datetime(self, xml, dt):
        field = parseString(xml).getElementsByTagName("field")[0]
        self.assertXMLEqual(field.childNodes[0].wholeText, dt)

    def assert_yaml_contains_datetime(self, yaml, dt):
        # Depending on the yaml dumper, '!timestamp' might be absent
        self.assertRegex(yaml, r"\n  fields: {dt: !(!timestamp)? '%s'}" % re.escape(dt))

    def test_naive_datetime(self):
        """
        Tests the serialization and deserialization of datetime objects through various formats, including python, json, xml, and yaml, to ensure accuracy and consistency across different data formats.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30)

        data = serializers.serialize("python", [Event(dt=dt)])
        self.assert_python_contains_datetime(data, dt)
        obj = next(serializers.deserialize("python", data)).object
        self.assertEqual(obj.dt, dt)

        data = serializers.serialize("json", [Event(dt=dt)])
        self.assert_json_contains_datetime(data, "2011-09-01T13:20:30")
        obj = next(serializers.deserialize("json", data)).object
        self.assertEqual(obj.dt, dt)

        data = serializers.serialize("xml", [Event(dt=dt)])
        self.assert_xml_contains_datetime(data, "2011-09-01T13:20:30")
        obj = next(serializers.deserialize("xml", data)).object
        self.assertEqual(obj.dt, dt)

        if not isinstance(
            serializers.get_serializer("yaml"), serializers.BadSerializer
        ):
            data = serializers.serialize(
                "yaml", [Event(dt=dt)], default_flow_style=None
            )
            self.assert_yaml_contains_datetime(data, "2011-09-01 13:20:30")
            obj = next(serializers.deserialize("yaml", data)).object
            self.assertEqual(obj.dt, dt)

    def test_naive_datetime_with_microsecond(self):
        """
        Tests serialization and deserialization of datetime objects with microseconds across different formats (python, json, xml, yaml).
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, 405060)

        data = serializers.serialize("python", [Event(dt=dt)])
        self.assert_python_contains_datetime(data, dt)
        obj = next(serializers.deserialize("python", data)).object
        self.assertEqual(obj.dt, dt)

        data = serializers.serialize("json", [Event(dt=dt)])
        self.assert_json_contains_datetime(data, "2011-09-01T13:20:30.405")
        obj = next(serializers.deserialize("json", data)).object
        self.assertEqual(obj.dt, dt.replace(microsecond=405000))

        data = serializers.serialize("xml", [Event(dt=dt)])
        self.assert_xml_contains_datetime(data, "2011-09-01T13:20:30.405060")
        obj = next(serializers.deserialize("xml", data)).object
        self.assertEqual(obj.dt, dt)

        if not isinstance(
            serializers.get_serializer("yaml"), serializers.BadSerializer
        ):
            data = serializers.serialize(
                "yaml", [Event(dt=dt)], default_flow_style=None
            )
            self.assert_yaml_contains_datetime(data, "2011-09-01 13:20:30.405060")
            obj = next(serializers.deserialize("yaml", data)).object
            self.assertEqual(obj.dt, dt)

    def test_aware_datetime_with_microsecond(self):
        """
        Tests the serialization and deserialization of DateTime objects with microseconds in different formats, including python, json, xml, and yaml, to ensure the datetime values are correctly preserved and restored.
        """
        dt = datetime.datetime(2011, 9, 1, 17, 20, 30, 405060, tzinfo=ICT)

        data = serializers.serialize("python", [Event(dt=dt)])
        self.assert_python_contains_datetime(data, dt)
        obj = next(serializers.deserialize("python", data)).object
        self.assertEqual(obj.dt, dt)

        data = serializers.serialize("json", [Event(dt=dt)])
        self.assert_json_contains_datetime(data, "2011-09-01T17:20:30.405+07:00")
        obj = next(serializers.deserialize("json", data)).object
        self.assertEqual(obj.dt, dt.replace(microsecond=405000))

        data = serializers.serialize("xml", [Event(dt=dt)])
        self.assert_xml_contains_datetime(data, "2011-09-01T17:20:30.405060+07:00")
        obj = next(serializers.deserialize("xml", data)).object
        self.assertEqual(obj.dt, dt)

        if not isinstance(
            serializers.get_serializer("yaml"), serializers.BadSerializer
        ):
            data = serializers.serialize(
                "yaml", [Event(dt=dt)], default_flow_style=None
            )
            self.assert_yaml_contains_datetime(data, "2011-09-01 17:20:30.405060+07:00")
            obj = next(serializers.deserialize("yaml", data)).object
            if HAS_YAML and yaml.__version__ < "5.3":
                self.assertEqual(obj.dt.replace(tzinfo=UTC), dt)
            else:
                self.assertEqual(obj.dt, dt)

    def test_aware_datetime_in_utc(self):
        """
        Tests the serialization and deserialization of an aware datetime object in UTC across different formats (python, json, xml, yaml) to ensure date and time values are preserved and correctly converted.
        """
        dt = datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC)

        data = serializers.serialize("python", [Event(dt=dt)])
        self.assert_python_contains_datetime(data, dt)
        obj = next(serializers.deserialize("python", data)).object
        self.assertEqual(obj.dt, dt)

        data = serializers.serialize("json", [Event(dt=dt)])
        self.assert_json_contains_datetime(data, "2011-09-01T10:20:30Z")
        obj = next(serializers.deserialize("json", data)).object
        self.assertEqual(obj.dt, dt)

        data = serializers.serialize("xml", [Event(dt=dt)])
        self.assert_xml_contains_datetime(data, "2011-09-01T10:20:30+00:00")
        obj = next(serializers.deserialize("xml", data)).object
        self.assertEqual(obj.dt, dt)

        if not isinstance(
            serializers.get_serializer("yaml"), serializers.BadSerializer
        ):
            data = serializers.serialize(
                "yaml", [Event(dt=dt)], default_flow_style=None
            )
            self.assert_yaml_contains_datetime(data, "2011-09-01 10:20:30+00:00")
            obj = next(serializers.deserialize("yaml", data)).object
            self.assertEqual(obj.dt.replace(tzinfo=UTC), dt)

    def test_aware_datetime_in_local_timezone(self):
        """
        Tests serialization and deserialization of datetime objects in local timezones across various formats, including python, json, xml, and yaml, ensuring that datetime objects are correctly converted and preserved.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)

        data = serializers.serialize("python", [Event(dt=dt)])
        self.assert_python_contains_datetime(data, dt)
        obj = next(serializers.deserialize("python", data)).object
        self.assertEqual(obj.dt, dt)

        data = serializers.serialize("json", [Event(dt=dt)])
        self.assert_json_contains_datetime(data, "2011-09-01T13:20:30+03:00")
        obj = next(serializers.deserialize("json", data)).object
        self.assertEqual(obj.dt, dt)

        data = serializers.serialize("xml", [Event(dt=dt)])
        self.assert_xml_contains_datetime(data, "2011-09-01T13:20:30+03:00")
        obj = next(serializers.deserialize("xml", data)).object
        self.assertEqual(obj.dt, dt)

        if not isinstance(
            serializers.get_serializer("yaml"), serializers.BadSerializer
        ):
            data = serializers.serialize(
                "yaml", [Event(dt=dt)], default_flow_style=None
            )
            self.assert_yaml_contains_datetime(data, "2011-09-01 13:20:30+03:00")
            obj = next(serializers.deserialize("yaml", data)).object
            if HAS_YAML and yaml.__version__ < "5.3":
                self.assertEqual(obj.dt.replace(tzinfo=UTC), dt)
            else:
                self.assertEqual(obj.dt, dt)

    def test_aware_datetime_in_other_timezone(self):
        """
        Tests the serialization and deserialization of datetime objects in different timezones across various formats, including Python, JSON, XML, and YAML, to ensure correct preservation of timezone information.
        """
        dt = datetime.datetime(2011, 9, 1, 17, 20, 30, tzinfo=ICT)

        data = serializers.serialize("python", [Event(dt=dt)])
        self.assert_python_contains_datetime(data, dt)
        obj = next(serializers.deserialize("python", data)).object
        self.assertEqual(obj.dt, dt)

        data = serializers.serialize("json", [Event(dt=dt)])
        self.assert_json_contains_datetime(data, "2011-09-01T17:20:30+07:00")
        obj = next(serializers.deserialize("json", data)).object
        self.assertEqual(obj.dt, dt)

        data = serializers.serialize("xml", [Event(dt=dt)])
        self.assert_xml_contains_datetime(data, "2011-09-01T17:20:30+07:00")
        obj = next(serializers.deserialize("xml", data)).object
        self.assertEqual(obj.dt, dt)

        if not isinstance(
            serializers.get_serializer("yaml"), serializers.BadSerializer
        ):
            data = serializers.serialize(
                "yaml", [Event(dt=dt)], default_flow_style=None
            )
            self.assert_yaml_contains_datetime(data, "2011-09-01 17:20:30+07:00")
            obj = next(serializers.deserialize("yaml", data)).object
            if HAS_YAML and yaml.__version__ < "5.3":
                self.assertEqual(obj.dt.replace(tzinfo=UTC), dt)
            else:
                self.assertEqual(obj.dt, dt)


@translation.override(None)
@override_settings(DATETIME_FORMAT="c", TIME_ZONE="Africa/Nairobi", USE_TZ=True)
class TemplateTests(SimpleTestCase):
    @requires_tz_support
    def test_localtime_templatetag_and_filters(self):
        """
        Test the functionality of the {% localtime %} templatetag and related filters, ensuring correct time conversion between various time zones and scenarios.
        """
        datetimes = {
            "utc": datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC),
            "eat": datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT),
            "ict": datetime.datetime(2011, 9, 1, 17, 20, 30, tzinfo=ICT),
            "naive": datetime.datetime(2011, 9, 1, 13, 20, 30),
        }
        templates = {
            "notag": Template(
                "{% load tz %}"
                "{{ dt }}|{{ dt|localtime }}|{{ dt|utc }}|{{ dt|timezone:ICT }}"
            ),
            "noarg": Template(
                "{% load tz %}{% localtime %}{{ dt }}|{{ dt|localtime }}|"
                "{{ dt|utc }}|{{ dt|timezone:ICT }}{% endlocaltime %}"
            ),
            "on": Template(
                "{% load tz %}{% localtime on %}{{ dt }}|{{ dt|localtime }}|"
                "{{ dt|utc }}|{{ dt|timezone:ICT }}{% endlocaltime %}"
            ),
            "off": Template(
                "{% load tz %}{% localtime off %}{{ dt }}|{{ dt|localtime }}|"
                "{{ dt|utc }}|{{ dt|timezone:ICT }}{% endlocaltime %}"
            ),
        }

        # Transform a list of keys in 'datetimes' to the expected template
        # output. This makes the definition of 'results' more readable.
        def t(*result):
            return "|".join(datetimes[key].isoformat() for key in result)

        # Results for USE_TZ = True

        results = {
            "utc": {
                "notag": t("eat", "eat", "utc", "ict"),
                "noarg": t("eat", "eat", "utc", "ict"),
                "on": t("eat", "eat", "utc", "ict"),
                "off": t("utc", "eat", "utc", "ict"),
            },
            "eat": {
                "notag": t("eat", "eat", "utc", "ict"),
                "noarg": t("eat", "eat", "utc", "ict"),
                "on": t("eat", "eat", "utc", "ict"),
                "off": t("eat", "eat", "utc", "ict"),
            },
            "ict": {
                "notag": t("eat", "eat", "utc", "ict"),
                "noarg": t("eat", "eat", "utc", "ict"),
                "on": t("eat", "eat", "utc", "ict"),
                "off": t("ict", "eat", "utc", "ict"),
            },
            "naive": {
                "notag": t("naive", "eat", "utc", "ict"),
                "noarg": t("naive", "eat", "utc", "ict"),
                "on": t("naive", "eat", "utc", "ict"),
                "off": t("naive", "eat", "utc", "ict"),
            },
        }

        for k1, dt in datetimes.items():
            for k2, tpl in templates.items():
                ctx = Context({"dt": dt, "ICT": ICT})
                actual = tpl.render(ctx)
                expected = results[k1][k2]
                self.assertEqual(
                    actual, expected, "%s / %s: %r != %r" % (k1, k2, actual, expected)
                )

        # Changes for USE_TZ = False

        results["utc"]["notag"] = t("utc", "eat", "utc", "ict")
        results["ict"]["notag"] = t("ict", "eat", "utc", "ict")

        with self.settings(USE_TZ=False):
            for k1, dt in datetimes.items():
                for k2, tpl in templates.items():
                    ctx = Context({"dt": dt, "ICT": ICT})
                    actual = tpl.render(ctx)
                    expected = results[k1][k2]
                    self.assertEqual(
                        actual,
                        expected,
                        "%s / %s: %r != %r" % (k1, k2, actual, expected),
                    )

    def test_localtime_filters_with_iana(self):
        """
        Tests the behavior of timezone-related filters, specifically localtime, utc, and timezone, when used with IANA time zones and datetime objects.
        """
        # Use an IANA timezone as local time
        tpl = Template("{% load tz %}{{ dt|localtime }}|{{ dt|utc }}")
        ctx = Context({"dt": datetime.datetime(2011, 9, 1, 12, 20, 30)})

        with self.settings(TIME_ZONE="Europe/Paris"):
            self.assertEqual(
                tpl.render(ctx), "2011-09-01T12:20:30+02:00|2011-09-01T10:20:30+00:00"
            )

        # Use an IANA timezone as argument
        tz = zoneinfo.ZoneInfo("Europe/Paris")
        tpl = Template("{% load tz %}{{ dt|timezone:tz }}")
        ctx = Context(
            {
                "dt": datetime.datetime(2011, 9, 1, 13, 20, 30),
                "tz": tz,
            }
        )
        self.assertEqual(tpl.render(ctx), "2011-09-01T12:20:30+02:00")

    def test_localtime_templatetag_invalid_argument(self):
        with self.assertRaises(TemplateSyntaxError):
            Template("{% load tz %}{% localtime foo %}{% endlocaltime %}").render()

    def test_localtime_filters_do_not_raise_exceptions(self):
        """
        Tests that the localtime, utc, and timezone filters handle invalid inputs without raising exceptions.
        """
        tpl = Template(
            "{% load tz %}{{ dt }}|{{ dt|localtime }}|{{ dt|utc }}|{{ dt|timezone:tz }}"
        )
        with self.settings(USE_TZ=True):
            # bad datetime value
            ctx = Context({"dt": None, "tz": ICT})
            self.assertEqual(tpl.render(ctx), "None|||")
            ctx = Context({"dt": "not a date", "tz": ICT})
            self.assertEqual(tpl.render(ctx), "not a date|||")
            # bad timezone value
            tpl = Template("{% load tz %}{{ dt|timezone:tz }}")
            ctx = Context({"dt": datetime.datetime(2011, 9, 1, 13, 20, 30), "tz": None})
            self.assertEqual(tpl.render(ctx), "")
            ctx = Context(
                {"dt": datetime.datetime(2011, 9, 1, 13, 20, 30), "tz": "not a tz"}
            )
            self.assertEqual(tpl.render(ctx), "")

    @requires_tz_support
    def test_timezone_templatetag(self):
        """
        Test the {% timezone %} templatetag.
        """
        tpl = Template(
            "{% load tz %}"
            "{{ dt }}|"
            "{% timezone tz1 %}"
            "{{ dt }}|"
            "{% timezone tz2 %}"
            "{{ dt }}"
            "{% endtimezone %}"
            "{% endtimezone %}"
        )
        ctx = Context(
            {
                "dt": datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC),
                "tz1": ICT,
                "tz2": None,
            }
        )
        self.assertEqual(
            tpl.render(ctx),
            "2011-09-01T13:20:30+03:00|2011-09-01T17:20:30+07:00|"
            "2011-09-01T13:20:30+03:00",
        )

    def test_timezone_templatetag_with_iana(self):
        """
        Tests the functionality of the {% timezone %} templatetag with IANA time zone providers, ensuring correct time conversions are applied to a given datetime object.
        """
        tpl = Template("{% load tz %}{% timezone tz %}{{ dt }}{% endtimezone %}")

        # Use a IANA timezone as argument
        tz = zoneinfo.ZoneInfo("Europe/Paris")
        ctx = Context(
            {
                "dt": datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT),
                "tz": tz,
            }
        )
        self.assertEqual(tpl.render(ctx), "2011-09-01T12:20:30+02:00")

        # Use a IANA timezone name as argument
        ctx = Context(
            {
                "dt": datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT),
                "tz": "Europe/Paris",
            }
        )
        self.assertEqual(tpl.render(ctx), "2011-09-01T12:20:30+02:00")

    @skipIf(sys.platform == "win32", "Windows uses non-standard time zone names")
    def test_get_current_timezone_templatetag(self):
        """
        Tests the functionality of the {% get_current_timezone %} template tag, verifying its ability to return the current timezone name or offset, depending on the context in which it is used.
        """
        tpl = Template(
            "{% load tz %}{% get_current_timezone as time_zone %}{{ time_zone }}"
        )

        self.assertEqual(tpl.render(Context()), "Africa/Nairobi")
        with timezone.override(UTC):
            self.assertEqual(tpl.render(Context()), "UTC")

        tpl = Template(
            "{% load tz %}{% timezone tz %}{% get_current_timezone as time_zone %}"
            "{% endtimezone %}{{ time_zone }}"
        )

        self.assertEqual(tpl.render(Context({"tz": ICT})), "+0700")
        with timezone.override(UTC):
            self.assertEqual(tpl.render(Context({"tz": ICT})), "+0700")

    def test_get_current_timezone_templatetag_with_iana(self):
        """
        Tests the functionality of the get_current_timezone template tag, verifying it correctly retrieves the current timezone under various conditions, including when the timezone is overridden.
        """
        tpl = Template(
            "{% load tz %}{% get_current_timezone as time_zone %}{{ time_zone }}"
        )
        tz = zoneinfo.ZoneInfo("Europe/Paris")
        with timezone.override(tz):
            self.assertEqual(tpl.render(Context()), "Europe/Paris")

        tpl = Template(
            "{% load tz %}{% timezone 'Europe/Paris' %}"
            "{% get_current_timezone as time_zone %}{% endtimezone %}"
            "{{ time_zone }}"
        )
        self.assertEqual(tpl.render(Context()), "Europe/Paris")

    def test_get_current_timezone_templatetag_invalid_argument(self):
        msg = (
            "'get_current_timezone' requires 'as variable' (got "
            "['get_current_timezone'])"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            Template("{% load tz %}{% get_current_timezone %}").render()

    @skipIf(sys.platform == "win32", "Windows uses non-standard time zone names")
    def test_tz_template_context_processor(self):
        """

        Test the django.template.context_processors.tz template context processor.

        This test ensures that the tz context processor correctly sets the TIME_ZONE
        variable in the template context to the default time zone ('Africa/Nairobi').

        """
        tpl = Template("{{ TIME_ZONE }}")
        context = Context()
        self.assertEqual(tpl.render(context), "")
        request_context = RequestContext(
            HttpRequest(), processors=[context_processors.tz]
        )
        self.assertEqual(tpl.render(request_context), "Africa/Nairobi")

    @requires_tz_support
    def test_date_and_time_template_filters(self):
        """

        Tests the date and time template filters with timezone support.

        Verifies that the date and time template filters correctly format a datetime object
        in different timezones.

        """
        tpl = Template("{{ dt|date:'Y-m-d' }} at {{ dt|time:'H:i:s' }}")
        ctx = Context({"dt": datetime.datetime(2011, 9, 1, 20, 20, 20, tzinfo=UTC)})
        self.assertEqual(tpl.render(ctx), "2011-09-01 at 23:20:20")
        with timezone.override(ICT):
            self.assertEqual(tpl.render(ctx), "2011-09-02 at 03:20:20")

    def test_date_and_time_template_filters_honor_localtime(self):
        """
        Tests if date and time template filters honor localized time settings by checking their output with and without localized time zones.
        """
        tpl = Template(
            "{% load tz %}{% localtime off %}{{ dt|date:'Y-m-d' }} at "
            "{{ dt|time:'H:i:s' }}{% endlocaltime %}"
        )
        ctx = Context({"dt": datetime.datetime(2011, 9, 1, 20, 20, 20, tzinfo=UTC)})
        self.assertEqual(tpl.render(ctx), "2011-09-01 at 20:20:20")
        with timezone.override(ICT):
            self.assertEqual(tpl.render(ctx), "2011-09-01 at 20:20:20")

    @requires_tz_support
    def test_now_template_tag_uses_current_time_zone(self):
        # Regression for #17343
        tpl = Template('{% now "O" %}')
        self.assertEqual(tpl.render(Context({})), "+0300")
        with timezone.override(ICT):
            self.assertEqual(tpl.render(Context({})), "+0700")


@override_settings(DATETIME_FORMAT="c", TIME_ZONE="Africa/Nairobi", USE_TZ=False)
class LegacyFormsTests(TestCase):
    def test_form(self):
        form = EventForm({"dt": "2011-09-01 13:20:30"})
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data["dt"], datetime.datetime(2011, 9, 1, 13, 20, 30)
        )

    def test_form_with_non_existent_time(self):
        """
        Tests the handling of a non-existent time in a given timezone due to daylight saving adjustments in the EventForm.

        Verifies that the form is valid and that the datetime is correctly parsed despite the time actually not existing in the specified timezone.
        """
        form = EventForm({"dt": "2011-03-27 02:30:00"})
        tz = zoneinfo.ZoneInfo("Europe/Paris")
        with timezone.override(tz):
            # This is a bug.
            self.assertTrue(form.is_valid())
            self.assertEqual(
                form.cleaned_data["dt"],
                datetime.datetime(2011, 3, 27, 2, 30, 0),
            )

    def test_form_with_ambiguous_time(self):
        """
        Tests that an EventForm with an ambiguous time is valid when a timezone is specified, 
        ensuring correct parsing and interpretation of the datetime input.
        """
        form = EventForm({"dt": "2011-10-30 02:30:00"})
        tz = zoneinfo.ZoneInfo("Europe/Paris")
        with timezone.override(tz):
            # This is a bug.
            self.assertTrue(form.is_valid())
            self.assertEqual(
                form.cleaned_data["dt"],
                datetime.datetime(2011, 10, 30, 2, 30, 0),
            )

    def test_split_form(self):
        form = EventSplitForm({"dt_0": "2011-09-01", "dt_1": "13:20:30"})
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data["dt"], datetime.datetime(2011, 9, 1, 13, 20, 30)
        )

    def test_model_form(self):
        EventModelForm({"dt": "2011-09-01 13:20:30"}).save()
        e = Event.objects.get()
        self.assertEqual(e.dt, datetime.datetime(2011, 9, 1, 13, 20, 30))


@override_settings(DATETIME_FORMAT="c", TIME_ZONE="Africa/Nairobi", USE_TZ=True)
class NewFormsTests(TestCase):
    @requires_tz_support
    def test_form(self):
        form = EventForm({"dt": "2011-09-01 13:20:30"})
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data["dt"],
            datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC),
        )

    def test_form_with_other_timezone(self):
        form = EventForm({"dt": "2011-09-01 17:20:30"})
        with timezone.override(ICT):
            self.assertTrue(form.is_valid())
            self.assertEqual(
                form.cleaned_data["dt"],
                datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC),
            )

    def test_form_with_non_existent_time(self):
        """
        Tests the EventForm for invalidation when given a date and time that does not exist in a specific time zone due to daylight saving time transitions.
        """
        tz = zoneinfo.ZoneInfo("Europe/Paris")
        with timezone.override(tz):
            form = EventForm({"dt": "2011-03-27 02:30:00"})
            self.assertFalse(form.is_valid())
            self.assertEqual(
                form.errors["dt"],
                [
                    "2011-03-27 02:30:00 couldn’t be interpreted in time zone "
                    "Europe/Paris; it may be ambiguous or it may not exist."
                ],
            )

    def test_form_with_ambiguous_time(self):
        """
        Tests that an EventForm instance with an ambiguous time in a specific timezone is deemed invalid.

        The test checks that the form validation fails when the time cannot be unambiguously interpreted in the given timezone, such as during daylight saving time transitions.
        """
        tz = zoneinfo.ZoneInfo("Europe/Paris")
        with timezone.override(tz):
            form = EventForm({"dt": "2011-10-30 02:30:00"})
            self.assertFalse(form.is_valid())
            self.assertEqual(
                form.errors["dt"],
                [
                    "2011-10-30 02:30:00 couldn’t be interpreted in time zone "
                    "Europe/Paris; it may be ambiguous or it may not exist."
                ],
            )

    @requires_tz_support
    def test_split_form(self):
        form = EventSplitForm({"dt_0": "2011-09-01", "dt_1": "13:20:30"})
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data["dt"],
            datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC),
        )

    @requires_tz_support
    def test_localized_form(self):
        form = EventLocalizedForm(
            initial={"dt": datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)}
        )
        with timezone.override(ICT):
            self.assertIn("2011-09-01 17:20:30", str(form))

    @requires_tz_support
    def test_model_form(self):
        EventModelForm({"dt": "2011-09-01 13:20:30"}).save()
        e = Event.objects.get()
        self.assertEqual(e.dt, datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC))

    @requires_tz_support
    def test_localized_model_form(self):
        form = EventLocalizedModelForm(
            instance=Event(dt=datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT))
        )
        with timezone.override(ICT):
            self.assertIn("2011-09-01 17:20:30", str(form))


@translation.override(None)
@override_settings(
    DATETIME_FORMAT="c",
    TIME_ZONE="Africa/Nairobi",
    USE_TZ=True,
    ROOT_URLCONF="timezones.urls",
)
class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.u1 = User.objects.create_user(
            password="secret",
            last_login=datetime.datetime(2007, 5, 30, 13, 20, 10, tzinfo=UTC),
            is_superuser=True,
            username="super",
            first_name="Super",
            last_name="User",
            email="super@example.com",
            is_staff=True,
            is_active=True,
            date_joined=datetime.datetime(2007, 5, 30, 13, 20, 10, tzinfo=UTC),
        )

    def setUp(self):
        self.client.force_login(self.u1)

    @requires_tz_support
    def test_changelist(self):
        e = Event.objects.create(
            dt=datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC)
        )
        response = self.client.get(reverse("admin_tz:timezones_event_changelist"))
        self.assertContains(response, e.dt.astimezone(EAT).isoformat())

    def test_changelist_in_other_timezone(self):
        e = Event.objects.create(
            dt=datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC)
        )
        with timezone.override(ICT):
            response = self.client.get(reverse("admin_tz:timezones_event_changelist"))
        self.assertContains(response, e.dt.astimezone(ICT).isoformat())

    @requires_tz_support
    def test_change_editable(self):
        e = Event.objects.create(
            dt=datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC)
        )
        response = self.client.get(
            reverse("admin_tz:timezones_event_change", args=(e.pk,))
        )
        self.assertContains(response, e.dt.astimezone(EAT).date().isoformat())
        self.assertContains(response, e.dt.astimezone(EAT).time().isoformat())

    def test_change_editable_in_other_timezone(self):
        """
        Tests that an event's datetime is correctly displayed in the admin interface when the event's timezone differs from the current timezone.
        """
        e = Event.objects.create(
            dt=datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC)
        )
        with timezone.override(ICT):
            response = self.client.get(
                reverse("admin_tz:timezones_event_change", args=(e.pk,))
            )
        self.assertContains(response, e.dt.astimezone(ICT).date().isoformat())
        self.assertContains(response, e.dt.astimezone(ICT).time().isoformat())

    @requires_tz_support
    def test_change_readonly(self):
        t = Timestamp.objects.create()
        response = self.client.get(
            reverse("admin_tz:timezones_timestamp_change", args=(t.pk,))
        )
        self.assertContains(response, t.created.astimezone(EAT).isoformat())

    def test_change_readonly_in_other_timezone(self):
        t = Timestamp.objects.create()
        with timezone.override(ICT):
            response = self.client.get(
                reverse("admin_tz:timezones_timestamp_change", args=(t.pk,))
            )
        self.assertContains(response, t.created.astimezone(ICT).isoformat())
