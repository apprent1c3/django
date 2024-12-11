import datetime
import json
from decimal import Decimal

from django import forms
from django.core import exceptions, serializers
from django.db.models import DateField, DateTimeField, F, Func, Value
from django.http import QueryDict
from django.test import override_settings
from django.test.utils import isolate_apps
from django.utils import timezone

from . import PostgreSQLSimpleTestCase, PostgreSQLTestCase
from .models import (
    BigAutoFieldModel,
    PostgreSQLModel,
    RangeLookupsModel,
    RangesModel,
    SmallAutoFieldModel,
)

try:
    from django.contrib.postgres import fields as pg_fields
    from django.contrib.postgres import forms as pg_forms
    from django.contrib.postgres.validators import (
        RangeMaxValueValidator,
        RangeMinValueValidator,
    )
    from django.db.backends.postgresql.psycopg_any import (
        DateRange,
        DateTimeTZRange,
        NumericRange,
    )
except ImportError:
    pass


@isolate_apps("postgres_tests")
class BasicTests(PostgreSQLSimpleTestCase):
    def test_get_field_display(self):
        class Model(PostgreSQLModel):
            field = pg_fields.IntegerRangeField(
                choices=[
                    ["1-50", [((1, 25), "1-25"), ([26, 50], "26-50")]],
                    ((51, 100), "51-100"),
                ],
            )

        tests = (
            ((1, 25), "1-25"),
            ([26, 50], "26-50"),
            ((51, 100), "51-100"),
            ((1, 2), "(1, 2)"),
            ([1, 2], "[1, 2]"),
        )
        for value, display in tests:
            with self.subTest(value=value, display=display):
                instance = Model(field=value)
                self.assertEqual(instance.get_field_display(), display)

    def test_discrete_range_fields_unsupported_default_bounds(self):
        """
        Tests whether discrete range fields in PostgreSQL raise a TypeError when 'default_bounds' is used, which is an unsupported argument for these field types. 

        The function covers BigIntegerRangeField, IntegerRangeField, and DateRangeField, ensuring that each raises the expected error when 'default_bounds' is provided, thus validating the constraints for valid argument values.
        """
        discrete_range_types = [
            pg_fields.BigIntegerRangeField,
            pg_fields.IntegerRangeField,
            pg_fields.DateRangeField,
        ]
        for field_type in discrete_range_types:
            msg = f"Cannot use 'default_bounds' with {field_type.__name__}."
            with self.assertRaisesMessage(TypeError, msg):
                field_type(choices=[((51, 100), "51-100")], default_bounds="[]")

    def test_continuous_range_fields_default_bounds(self):
        continuous_range_types = [
            pg_fields.DecimalRangeField,
            pg_fields.DateTimeRangeField,
        ]
        for field_type in continuous_range_types:
            field = field_type(choices=[((51, 100), "51-100")], default_bounds="[]")
            self.assertEqual(field.default_bounds, "[]")

    def test_invalid_default_bounds(self):
        tests = [")]", ")[", "](", "])", "([", "[(", "x", "", None]
        msg = "default_bounds must be one of '[)', '(]', '()', or '[]'."
        for invalid_bounds in tests:
            with self.assertRaisesMessage(ValueError, msg):
                pg_fields.DecimalRangeField(default_bounds=invalid_bounds)

    def test_deconstruct(self):
        """

        Tests the deconstruction of a DecimalRangeField.

        This test case ensures that the field's deconstruct method correctly
        returns its attributes, specifically the default_bounds parameter.
        The test covers two scenarios: one where no default bounds are set,
        and another where default bounds are explicitly provided.

        The expected outcome is that the deconstruct method returns an empty
        dictionary when no default bounds are set, and a dictionary containing
        the default_bounds key when default bounds are specified.

        """
        field = pg_fields.DecimalRangeField()
        *_, kwargs = field.deconstruct()
        self.assertEqual(kwargs, {})
        field = pg_fields.DecimalRangeField(default_bounds="[]")
        *_, kwargs = field.deconstruct()
        self.assertEqual(kwargs, {"default_bounds": "[]"})


class TestSaveLoad(PostgreSQLTestCase):
    def test_all_fields(self):
        """

        Test that all fields of the RangesModel instance are correctly saved and loaded.

        Verifies that the fields for integers, big integers, decimals, timestamps, and dates
        are properly persisted to the database and retrieved without data loss or corruption.

        """
        now = timezone.now()
        instance = RangesModel(
            ints=NumericRange(0, 10),
            bigints=NumericRange(10, 20),
            decimals=NumericRange(20, 30),
            timestamps=DateTimeTZRange(now - datetime.timedelta(hours=1), now),
            dates=DateRange(now.date() - datetime.timedelta(days=1), now.date()),
        )
        instance.save()
        loaded = RangesModel.objects.get()
        self.assertEqual(instance.ints, loaded.ints)
        self.assertEqual(instance.bigints, loaded.bigints)
        self.assertEqual(instance.decimals, loaded.decimals)
        self.assertEqual(instance.timestamps, loaded.timestamps)
        self.assertEqual(instance.dates, loaded.dates)

    def test_range_object(self):
        """

        Tests the persistence of a NumericRange object through the RangesModel.

        This test case verifies that a NumericRange object, when assigned to an instance of RangesModel and saved, can be retrieved accurately from the database.

        The test covers the following scenarios:
        - Creating a NumericRange object with a specified range
        - Assigning the NumericRange object to a RangesModel instance
        - Saving the instance to the database
        - Retrieving the instance from the database
        - Verifying that the retrieved NumericRange object matches the original object

        """
        r = NumericRange(0, 10)
        instance = RangesModel(ints=r)
        instance.save()
        loaded = RangesModel.objects.get()
        self.assertEqual(r, loaded.ints)

    def test_tuple(self):
        """
        Tests the storage and retrieval of a tuple value using the RangesModel.

        Verifies that a tuple value assigned to the 'ints' field of a RangesModel instance 
        is successfully saved to the database and loaded back into a new instance 
        as an equivalent NumericRange object. 

        This test ensures the seamless conversion between the tuple and NumericRange 
        data types, allowing for correct usage of the RangesModel in various scenarios.
        """
        instance = RangesModel(ints=(0, 10))
        instance.save()
        loaded = RangesModel.objects.get()
        self.assertEqual(NumericRange(0, 10), loaded.ints)

    def test_tuple_range_with_default_bounds(self):
        range_ = (timezone.now(), timezone.now() + datetime.timedelta(hours=1))
        RangesModel.objects.create(timestamps_closed_bounds=range_, timestamps=range_)
        loaded = RangesModel.objects.get()
        self.assertEqual(
            loaded.timestamps_closed_bounds,
            DateTimeTZRange(range_[0], range_[1], "[]"),
        )
        self.assertEqual(
            loaded.timestamps,
            DateTimeTZRange(range_[0], range_[1], "[)"),
        )

    def test_range_object_boundaries(self):
        """
        Tests the boundaries of a NumericRange object when used with a RangesModel instance.

        Verifies that a range with inclusive boundaries (denoted by '[]') is correctly 
        saved and loaded, ensuring that the boundaries are preserved and that the 
        endpoint of the range is included in the loaded range.
        """
        r = NumericRange(0, 10, "[]")
        instance = RangesModel(decimals=r)
        instance.save()
        loaded = RangesModel.objects.get()
        self.assertEqual(r, loaded.decimals)
        self.assertIn(10, loaded.decimals)

    def test_range_object_boundaries_range_with_default_bounds(self):
        range_ = DateTimeTZRange(
            timezone.now(),
            timezone.now() + datetime.timedelta(hours=1),
            bounds="()",
        )
        RangesModel.objects.create(timestamps_closed_bounds=range_)
        loaded = RangesModel.objects.get()
        self.assertEqual(loaded.timestamps_closed_bounds, range_)

    def test_unbounded(self):
        r = NumericRange(None, None, "()")
        instance = RangesModel(decimals=r)
        instance.save()
        loaded = RangesModel.objects.get()
        self.assertEqual(r, loaded.decimals)

    def test_empty(self):
        r = NumericRange(empty=True)
        instance = RangesModel(ints=r)
        instance.save()
        loaded = RangesModel.objects.get()
        self.assertEqual(r, loaded.ints)

    def test_null(self):
        """
        Tests that a RangesModel instance can be saved and loaded with null integer values.

        Verifies that when an instance is created without specifying integer values and then saved, 
        the loaded instance also has null integer values, ensuring data integrity and expected behavior.
        """
        instance = RangesModel(ints=None)
        instance.save()
        loaded = RangesModel.objects.get()
        self.assertIsNone(loaded.ints)

    def test_model_set_on_base_field(self):
        """

        Verify that the base field of a model field is correctly set.

        This test checks that the model attribute of a field and its base field
        are both set to the expected model class, confirming that the field is
        properly associated with its parent model.

        The test instance is created from the RangesModel class and the 'ints' field
        is retrieved. The model and base field model are then asserted to be equal
        to the RangesModel, confirming the correct relationship.

        """
        instance = RangesModel()
        field = instance._meta.get_field("ints")
        self.assertEqual(field.model, RangesModel)
        self.assertEqual(field.base_field.model, RangesModel)


class TestRangeContainsLookup(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Setup test data for testing date and timestamp ranges.

        This method initializes class-level attributes with test data, including lists of
        timestamps and dates, as well as model objects with varying date and timestamp
        ranges. The data is used to support testing of date and timestamp range functionality.

        The following attributes are set up:
        - timestamps: a list of datetime objects
        - aware_timestamps: a list of timezone-aware datetime objects
        - dates: a list of date objects
        - obj: a model object with date and timestamp ranges
        - aware_obj: a model object with timezone-aware date and timestamp ranges

        Additional model objects are created to support testing of varying date and
        timestamp ranges.

        """
        cls.timestamps = [
            datetime.datetime(year=2016, month=1, day=1),
            datetime.datetime(year=2016, month=1, day=2, hour=1),
            datetime.datetime(year=2016, month=1, day=2, hour=12),
            datetime.datetime(year=2016, month=1, day=3),
            datetime.datetime(year=2016, month=1, day=3, hour=1),
            datetime.datetime(year=2016, month=2, day=2),
        ]
        cls.aware_timestamps = [
            timezone.make_aware(timestamp) for timestamp in cls.timestamps
        ]
        cls.dates = [
            datetime.date(year=2016, month=1, day=1),
            datetime.date(year=2016, month=1, day=2),
            datetime.date(year=2016, month=1, day=3),
            datetime.date(year=2016, month=1, day=4),
            datetime.date(year=2016, month=2, day=2),
            datetime.date(year=2016, month=2, day=3),
        ]
        cls.obj = RangesModel.objects.create(
            dates=(cls.dates[0], cls.dates[3]),
            dates_inner=(cls.dates[1], cls.dates[2]),
            timestamps=(cls.timestamps[0], cls.timestamps[3]),
            timestamps_inner=(cls.timestamps[1], cls.timestamps[2]),
        )
        cls.aware_obj = RangesModel.objects.create(
            dates=(cls.dates[0], cls.dates[3]),
            dates_inner=(cls.dates[1], cls.dates[2]),
            timestamps=(cls.aware_timestamps[0], cls.aware_timestamps[3]),
            timestamps_inner=(cls.timestamps[1], cls.timestamps[2]),
        )
        # Objects that don't match any queries.
        for i in range(3, 4):
            RangesModel.objects.create(
                dates=(cls.dates[i], cls.dates[i + 1]),
                timestamps=(cls.timestamps[i], cls.timestamps[i + 1]),
            )
            RangesModel.objects.create(
                dates=(cls.dates[i], cls.dates[i + 1]),
                timestamps=(cls.aware_timestamps[i], cls.aware_timestamps[i + 1]),
            )

    def test_datetime_range_contains(self):
        """

        Test whether the datetime range 'contains' lookup is functioning correctly.

        This test checks that the 'contains' lookup for datetime fields in the model 
        returns the expected objects when given various filter arguments, including 
        naive and aware timestamps, timestamp ranges, and database function calls.

        The test iterates over a variety of filter arguments, including timestamps, 
        aware timestamps, timestamp ranges, and database functions, to ensure that 
        the 'contains' lookup is working as expected in different scenarios.

        The expected result is that the objects that have a timestamps field containing 
        the specified filter argument are returned by the query.

        """
        filter_args = (
            self.timestamps[1],
            self.aware_timestamps[1],
            (self.timestamps[1], self.timestamps[2]),
            (self.aware_timestamps[1], self.aware_timestamps[2]),
            Value(self.dates[0]),
            Func(F("dates"), function="lower", output_field=DateTimeField()),
            F("timestamps_inner"),
        )
        for filter_arg in filter_args:
            with self.subTest(filter_arg=filter_arg):
                self.assertCountEqual(
                    RangesModel.objects.filter(**{"timestamps__contains": filter_arg}),
                    [self.obj, self.aware_obj],
                )

    def test_date_range_contains(self):
        filter_args = (
            self.timestamps[1],
            (self.dates[1], self.dates[2]),
            Value(self.dates[0], output_field=DateField()),
            Func(F("timestamps"), function="lower", output_field=DateField()),
            F("dates_inner"),
        )
        for filter_arg in filter_args:
            with self.subTest(filter_arg=filter_arg):
                self.assertCountEqual(
                    RangesModel.objects.filter(**{"dates__contains": filter_arg}),
                    [self.obj, self.aware_obj],
                )


class TestQuerying(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.objs = RangesModel.objects.bulk_create(
            [
                RangesModel(ints=NumericRange(0, 10)),
                RangesModel(ints=NumericRange(5, 15)),
                RangesModel(ints=NumericRange(None, 0)),
                RangesModel(ints=NumericRange(empty=True)),
                RangesModel(ints=None),
            ]
        )

    def test_exact(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__exact=NumericRange(0, 10)),
            [self.objs[0]],
        )

    def test_isnull(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__isnull=True),
            [self.objs[4]],
        )

    def test_isempty(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__isempty=True),
            [self.objs[3]],
        )

    def test_contains(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__contains=8),
            [self.objs[0], self.objs[1]],
        )

    def test_contains_range(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__contains=NumericRange(3, 8)),
            [self.objs[0]],
        )

    def test_contained_by(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__contained_by=NumericRange(0, 20)),
            [self.objs[0], self.objs[1], self.objs[3]],
        )

    def test_overlap(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__overlap=NumericRange(3, 8)),
            [self.objs[0], self.objs[1]],
        )

    def test_fully_lt(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__fully_lt=NumericRange(5, 10)),
            [self.objs[2]],
        )

    def test_fully_gt(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__fully_gt=NumericRange(5, 10)),
            [],
        )

    def test_not_lt(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__not_lt=NumericRange(5, 10)),
            [self.objs[1]],
        )

    def test_not_gt(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__not_gt=NumericRange(5, 10)),
            [self.objs[0], self.objs[2]],
        )

    def test_adjacent_to(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__adjacent_to=NumericRange(0, 5)),
            [self.objs[1], self.objs[2]],
        )

    def test_startswith(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__startswith=0),
            [self.objs[0]],
        )

    def test_endswith(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__endswith=0),
            [self.objs[2]],
        )

    def test_startswith_chaining(self):
        self.assertSequenceEqual(
            RangesModel.objects.filter(ints__startswith__gte=0),
            [self.objs[0], self.objs[1]],
        )

    def test_bound_type(self):
        decimals = RangesModel.objects.bulk_create(
            [
                RangesModel(decimals=NumericRange(None, 10)),
                RangesModel(decimals=NumericRange(10, None)),
                RangesModel(decimals=NumericRange(5, 15)),
                RangesModel(decimals=NumericRange(5, 15, "(]")),
            ]
        )
        tests = [
            ("lower_inc", True, [decimals[1], decimals[2]]),
            ("lower_inc", False, [decimals[0], decimals[3]]),
            ("lower_inf", True, [decimals[0]]),
            ("lower_inf", False, [decimals[1], decimals[2], decimals[3]]),
            ("upper_inc", True, [decimals[3]]),
            ("upper_inc", False, [decimals[0], decimals[1], decimals[2]]),
            ("upper_inf", True, [decimals[1]]),
            ("upper_inf", False, [decimals[0], decimals[2], decimals[3]]),
        ]
        for lookup, filter_arg, excepted_result in tests:
            with self.subTest(lookup=lookup, filter_arg=filter_arg):
                self.assertSequenceEqual(
                    RangesModel.objects.filter(**{"decimals__%s" % lookup: filter_arg}),
                    excepted_result,
                )


class TestQueryingWithRanges(PostgreSQLTestCase):
    def test_date_range(self):
        objs = [
            RangeLookupsModel.objects.create(date="2015-01-01"),
            RangeLookupsModel.objects.create(date="2015-05-05"),
        ]
        self.assertSequenceEqual(
            RangeLookupsModel.objects.filter(
                date__contained_by=DateRange("2015-01-01", "2015-05-04")
            ),
            [objs[0]],
        )

    def test_date_range_datetime_field(self):
        """

        Tests the functionality of filtering datetime fields by a date range.

        This test case verifies that objects with a datetime field can be filtered based on a specified date range,
        using the `contained_by` lookup type. The test creates sample objects and asserts that only the objects
        with a timestamp within the given date range are successfully retrieved.

        The date range is defined from the start of the range to one day before the end of the range, allowing for 
        inclusive filtering of dates that fall within this range.

        """
        objs = [
            RangeLookupsModel.objects.create(timestamp="2015-01-01"),
            RangeLookupsModel.objects.create(timestamp="2015-05-05"),
        ]
        self.assertSequenceEqual(
            RangeLookupsModel.objects.filter(
                timestamp__date__contained_by=DateRange("2015-01-01", "2015-05-04")
            ),
            [objs[0]],
        )

    def test_datetime_range(self):
        """

        Tests the functionality of the DateTimeTZRange lookup to filter objects based on a specified date and time range.

        The test creates two objects with different timestamps and then uses the contained_by lookup to filter objects
        that fall within a specified range. It asserts that only the object whose timestamp is fully contained within
        the given range is returned in the query results.

        This test ensures the lookup correctly identifies objects that fall within a specified datetime range, including
        objects that are at the start of the range but excludes objects that are outside the range or at the end of the range.

        """
        objs = [
            RangeLookupsModel.objects.create(timestamp="2015-01-01T09:00:00"),
            RangeLookupsModel.objects.create(timestamp="2015-05-05T17:00:00"),
        ]
        self.assertSequenceEqual(
            RangeLookupsModel.objects.filter(
                timestamp__contained_by=DateTimeTZRange(
                    "2015-01-01T09:00", "2015-05-04T23:55"
                )
            ),
            [objs[0]],
        )

    def test_small_integer_field_contained_by(self):
        """
        Tests that the 'contained_by' lookup for a SmallIntegerField correctly filters objects. 

        This test case checks if an object with a small integer value is contained within a specified numeric range. The range is defined by a lower and upper bound, and the test verifies that only the object whose small integer value falls within this range is returned. The test helps ensure that the 'contained_by' lookup is functioning as expected for small integer fields.
        """
        objs = [
            RangeLookupsModel.objects.create(small_integer=8),
            RangeLookupsModel.objects.create(small_integer=4),
            RangeLookupsModel.objects.create(small_integer=-1),
        ]
        self.assertSequenceEqual(
            RangeLookupsModel.objects.filter(
                small_integer__contained_by=NumericRange(4, 6)
            ),
            [objs[1]],
        )

    def test_integer_range(self):
        """
        Checks if the ``integer__contained_by`` lookup type correctly filters objects within a specified numeric range.

        :returns: None
        :raises: AssertionError if the filtered objects do not match the expected sequence
        """
        objs = [
            RangeLookupsModel.objects.create(integer=5),
            RangeLookupsModel.objects.create(integer=99),
            RangeLookupsModel.objects.create(integer=-1),
        ]
        self.assertSequenceEqual(
            RangeLookupsModel.objects.filter(integer__contained_by=NumericRange(1, 98)),
            [objs[0]],
        )

    def test_biginteger_range(self):
        objs = [
            RangeLookupsModel.objects.create(big_integer=5),
            RangeLookupsModel.objects.create(big_integer=99),
            RangeLookupsModel.objects.create(big_integer=-1),
        ]
        self.assertSequenceEqual(
            RangeLookupsModel.objects.filter(
                big_integer__contained_by=NumericRange(1, 98)
            ),
            [objs[0]],
        )

    def test_decimal_field_contained_by(self):
        """

        Tests the decimal_field__contained_by lookup type for decimal fields.

        This test case verifies that the contained_by lookup correctly filters model instances
        based on whether their decimal field value falls within a specified numeric range.

        The test creates several model instances with different decimal field values and then
        checks that the filter correctly identifies the instances that have values within the
        given range, and excludes those that are outside of it.

        """
        objs = [
            RangeLookupsModel.objects.create(decimal_field=Decimal("1.33")),
            RangeLookupsModel.objects.create(decimal_field=Decimal("2.88")),
            RangeLookupsModel.objects.create(decimal_field=Decimal("99.17")),
        ]
        self.assertSequenceEqual(
            RangeLookupsModel.objects.filter(
                decimal_field__contained_by=NumericRange(
                    Decimal("1.89"), Decimal("7.91")
                ),
            ),
            [objs[1]],
        )

    def test_float_range(self):
        objs = [
            RangeLookupsModel.objects.create(float=5),
            RangeLookupsModel.objects.create(float=99),
            RangeLookupsModel.objects.create(float=-1),
        ]
        self.assertSequenceEqual(
            RangeLookupsModel.objects.filter(float__contained_by=NumericRange(1, 98)),
            [objs[0]],
        )

    def test_small_auto_field_contained_by(self):
        """
        Tests that the contained_by lookup type returns correct results when filtering over a range of SmallAutoField IDs.

        The test case creates multiple SmallAutoFieldModel objects, then uses a NumericRange to filter the objects where the ID is contained within a specified range, verifying that the returned sequence matches the expected subset of objects.
        """
        objs = SmallAutoFieldModel.objects.bulk_create(
            [SmallAutoFieldModel() for i in range(1, 5)]
        )
        self.assertSequenceEqual(
            SmallAutoFieldModel.objects.filter(
                id__contained_by=NumericRange(objs[1].pk, objs[3].pk),
            ),
            objs[1:3],
        )

    def test_auto_field_contained_by(self):
        """

        Tests the functionality of the 'contained_by' lookup on an auto field.

        This test creates multiple instances of RangeLookupsModel, then filters the instances
        to only include those whose id falls within a specified numeric range. The test
        verifies that the filtered results match the expected sequence of objects.

        """
        objs = RangeLookupsModel.objects.bulk_create(
            [RangeLookupsModel() for i in range(1, 5)]
        )
        self.assertSequenceEqual(
            RangeLookupsModel.objects.filter(
                id__contained_by=NumericRange(objs[1].pk, objs[3].pk),
            ),
            objs[1:3],
        )

    def test_big_auto_field_contained_by(self):
        objs = BigAutoFieldModel.objects.bulk_create(
            [BigAutoFieldModel() for i in range(1, 5)]
        )
        self.assertSequenceEqual(
            BigAutoFieldModel.objects.filter(
                id__contained_by=NumericRange(objs[1].pk, objs[3].pk),
            ),
            objs[1:3],
        )

    def test_f_ranges(self):
        """
        Tests the functionality of filtering RangeLookupsModel instances based on the 'float' field being contained within the 'decimals' range of their parent RangesModel instance.

            Specifically, this test case checks that objects are correctly filtered when their 'float' value falls within or outside the defined numeric range of the parent object.

            The test creates a parent RangesModel instance with a numeric range, and then creates two RangeLookupsModel instances with different 'float' values. It then verifies that the filter operation correctly returns the object whose 'float' value is contained within the parent's range, while excluding the object whose value falls outside this range.
        """
        parent = RangesModel.objects.create(decimals=NumericRange(0, 10))
        objs = [
            RangeLookupsModel.objects.create(float=5, parent=parent),
            RangeLookupsModel.objects.create(float=99, parent=parent),
        ]
        self.assertSequenceEqual(
            RangeLookupsModel.objects.filter(float__contained_by=F("parent__decimals")),
            [objs[0]],
        )

    def test_exclude(self):
        """
        Tests the exclude method of the RangeLookupsModel manager to ensure it correctly filters out objects 
        whose float field is within a specified numeric range.

        In this test, the numeric range is set to include all values between 0 and 100 inclusive, and the test 
        verifies that an object with a float value outside this range is not excluded from the results. 
        This checks the correctness of excluding objects based on range lookups in the model's float field.
        """
        objs = [
            RangeLookupsModel.objects.create(float=5),
            RangeLookupsModel.objects.create(float=99),
            RangeLookupsModel.objects.create(float=-1),
        ]
        self.assertSequenceEqual(
            RangeLookupsModel.objects.exclude(float__contained_by=NumericRange(0, 100)),
            [objs[2]],
        )


class TestSerialization(PostgreSQLSimpleTestCase):
    test_data = (
        '[{"fields": {"ints": "{\\"upper\\": \\"10\\", \\"lower\\": \\"0\\", '
        '\\"bounds\\": \\"[)\\"}", "decimals": "{\\"empty\\": true}", '
        '"bigints": null, "timestamps": '
        '"{\\"upper\\": \\"2014-02-02T12:12:12+00:00\\", '
        '\\"lower\\": \\"2014-01-01T00:00:00+00:00\\", \\"bounds\\": \\"[)\\"}", '
        '"timestamps_inner": null, '
        '"timestamps_closed_bounds": "{\\"upper\\": \\"2014-02-02T12:12:12+00:00\\", '
        '\\"lower\\": \\"2014-01-01T00:00:00+00:00\\", \\"bounds\\": \\"()\\"}", '
        '"dates": "{\\"upper\\": \\"2014-02-02\\", \\"lower\\": \\"2014-01-01\\", '
        '\\"bounds\\": \\"[)\\"}", "dates_inner": null }, '
        '"model": "postgres_tests.rangesmodel", "pk": null}]'
    )

    lower_date = datetime.date(2014, 1, 1)
    upper_date = datetime.date(2014, 2, 2)
    lower_dt = datetime.datetime(2014, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    upper_dt = datetime.datetime(2014, 2, 2, 12, 12, 12, tzinfo=datetime.timezone.utc)

    def test_dumping(self):
        """
        Tests the dumping of a RangesModel instance to JSON format.
        Verifies that the resulting JSON data matches the expected output for various numeric and date range fields.
        Checks the serialization of different field types, including integers, decimals, timestamps, and dates, with both open and closed bounds.
        """
        instance = RangesModel(
            ints=NumericRange(0, 10),
            decimals=NumericRange(empty=True),
            timestamps=DateTimeTZRange(self.lower_dt, self.upper_dt),
            timestamps_closed_bounds=DateTimeTZRange(
                self.lower_dt,
                self.upper_dt,
                bounds="()",
            ),
            dates=DateRange(self.lower_date, self.upper_date),
        )
        data = serializers.serialize("json", [instance])
        dumped = json.loads(data)
        for field in ("ints", "dates", "timestamps", "timestamps_closed_bounds"):
            dumped[0]["fields"][field] = json.loads(dumped[0]["fields"][field])
        check = json.loads(self.test_data)
        for field in ("ints", "dates", "timestamps", "timestamps_closed_bounds"):
            check[0]["fields"][field] = json.loads(check[0]["fields"][field])

        self.assertEqual(dumped, check)

    def test_loading(self):
        """
        Tests the loading of an instance from JSON data, verifying that its attributes, including numeric ranges, decimal ranges, integer values, date ranges, and timestamp ranges, are correctly deserialized. 

        The test checks that the deserialized instance's attributes match the expected values, including empty ranges, none values, and bounds for date and timestamp ranges.
        """
        instance = list(serializers.deserialize("json", self.test_data))[0].object
        self.assertEqual(instance.ints, NumericRange(0, 10))
        self.assertEqual(instance.decimals, NumericRange(empty=True))
        self.assertIsNone(instance.bigints)
        self.assertEqual(instance.dates, DateRange(self.lower_date, self.upper_date))
        self.assertEqual(
            instance.timestamps, DateTimeTZRange(self.lower_dt, self.upper_dt)
        )
        self.assertEqual(
            instance.timestamps_closed_bounds,
            DateTimeTZRange(self.lower_dt, self.upper_dt, bounds="()"),
        )

    def test_serialize_range_with_null(self):
        instance = RangesModel(ints=NumericRange(None, 10))
        data = serializers.serialize("json", [instance])
        new_instance = list(serializers.deserialize("json", data))[0].object
        self.assertEqual(new_instance.ints, NumericRange(None, 10))

        instance = RangesModel(ints=NumericRange(10, None))
        data = serializers.serialize("json", [instance])
        new_instance = list(serializers.deserialize("json", data))[0].object
        self.assertEqual(new_instance.ints, NumericRange(10, None))


class TestChecks(PostgreSQLSimpleTestCase):
    def test_choices_tuple_list(self):
        class Model(PostgreSQLModel):
            field = pg_fields.IntegerRangeField(
                choices=[
                    ["1-50", [((1, 25), "1-25"), ([26, 50], "26-50")]],
                    ((51, 100), "51-100"),
                ],
            )

        self.assertEqual(Model._meta.get_field("field").check(), [])


class TestValidators(PostgreSQLSimpleTestCase):
    def test_max(self):
        """
        Tests the RangeMaxValueValidator to ensure it correctly enforces a maximum value constraint on a numeric range.

        The test case verifies that the validator allows a numeric range with an upper bound that does not exceed the specified maximum value.
        It also checks that the validator raises a ValidationError with the expected message and code when the upper bound exceeds the maximum value, 
        including the case where the upper bound is not specified (i.e., None).
        """
        validator = RangeMaxValueValidator(5)
        validator(NumericRange(0, 5))
        msg = "Ensure that the upper bound of the range is not greater than 5."
        with self.assertRaises(exceptions.ValidationError) as cm:
            validator(NumericRange(0, 10))
        self.assertEqual(cm.exception.messages[0], msg)
        self.assertEqual(cm.exception.code, "max_value")
        with self.assertRaisesMessage(exceptions.ValidationError, msg):
            validator(NumericRange(0, None))  # an unbound range

    def test_min(self):
        """

        Tests the RangeMinValueValidator for numeric ranges.

        Validates that the lower bound of a numeric range is not less than the
        specified minimum value. If the lower bound is less than the minimum,
        it raises a ValidationError with a corresponding error message and code.

        Verifies the validator's behavior for both cases: when the lower bound
        is less than the minimum value and when it is None (undefined).

        """
        validator = RangeMinValueValidator(5)
        validator(NumericRange(10, 15))
        msg = "Ensure that the lower bound of the range is not less than 5."
        with self.assertRaises(exceptions.ValidationError) as cm:
            validator(NumericRange(0, 10))
        self.assertEqual(cm.exception.messages[0], msg)
        self.assertEqual(cm.exception.code, "min_value")
        with self.assertRaisesMessage(exceptions.ValidationError, msg):
            validator(NumericRange(None, 10))  # an unbound range


class TestFormField(PostgreSQLSimpleTestCase):
    def test_valid_integer(self):
        """

        Tests the validation of a valid integer range for the IntegerRangeField.

        This test case verifies that the clean method of the IntegerRangeField
        correctly processes a list of strings representing integers and returns a
        NumericRange object with the expected lower and upper bounds.

        The test checks if the cleaned value matches the expected NumericRange object,
        ensuring that the field validates and converts the input correctly.

        """
        field = pg_forms.IntegerRangeField()
        value = field.clean(["1", "2"])
        self.assertEqual(value, NumericRange(1, 2))

    def test_valid_decimal(self):
        """
        Tests the cleaning of a valid decimal range value in a DecimalRangeField.

        Checks that the field correctly interprets and returns a NumericRange object 
        with Decimal values when provided with a list of valid decimal strings.

        The test ensures that the DecimalRangeField functionality is working as expected, 
        allowing users to enter decimal range values in a valid format and receiving 
        the corresponding NumericRange object in return.
        """
        field = pg_forms.DecimalRangeField()
        value = field.clean(["1.12345", "2.001"])
        self.assertEqual(value, NumericRange(Decimal("1.12345"), Decimal("2.001")))

    def test_valid_timestamps(self):
        field = pg_forms.DateTimeRangeField()
        value = field.clean(["01/01/2014 00:00:00", "02/02/2014 12:12:12"])
        lower = datetime.datetime(2014, 1, 1, 0, 0, 0)
        upper = datetime.datetime(2014, 2, 2, 12, 12, 12)
        self.assertEqual(value, DateTimeTZRange(lower, upper))

    def test_valid_dates(self):
        field = pg_forms.DateRangeField()
        value = field.clean(["01/01/2014", "02/02/2014"])
        lower = datetime.date(2014, 1, 1)
        upper = datetime.date(2014, 2, 2)
        self.assertEqual(value, DateRange(lower, upper))

    def test_using_split_datetime_widget(self):
        """
        Tests the rendering and validation of a SplitDateTimeRangeField using a SplitForm.

        This function verifies that the field is correctly displayed as a set of four input fields 
        (a start date, a start time, an end date, and an end time), and that valid input data 
        is correctly converted into a DateTimeTZRange object.
        """
        class SplitDateTimeRangeField(pg_forms.DateTimeRangeField):
            base_field = forms.SplitDateTimeField

        class SplitForm(forms.Form):
            field = SplitDateTimeRangeField()

        form = SplitForm()
        self.assertHTMLEqual(
            str(form),
            """
            <div>
                <fieldset>
                    <legend>Field:</legend>
                    <input id="id_field_0_0" name="field_0_0" type="text">
                    <input id="id_field_0_1" name="field_0_1" type="text">
                    <input id="id_field_1_0" name="field_1_0" type="text">
                    <input id="id_field_1_1" name="field_1_1" type="text">
                </fieldset>
            </div>
        """,
        )
        form = SplitForm(
            {
                "field_0_0": "01/01/2014",
                "field_0_1": "00:00:00",
                "field_1_0": "02/02/2014",
                "field_1_1": "12:12:12",
            }
        )
        self.assertTrue(form.is_valid())
        lower = datetime.datetime(2014, 1, 1, 0, 0, 0)
        upper = datetime.datetime(2014, 2, 2, 12, 12, 12)
        self.assertEqual(form.cleaned_data["field"], DateTimeTZRange(lower, upper))

    def test_none(self):
        """
        .. method:: test_none()

           Tests that the :class:`IntegerRangeField` correctly handles empty input when the field is not required.

           Verifies that when an empty list is provided as input to the field's :meth:`clean` method, the method returns :const:`None` as expected.
        """
        field = pg_forms.IntegerRangeField(required=False)
        value = field.clean(["", ""])
        self.assertIsNone(value)

    def test_datetime_form_as_table(self):
        class DateTimeRangeForm(forms.Form):
            datetime_field = pg_forms.DateTimeRangeField(show_hidden_initial=True)

        form = DateTimeRangeForm()
        self.assertHTMLEqual(
            form.as_table(),
            """
            <tr><th>
            <label>Datetime field:</label>
            </th><td>
            <input type="text" name="datetime_field_0" id="id_datetime_field_0">
            <input type="text" name="datetime_field_1" id="id_datetime_field_1">
            <input type="hidden" name="initial-datetime_field_0"
            id="initial-id_datetime_field_0">
            <input type="hidden" name="initial-datetime_field_1"
            id="initial-id_datetime_field_1">
            </td></tr>
            """,
        )
        form = DateTimeRangeForm(
            {
                "datetime_field_0": "2010-01-01 11:13:00",
                "datetime_field_1": "2020-12-12 16:59:00",
            }
        )
        self.assertHTMLEqual(
            form.as_table(),
            """
            <tr><th>
            <label>Datetime field:</label>
            </th><td>
            <input type="text" name="datetime_field_0"
            value="2010-01-01 11:13:00" id="id_datetime_field_0">
            <input type="text" name="datetime_field_1"
            value="2020-12-12 16:59:00" id="id_datetime_field_1">
            <input type="hidden" name="initial-datetime_field_0"
            value="2010-01-01 11:13:00" id="initial-id_datetime_field_0">
            <input type="hidden" name="initial-datetime_field_1"
            value="2020-12-12 16:59:00" id="initial-id_datetime_field_1"></td></tr>
            """,
        )

    def test_datetime_form_initial_data(self):
        """

        Tests the behavior of a DateTimeRangeField form when the initial data is provided.

        This test case verifies that the form correctly determines whether its data has changed
        when compared to the initial data. It checks the form's has_changed method in two scenarios:
        when the initial data differs from the current data, and when the initial data matches the current data.

        """
        class DateTimeRangeForm(forms.Form):
            datetime_field = pg_forms.DateTimeRangeField(show_hidden_initial=True)

        data = QueryDict(mutable=True)
        data.update(
            {
                "datetime_field_0": "2010-01-01 11:13:00",
                "datetime_field_1": "",
                "initial-datetime_field_0": "2010-01-01 10:12:00",
                "initial-datetime_field_1": "",
            }
        )
        form = DateTimeRangeForm(data=data)
        self.assertTrue(form.has_changed())

        data["initial-datetime_field_0"] = "2010-01-01 11:13:00"
        form = DateTimeRangeForm(data=data)
        self.assertFalse(form.has_changed())

    def test_rendering(self):
        """

        Tests the rendering of the IntegerRangeField in a form.

        Verifies that the IntegerRangeField is correctly rendered as two number input fields
        within a fieldset in the HTML representation of the form.

        The test checks for the presence of a div element containing a fieldset with a legend,
        and two input fields of type number, with the expected id and name attributes.

        """
        class RangeForm(forms.Form):
            ints = pg_forms.IntegerRangeField()

        self.assertHTMLEqual(
            str(RangeForm()),
            """
        <div>
            <fieldset>
                <legend>Ints:</legend>
                <input id="id_ints_0" name="ints_0" type="number">
                <input id="id_ints_1" name="ints_1" type="number">
            </fieldset>
        </div>
        """,
        )

    def test_integer_lower_bound_higher(self):
        """
        Tests that the lower bound of an integer range cannot be higher than the upper bound.

        Verifies that a :class:`ValidationError` is raised when attempting to set the start of the range greater than the end, 
        with a specific error message indicating a bound ordering issue and a corresponding error code.
        """
        field = pg_forms.IntegerRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["10", "2"])
        self.assertEqual(
            cm.exception.messages[0],
            "The start of the range must not exceed the end of the range.",
        )
        self.assertEqual(cm.exception.code, "bound_ordering")

    def test_integer_open(self):
        """

        Tests that an empty lower bound and a lower bound of '0' are properly cleaned to a NumericRange object.

        The test case checks the behavior of the IntegerRangeField when given an empty string as the lower bound and '0' as the upper bound.
        It verifies that the clean method correctly returns a NumericRange object with None as the lower bound and 0 as the upper bound.

        """
        field = pg_forms.IntegerRangeField()
        value = field.clean(["", "0"])
        self.assertEqual(value, NumericRange(None, 0))

    def test_integer_incorrect_data_type(self):
        field = pg_forms.IntegerRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean("1")
        self.assertEqual(cm.exception.messages[0], "Enter two whole numbers.")
        self.assertEqual(cm.exception.code, "invalid")

    def test_integer_invalid_lower(self):
        """
        Tests that the IntegerRangeField validation correctly raises an error when the lower bound is not a valid integer.
        """
        field = pg_forms.IntegerRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["a", "2"])
        self.assertEqual(cm.exception.messages[0], "Enter a whole number.")

    def test_integer_invalid_upper(self):
        """
        Tests that the IntegerRangeField raises a ValidationError when given an invalid upper bound that is not a whole number.
        """
        field = pg_forms.IntegerRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["1", "b"])
        self.assertEqual(cm.exception.messages[0], "Enter a whole number.")

    def test_integer_required(self):
        """

        Tests the required validation of an IntegerRangeField.

        Verifies that when the field is marked as required, it correctly raises a 
        ValidationError when no input is provided, and that it correctly handles 
        partial input, setting the upper bound to None when only the lower bound 
        is provided.

        The test also checks the error message raised when the field is not provided, 
        ensuring it matches the expected 'This field is required.' message.

        """
        field = pg_forms.IntegerRangeField(required=True)
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["", ""])
        self.assertEqual(cm.exception.messages[0], "This field is required.")
        value = field.clean([1, ""])
        self.assertEqual(value, NumericRange(1, None))

    def test_decimal_lower_bound_higher(self):
        """
        Tests that the start value of a DecimalRangeField does not exceed the end value.

        Verifies that attempting to set the lower bound of the range higher than the upper bound results in a ValidationError.
        The error message indicates that the start of the range must not be greater than the end, and the error code is 'bound_ordering'.
        """
        field = pg_forms.DecimalRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["1.8", "1.6"])
        self.assertEqual(
            cm.exception.messages[0],
            "The start of the range must not exceed the end of the range.",
        )
        self.assertEqual(cm.exception.code, "bound_ordering")

    def test_decimal_open(self):
        """
        darf not be used here as it would make it seem like we are explaining the function itself, it's more about providing proper usage comments. 
        Tests the DecimalRangeField's ability to handle incomplete input with an open ended range.

        The test checks that when the lower bound of the range is not provided, 
        the upper bound is correctly parsed and the lower bound is set to None.
        """
        field = pg_forms.DecimalRangeField()
        value = field.clean(["", "3.1415926"])
        self.assertEqual(value, NumericRange(None, Decimal("3.1415926")))

    def test_decimal_incorrect_data_type(self):
        """

        Test that the DecimalRangeField rejects single decimal numbers.

        Verifies that an error is raised when attempting to clean a single decimal value.
        The expected error message is 'Enter two numbers.' and the error code is 'invalid',
        indicating that the input data type is not a valid range of two decimal numbers.

        """
        field = pg_forms.DecimalRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean("1.6")
        self.assertEqual(cm.exception.messages[0], "Enter two numbers.")
        self.assertEqual(cm.exception.code, "invalid")

    def test_decimal_invalid_lower(self):
        """
        Tests that the DecimalRangeField raises a ValidationError when given an invalid lower value, such as a string that cannot be converted to a decimal number. Verifies that the error message correctly instructs the user to enter a number.
        """
        field = pg_forms.DecimalRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["a", "3.1415926"])
        self.assertEqual(cm.exception.messages[0], "Enter a number.")

    def test_decimal_invalid_upper(self):
        field = pg_forms.DecimalRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["1.61803399", "b"])
        self.assertEqual(cm.exception.messages[0], "Enter a number.")

    def test_decimal_required(self):
        """
        Tests that the DecimalRangeField enforces requirement when initialized with required=True.

        Verifies that attempting to clean an empty field raises a ValidationError with a 
        correct error message and that successfully cleaning the field returns the expected 
        NumericRange value for a valid input. Ensures that if only the first value is provided, 
        the second value defaults to None in the resulting NumericRange object.
        """
        field = pg_forms.DecimalRangeField(required=True)
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["", ""])
        self.assertEqual(cm.exception.messages[0], "This field is required.")
        value = field.clean(["1.61803399", ""])
        self.assertEqual(value, NumericRange(Decimal("1.61803399"), None))

    def test_date_lower_bound_higher(self):
        """
        Tests that the start date of a date range does not exceed the end date.

        Verifies that a :class:`ValidationError` is raised when the start date is later than the end date, 
        with a specific error message and code indicating bound ordering issue.

        Ensures that the validation logic for date ranges is enforced correctly to prevent invalid date ranges.

        """
        field = pg_forms.DateRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["2013-04-09", "1976-04-16"])
        self.assertEqual(
            cm.exception.messages[0],
            "The start of the range must not exceed the end of the range.",
        )
        self.assertEqual(cm.exception.code, "bound_ordering")

    def test_date_open(self):
        """

        Tests the date open functionality of the DateRangeField.

        Verifies that when the start date of a date range is empty or not provided, 
        the `clean` method correctly processes the end date and returns a DateRange object 
        with the start date set to None.

        """
        field = pg_forms.DateRangeField()
        value = field.clean(["", "2013-04-09"])
        self.assertEqual(value, DateRange(None, datetime.date(2013, 4, 9)))

    def test_date_incorrect_data_type(self):
        field = pg_forms.DateRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean("1")
        self.assertEqual(cm.exception.messages[0], "Enter two valid dates.")
        self.assertEqual(cm.exception.code, "invalid")

    def test_date_invalid_lower(self):
        """
        Tests that the DateRangeField raises a ValidationError when given an invalid date as its lower bound.

        The function verifies that attempting to clean a date range with an invalid lower date value results in a ValidationError,
        with the expected error message indicating that a valid date must be entered.
        """
        field = pg_forms.DateRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["a", "2013-04-09"])
        self.assertEqual(cm.exception.messages[0], "Enter a valid date.")

    def test_date_invalid_upper(self):
        """
        Tests that the date validation fails when an invalid date is provided in the upper bound of a date range.

        This test checks that a ValidationError is raised when the upper bound of a date range is not a valid date.
        It verifies that the error message is 'Enter a valid date.', indicating that the input could not be parsed as a date.
        The test case covers a common scenario where user input may not conform to the expected date format, ensuring the field's validation behaves as expected.
        """
        field = pg_forms.DateRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["2013-04-09", "b"])
        self.assertEqual(cm.exception.messages[0], "Enter a valid date.")

    def test_date_required(self):
        """

        Tests that a DateRangeField with required=True enforces the requirement.

        The test checks that attempting to clean the field with empty input raises a
        ValidationError with the expected message. It also verifies that providing
        a valid start date, with or without an end date, results in a properly
        constructed DateRange object.

        """
        field = pg_forms.DateRangeField(required=True)
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["", ""])
        self.assertEqual(cm.exception.messages[0], "This field is required.")
        value = field.clean(["1976-04-16", ""])
        self.assertEqual(value, DateRange(datetime.date(1976, 4, 16), None))

    def test_date_has_changed_first(self):
        self.assertTrue(
            pg_forms.DateRangeField().has_changed(
                ["2010-01-01", "2020-12-12"],
                ["2010-01-31", "2020-12-12"],
            )
        )

    def test_date_has_changed_last(self):
        self.assertTrue(
            pg_forms.DateRangeField().has_changed(
                ["2010-01-01", "2020-12-12"],
                ["2010-01-01", "2020-12-31"],
            )
        )

    def test_datetime_lower_bound_higher(self):
        """

        Tests that a ValidationError is raised when the lower bound of a DateTimeRangeField is higher than the upper bound.

        The function creates a DateTimeRangeField instance and attempts to clean a range where the start date/time is later than the end date/time.
        It verifies that the raised exception has the expected error message and code, ensuring that the field's validation works correctly.

        """
        field = pg_forms.DateTimeRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["2006-10-25 14:59", "2006-10-25 14:58"])
        self.assertEqual(
            cm.exception.messages[0],
            "The start of the range must not exceed the end of the range.",
        )
        self.assertEqual(cm.exception.code, "bound_ordering")

    def test_datetime_open(self):
        """

        Tests the cleaning functionality of a DateTimeRangeField when provided with a partial date range.

        This test case verifies that when an empty start date and a valid end date are provided, 
        the cleaned value is a DateTimeTZRange object with a null start date and the specified end date.

        The purpose of this test is to ensure that the DateTimeRangeField behaves as expected when 
        handling incomplete date ranges, specifically when the start date is missing.

        """
        field = pg_forms.DateTimeRangeField()
        value = field.clean(["", "2013-04-09 11:45"])
        self.assertEqual(
            value, DateTimeTZRange(None, datetime.datetime(2013, 4, 9, 11, 45))
        )

    def test_datetime_incorrect_data_type(self):
        field = pg_forms.DateTimeRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean("2013-04-09 11:45")
        self.assertEqual(cm.exception.messages[0], "Enter two valid date/times.")
        self.assertEqual(cm.exception.code, "invalid")

    def test_datetime_invalid_lower(self):
        field = pg_forms.DateTimeRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["45", "2013-04-09 11:45"])
        self.assertEqual(cm.exception.messages[0], "Enter a valid date/time.")

    def test_datetime_invalid_upper(self):
        """

        Tests that the DateTimeRangeField raises a ValidationError when the upper date/time value is invalid.

        Ensures that the field correctly handles cases where the end of the date/time range is not a valid date/time string.

        """
        field = pg_forms.DateTimeRangeField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["2013-04-09 11:45", "sweet pickles"])
        self.assertEqual(cm.exception.messages[0], "Enter a valid date/time.")

    def test_datetime_required(self):
        """
        Tests that the DateTimeRangeField with required=True validation behaves correctly.

        The test checks that a ValidationError is raised when both the start and end dates are empty.
        It also verifies that when only the start date is provided, the field returns a DateTimeTZRange object with the start date set and the end date set to None.

        The expected error message for an empty field is 'This field is required.'
        """
        field = pg_forms.DateTimeRangeField(required=True)
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["", ""])
        self.assertEqual(cm.exception.messages[0], "This field is required.")
        value = field.clean(["2013-04-09 11:45", ""])
        self.assertEqual(
            value, DateTimeTZRange(datetime.datetime(2013, 4, 9, 11, 45), None)
        )

    @override_settings(USE_TZ=True, TIME_ZONE="Africa/Johannesburg")
    def test_datetime_prepare_value(self):
        field = pg_forms.DateTimeRangeField()
        value = field.prepare_value(
            DateTimeTZRange(
                datetime.datetime(2015, 5, 22, 16, 6, 33, tzinfo=datetime.timezone.utc),
                None,
            )
        )
        self.assertEqual(value, [datetime.datetime(2015, 5, 22, 18, 6, 33), None])

    def test_datetime_has_changed_first(self):
        self.assertTrue(
            pg_forms.DateTimeRangeField().has_changed(
                ["2010-01-01 00:00", "2020-12-12 00:00"],
                ["2010-01-31 23:00", "2020-12-12 00:00"],
            )
        )

    def test_datetime_has_changed_last(self):
        self.assertTrue(
            pg_forms.DateTimeRangeField().has_changed(
                ["2010-01-01 00:00", "2020-12-12 00:00"],
                ["2010-01-01 00:00", "2020-12-31 23:00"],
            )
        )

    def test_model_field_formfield_integer(self):
        model_field = pg_fields.IntegerRangeField()
        form_field = model_field.formfield()
        self.assertIsInstance(form_field, pg_forms.IntegerRangeField)
        self.assertEqual(form_field.range_kwargs, {})

    def test_model_field_formfield_biginteger(self):
        model_field = pg_fields.BigIntegerRangeField()
        form_field = model_field.formfield()
        self.assertIsInstance(form_field, pg_forms.IntegerRangeField)
        self.assertEqual(form_field.range_kwargs, {})

    def test_model_field_formfield_float(self):
        model_field = pg_fields.DecimalRangeField(default_bounds="()")
        form_field = model_field.formfield()
        self.assertIsInstance(form_field, pg_forms.DecimalRangeField)
        self.assertEqual(form_field.range_kwargs, {"bounds": "()"})

    def test_model_field_formfield_date(self):
        model_field = pg_fields.DateRangeField()
        form_field = model_field.formfield()
        self.assertIsInstance(form_field, pg_forms.DateRangeField)
        self.assertEqual(form_field.range_kwargs, {})

    def test_model_field_formfield_datetime(self):
        """
        Tests whether a model's DateTimeRangeField correctly creates a form field.

        The function verifies that the form field created from the model field is an instance of DateTimeRangeField and 
        that it uses the canonical range bounds as its range keyword arguments. This ensures that the DateTimeRangeField 
        behaves as expected when generating a form field, providing the correct bounds for date and time input.
        """
        model_field = pg_fields.DateTimeRangeField()
        form_field = model_field.formfield()
        self.assertIsInstance(form_field, pg_forms.DateTimeRangeField)
        self.assertEqual(
            form_field.range_kwargs,
            {"bounds": pg_fields.ranges.CANONICAL_RANGE_BOUNDS},
        )

    def test_model_field_formfield_datetime_default_bounds(self):
        model_field = pg_fields.DateTimeRangeField(default_bounds="[]")
        form_field = model_field.formfield()
        self.assertIsInstance(form_field, pg_forms.DateTimeRangeField)
        self.assertEqual(form_field.range_kwargs, {"bounds": "[]"})

    def test_model_field_with_default_bounds(self):
        field = pg_forms.DateTimeRangeField(default_bounds="[]")
        value = field.clean(["2014-01-01 00:00:00", "2014-02-03 12:13:14"])
        lower = datetime.datetime(2014, 1, 1, 0, 0, 0)
        upper = datetime.datetime(2014, 2, 3, 12, 13, 14)
        self.assertEqual(value, DateTimeTZRange(lower, upper, "[]"))

    def test_has_changed(self):
        for field, value in (
            (pg_forms.DateRangeField(), ["2010-01-01", "2020-12-12"]),
            (pg_forms.DateTimeRangeField(), ["2010-01-01 11:13", "2020-12-12 14:52"]),
            (pg_forms.IntegerRangeField(), [1, 2]),
            (pg_forms.DecimalRangeField(), ["1.12345", "2.001"]),
        ):
            with self.subTest(field=field.__class__.__name__):
                self.assertTrue(field.has_changed(None, value))
                self.assertTrue(field.has_changed([value[0], ""], value))
                self.assertTrue(field.has_changed(["", value[1]], value))
                self.assertFalse(field.has_changed(value, value))


class TestWidget(PostgreSQLSimpleTestCase):
    def test_range_widget(self):
        """
        Tests the rendering of the DateTimeRangeField widget, ensuring it produces the correct HTML for different input scenarios. 

        This test case covers three scenarios: an empty input, a null input, and a populated DateTimeTZRange object. It verifies that the widget renders the expected HTML structure, including input fields for the start and end dates, with correct naming conventions and formatted date-time values when a DateTimeTZRange object is provided.
        """
        f = pg_forms.ranges.DateTimeRangeField()
        self.assertHTMLEqual(
            f.widget.render("datetimerange", ""),
            '<input type="text" name="datetimerange_0">'
            '<input type="text" name="datetimerange_1">',
        )
        self.assertHTMLEqual(
            f.widget.render("datetimerange", None),
            '<input type="text" name="datetimerange_0">'
            '<input type="text" name="datetimerange_1">',
        )
        dt_range = DateTimeTZRange(
            datetime.datetime(2006, 1, 10, 7, 30), datetime.datetime(2006, 2, 12, 9, 50)
        )
        self.assertHTMLEqual(
            f.widget.render("datetimerange", dt_range),
            '<input type="text" name="datetimerange_0" value="2006-01-10 07:30:00">'
            '<input type="text" name="datetimerange_1" value="2006-02-12 09:50:00">',
        )

    def test_range_widget_render_tuple_value(self):
        """
        Tests the rendering of a DateTimeRangeField widget with a tuple value.

        This test case verifies that the DateTimeRangeField widget correctly renders a tuple of datetime values as two separate HTML input fields.
        The rendered HTML is expected to contain two input fields with the correct name attributes and formatted datetime values. The goal is to ensure that the widget can handle tuple values and produce the expected output for date and time range fields in a user interface. 
        """
        field = pg_forms.ranges.DateTimeRangeField()
        dt_range_tuple = (
            datetime.datetime(2022, 4, 22, 10, 24),
            datetime.datetime(2022, 5, 12, 9, 25),
        )
        self.assertHTMLEqual(
            field.widget.render("datetimerange", dt_range_tuple),
            '<input type="text" name="datetimerange_0" value="2022-04-22 10:24:00">'
            '<input type="text" name="datetimerange_1" value="2022-05-12 09:25:00">',
        )
