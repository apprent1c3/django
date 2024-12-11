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
        """

        Tests the storage and retrieval of a naive datetime object with microseconds.

        This test case verifies that a datetime object with microseconds is correctly
        stored in the database and retrieved without losing any precision.

        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, 405060)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    @skipUnlessDBFeature("supports_timezones")
    def test_aware_datetime_in_local_timezone(self):
        """
        Tests the handling of an aware datetime object in the local timezone.

        The test creates an Event object with a datetime in the Eastern African Time (EAT) timezone, 
        then retrieves the object and checks that the timezone information is lost, 
        but the datetime remains the same when the original timezone is reapplied.
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
        Tests that an aware datetime object in the local timezone, including microseconds, 
        is properly stored and retrieved from the database.

        This test ensures that when a datetime object with a timezone and microseconds is 
        saved to the database, the resulting datetime object retrieved from the database 
        has its timezone information removed, but the date and time values, including 
        microseconds, are preserved and match the original value when the timezone is reapplied.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, 405060, tzinfo=EAT)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertIsNone(event.dt.tzinfo)
        # interpret the naive datetime in local time to get the correct value
        self.assertEqual(event.dt.replace(tzinfo=EAT), dt)

    @skipUnlessDBFeature("supports_timezones")
    def test_aware_datetime_in_utc(self):
        dt = datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertIsNone(event.dt.tzinfo)
        # interpret the naive datetime in local time to get the correct value
        self.assertEqual(event.dt.replace(tzinfo=EAT), dt)

    @skipUnlessDBFeature("supports_timezones")
    def test_aware_datetime_in_other_timezone(self):
        """

        Tests creation and retrieval of an event with an aware datetime object 
        in a non-default timezone. Verifies that the timezone information is 
        lost when retrieving the event, and that it can be correctly recreated 
        by setting the desired timezone.

        Checks the following conditions:
        - An aware datetime object with a specific timezone can be used 
          when creating an event.
        - The timezone information is not preserved when the event is 
          retrieved from the database.
        - The original datetime value can be recreated by applying the 
          original timezone to the retrieved datetime value. 

        """
        dt = datetime.datetime(2011, 9, 1, 17, 20, 30, tzinfo=ICT)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertIsNone(event.dt.tzinfo)
        # interpret the naive datetime in local time to get the correct value
        self.assertEqual(event.dt.replace(tzinfo=EAT), dt)

    @skipIfDBFeature("supports_timezones")
    def test_aware_datetime_unsupported(self):
        """
        Tests the behavior of creating an event with an aware datetime when the database backend does not support timezone-aware datetimes and USE_TZ is False.

        Verifies that a ValueError is raised with a descriptive message when attempting to create an event with a datetime object that includes timezone information, indicating that the operation is not supported by the underlying database backend.

        The test ensures that the application correctly handles and reports this limitation, providing a clear error message to the user rather than producing unexpected behavior or errors.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)
        msg = "backend does not support timezone-aware datetimes when USE_TZ is False."
        with self.assertRaisesMessage(ValueError, msg):
            Event.objects.create(dt=dt)

    def test_auto_now_and_auto_now_add(self):
        """
        Tests the automatic updating of 'created' and 'updated' timestamps.

        This test case verifies that when a new Timestamp object is created, 
        its 'created' and 'updated' timestamps are automatically set to the current time. 
        It also checks that the 'updated' timestamp is within a reasonable time range, 
        ensuring it is neither in the past nor too far in the future (i.e., within 2 seconds of the current time).
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

        Tests the filtering functionality of Event objects based on the 'dt' datetime field.

        Verifies that the filter operations greater than or equal to (__gte), and greater than (__gt) 
        work as expected by checking the count of filtered objects.

        The test covers the following scenarios:
        - Filtering events that occur on or after a specific datetime.
        - Filtering events that occur strictly after a specific datetime.

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
        Tests the aggregation of Event objects by querying the minimum and maximum datetime values.

         This test case creates multiple Event objects with different datetime values and then uses the aggregate function to calculate the minimum and maximum datetime values. It verifies that the result matches the expected output, ensuring that the aggregation query works correctly.
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

        Tests the usage of Django's query annotation to calculate the minimum datetime for a session.

        Checks that sessions can be annotated with the earliest datetime from their associated events, 
        and then ordered by this annotated value, or filtered based on it.

        Verifies three cases:
        - All sessions are ordered by their earliest event datetime.
        - Sessions with an earliest event before a certain datetime are correctly filtered.
        - Sessions with an earliest event at or after a certain datetime are correctly filtered.

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
        Tests the cursor's execute method to ensure it correctly handles naive datetime objects when inserting into a database table. 

        The test verifies that a naive datetime object can be successfully stored in the database and retrieved without any modification, confirming that the database interaction layer properly supports the use of naive datetimes.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30)
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO timezones_event (dt) VALUES (%s)", [dt])
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    def test_cursor_execute_returns_naive_datetime(self):
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
        """
        Tests that creating a DailyEvent with a timezone-aware time raises a ValueError.

        This test verifies that an error is raised when attempting to create a DailyEvent
        with a time that includes timezone information, since the database backend does
        not support timezone-aware times.

        The test case creates a timezone-aware time object and attempts to use it to
        create a new DailyEvent. It then checks that the expected ValueError is raised,
        with the message indicating that the backend does not support timezone-aware times.
        """
        t = datetime.time(13, 20, 30, tzinfo=EAT)
        msg = "backend does not support timezone-aware times."
        with self.assertRaisesMessage(ValueError, msg):
            DailyEvent.objects.create(time=t)

    @requires_tz_support
    def test_naive_datetime(self):
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30)
        with self.assertWarnsMessage(RuntimeWarning, self.naive_warning):
            Event.objects.create(dt=dt)
        event = Event.objects.get()
        # naive datetimes are interpreted in local time
        self.assertEqual(event.dt, dt.replace(tzinfo=EAT))

    @requires_tz_support
    def test_datetime_from_date(self):
        """
        Tests the creation of an Event object with a naive date object.

        This test case checks that when a date object without timezone information is used
        to create an Event, a warning is raised and the date is converted to a datetime
        object with the default timezone.

        It verifies that the created Event object has a datetime attribute with the correct
        date and timezone information. 

        :raises: RuntimeWarning if the date object is naive (i.e., it does not contain
            timezone information)
        :returns: None
        """
        dt = datetime.date(2011, 9, 1)
        with self.assertWarnsMessage(RuntimeWarning, self.naive_warning):
            Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertEqual(event.dt, datetime.datetime(2011, 9, 1, tzinfo=EAT))

    @requires_tz_support
    def test_filter_unbound_datetime_with_naive_date(self):
        """
        Tests the filtering of unbound datetime fields in a Django query where the date is naive (i.e., without timezone information) and verifies that a RuntimeWarning is raised with an appropriate message when attempting to filter an unbound datetime field with a naive date.
        """
        dt = datetime.date(2011, 9, 1)
        msg = "DateTimeField (unbound) received a naive datetime"
        with self.assertWarnsMessage(RuntimeWarning, msg):
            Event.objects.annotate(unbound_datetime=Now()).filter(unbound_datetime=dt)

    @requires_tz_support
    def test_naive_datetime_with_microsecond(self):
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, 405060)
        with self.assertWarnsMessage(RuntimeWarning, self.naive_warning):
            Event.objects.create(dt=dt)
        event = Event.objects.get()
        # naive datetimes are interpreted in local time
        self.assertEqual(event.dt, dt.replace(tzinfo=EAT))

    def test_aware_datetime_in_local_timezone(self):
        """
        Checks if a datetime object created in a specific timezone is correctly stored and retrieved from the database, ensuring that the timezone information is preserved. The test uses the Eastern Africa Time (EAT) timezone to verify that datetime objects are properly converted between the local timezone and the database.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    def test_aware_datetime_in_local_timezone_with_microsecond(self):
        """
        Tests the ability to store a datetime object with microseconds in a local timezone. 
        Verifies that the datetime is stored and retrieved correctly without losing its original timezone or microsecond precision.
        """
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, 405060, tzinfo=EAT)
        Event.objects.create(dt=dt)
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    def test_aware_datetime_in_utc(self):
        """
        Tests that a datetime object aware of its timezone (UTC) can be correctly stored and retrieved from the database.

        This test checks that the datetime object is created with the correct timezone information and that it is preserved when the object is saved to and retrieved from the database.

        The test covers the following:

        * Creating a datetime object in UTC timezone
        * Saving this datetime object to the database as part of an Event object
        * Retrieving the Event object from the database
        * Verifying that the datetime object retrieved from the database matches the original datetime object

        By ensuring that datetime objects with timezone information are handled correctly, this test helps prevent potential issues with date and time calculations across different timezones.
        """
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

        Tests the filtering of events based on a datetime query.

        This test case verifies that the filter method on the Event model correctly
        returns events that match a specific datetime range. It checks the behavior of 
        the `__gte` (greater than or equal to) and `__gt` (greater than) lookup types 
        to ensure that events are properly filtered based on their datetime attributes.

        The test includes checks for events that occur at or after a given time, as well 
        as events that occur strictly after a given time, to ensure that the filter 
        method behaves as expected in both cases.

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

        Tests the filtering of events based on timezone-aware datetime objects.

        Ensures that events can be correctly filtered using exact dates, 
        date ranges, and inclusions with timezone considerations.
        Verifies that filter operations, including exact, in, and range lookups,
        function as expected when dealing with timezone-aware datetime objects.

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

        Tests the conversion of datetimes across different timezones.

        This test ensures that events are correctly filtered by date regardless of the 
        timezone in which the database connection is operating. Specifically, it checks 
        that the date component of an event's datetime is correctly interpreted when 
        the database connection is set to different timezones.

        The test creates events with specific datetimes in different timezones and then 
        queries the database to verify that the events are correctly retrieved based 
        on their date. It covers scenarios where the event's date falls on a different 
        date in the database connection's timezone due to the timezone offset.

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

        Tests the filtering of Events by datetime, specifically when using a naive datetime object (i.e., one without timezone information).

        This test creates an Event with a datetime in the EAT (East Africa Time) timezone, then filters Events using a naive datetime object. It checks that the expected number of Events are returned, and that a warning is raised to indicate that the naive datetime object may lead to incorrect results due to timezone ambiguity.

        The test covers exact, less-than-or-equal-to, and greater-than filters to ensure that the warning is raised and the correct results are returned in each case.

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
        Tests the query annotation functionality on Session objects.

         This test creates test data consisting of morning and afternoon sessions, 
         each with associated session events. It then verifies that:

         * The sessions are correctly annotated with the minimum datetime of their associated events,
           and that they can be ordered by this datetime.
         * Sessions can be filtered by the annotated datetime, 
           allowing for retrieval of sessions with events before or after a certain point in time.
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
        Tests that querying datetimes in a different timezone returns the expected results.

            This test creates two events with datetimes in the Eastern African Time (EAT) timezone.
            It then overrides the timezone to UTC and queries the events for their datetimes.
            The test checks that the returned datetimes are in the UTC timezone and correspond to the correct year, month, day, hour, minute, and second.
            The test ensures that the datetime values are correctly converted from EAT to UTC.
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
        """
        Tests that raw SQL queries on the Event model return the expected results.

        This test case checks the functionality of executing raw SQL queries on the Event model,
        specifically when querying for events by date and time. It verifies that the results
        from the raw SQL query match the expected event instances, ensuring consistency between
        the Django ORM and raw SQL queries.

        The test creates an event instance with a specific date and time, and then uses a raw SQL
        query to retrieve events with the same date and time. The results are compared to the
        original event instance to confirm that the raw SQL query returns the expected data.
        """
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
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO timezones_event (dt) VALUES (%s)", [dt])
        event = Event.objects.get()
        self.assertEqual(event.dt, dt)

    @skipIfDBFeature("supports_timezones")
    def test_cursor_execute_accepts_naive_datetime(self):
        """
        Parameters
        ----------
        None

        Returns
        -------
        None

        Description
        -----------
        Tests whether the cursor's execute method can handle naive datetime objects.

        This test checks if a naive datetime object (a datetime object without timezone information) 
        can be inserted into a database table and if the resulting date remains consistent with the original date 
        when retrieved. It specifically verifies that the timezone information is preserved during this process.

        Note
        ----
        This test is skipped if the database being used supports timezones.
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
        dt = datetime.datetime(2011, 9, 1, 13, 20, 30, tzinfo=EAT)
        Event.objects.create(dt=dt)
        with connection.cursor() as cursor:
            cursor.execute("SELECT dt FROM timezones_event WHERE dt = %s", [dt])
            self.assertEqual(cursor.fetchall()[0][0], dt)

    @skipIfDBFeature("supports_timezones")
    def test_cursor_execute_returns_naive_datetime(self):
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
        Tests if a database cursor correctly handles explicit time zones.

        This test case verifies that when the database connection time zone is overridden,
        the cursor's execution of a SQL query to retrieve the current timestamp correctly
        accounts for the specified time zone. The test checks if the time zone of the
        retrieved timestamp is set to the expected value. This ensures that the database
        cursor is properly handling time zone conversions when executing queries with
        an explicitly specified time zone.

        The test specifically checks the time zone 'Europe/Paris' to ensure that the
        cursor correctly handles this time zone when it is explicitly set for the
        database connection.

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
        """

        Tests that a newly created MaybeEvent instance has a null datetime (dt) value.

        This test case verifies the default state of a MaybeEvent object's datetime attribute
        after creation, ensuring it is appropriately initialized as null.

        """
        e = MaybeEvent.objects.create()
        self.assertIsNone(e.dt)

    def test_update_with_timedelta(self):
        """
        Tests the update of an Event's datetime attribute using a timedelta.

        Verifies that an Event's datetime can be successfully updated by adding a 
        specified time interval. The test creates an Event with the current datetime, 
        then updates the datetime by adding a two-hour interval. It checks if the 
        updated datetime matches the expected result, ensuring the update operation 
        was performed correctly.

        This test case covers the functionality of updating Event datetimes with 
        relative time intervals, which is useful for scheduling and time-based 
        operations.

        Returns:
            None

        Raises:
            AssertionError: If the updated datetime does not match the expected result.

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
        if connection.features.supports_timezones:
            raise SkipTest("Database has feature(s) supports_timezones")
        if not connection.features.test_db_allows_multiple_connections:
            raise SkipTest(
                "Database doesn't support feature(s): "
                "test_db_allows_multiple_connections"
            )

        super().setUpClass()

    def test_read_datetime(self):
        fake_dt = datetime.datetime(2011, 9, 1, 17, 20, 30, tzinfo=UTC)
        Event.objects.create(dt=fake_dt)

        with override_database_connection_timezone("Asia/Bangkok"):
            event = Event.objects.get()
            dt = datetime.datetime(2011, 9, 1, 10, 20, 30, tzinfo=UTC)
        self.assertEqual(event.dt, dt)

    def test_write_datetime(self):
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
        Tests serialization and deserialization of datetime objects through different serializers.

        This test case checks the correct handling of datetime objects when serializing and deserializing data using various formats such as python, json, xml, and yaml. It verifies that the original datetime object is correctly converted to the respective format and that it can be successfully deserialized back to its original form, ensuring data integrity and accuracy throughout the serialization and deserialization process.
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

        Tests the serialization and deserialization of datetime objects with microseconds using different formats.

        This test ensures that datetime objects can be correctly serialized to and deserialized from different formats, 
        including Python, JSON, XML, and YAML. It verifies that the datetime information, including microseconds, 
        is preserved throughout the serialization and deserialization process.

        The test covers the following scenarios:
        - Serialization and deserialization of datetime objects with microseconds using the Python format.
        - Serialization and deserialization of datetime objects with microseconds using the JSON format, 
          which has a precision limit of milliseconds.
        - Serialization and deserialization of datetime objects with microseconds using the XML format.
        - Serialization and deserialization of datetime objects with microseconds using the YAML format, 
          if the YAML serializer is available.

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
        Tests the serialization and deserialization of datetime objects with microseconds across various formats.

        This test case verifies that datetime objects with microseconds are correctly serialized and deserialized using different formats, including Python, JSON, XML, and YAML. It ensures that the datetime object is preserved with its original value and timezone information after the serialization and deserialization process.

        The test covers various scenarios, including the handling of microseconds in different formats and the impact of YAML version on the deserialization result. The test assertions verify that the original datetime object is correctly reconstructed after deserialization, with considerations for potential limitations in certain formats or library versions.
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
        Tests the serialization and deserialization of aware datetime objects in UTC.

        Ensure that datetimes are correctly converted to and from different serialization formats,
        including Python's native serialization, JSON, XML, and YAML. 

        Verifies that the original datetime is preserved after serialization and deserialization,
        regardless of the chosen format.

        Also checks the correctness of the datetime representation in each of the serialized formats,
        such as '2011-09-01T10:20:30Z' for JSON, '2011-09-01T10:20:30+00:00' for XML, and 
        '2011-09-01 10:20:30+00:00' for YAML.

        Skips YAML tests if the YAML serializer is not available.
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

        Tests the serialization and deserialization of datetime objects in the local timezone.

        This test case ensures that datetime objects with timezone information are correctly
        serialized and deserialized using different serialization formats (python, json, xml, yaml).
        It verifies that the datetime object remains intact across the serialization and deserialization
        process, including its timezone information.

        The test checks both the serialization output and the deserialized object to ensure
        that the datetime information is preserved and accurate.

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
        Tests the serialization and deserialization of datetime objects in different timezones across various formats.

        Verifies that datetime objects are correctly preserved when serialized to and deserialized from python, json, xml, and yaml formats, 
        regardless of the original timezone. The test checks that the resulting deserialized object matches the original datetime object, 
        accounting for any timezone conversions that may occur during the process.
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
        Test the {% localtime %} templatetag and related filters.
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
        Test the |localtime, |utc, and |timezone filters with iana zones.
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
        """

        Tests that the localtime templatetag raises a TemplateSyntaxError when passed an invalid argument.

        The localtime templatetag is expected to take a valid datetime object as an argument, 
        but in this test case, an invalid argument 'foo' is passed to verify that the 
        templatetag correctly handles invalid input and raises an exception as expected.

        """
        with self.assertRaises(TemplateSyntaxError):
            Template("{% load tz %}{% localtime foo %}{% endlocaltime %}").render()

    def test_localtime_filters_do_not_raise_exceptions(self):
        """
        Test the |localtime, |utc, and |timezone filters on bad inputs.
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
        Test the {% timezone %} templatetag with IANA time zone providers.
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
        Test the {% get_current_timezone %} templatetag.
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
        Tests the functionality of the get_current_timezone template tag.

        Verifies that the tag correctly retrieves the current timezone, both when 
        the timezone is set globally and when it is overridden within a template 
        block. Ensures that the retrieved timezone matches the expected value 
        in both cases, demonstrating the tag's ability to adapt to different 
        timezone contexts.

        The test covers two primary scenarios:

        * When the timezone is overridden globally, the tag should return the 
          globally set timezone.
        * When the timezone is overridden within a template block, the tag 
          should return the timezone set within that block.

        By verifying the tag's behavior in these scenarios, this test ensures 
        that the get_current_timezone template tag functions as expected, 
        providing accurate and contextually correct timezone information.
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
        """

        Tests that the 'get_current_timezone' template tag raises a TemplateSyntaxError
        when used without the required 'as variable' argument.

        This test case verifies that the template tag correctly enforces its usage,
        preventing invalid syntax and ensuring that the tag is used consistently
        with the expected 'as variable' format.

        """
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
        tpl = Template("{{ dt|date:'Y-m-d' }} at {{ dt|time:'H:i:s' }}")
        ctx = Context({"dt": datetime.datetime(2011, 9, 1, 20, 20, 20, tzinfo=UTC)})
        self.assertEqual(tpl.render(ctx), "2011-09-01 at 23:20:20")
        with timezone.override(ICT):
            self.assertEqual(tpl.render(ctx), "2011-09-02 at 03:20:20")

    def test_date_and_time_template_filters_honor_localtime(self):
        """

        Tests whether the date and time template filters correctly honor the localtime setting.

        This test case verifies that when the localtime setting is turned off, the date and time filters
        will display the datetime object in the UTC timezone, regardless of the current timezone.

        The test uses a datetime object with a specific date and time, and checks that the rendered template
        produces the expected output both with and without overriding the timezone to ICT.

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
        """

        Tests the 'now' template tag to ensure it utilizes the current time zone.

        The function verifies that the 'now' template tag renders the correct time zone offset
        in two different scenarios: the default time zone and a overridden time zone. The test
        checks for the expected output in both cases, ensuring the template tag accurately
        reflects the current time zone.

        Args:
            None

        Returns:
            None

        """
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
        Tests the validation of an EventForm when the input time is ambiguous due to daylight saving time (DST) transition.

        The test case simulates the submission of a form with a date and time that could fall within a DST transition period.
        It verifies that the form is valid and that the cleaned data is correctly parsed into a datetime object, taking into account the specified time zone.

        The test is performed within a specific time zone (Europe/Paris) to ensure consistent results. The expected outcome is that the form is validated successfully and the datetime object is correctly created, with the correct time and date components.
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
        """
        Tests the splitting of a form into a single datetime object.

        Verifies that a form with separate date and time fields can be successfully validated
        and that the cleaned data results in a datetime object with the correct date and time.

        This test case covers the scenario where the form is initialized with a valid date and time,
        and checks that the resulting datetime object is correctly assembled from the form data.
        """
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

        Tests an event form submission with an ambiguous time.

        The function attempts to validate an EventForm with a specific date and time ('2011-10-30 02:30:00') 
        in the 'Europe/Paris' time zone, where the given time is ambiguous due to daylight saving time (DST) transition.
        It verifies that the form is invalid and that the expected error message is returned, indicating that the time
        could not be interpreted in the given time zone due to ambiguity or non-existence.

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
        """

        Tests the rendering of a localized model form.

        This test case verifies that the EventLocalizedModelForm correctly handles timezone-aware datetime fields.
        It creates an instance of the form with a specific datetime value in the EAT timezone, then overrides the 
        timezone to ICT and checks that the rendered form contains the expected datetime string in the 
        correct timezone. This ensures that the form properly localizes the datetime value to the current timezone.

        :raises AssertionError: If the rendered form does not contain the expected datetime string.

        """
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
        """

        Tests the change view for an editable event in the admin interface.

        Verifies that the event's date and time are correctly displayed in the target timezone.
        The test covers the case where the event's datetime is stored in UTC and needs to be
        converted to the target timezone (EAT) for display in the change view.

        The test creates an event with a specific datetime, retrieves the change view for that
        event, and checks that the response contains the expected date and time in the target
        timezone, formatted as ISO strings.

        """
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
        /tests of the admin interface for editing an event's datetime/
        Tests whether the datetime of an event is correctly displayed for editing in a timezone other than the event's original timezone.

        The test creates an event at a specific datetime in the UTC timezone, switches to the ICT timezone, and then checks the admin interface for editing the event.
        It verifies that the date and time of the event are displayed in the ICT timezone, ensuring that the datetime is correctly converted and formatted for the current timezone.
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
        """

        Tests the change view for a readonly Timestamp object, verifying that the created timestamp is displayed in the correct timezone.

        This test case creates a new Timestamp object, then retrieves the change view for that object via the admin interface.
        It checks that the created timestamp is correctly converted to the specified timezone (EAT) and displayed in ISO format.

        """
        t = Timestamp.objects.create()
        response = self.client.get(
            reverse("admin_tz:timezones_timestamp_change", args=(t.pk,))
        )
        self.assertContains(response, t.created.astimezone(EAT).isoformat())

    def test_change_readonly_in_other_timezone(self):
        """

        Tests whether the 'created' timestamp of a Timestamp object is correctly 
        displayed in a different timezone (ICT) when editing the object in the admin interface.

        The test case verifies that the timestamp is converted to the ICT timezone and 
        rendered in the ISO 8601 format, ensuring proper timezone handling.

        """
        t = Timestamp.objects.create()
        with timezone.override(ICT):
            response = self.client.get(
                reverse("admin_tz:timezones_timestamp_change", args=(t.pk,))
            )
        self.assertContains(response, t.created.astimezone(ICT).isoformat())
