import zoneinfo
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone

from django.conf import settings
from django.db import DataError, OperationalError
from django.db.models import (
    DateField,
    DateTimeField,
    F,
    IntegerField,
    Max,
    OuterRef,
    Subquery,
    TimeField,
)
from django.db.models.functions import (
    Extract,
    ExtractDay,
    ExtractHour,
    ExtractIsoWeekDay,
    ExtractIsoYear,
    ExtractMinute,
    ExtractMonth,
    ExtractQuarter,
    ExtractSecond,
    ExtractWeek,
    ExtractWeekDay,
    ExtractYear,
    Trunc,
    TruncDate,
    TruncDay,
    TruncHour,
    TruncMinute,
    TruncMonth,
    TruncQuarter,
    TruncSecond,
    TruncTime,
    TruncWeek,
    TruncYear,
)
from django.test import (
    TestCase,
    override_settings,
    skipIfDBFeature,
    skipUnlessDBFeature,
)
from django.utils import timezone

from ..models import Author, DTModel, Fan


def truncate_to(value, kind, tzinfo=None):
    # Convert to target timezone before truncation
    """
    Truncates a date or datetime value to the specified precision.

    The function accepts a date or datetime object and truncates it to the specified kind, which can be one of the following:
        * second: Truncates to the nearest second, removing microseconds.
        * minute: Truncates to the nearest minute, removing seconds and microseconds.
        * hour: Truncates to the nearest hour, removing minutes, seconds, and microseconds.
        * day: Truncates to the start of the day, removing hours, minutes, seconds, and microseconds.
        * week: Truncates to the start of the week, removing days, hours, minutes, seconds, and microseconds.
        * month: Truncates to the start of the month, removing days, hours, minutes, seconds, and microseconds.
        * quarter: Truncates to the start of the quarter, removing months, days, hours, minutes, seconds, and microseconds.

    The function also accepts an optional timezone object. If provided, it will convert the input value to the specified timezone before truncation. The output value will also be in the specified timezone.

    Returns the truncated date or datetime value.
    """
    if tzinfo is not None:
        value = value.astimezone(tzinfo)

    def truncate(value, kind):
        """
        Truncates a datetime value to a specified level of precision.

        The function takes two parameters: the datetime value to truncate and the level of precision. The precision level can be one of 'second', 'minute', 'hour', 'day', 'week', 'month', 'quarter', or 'year'. The function returns a new datetime object with the specified level of precision, where all lower-level components are set to zero.

        For example, truncating a datetime to the 'day' level will set the hour, minute, second, and microsecond components to zero. Truncating to the 'week' level will set the day of the week to Monday (i.e., the first day of the week) and the time components to zero.

        This function can be used to perform aggregation operations, such as grouping data by time period, or to simplify datetime values for display or comparison purposes.

        Parameters:
            value (datetime): The datetime value to truncate.
            kind (str): The level of precision, one of 'second', 'minute', 'hour', 'day', 'week', 'month', 'quarter', or 'year'.

        Returns:
            datetime: The truncated datetime value.
        """
        if kind == "second":
            return value.replace(microsecond=0)
        if kind == "minute":
            return value.replace(second=0, microsecond=0)
        if kind == "hour":
            return value.replace(minute=0, second=0, microsecond=0)
        if kind == "day":
            if isinstance(value, datetime):
                return value.replace(hour=0, minute=0, second=0, microsecond=0)
            return value
        if kind == "week":
            if isinstance(value, datetime):
                return (value - timedelta(days=value.weekday())).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            return value - timedelta(days=value.weekday())
        if kind == "month":
            if isinstance(value, datetime):
                return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return value.replace(day=1)
        if kind == "quarter":
            month_in_quarter = value.month - (value.month - 1) % 3
            if isinstance(value, datetime):
                return value.replace(
                    month=month_in_quarter,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            return value.replace(month=month_in_quarter, day=1)
        # otherwise, truncate to year
        if isinstance(value, datetime):
            return value.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
        return value.replace(month=1, day=1)

    value = truncate(value, kind)
    if tzinfo is not None:
        # If there was a daylight saving transition, then reset the timezone.
        value = timezone.make_aware(value.replace(tzinfo=None), tzinfo)
    return value


@override_settings(USE_TZ=False)
class DateFunctionTests(TestCase):
    def create_model(self, start_datetime, end_datetime):
        return DTModel.objects.create(
            name=start_datetime.isoformat() if start_datetime else "None",
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            start_date=start_datetime.date() if start_datetime else None,
            end_date=end_datetime.date() if end_datetime else None,
            start_time=start_datetime.time() if start_datetime else None,
            end_time=end_datetime.time() if end_datetime else None,
            duration=(
                (end_datetime - start_datetime)
                if start_datetime and end_datetime
                else None
            ),
        )

    def test_extract_year_exact_lookup(self):
        """
        Extract year uses a BETWEEN filter to compare the year to allow indexes
        to be used.
        """
        start_datetime = datetime(2015, 6, 15, 14, 10)
        end_datetime = datetime(2016, 6, 15, 14, 10)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)

        for lookup in ("year", "iso_year"):
            with self.subTest(lookup):
                qs = DTModel.objects.filter(
                    **{"start_datetime__%s__exact" % lookup: 2015}
                )
                self.assertEqual(qs.count(), 1)
                query_string = str(qs.query).lower()
                self.assertEqual(query_string.count(" between "), 1)
                self.assertEqual(query_string.count("extract"), 0)
                # exact is implied and should be the same
                qs = DTModel.objects.filter(**{"start_datetime__%s" % lookup: 2015})
                self.assertEqual(qs.count(), 1)
                query_string = str(qs.query).lower()
                self.assertEqual(query_string.count(" between "), 1)
                self.assertEqual(query_string.count("extract"), 0)
                # date and datetime fields should behave the same
                qs = DTModel.objects.filter(**{"start_date__%s" % lookup: 2015})
                self.assertEqual(qs.count(), 1)
                query_string = str(qs.query).lower()
                self.assertEqual(query_string.count(" between "), 1)
                self.assertEqual(query_string.count("extract"), 0)
                # an expression rhs cannot use the between optimization.
                qs = DTModel.objects.annotate(
                    start_year=ExtractYear("start_datetime"),
                ).filter(end_datetime__year=F("start_year") + 1)
                self.assertEqual(qs.count(), 1)
                query_string = str(qs.query).lower()
                self.assertEqual(query_string.count(" between "), 0)
                self.assertEqual(query_string.count("extract"), 3)

    def test_extract_year_greaterthan_lookup(self):
        """

        Tests date-time field lookups with year extraction.

        This test case checks the correct functioning of year and iso_year lookups
        for datetime fields in the database. It covers greater than and greater than
        or equal to comparisons, as well as annotated queries that reference the
        extracted year. The test ensures that the expected number of results are
        returned and that the SQL query uses the extract function as required.

        """
        start_datetime = datetime(2015, 6, 15, 14, 10)
        end_datetime = datetime(2016, 6, 15, 14, 10)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)

        for lookup in ("year", "iso_year"):
            with self.subTest(lookup):
                qs = DTModel.objects.filter(**{"start_datetime__%s__gt" % lookup: 2015})
                self.assertEqual(qs.count(), 1)
                self.assertEqual(str(qs.query).lower().count("extract"), 0)
                qs = DTModel.objects.filter(
                    **{"start_datetime__%s__gte" % lookup: 2015}
                )
                self.assertEqual(qs.count(), 2)
                self.assertEqual(str(qs.query).lower().count("extract"), 0)
                qs = DTModel.objects.annotate(
                    start_year=ExtractYear("start_datetime"),
                ).filter(**{"end_datetime__%s__gte" % lookup: F("start_year")})
                self.assertEqual(qs.count(), 1)
                self.assertGreaterEqual(str(qs.query).lower().count("extract"), 2)

    def test_extract_year_lessthan_lookup(self):
        start_datetime = datetime(2015, 6, 15, 14, 10)
        end_datetime = datetime(2016, 6, 15, 14, 10)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)

        for lookup in ("year", "iso_year"):
            with self.subTest(lookup):
                qs = DTModel.objects.filter(**{"start_datetime__%s__lt" % lookup: 2016})
                self.assertEqual(qs.count(), 1)
                self.assertEqual(str(qs.query).count("extract"), 0)
                qs = DTModel.objects.filter(
                    **{"start_datetime__%s__lte" % lookup: 2016}
                )
                self.assertEqual(qs.count(), 2)
                self.assertEqual(str(qs.query).count("extract"), 0)
                qs = DTModel.objects.annotate(
                    end_year=ExtractYear("end_datetime"),
                ).filter(**{"start_datetime__%s__lte" % lookup: F("end_year")})
                self.assertEqual(qs.count(), 1)
                self.assertGreaterEqual(str(qs.query).lower().count("extract"), 2)

    def test_extract_lookup_name_sql_injection(self):
        """

        Tests the resistance of the Extract 'lookup_name' SQL lookup to SQL injection attacks.

        This test case attempts to inject malicious SQL code through the Extract lookup,
        which is expected to raise either an OperationalError or a ValueError.

        The test creates model instances with different datetime ranges and then tries
        to filter the instances using an Extract lookup with a malicious SQL injection string.
        The test passes if the database raises an error when executing the malicious query.

        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)

        with self.assertRaises((OperationalError, ValueError)):
            DTModel.objects.filter(
                start_datetime__year=Extract(
                    "start_datetime", "day' FROM start_datetime)) OR 1=1;--"
                )
            ).exists()

    def test_extract_func(self):
        """
        Tests the functionality of extracting date and time components from datetime fields using the Extract function.

        This test case includes checks for:

        * Input validation: verifies that the Extract function raises ValueErrors when given invalid input, such as a missing lookup name or an unsupported field type.
        * Extraction of various date and time components: tests the extraction of year, quarter, month, day, week, week day, iso week day, hour, minute, and second components from datetime fields.
        * Ordering and filtering: verifies that the extracted components can be used for ordering and filtering querysets.

        These tests ensure that the Extract function behaves correctly and provides the expected results for different input scenarios and use cases.
        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)

        with self.assertRaisesMessage(ValueError, "lookup_name must be provided"):
            Extract("start_datetime")

        msg = (
            "Extract input expression must be DateField, DateTimeField, TimeField, or "
            "DurationField."
        )
        with self.assertRaisesMessage(ValueError, msg):
            list(DTModel.objects.annotate(extracted=Extract("name", "hour")))

        with self.assertRaisesMessage(
            ValueError,
            "Cannot extract time component 'second' from DateField 'start_date'.",
        ):
            list(DTModel.objects.annotate(extracted=Extract("start_date", "second")))

        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=Extract("start_datetime", "year")
            ).order_by("start_datetime"),
            [(start_datetime, start_datetime.year), (end_datetime, end_datetime.year)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=Extract("start_datetime", "quarter")
            ).order_by("start_datetime"),
            [(start_datetime, 2), (end_datetime, 2)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=Extract("start_datetime", "month")
            ).order_by("start_datetime"),
            [
                (start_datetime, start_datetime.month),
                (end_datetime, end_datetime.month),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=Extract("start_datetime", "day")
            ).order_by("start_datetime"),
            [(start_datetime, start_datetime.day), (end_datetime, end_datetime.day)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=Extract("start_datetime", "week")
            ).order_by("start_datetime"),
            [(start_datetime, 25), (end_datetime, 24)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=Extract("start_datetime", "week_day")
            ).order_by("start_datetime"),
            [
                (start_datetime, (start_datetime.isoweekday() % 7) + 1),
                (end_datetime, (end_datetime.isoweekday() % 7) + 1),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=Extract("start_datetime", "iso_week_day"),
            ).order_by("start_datetime"),
            [
                (start_datetime, start_datetime.isoweekday()),
                (end_datetime, end_datetime.isoweekday()),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=Extract("start_datetime", "hour")
            ).order_by("start_datetime"),
            [(start_datetime, start_datetime.hour), (end_datetime, end_datetime.hour)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=Extract("start_datetime", "minute")
            ).order_by("start_datetime"),
            [
                (start_datetime, start_datetime.minute),
                (end_datetime, end_datetime.minute),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=Extract("start_datetime", "second")
            ).order_by("start_datetime"),
            [
                (start_datetime, start_datetime.second),
                (end_datetime, end_datetime.second),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__year=Extract("start_datetime", "year")
            ).count(),
            2,
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__hour=Extract("start_datetime", "hour")
            ).count(),
            2,
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_date__month=Extract("start_date", "month")
            ).count(),
            2,
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_time__hour=Extract("start_time", "hour")
            ).count(),
            2,
        )

    def test_extract_none(self):
        """
        Tests the extraction of datetime components when the field value is None.

        Verifies that annotating a queryset with datetime extraction functions 
        returns None when the field value is None, for various date and time fields 
        and components, such as year and hour. 

        Ensures that the extracted component is properly set to None in the 
        resulting objects, for different extraction scenarios.
        """
        self.create_model(None, None)
        for t in (
            Extract("start_datetime", "year"),
            Extract("start_date", "year"),
            Extract("start_time", "hour"),
        ):
            with self.subTest(t):
                self.assertIsNone(
                    DTModel.objects.annotate(extracted=t).first().extracted
                )

    def test_extract_outerref_validation(self):
        """

        Tests the validation of the Extract expression in OuterRef.

        Verifies that using an Extract expression with an inner query referencing an incorrect field type raises a ValueError.

        The validation checks that the input expression to Extract is one of the supported Django model field types, which are DateField, DateTimeField, TimeField, or DurationField.

        This test ensures that the query annotation correctly enforces the field type constraint when using OuterRef in conjunction with Extract.

        """
        inner_qs = DTModel.objects.filter(name=ExtractMonth(OuterRef("name")))
        msg = (
            "Extract input expression must be DateField, DateTimeField, "
            "TimeField, or DurationField."
        )
        with self.assertRaisesMessage(ValueError, msg):
            DTModel.objects.annotate(related_name=Subquery(inner_qs.values("name")[:1]))

    @skipUnlessDBFeature("has_native_duration_field")
    def test_extract_duration(self):
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=Extract("duration", "second")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, (end_datetime - start_datetime).seconds % 60),
                (end_datetime, (start_datetime - end_datetime).seconds % 60),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.annotate(
                duration_days=Extract("duration", "day"),
            )
            .filter(duration_days__gt=200)
            .count(),
            1,
        )

    @skipIfDBFeature("has_native_duration_field")
    def test_extract_duration_without_native_duration_field(self):
        """

        Tests the extraction of duration without native DurationField database support.

        Verifies that attempting to extract duration from a model instance raises a
        ValueError, as this operation requires native DurationField support in the
        underlying database.

        The test is skipped if the database has native DurationField support, as this
        would not raise the expected error.

        """
        msg = "Extract requires native DurationField database support."
        with self.assertRaisesMessage(ValueError, msg):
            list(DTModel.objects.annotate(extracted=Extract("duration", "second")))

    def test_extract_duration_unsupported_lookups(self):
        """
        Tests the Extract function on a DurationField with unsupported lookups.

        This test ensures that attempting to extract a component not supported by the 
        DurationField, such as year or month, raises a ValueError with a suitable error message.

        The test iterates over various unsupported lookup types, verifying that the expected 
        error is raised in each case, providing assurance that the Extract function behaves 
        correctly when used with a DurationField and invalid lookup parameters.
        """
        msg = "Cannot extract component '%s' from DurationField 'duration'."
        for lookup in (
            "year",
            "iso_year",
            "month",
            "week",
            "week_day",
            "iso_week_day",
            "quarter",
        ):
            with self.subTest(lookup):
                with self.assertRaisesMessage(ValueError, msg % lookup):
                    DTModel.objects.annotate(extracted=Extract("duration", lookup))

    def test_extract_year_func(self):
        """
        Tests the functionality of extracting the year from datetime fields.

        This test case creates model instances with different datetime values and then 
        verifies the correctness of extracting years from 'start_datetime' and 'start_date' 
        fields using Django's ExtractYear database function. It checks the extraction 
        in two ways: by annotating and ordering querysets, and by filtering objects 
        based on the extracted year. 

        The test also covers cases with timezone-aware datetime objects if the 
        'USE_TZ' setting is enabled.

        The goal is to ensure that the ExtractYear function works correctly in various 
        scenarios, providing a robust method for extracting years from datetime fields 
        in Django models.
        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractYear("start_datetime")).order_by(
                "start_datetime"
            ),
            [(start_datetime, start_datetime.year), (end_datetime, end_datetime.year)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractYear("start_date")).order_by(
                "start_datetime"
            ),
            [(start_datetime, start_datetime.year), (end_datetime, end_datetime.year)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__year=ExtractYear("start_datetime")
            ).count(),
            2,
        )

    def test_extract_iso_year_func(self):
        """

        Tests the extraction of the ISO year from datetime fields.

        Verifies that the ExtractIsoYear function correctly extracts the year from 
        datetime objects, both with and without timezone awareness.

        Checks the annotation of querysets with extracted years, as well as the 
        filtering of querysets based on extracted years. Also tests that the 
        extraction works correctly for both datetime and date fields.

        The test cases cover a range of scenarios, including extraction from 
        datetime objects with different years and orderings, to ensure the 
        functionality is correct and consistent. 

        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=ExtractIsoYear("start_datetime")
            ).order_by("start_datetime"),
            [(start_datetime, start_datetime.year), (end_datetime, end_datetime.year)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractIsoYear("start_date")).order_by(
                "start_datetime"
            ),
            [(start_datetime, start_datetime.year), (end_datetime, end_datetime.year)],
            lambda m: (m.start_datetime, m.extracted),
        )
        # Both dates are from the same week year.
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__iso_year=ExtractIsoYear("start_datetime")
            ).count(),
            2,
        )

    def test_extract_iso_year_func_boundaries(self):
        """
        Tests the functionality of extracting ISO year from datetime fields, specifically at the boundaries of years and across daylight saving time changes. 

        Verifies the correctness of the ExtractIsoYear annotation in Django ORM queries, ensuring it correctly handles dates near the end and beginning of the year, and provides the accurate ISO year for each date. 

        Also, checks the correct functionality of the iso_year lookup in database queries, including filtering for a specific ISO year, greater than, and less than or equal to, to ensure the expected results are returned in the correct order.
        """
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            end_datetime = timezone.make_aware(end_datetime)
        week_52_day_2014 = datetime(2014, 12, 27, 13, 0)  # Sunday
        week_1_day_2014_2015 = datetime(2014, 12, 31, 13, 0)  # Wednesday
        week_53_day_2015 = datetime(2015, 12, 31, 13, 0)  # Thursday
        if settings.USE_TZ:
            week_1_day_2014_2015 = timezone.make_aware(week_1_day_2014_2015)
            week_52_day_2014 = timezone.make_aware(week_52_day_2014)
            week_53_day_2015 = timezone.make_aware(week_53_day_2015)
        days = [week_52_day_2014, week_1_day_2014_2015, week_53_day_2015]
        obj_1_iso_2014 = self.create_model(week_52_day_2014, end_datetime)
        obj_1_iso_2015 = self.create_model(week_1_day_2014_2015, end_datetime)
        obj_2_iso_2015 = self.create_model(week_53_day_2015, end_datetime)
        qs = (
            DTModel.objects.filter(start_datetime__in=days)
            .annotate(
                extracted=ExtractIsoYear("start_datetime"),
            )
            .order_by("start_datetime")
        )
        self.assertQuerySetEqual(
            qs,
            [
                (week_52_day_2014, 2014),
                (week_1_day_2014_2015, 2015),
                (week_53_day_2015, 2015),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )

        qs = DTModel.objects.filter(
            start_datetime__iso_year=2015,
        ).order_by("start_datetime")
        self.assertSequenceEqual(qs, [obj_1_iso_2015, obj_2_iso_2015])
        qs = DTModel.objects.filter(
            start_datetime__iso_year__gt=2014,
        ).order_by("start_datetime")
        self.assertSequenceEqual(qs, [obj_1_iso_2015, obj_2_iso_2015])
        qs = DTModel.objects.filter(
            start_datetime__iso_year__lte=2014,
        ).order_by("start_datetime")
        self.assertSequenceEqual(qs, [obj_1_iso_2014])

    def test_extract_month_func(self):
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractMonth("start_datetime")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, start_datetime.month),
                (end_datetime, end_datetime.month),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractMonth("start_date")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, start_datetime.month),
                (end_datetime, end_datetime.month),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__month=ExtractMonth("start_datetime")
            ).count(),
            2,
        )

    def test_extract_day_func(self):
        """
        Tests the functionality of extracting the day from a datetime or date field in a model.

        The test creates two model instances with different start and end dates, 
        then checks that the ExtractDay function correctly extracts the day of the month 
        from both datetime and date fields, and that it can be used in queries to filter objects.
        The test also checks that the extraction works correctly regardless of whether time zones are in use.
        It verifies that the results are ordered correctly and that the expected number of objects are returned when filtered by day.
        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractDay("start_datetime")).order_by(
                "start_datetime"
            ),
            [(start_datetime, start_datetime.day), (end_datetime, end_datetime.day)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractDay("start_date")).order_by(
                "start_datetime"
            ),
            [(start_datetime, start_datetime.day), (end_datetime, end_datetime.day)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__day=ExtractDay("start_datetime")
            ).count(),
            2,
        )

    def test_extract_week_func(self):
        """

        Tests the extraction of the week from a datetime or date field.

        This test case verifies that the ExtractWeek function correctly extracts the week 
        number from a given date or datetime field. It creates two model instances with 
        different start dates, and then checks that the week number is correctly extracted 
        in various scenarios, including when the date is annotated with the extracted week 
        and when the start date is used with the week lookup.

        It also checks that the week extraction works correctly when the USE_TZ setting is 
        enabled and the dates are timezone-aware.

        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractWeek("start_datetime")).order_by(
                "start_datetime"
            ),
            [(start_datetime, 25), (end_datetime, 24)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractWeek("start_date")).order_by(
                "start_datetime"
            ),
            [(start_datetime, 25), (end_datetime, 24)],
            lambda m: (m.start_datetime, m.extracted),
        )
        # both dates are from the same week.
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__week=ExtractWeek("start_datetime")
            ).count(),
            2,
        )

    def test_extract_quarter_func(self):
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 8, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=ExtractQuarter("start_datetime")
            ).order_by("start_datetime"),
            [(start_datetime, 2), (end_datetime, 3)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractQuarter("start_date")).order_by(
                "start_datetime"
            ),
            [(start_datetime, 2), (end_datetime, 3)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__quarter=ExtractQuarter("start_datetime")
            ).count(),
            2,
        )

    def test_extract_quarter_func_boundaries(self):
        """
        Tests the extraction of quarter boundaries from datetime objects.

        This test case verifies that the ExtractQuarter function correctly identifies 
        the quarter of the year for given datetime objects, and that it works 
        correctly with both aware and naive datetime objects. It creates sample data 
        for the last quarter of 2014 and the first quarter of 2015, extracts the 
        quarter for each, and then checks that the results are as expected.

        The test coverage includes the following scenarios:
        - Extraction of quarter for datetime objects representing the start of a quarter
        - Extraction of quarter for datetime objects representing the end of a quarter

        It ensures that the ExtractQuarter function behaves correctly in a database 
        query context, where datetime objects may be annotated and ordered by their 
        start datetime values.
        """
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            end_datetime = timezone.make_aware(end_datetime)

        last_quarter_2014 = datetime(2014, 12, 31, 13, 0)
        first_quarter_2015 = datetime(2015, 1, 1, 13, 0)
        if settings.USE_TZ:
            last_quarter_2014 = timezone.make_aware(last_quarter_2014)
            first_quarter_2015 = timezone.make_aware(first_quarter_2015)
        dates = [last_quarter_2014, first_quarter_2015]
        self.create_model(last_quarter_2014, end_datetime)
        self.create_model(first_quarter_2015, end_datetime)
        qs = (
            DTModel.objects.filter(start_datetime__in=dates)
            .annotate(
                extracted=ExtractQuarter("start_datetime"),
            )
            .order_by("start_datetime")
        )
        self.assertQuerySetEqual(
            qs,
            [
                (last_quarter_2014, 4),
                (first_quarter_2015, 1),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )

    def test_extract_week_func_boundaries(self):
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            end_datetime = timezone.make_aware(end_datetime)

        week_52_day_2014 = datetime(2014, 12, 27, 13, 0)  # Sunday
        week_1_day_2014_2015 = datetime(2014, 12, 31, 13, 0)  # Wednesday
        week_53_day_2015 = datetime(2015, 12, 31, 13, 0)  # Thursday
        if settings.USE_TZ:
            week_1_day_2014_2015 = timezone.make_aware(week_1_day_2014_2015)
            week_52_day_2014 = timezone.make_aware(week_52_day_2014)
            week_53_day_2015 = timezone.make_aware(week_53_day_2015)

        days = [week_52_day_2014, week_1_day_2014_2015, week_53_day_2015]
        self.create_model(week_53_day_2015, end_datetime)
        self.create_model(week_52_day_2014, end_datetime)
        self.create_model(week_1_day_2014_2015, end_datetime)
        qs = (
            DTModel.objects.filter(start_datetime__in=days)
            .annotate(
                extracted=ExtractWeek("start_datetime"),
            )
            .order_by("start_datetime")
        )
        self.assertQuerySetEqual(
            qs,
            [
                (week_52_day_2014, 52),
                (week_1_day_2014_2015, 1),
                (week_53_day_2015, 53),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )

    def test_extract_weekday_func(self):
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=ExtractWeekDay("start_datetime")
            ).order_by("start_datetime"),
            [
                (start_datetime, (start_datetime.isoweekday() % 7) + 1),
                (end_datetime, (end_datetime.isoweekday() % 7) + 1),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractWeekDay("start_date")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, (start_datetime.isoweekday() % 7) + 1),
                (end_datetime, (end_datetime.isoweekday() % 7) + 1),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__week_day=ExtractWeekDay("start_datetime")
            ).count(),
            2,
        )

    def test_extract_iso_weekday_func(self):
        """

        Tests the functionality of extracting ISO weekday from datetime fields.

        This test case covers the extraction of ISO weekday from both datetime fields 
        (start_datetime) and date fields (start_date) in the DTModel.

        It verifies that the extracted weekday values match the expected values 
        obtained using the isoweekday() method. Additionally, it checks the filtering 
        of objects based on the extracted weekday values.

        The test case handles both timezone-aware and naive datetime objects, 
        depending on the USE_TZ settings.

        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=ExtractIsoWeekDay("start_datetime"),
            ).order_by("start_datetime"),
            [
                (start_datetime, start_datetime.isoweekday()),
                (end_datetime, end_datetime.isoweekday()),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=ExtractIsoWeekDay("start_date"),
            ).order_by("start_datetime"),
            [
                (start_datetime, start_datetime.isoweekday()),
                (end_datetime, end_datetime.isoweekday()),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__week_day=ExtractWeekDay("start_datetime"),
            ).count(),
            2,
        )

    def test_extract_hour_func(self):
        """

        Tests the extraction of hours from datetime fields.

        This test function verifies the correct functionality of the ExtractHour 
        functionality in various scenarios, including the extraction of hours from 
        both 'start_datetime' and 'start_time' fields, as well as filtering by 
        hour. It ensures that the extracted hour is correctly annotated and 
        returned in the resulting querysets. 

        The test covers time zone awareness, depending on the USE_TZ setting.

        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractHour("start_datetime")).order_by(
                "start_datetime"
            ),
            [(start_datetime, start_datetime.hour), (end_datetime, end_datetime.hour)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractHour("start_time")).order_by(
                "start_datetime"
            ),
            [(start_datetime, start_datetime.hour), (end_datetime, end_datetime.hour)],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__hour=ExtractHour("start_datetime")
            ).count(),
            2,
        )

    def test_extract_minute_func(self):
        """
        #: Tests the functionality of extracting the minute component from a datetime field.
        #: 
        #: Verifies that the ExtractMinute function works correctly for both aware and naive datetimes.
        #: It checks if the extracted minute is correct for two different datetime objects and 
        #: if the minute can be used in filtering django model querysets.
        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=ExtractMinute("start_datetime")
            ).order_by("start_datetime"),
            [
                (start_datetime, start_datetime.minute),
                (end_datetime, end_datetime.minute),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractMinute("start_time")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, start_datetime.minute),
                (end_datetime, end_datetime.minute),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__minute=ExtractMinute("start_datetime")
            ).count(),
            2,
        )

    def test_extract_second_func(self):
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                extracted=ExtractSecond("start_datetime")
            ).order_by("start_datetime"),
            [
                (start_datetime, start_datetime.second),
                (end_datetime, end_datetime.second),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=ExtractSecond("start_time")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, start_datetime.second),
                (end_datetime, end_datetime.second),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__second=ExtractSecond("start_datetime")
            ).count(),
            2,
        )

    def test_extract_second_func_no_fractional(self):
        """

        Tests the extraction of the second component from datetime fields without fractional seconds.

        Verifies that the database query correctly filters objects based on the second component of 
        their start and end datetime fields, ensuring that the second components are equal.

        The test accounts for timezone-aware datetime objects if the USE_TZ setting is enabled.

        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 30, 50, 783)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        obj = self.create_model(start_datetime, end_datetime)
        self.assertSequenceEqual(
            DTModel.objects.filter(start_datetime__second=F("end_datetime__second")),
            [obj],
        )
        self.assertSequenceEqual(
            DTModel.objects.filter(start_time__second=F("end_time__second")),
            [obj],
        )

    def test_trunc_lookup_name_sql_injection(self):
        """

        Tests the lookup name 'trunc' for potential SQL injection vulnerabilities.

        This test creates model instances with specific start and end datetimes, then attempts to
        filter the model using a truncated datetime query that includes a malicious SQL injection
        string. If the SQL injection is successful, it should return a different result than expected.
        The test verifies that the SQL injection attempt fails and raises no exceptions, ensuring
        that the lookup name 'trunc' is properly sanitized against SQL injection attacks.

        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        # Database backends raise an exception or don't return any results.
        try:
            exists = DTModel.objects.filter(
                start_datetime__date=Trunc(
                    "start_datetime",
                    "year', start_datetime)) OR 1=1;--",
                )
            ).exists()
        except (DataError, OperationalError):
            pass
        else:
            self.assertIs(exists, False)

    def test_trunc_func(self):
        start_datetime = datetime(999, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)

        def assertDatetimeKind(kind):
            truncated_start = truncate_to(start_datetime, kind)
            truncated_end = truncate_to(end_datetime, kind)
            queryset = DTModel.objects.annotate(
                truncated=Trunc("start_datetime", kind, output_field=DateTimeField())
            ).order_by("start_datetime")
            self.assertSequenceEqual(
                queryset.values_list("start_datetime", "truncated"),
                [
                    (start_datetime, truncated_start),
                    (end_datetime, truncated_end),
                ],
            )

        def assertDateKind(kind):
            """

            Asserts that the date truncation to a specified kind matches the expected result.

            The function checks if the truncated start and end dates match the expected values,
            which are calculated by truncating the start and end datetime dates to the specified kind.

            The kind parameter determines the level of truncation, such as 'day', 'month', or 'year'.
            The function uses the Trunc database function to truncate the start_date field of the DTModel instances,
            and then compares the results with the expected truncated start and end dates.

            Args:
                kind (str): The level of truncation, e.g. 'day', 'month', 'year'.

            Returns:
                None

            """
            truncated_start = truncate_to(start_datetime.date(), kind)
            truncated_end = truncate_to(end_datetime.date(), kind)
            queryset = DTModel.objects.annotate(
                truncated=Trunc("start_date", kind, output_field=DateField())
            ).order_by("start_datetime")
            self.assertSequenceEqual(
                queryset.values_list("start_datetime", "truncated"),
                [
                    (start_datetime, truncated_start),
                    (end_datetime, truncated_end),
                ],
            )

        def assertTimeKind(kind):
            truncated_start = truncate_to(start_datetime.time(), kind)
            truncated_end = truncate_to(end_datetime.time(), kind)
            queryset = DTModel.objects.annotate(
                truncated=Trunc("start_time", kind, output_field=TimeField())
            ).order_by("start_datetime")
            self.assertSequenceEqual(
                queryset.values_list("start_datetime", "truncated"),
                [
                    (start_datetime, truncated_start),
                    (end_datetime, truncated_end),
                ],
            )

        def assertDatetimeToTimeKind(kind):
            """

            Asserts the correct truncation of datetime to time kind.

            This function verifies that the start and end datetimes are correctly truncated to the specified time kind.
            It checks the output of the truncation operation against the expected truncated values for start and end datetimes.

            :param kind: The time kind to truncate to (e.g. minute, hour)

            """
            truncated_start = truncate_to(start_datetime.time(), kind)
            truncated_end = truncate_to(end_datetime.time(), kind)
            queryset = DTModel.objects.annotate(
                truncated=Trunc("start_datetime", kind, output_field=TimeField()),
            ).order_by("start_datetime")
            self.assertSequenceEqual(
                queryset.values_list("start_datetime", "truncated"),
                [
                    (start_datetime, truncated_start),
                    (end_datetime, truncated_end),
                ],
            )

        date_truncations = ["year", "quarter", "month", "day"]
        time_truncations = ["hour", "minute", "second"]
        tests = [
            (assertDateKind, date_truncations),
            (assertTimeKind, time_truncations),
            (assertDatetimeKind, [*date_truncations, *time_truncations]),
            (assertDatetimeToTimeKind, time_truncations),
        ]
        for assertion, truncations in tests:
            for truncation in truncations:
                with self.subTest(assertion=assertion.__name__, truncation=truncation):
                    assertion(truncation)

        qs = DTModel.objects.filter(
            start_datetime__date=Trunc(
                "start_datetime", "day", output_field=DateField()
            )
        )
        self.assertEqual(qs.count(), 2)

    def _test_trunc_week(self, start_datetime, end_datetime):
        """

        Tests the truncation of datetimes to the week level for both aware and naive datetime inputs.

        This method creates test models with the provided start and end datetimes and then checks that 
        truncating these dates to the week level using Django's Trunc function produces the expected results.

        It covers both datetime fields and date fields, verifying that the truncated values match the expected 
        truncated dates when ordering by the start datetime.

        The test handles timezone-aware inputs if the USE_TZ setting is enabled.

        """
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)

        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                truncated=Trunc("start_datetime", "week", output_field=DateTimeField())
            ).order_by("start_datetime"),
            [
                (start_datetime, truncate_to(start_datetime, "week")),
                (end_datetime, truncate_to(end_datetime, "week")),
            ],
            lambda m: (m.start_datetime, m.truncated),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(
                truncated=Trunc("start_date", "week", output_field=DateField())
            ).order_by("start_datetime"),
            [
                (start_datetime, truncate_to(start_datetime.date(), "week")),
                (end_datetime, truncate_to(end_datetime.date(), "week")),
            ],
            lambda m: (m.start_datetime, m.truncated),
        )

    def test_trunc_week(self):
        self._test_trunc_week(
            start_datetime=datetime(2015, 6, 15, 14, 30, 50, 321),
            end_datetime=datetime(2016, 6, 15, 14, 10, 50, 123),
        )

    def test_trunc_week_before_1000(self):
        self._test_trunc_week(
            start_datetime=datetime(999, 6, 15, 14, 30, 50, 321),
            end_datetime=datetime(2016, 6, 15, 14, 10, 50, 123),
        )

    def test_trunc_invalid_arguments(self):
        msg = "output_field must be either DateField, TimeField, or DateTimeField"
        with self.assertRaisesMessage(ValueError, msg):
            list(
                DTModel.objects.annotate(
                    truncated=Trunc(
                        "start_datetime", "year", output_field=IntegerField()
                    ),
                )
            )
        msg = "'name' isn't a DateField, TimeField, or DateTimeField."
        with self.assertRaisesMessage(TypeError, msg):
            list(
                DTModel.objects.annotate(
                    truncated=Trunc("name", "year", output_field=DateTimeField()),
                )
            )
        msg = "Cannot truncate DateField 'start_date' to DateTimeField"
        with self.assertRaisesMessage(ValueError, msg):
            list(DTModel.objects.annotate(truncated=Trunc("start_date", "second")))
        with self.assertRaisesMessage(ValueError, msg):
            list(
                DTModel.objects.annotate(
                    truncated=Trunc(
                        "start_date", "month", output_field=DateTimeField()
                    ),
                )
            )
        msg = "Cannot truncate TimeField 'start_time' to DateTimeField"
        with self.assertRaisesMessage(ValueError, msg):
            list(DTModel.objects.annotate(truncated=Trunc("start_time", "month")))
        with self.assertRaisesMessage(ValueError, msg):
            list(
                DTModel.objects.annotate(
                    truncated=Trunc(
                        "start_time", "second", output_field=DateTimeField()
                    ),
                )
            )

    def test_trunc_none(self):
        self.create_model(None, None)
        for t in (
            Trunc("start_datetime", "year"),
            Trunc("start_date", "year"),
            Trunc("start_time", "hour"),
        ):
            with self.subTest(t):
                self.assertIsNone(
                    DTModel.objects.annotate(truncated=t).first().truncated
                )

    def test_trunc_year_func(self):
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = truncate_to(datetime(2016, 6, 15, 14, 10, 50, 123), "year")
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncYear("start_datetime")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime, "year")),
                (end_datetime, truncate_to(end_datetime, "year")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncYear("start_date")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime.date(), "year")),
                (end_datetime, truncate_to(end_datetime.date(), "year")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(start_datetime=TruncYear("start_datetime")).count(),
            1,
        )

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate TimeField 'start_time' to DateTimeField"
        ):
            list(DTModel.objects.annotate(truncated=TruncYear("start_time")))

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate TimeField 'start_time' to DateTimeField"
        ):
            list(
                DTModel.objects.annotate(
                    truncated=TruncYear("start_time", output_field=TimeField())
                )
            )

    def test_trunc_quarter_func(self):
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = truncate_to(datetime(2016, 10, 15, 14, 10, 50, 123), "quarter")
        last_quarter_2015 = truncate_to(
            datetime(2015, 12, 31, 14, 10, 50, 123), "quarter"
        )
        first_quarter_2016 = truncate_to(
            datetime(2016, 1, 1, 14, 10, 50, 123), "quarter"
        )
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
            last_quarter_2015 = timezone.make_aware(last_quarter_2015)
            first_quarter_2016 = timezone.make_aware(first_quarter_2016)
        self.create_model(start_datetime=start_datetime, end_datetime=end_datetime)
        self.create_model(start_datetime=end_datetime, end_datetime=start_datetime)
        self.create_model(start_datetime=last_quarter_2015, end_datetime=end_datetime)
        self.create_model(start_datetime=first_quarter_2016, end_datetime=end_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncQuarter("start_date")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime.date(), "quarter")),
                (last_quarter_2015, truncate_to(last_quarter_2015.date(), "quarter")),
                (first_quarter_2016, truncate_to(first_quarter_2016.date(), "quarter")),
                (end_datetime, truncate_to(end_datetime.date(), "quarter")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncQuarter("start_datetime")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime, "quarter")),
                (last_quarter_2015, truncate_to(last_quarter_2015, "quarter")),
                (first_quarter_2016, truncate_to(first_quarter_2016, "quarter")),
                (end_datetime, truncate_to(end_datetime, "quarter")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate TimeField 'start_time' to DateTimeField"
        ):
            list(DTModel.objects.annotate(truncated=TruncQuarter("start_time")))

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate TimeField 'start_time' to DateTimeField"
        ):
            list(
                DTModel.objects.annotate(
                    truncated=TruncQuarter("start_time", output_field=TimeField())
                )
            )

    def test_trunc_month_func(self):
        """

            Tests the truncation of date and time fields to the month level using the TruncMonth function.

            The function checks the correct truncation of datetime fields to the month level, 
            both with and without timezone awareness. It also verifies the truncation of date fields.

            Additionally, it ensures that attempting to truncate a TimeField to a DateTimeField raises a ValueError.

        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = truncate_to(datetime(2016, 6, 15, 14, 10, 50, 123), "month")
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncMonth("start_datetime")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime, "month")),
                (end_datetime, truncate_to(end_datetime, "month")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncMonth("start_date")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime.date(), "month")),
                (end_datetime, truncate_to(end_datetime.date(), "month")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(start_datetime=TruncMonth("start_datetime")).count(),
            1,
        )

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate TimeField 'start_time' to DateTimeField"
        ):
            list(DTModel.objects.annotate(truncated=TruncMonth("start_time")))

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate TimeField 'start_time' to DateTimeField"
        ):
            list(
                DTModel.objects.annotate(
                    truncated=TruncMonth("start_time", output_field=TimeField())
                )
            )

    def test_trunc_week_func(self):
        """
        Tests the TruncWeek function, which truncates a datetime object to the start of a week.

        This function verifies that the TruncWeek function correctly truncates datetime objects
        to the start of a week, and that it works as expected in both timezone-aware and
        timezone-naive modes. It also tests that attempting to truncate a TimeField to a
        DateTimeField raises a ValueError, as expected.

        The test cases cover the following scenarios:
        - Truncating a datetime object to the start of a week and verifying the result.
        - Verifying that the TruncWeek function works correctly when annotating a QuerySet.
        - Testing that filtering a QuerySet using TruncWeek works as expected.
        - Checking that attempting to truncate a TimeField to a DateTimeField raises a ValueError.

        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = truncate_to(datetime(2016, 6, 15, 14, 10, 50, 123), "week")
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncWeek("start_datetime")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime, "week")),
                (end_datetime, truncate_to(end_datetime, "week")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(start_datetime=TruncWeek("start_datetime")).count(),
            1,
        )

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate TimeField 'start_time' to DateTimeField"
        ):
            list(DTModel.objects.annotate(truncated=TruncWeek("start_time")))

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate TimeField 'start_time' to DateTimeField"
        ):
            list(
                DTModel.objects.annotate(
                    truncated=TruncWeek("start_time", output_field=TimeField())
                )
            )

    def test_trunc_date_func(self):
        """

        Tests the functionality of the TruncDate function used in the Django ORM.

        This function checks that annotating a QuerySet with TruncDate('start_datetime')
        correctly extracts the date from the datetime field, and that it can be used
        in conjunction with other methods such as filter() and order_by(). It also
        verifies that attempting to truncate a TimeField raises a ValueError, as
        expected.

        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncDate("start_datetime")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, start_datetime.date()),
                (end_datetime, end_datetime.date()),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__date=TruncDate("start_datetime")
            ).count(),
            2,
        )

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate TimeField 'start_time' to DateField"
        ):
            list(DTModel.objects.annotate(truncated=TruncDate("start_time")))

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate TimeField 'start_time' to DateField"
        ):
            list(
                DTModel.objects.annotate(
                    truncated=TruncDate("start_time", output_field=TimeField())
                )
            )

    def test_trunc_date_none(self):
        self.create_model(None, None)
        self.assertIsNone(
            DTModel.objects.annotate(truncated=TruncDate("start_datetime"))
            .first()
            .truncated
        )

    def test_trunc_time_func(self):
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncTime("start_datetime")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, start_datetime.time()),
                (end_datetime, end_datetime.time()),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime__time=TruncTime("start_datetime")
            ).count(),
            2,
        )

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate DateField 'start_date' to TimeField"
        ):
            list(DTModel.objects.annotate(truncated=TruncTime("start_date")))

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate DateField 'start_date' to TimeField"
        ):
            list(
                DTModel.objects.annotate(
                    truncated=TruncTime("start_date", output_field=DateField())
                )
            )

    def test_trunc_time_none(self):
        """
        Tests the TruncTime database function with a None input value, verifying that annotating a queryset with TruncTime('start_datetime') returns None when the input value is None.
        """
        self.create_model(None, None)
        self.assertIsNone(
            DTModel.objects.annotate(truncated=TruncTime("start_datetime"))
            .first()
            .truncated
        )

    def test_trunc_time_comparison(self):
        start_datetime = datetime(2015, 6, 15, 14, 30, 26)  # 0 microseconds.
        end_datetime = datetime(2015, 6, 15, 14, 30, 26, 321)
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.assertIs(
            DTModel.objects.filter(
                start_datetime__time=start_datetime.time(),
                end_datetime__time=end_datetime.time(),
            ).exists(),
            True,
        )
        self.assertIs(
            DTModel.objects.annotate(
                extracted_start=TruncTime("start_datetime"),
                extracted_end=TruncTime("end_datetime"),
            )
            .filter(
                extracted_start=start_datetime.time(),
                extracted_end=end_datetime.time(),
            )
            .exists(),
            True,
        )

    def test_trunc_day_func(self):
        """

        Tests the TruncDay database function to ensure it correctly truncates a datetime to a day.

        This test case covers both aware and naive datetime objects. It also verifies the
        functionality of TruncDay in various usage scenarios, including annotation and
        filtering of QuerySets. Additionally, it checks that attempting to truncate a TimeField
        to a DateTimeField raises a ValueError, as expected.

        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = truncate_to(datetime(2016, 6, 15, 14, 10, 50, 123), "day")
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncDay("start_datetime")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime, "day")),
                (end_datetime, truncate_to(end_datetime, "day")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(start_datetime=TruncDay("start_datetime")).count(), 1
        )

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate TimeField 'start_time' to DateTimeField"
        ):
            list(DTModel.objects.annotate(truncated=TruncDay("start_time")))

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate TimeField 'start_time' to DateTimeField"
        ):
            list(
                DTModel.objects.annotate(
                    truncated=TruncDay("start_time", output_field=TimeField())
                )
            )

    def test_trunc_hour_func(self):
        """

        Tests the TruncHour function to ensure it correctly truncates datetime fields to the hour.

        The TruncHour function truncates a datetime field to the hour, effectively rounding down to the nearest hour.
        This function is tested on both datetime fields and time fields, as well as with and without timezone awareness.

        The test cases cover the following scenarios:

        * Truncating a datetime field to the hour
        * Truncating a time field to the hour
        * Filtering by a truncated datetime field
        * Attempting to truncate a date field to a datetime field, which should raise a ValueError

        These tests ensure that the TruncHour function behaves correctly and as expected in a variety of situations.

        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = truncate_to(datetime(2016, 6, 15, 14, 10, 50, 123), "hour")
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncHour("start_datetime")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime, "hour")),
                (end_datetime, truncate_to(end_datetime, "hour")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncHour("start_time")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime.time(), "hour")),
                (end_datetime, truncate_to(end_datetime.time(), "hour")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(start_datetime=TruncHour("start_datetime")).count(),
            1,
        )

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate DateField 'start_date' to DateTimeField"
        ):
            list(DTModel.objects.annotate(truncated=TruncHour("start_date")))

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate DateField 'start_date' to DateTimeField"
        ):
            list(
                DTModel.objects.annotate(
                    truncated=TruncHour("start_date", output_field=DateField())
                )
            )

    def test_trunc_minute_func(self):
        """
        Tests the functionality of the TruncMinute function in various scenarios.

        This test case checks the truncation of datetime objects to the minute level,
        both for naive and timezone-aware datetimes. It verifies that the TruncMinute
        function correctly truncates the seconds and microseconds from datetime objects.

        The test also checks the behavior of the TruncMinute function when used with
        different fields, including DateTimeField and TimeField, and ensures that it
        raises the expected errors when used with incompatible field types, such as DateField.

        Additional checks are performed to validate the correctness of the TruncMinute
        function when used in ORM queries, including annotation and filtering of querysets.
        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = truncate_to(datetime(2016, 6, 15, 14, 10, 50, 123), "minute")
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncMinute("start_datetime")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime, "minute")),
                (end_datetime, truncate_to(end_datetime, "minute")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncMinute("start_time")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime.time(), "minute")),
                (end_datetime, truncate_to(end_datetime.time(), "minute")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime=TruncMinute("start_datetime")
            ).count(),
            1,
        )

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate DateField 'start_date' to DateTimeField"
        ):
            list(DTModel.objects.annotate(truncated=TruncMinute("start_date")))

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate DateField 'start_date' to DateTimeField"
        ):
            list(
                DTModel.objects.annotate(
                    truncated=TruncMinute("start_date", output_field=DateField())
                )
            )

    def test_trunc_second_func(self):
        """
        Tests the functionality of the TruncSecond database function.

        This test case checks the correct truncation of datetime fields to the second,
        including edge cases with time zones, and incorrect usage with date fields.

        It verifies that the TruncSecond function:

        * Correctly truncates datetime fields to the second
        * Handles time zones correctly
        * Raises an error when used with date fields

        The test also checks the results of annotating QuerySets with the TruncSecond function
        and filtering QuerySets using the TruncSecond function.
        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = truncate_to(datetime(2016, 6, 15, 14, 10, 50, 123), "second")
        if settings.USE_TZ:
            start_datetime = timezone.make_aware(start_datetime)
            end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncSecond("start_datetime")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime, "second")),
                (end_datetime, truncate_to(end_datetime, "second")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertQuerySetEqual(
            DTModel.objects.annotate(extracted=TruncSecond("start_time")).order_by(
                "start_datetime"
            ),
            [
                (start_datetime, truncate_to(start_datetime.time(), "second")),
                (end_datetime, truncate_to(end_datetime.time(), "second")),
            ],
            lambda m: (m.start_datetime, m.extracted),
        )
        self.assertEqual(
            DTModel.objects.filter(
                start_datetime=TruncSecond("start_datetime")
            ).count(),
            1,
        )

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate DateField 'start_date' to DateTimeField"
        ):
            list(DTModel.objects.annotate(truncated=TruncSecond("start_date")))

        with self.assertRaisesMessage(
            ValueError, "Cannot truncate DateField 'start_date' to DateTimeField"
        ):
            list(
                DTModel.objects.annotate(
                    truncated=TruncSecond("start_date", output_field=DateField())
                )
            )

    def test_trunc_subquery_with_parameters(self):
        """

        Test case for truncating subqueries with parameters.

        This test creates authors and their corresponding fans with specific dates 
        and checks the newest fan year for each author. The test annotates 
        each author with the newest fan year by using a subquery to get the 
        newest fan since date and then truncating it to the year.

        It verifies that the annotated values are correct and that the results 
        are ordered by author name.

        The test also considers timezone-aware dates if the USE_TZ setting is enabled.

        """
        author_1 = Author.objects.create(name="J. R. R. Tolkien")
        author_2 = Author.objects.create(name="G. R. R. Martin")
        fan_since_1 = datetime(2016, 2, 3, 15, 0, 0)
        fan_since_2 = datetime(2015, 2, 3, 15, 0, 0)
        fan_since_3 = datetime(2017, 2, 3, 15, 0, 0)
        if settings.USE_TZ:
            fan_since_1 = timezone.make_aware(fan_since_1)
            fan_since_2 = timezone.make_aware(fan_since_2)
            fan_since_3 = timezone.make_aware(fan_since_3)
        Fan.objects.create(author=author_1, name="Tom", fan_since=fan_since_1)
        Fan.objects.create(author=author_1, name="Emma", fan_since=fan_since_2)
        Fan.objects.create(author=author_2, name="Isabella", fan_since=fan_since_3)

        inner = (
            Fan.objects.filter(
                author=OuterRef("pk"), name__in=("Emma", "Isabella", "Tom")
            )
            .values("author")
            .annotate(newest_fan=Max("fan_since"))
            .values("newest_fan")
        )
        outer = Author.objects.annotate(
            newest_fan_year=TruncYear(Subquery(inner, output_field=DateTimeField()))
        )
        tz = datetime_timezone.utc if settings.USE_TZ else None
        self.assertSequenceEqual(
            outer.order_by("name").values("name", "newest_fan_year"),
            [
                {
                    "name": "G. R. R. Martin",
                    "newest_fan_year": datetime(2017, 1, 1, 0, 0, tzinfo=tz),
                },
                {
                    "name": "J. R. R. Tolkien",
                    "newest_fan_year": datetime(2016, 1, 1, 0, 0, tzinfo=tz),
                },
            ],
        )

    def test_extract_outerref(self):
        """
        Tests the extraction of outer references in database queries.

        This test case verifies the functionality of annotating objects with a subquery
        that references the outer query. It creates several model instances with different
        datetime fields and then uses a subquery to annotate each object with the primary
        key of another object that matches a specific condition.

        The test checks if the annotation correctly assigns the primary key of the related
        object to each instance, or returns None if no matching object exists. The results
        are then compared to the expected output to ensure the correctness of the query.

        The test also accounts for timezone awareness, making it applicable to both timezone-aware and naive datetime fields.
        """
        datetime_1 = datetime(2000, 1, 1)
        datetime_2 = datetime(2001, 3, 5)
        datetime_3 = datetime(2002, 1, 3)
        if settings.USE_TZ:
            datetime_1 = timezone.make_aware(datetime_1)
            datetime_2 = timezone.make_aware(datetime_2)
            datetime_3 = timezone.make_aware(datetime_3)
        obj_1 = self.create_model(datetime_1, datetime_3)
        obj_2 = self.create_model(datetime_2, datetime_1)
        obj_3 = self.create_model(datetime_3, datetime_2)

        inner_qs = DTModel.objects.filter(
            start_datetime__year=2000,
            start_datetime__month=ExtractMonth(OuterRef("end_datetime")),
        )
        qs = DTModel.objects.annotate(
            related_pk=Subquery(inner_qs.values("pk")[:1]),
        )
        self.assertSequenceEqual(
            qs.order_by("name").values("pk", "related_pk"),
            [
                {"pk": obj_1.pk, "related_pk": obj_1.pk},
                {"pk": obj_2.pk, "related_pk": obj_1.pk},
                {"pk": obj_3.pk, "related_pk": None},
            ],
        )


@override_settings(USE_TZ=True, TIME_ZONE="UTC")
class DateFunctionWithTimeZoneTests(DateFunctionTests):
    def test_extract_func_with_timezone(self):
        """
        .. method:: test_extract_func_with_timezone()

           Tests the extraction of various date and time components from a 
           datetime object, with and without timezone information. The test 
           covers the extraction of day, week, year, day of the week, hour, 
           minute, and quarter, with specific examples using the UTC timezone 
           and the Australia/Melbourne timezone. It also tests the extraction 
           of date and time components with timezone-aware datetime objects 
           and with timezone overrides. The test verifies that the extracts 
           return the expected values for different timezones, ensuring that 
           the extraction functions behave correctly with timezone information.
        """
        start_datetime = datetime(2015, 6, 15, 23, 30, 1, 321)
        end_datetime = datetime(2015, 6, 16, 13, 11, 27, 123)
        start_datetime = timezone.make_aware(start_datetime)
        end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        delta_tzinfo_pos = datetime_timezone(timedelta(hours=5))
        delta_tzinfo_neg = datetime_timezone(timedelta(hours=-5, minutes=17))
        melb = zoneinfo.ZoneInfo("Australia/Melbourne")

        qs = DTModel.objects.annotate(
            day=Extract("start_datetime", "day"),
            day_melb=Extract("start_datetime", "day", tzinfo=melb),
            week=Extract("start_datetime", "week", tzinfo=melb),
            isoyear=ExtractIsoYear("start_datetime", tzinfo=melb),
            weekday=ExtractWeekDay("start_datetime"),
            weekday_melb=ExtractWeekDay("start_datetime", tzinfo=melb),
            isoweekday=ExtractIsoWeekDay("start_datetime"),
            isoweekday_melb=ExtractIsoWeekDay("start_datetime", tzinfo=melb),
            quarter=ExtractQuarter("start_datetime", tzinfo=melb),
            hour=ExtractHour("start_datetime"),
            hour_melb=ExtractHour("start_datetime", tzinfo=melb),
            hour_with_delta_pos=ExtractHour("start_datetime", tzinfo=delta_tzinfo_pos),
            hour_with_delta_neg=ExtractHour("start_datetime", tzinfo=delta_tzinfo_neg),
            minute_with_delta_neg=ExtractMinute(
                "start_datetime", tzinfo=delta_tzinfo_neg
            ),
        ).order_by("start_datetime")

        utc_model = qs.get()
        self.assertEqual(utc_model.day, 15)
        self.assertEqual(utc_model.day_melb, 16)
        self.assertEqual(utc_model.week, 25)
        self.assertEqual(utc_model.isoyear, 2015)
        self.assertEqual(utc_model.weekday, 2)
        self.assertEqual(utc_model.weekday_melb, 3)
        self.assertEqual(utc_model.isoweekday, 1)
        self.assertEqual(utc_model.isoweekday_melb, 2)
        self.assertEqual(utc_model.quarter, 2)
        self.assertEqual(utc_model.hour, 23)
        self.assertEqual(utc_model.hour_melb, 9)
        self.assertEqual(utc_model.hour_with_delta_pos, 4)
        self.assertEqual(utc_model.hour_with_delta_neg, 18)
        self.assertEqual(utc_model.minute_with_delta_neg, 47)

        with timezone.override(melb):
            melb_model = qs.get()

        self.assertEqual(melb_model.day, 16)
        self.assertEqual(melb_model.day_melb, 16)
        self.assertEqual(melb_model.week, 25)
        self.assertEqual(melb_model.isoyear, 2015)
        self.assertEqual(melb_model.weekday, 3)
        self.assertEqual(melb_model.isoweekday, 2)
        self.assertEqual(melb_model.quarter, 2)
        self.assertEqual(melb_model.weekday_melb, 3)
        self.assertEqual(melb_model.isoweekday_melb, 2)
        self.assertEqual(melb_model.hour, 9)
        self.assertEqual(melb_model.hour_melb, 9)

    def test_extract_func_with_timezone_minus_no_offset(self):
        start_datetime = datetime(2015, 6, 15, 23, 30, 1, 321)
        end_datetime = datetime(2015, 6, 16, 13, 11, 27, 123)
        start_datetime = timezone.make_aware(start_datetime)
        end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        ust_nera = zoneinfo.ZoneInfo("Asia/Ust-Nera")

        qs = DTModel.objects.annotate(
            hour=ExtractHour("start_datetime"),
            hour_tz=ExtractHour("start_datetime", tzinfo=ust_nera),
        ).order_by("start_datetime")

        utc_model = qs.get()
        self.assertEqual(utc_model.hour, 23)
        self.assertEqual(utc_model.hour_tz, 9)

        with timezone.override(ust_nera):
            ust_nera_model = qs.get()

        self.assertEqual(ust_nera_model.hour, 9)
        self.assertEqual(ust_nera_model.hour_tz, 9)

    def test_extract_func_explicit_timezone_priority(self):
        start_datetime = datetime(2015, 6, 15, 23, 30, 1, 321)
        end_datetime = datetime(2015, 6, 16, 13, 11, 27, 123)
        start_datetime = timezone.make_aware(start_datetime)
        end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        melb = zoneinfo.ZoneInfo("Australia/Melbourne")
        with timezone.override(melb):
            model = (
                DTModel.objects.annotate(
                    day_melb=Extract("start_datetime", "day"),
                    day_utc=Extract(
                        "start_datetime", "day", tzinfo=datetime_timezone.utc
                    ),
                )
                .order_by("start_datetime")
                .get()
            )
            self.assertEqual(model.day_melb, 16)
            self.assertEqual(model.day_utc, 15)

    def test_extract_invalid_field_with_timezone(self):
        melb = zoneinfo.ZoneInfo("Australia/Melbourne")
        msg = "tzinfo can only be used with DateTimeField."
        with self.assertRaisesMessage(ValueError, msg):
            DTModel.objects.annotate(
                day_melb=Extract("start_date", "day", tzinfo=melb),
            ).get()
        with self.assertRaisesMessage(ValueError, msg):
            DTModel.objects.annotate(
                hour_melb=Extract("start_time", "hour", tzinfo=melb),
            ).get()

    def test_trunc_timezone_applied_before_truncation(self):
        """
        Test that timezone is applied before truncation.

        This test case verifies the correct behavior when truncating datetime fields
        to different levels (year, date, time) in various time zones. It ensures that
        the timezone is applied to the original datetime before truncation, resulting
        in correct truncated values.

        The test covers scenarios with different time zones, specifically Melbourne
        and Los Angeles, and checks that the resulting truncated values (year, date,
        time) match the expected values after applying the respective time zone
        offsets. This guarantees that the truncation operation respects the timezone
        information and produces accurate results in different regions.
        """
        start_datetime = datetime(2016, 1, 1, 1, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        start_datetime = timezone.make_aware(start_datetime)
        end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        melb = zoneinfo.ZoneInfo("Australia/Melbourne")
        pacific = zoneinfo.ZoneInfo("America/Los_Angeles")

        model = (
            DTModel.objects.annotate(
                melb_year=TruncYear("start_datetime", tzinfo=melb),
                pacific_year=TruncYear("start_datetime", tzinfo=pacific),
                melb_date=TruncDate("start_datetime", tzinfo=melb),
                pacific_date=TruncDate("start_datetime", tzinfo=pacific),
                melb_time=TruncTime("start_datetime", tzinfo=melb),
                pacific_time=TruncTime("start_datetime", tzinfo=pacific),
            )
            .order_by("start_datetime")
            .get()
        )

        melb_start_datetime = start_datetime.astimezone(melb)
        pacific_start_datetime = start_datetime.astimezone(pacific)
        self.assertEqual(model.start_datetime, start_datetime)
        self.assertEqual(model.melb_year, truncate_to(start_datetime, "year", melb))
        self.assertEqual(
            model.pacific_year, truncate_to(start_datetime, "year", pacific)
        )
        self.assertEqual(model.start_datetime.year, 2016)
        self.assertEqual(model.melb_year.year, 2016)
        self.assertEqual(model.pacific_year.year, 2015)
        self.assertEqual(model.melb_date, melb_start_datetime.date())
        self.assertEqual(model.pacific_date, pacific_start_datetime.date())
        self.assertEqual(model.melb_time, melb_start_datetime.time())
        self.assertEqual(model.pacific_time, pacific_start_datetime.time())

    def test_trunc_func_with_timezone(self):
        """
        If the truncated datetime transitions to a different offset (daylight
        saving) then the returned value will have that new timezone/offset.
        """
        start_datetime = datetime(2015, 6, 15, 14, 30, 50, 321)
        end_datetime = datetime(2016, 6, 15, 14, 10, 50, 123)
        start_datetime = timezone.make_aware(start_datetime)
        end_datetime = timezone.make_aware(end_datetime)
        self.create_model(start_datetime, end_datetime)
        self.create_model(end_datetime, start_datetime)

        def assertDatetimeKind(kind, tzinfo):
            truncated_start = truncate_to(
                start_datetime.astimezone(tzinfo), kind, tzinfo
            )
            truncated_end = truncate_to(end_datetime.astimezone(tzinfo), kind, tzinfo)
            queryset = DTModel.objects.annotate(
                truncated=Trunc(
                    "start_datetime",
                    kind,
                    output_field=DateTimeField(),
                    tzinfo=tzinfo,
                )
            ).order_by("start_datetime")
            self.assertSequenceEqual(
                queryset.values_list("start_datetime", "truncated"),
                [
                    (start_datetime, truncated_start),
                    (end_datetime, truncated_end),
                ],
            )

        def assertDatetimeToDateKind(kind, tzinfo):
            truncated_start = truncate_to(
                start_datetime.astimezone(tzinfo).date(), kind
            )
            truncated_end = truncate_to(end_datetime.astimezone(tzinfo).date(), kind)
            queryset = DTModel.objects.annotate(
                truncated=Trunc(
                    "start_datetime",
                    kind,
                    output_field=DateField(),
                    tzinfo=tzinfo,
                ),
            ).order_by("start_datetime")
            self.assertSequenceEqual(
                queryset.values_list("start_datetime", "truncated"),
                [
                    (start_datetime, truncated_start),
                    (end_datetime, truncated_end),
                ],
            )

        def assertDatetimeToTimeKind(kind, tzinfo):
            truncated_start = truncate_to(
                start_datetime.astimezone(tzinfo).time(), kind
            )
            truncated_end = truncate_to(end_datetime.astimezone(tzinfo).time(), kind)
            queryset = DTModel.objects.annotate(
                truncated=Trunc(
                    "start_datetime",
                    kind,
                    output_field=TimeField(),
                    tzinfo=tzinfo,
                )
            ).order_by("start_datetime")
            self.assertSequenceEqual(
                queryset.values_list("start_datetime", "truncated"),
                [
                    (start_datetime, truncated_start),
                    (end_datetime, truncated_end),
                ],
            )

        timezones = [
            zoneinfo.ZoneInfo("Australia/Melbourne"),
            zoneinfo.ZoneInfo("Etc/GMT+10"),
        ]
        date_truncations = ["year", "quarter", "month", "week", "day"]
        time_truncations = ["hour", "minute", "second"]
        tests = [
            (assertDatetimeToDateKind, date_truncations),
            (assertDatetimeToTimeKind, time_truncations),
            (assertDatetimeKind, [*date_truncations, *time_truncations]),
        ]
        for assertion, truncations in tests:
            for truncation in truncations:
                for tzinfo in timezones:
                    with self.subTest(
                        assertion=assertion.__name__,
                        truncation=truncation,
                        tzinfo=tzinfo.key,
                    ):
                        assertion(truncation, tzinfo)

        qs = DTModel.objects.filter(
            start_datetime__date=Trunc(
                "start_datetime", "day", output_field=DateField()
            )
        )
        self.assertEqual(qs.count(), 2)

    def test_trunc_invalid_field_with_timezone(self):
        melb = zoneinfo.ZoneInfo("Australia/Melbourne")
        msg = "tzinfo can only be used with DateTimeField."
        with self.assertRaisesMessage(ValueError, msg):
            DTModel.objects.annotate(
                day_melb=Trunc("start_date", "day", tzinfo=melb),
            ).get()
        with self.assertRaisesMessage(ValueError, msg):
            DTModel.objects.annotate(
                hour_melb=Trunc("start_time", "hour", tzinfo=melb),
            ).get()
