import decimal
import enum
import json
import unittest
import uuid

from django import forms
from django.contrib.admin.utils import display_for_field
from django.core import checks, exceptions, serializers, validators
from django.core.exceptions import FieldError
from django.core.management import call_command
from django.db import IntegrityError, connection, models
from django.db.models.expressions import Exists, F, OuterRef, RawSQL, Value
from django.db.models.functions import Cast, JSONObject, Upper
from django.test import TransactionTestCase, override_settings, skipUnlessDBFeature
from django.test.utils import isolate_apps
from django.utils import timezone

from . import PostgreSQLSimpleTestCase, PostgreSQLTestCase, PostgreSQLWidgetTestCase
from .models import (
    ArrayEnumModel,
    ArrayFieldSubclass,
    CharArrayModel,
    DateTimeArrayModel,
    IntegerArrayModel,
    NestedIntegerArrayModel,
    NullableIntegerArrayModel,
    OtherTypesArrayModel,
    PostgreSQLModel,
    Tag,
)

try:
    from django.contrib.postgres.aggregates import ArrayAgg
    from django.contrib.postgres.expressions import ArraySubquery
    from django.contrib.postgres.fields import ArrayField
    from django.contrib.postgres.fields.array import IndexTransform, SliceTransform
    from django.contrib.postgres.forms import (
        SimpleArrayField,
        SplitArrayField,
        SplitArrayWidget,
    )
    from django.db.backends.postgresql.psycopg_any import NumericRange
except ImportError:
    pass


@isolate_apps("postgres_tests")
class BasicTests(PostgreSQLSimpleTestCase):
    def test_get_field_display(self):
        class MyModel(PostgreSQLModel):
            field = ArrayField(
                models.CharField(max_length=16),
                choices=[
                    ["Media", [(["vinyl", "cd"], "Audio")]],
                    (("mp3", "mp4"), "Digital"),
                ],
            )

        tests = (
            (["vinyl", "cd"], "Audio"),
            (("mp3", "mp4"), "Digital"),
            (("a", "b"), "('a', 'b')"),
            (["c", "d"], "['c', 'd']"),
        )
        for value, display in tests:
            with self.subTest(value=value, display=display):
                instance = MyModel(field=value)
                self.assertEqual(instance.get_field_display(), display)

    def test_get_field_display_nested_array(self):
        class MyModel(PostgreSQLModel):
            field = ArrayField(
                ArrayField(models.CharField(max_length=16)),
                choices=[
                    [
                        "Media",
                        [([["vinyl", "cd"], ("x",)], "Audio")],
                    ],
                    ((["mp3"], ("mp4",)), "Digital"),
                ],
            )

        tests = (
            ([["vinyl", "cd"], ("x",)], "Audio"),
            ((["mp3"], ("mp4",)), "Digital"),
            ((("a", "b"), ("c",)), "(('a', 'b'), ('c',))"),
            ([["a", "b"], ["c"]], "[['a', 'b'], ['c']]"),
        )
        for value, display in tests:
            with self.subTest(value=value, display=display):
                instance = MyModel(field=value)
                self.assertEqual(instance.get_field_display(), display)


class TestSaveLoad(PostgreSQLTestCase):
    def test_integer(self):
        instance = IntegerArrayModel(field=[1, 2, 3])
        instance.save()
        loaded = IntegerArrayModel.objects.get()
        self.assertEqual(instance.field, loaded.field)

    def test_char(self):
        """
        Tests the loading and saving of character array fields.

        This function ensures that character arrays are properly persisted and retrieved
        from the database, by creating a model instance with a sample character array,
        saving it, and then reloading the instance to verify that the field values match.

        The test checks for data integrity and consistency between the original and
        retrieved model instances, confirming that the character array is correctly
        serialized and deserialized during the save and load process.
        """
        instance = CharArrayModel(field=["hello", "goodbye"])
        instance.save()
        loaded = CharArrayModel.objects.get()
        self.assertEqual(instance.field, loaded.field)

    def test_dates(self):
        instance = DateTimeArrayModel(
            datetimes=[timezone.now()],
            dates=[timezone.now().date()],
            times=[timezone.now().time()],
        )
        instance.save()
        loaded = DateTimeArrayModel.objects.get()
        self.assertEqual(instance.datetimes, loaded.datetimes)
        self.assertEqual(instance.dates, loaded.dates)
        self.assertEqual(instance.times, loaded.times)

    def test_tuples(self):
        """
        Checks if saving and loading an IntegerArrayModel instance with a tuple field preserves the original tuple value.
        """
        instance = IntegerArrayModel(field=(1,))
        instance.save()
        loaded = IntegerArrayModel.objects.get()
        self.assertSequenceEqual(instance.field, loaded.field)

    def test_integers_passed_as_strings(self):
        # This checks that get_prep_value is deferred properly
        instance = IntegerArrayModel(field=["1"])
        instance.save()
        loaded = IntegerArrayModel.objects.get()
        self.assertEqual(loaded.field, [1])

    def test_default_null(self):
        """
        Tests that the default value for a nullable integer array field is correctly set to null when not provided.

        Verifies that when an instance of the model is saved without specifying a value for the field, the field is loaded as null, and its value remains consistent between the original instance and the reloaded instance from the database.
        """
        instance = NullableIntegerArrayModel()
        instance.save()
        loaded = NullableIntegerArrayModel.objects.get(pk=instance.pk)
        self.assertIsNone(loaded.field)
        self.assertEqual(instance.field, loaded.field)

    def test_null_handling(self):
        """
        Tests the handling of null values in the IntegerArrayModel and NullableIntegerArrayModel classes.

        Checks that a nullable integer array field can be saved and loaded correctly with a null value,
        and that a non-nullable integer array field raises an IntegrityError when attempting to save a null value.
        """
        instance = NullableIntegerArrayModel(field=None)
        instance.save()
        loaded = NullableIntegerArrayModel.objects.get()
        self.assertEqual(instance.field, loaded.field)

        instance = IntegerArrayModel(field=None)
        with self.assertRaises(IntegrityError):
            instance.save()

    def test_nested(self):
        """
        #: Tests the serialization and deserialization of a NestedIntegerArrayModel instance.
         #: 
         #: Verifies that the model's field, which contains a nested array of integers, 
         #: is correctly saved to the database and then retrieved without any data loss or corruption. 
         #: The test ensures that the original and loaded instances have identical field values.
        """
        instance = NestedIntegerArrayModel(field=[[1, 2], [3, 4]])
        instance.save()
        loaded = NestedIntegerArrayModel.objects.get()
        self.assertEqual(instance.field, loaded.field)

    def test_other_array_types(self):
        """

        Tests the serialization and deserialization of an instance of OtherTypesArrayModel.

        Verifies that various array fields, including IPs, UUIDs, decimals, tags, JSON objects, and numeric ranges, 
        are correctly saved to and retrieved from the database. 

        The test creates an instance of OtherTypesArrayModel with sample data, saves it, and then loads it back from the database.
        It then asserts that the original and loaded instances have the same values for each array field.

        """
        instance = OtherTypesArrayModel(
            ips=["192.168.0.1", "::1"],
            uuids=[uuid.uuid4()],
            decimals=[decimal.Decimal(1.25), 1.75],
            tags=[Tag(1), Tag(2), Tag(3)],
            json=[{"a": 1}, {"b": 2}],
            int_ranges=[NumericRange(10, 20), NumericRange(30, 40)],
            bigint_ranges=[
                NumericRange(7000000000, 10000000000),
                NumericRange(50000000000, 70000000000),
            ],
        )
        instance.save()
        loaded = OtherTypesArrayModel.objects.get()
        self.assertEqual(instance.ips, loaded.ips)
        self.assertEqual(instance.uuids, loaded.uuids)
        self.assertEqual(instance.decimals, loaded.decimals)
        self.assertEqual(instance.tags, loaded.tags)
        self.assertEqual(instance.json, loaded.json)
        self.assertEqual(instance.int_ranges, loaded.int_ranges)
        self.assertEqual(instance.bigint_ranges, loaded.bigint_ranges)

    def test_null_from_db_value_handling(self):
        """
        Tests handling of null values loaded from the database for the model's fields. 
        Verifies that when a model instance is refreshed from the database, fields with null values 
        are correctly set to None or appropriate empty values, ensuring data integrity and consistency.
        """
        instance = OtherTypesArrayModel.objects.create(
            ips=["192.168.0.1", "::1"],
            uuids=[uuid.uuid4()],
            decimals=[decimal.Decimal(1.25), 1.75],
            tags=None,
        )
        instance.refresh_from_db()
        self.assertIsNone(instance.tags)
        self.assertEqual(instance.json, [])
        self.assertIsNone(instance.int_ranges)
        self.assertIsNone(instance.bigint_ranges)

    def test_model_set_on_base_field(self):
        """
        Tests the relationship between the model and the base field of the 'field' attribute in the IntegerArrayModel, validating that both the field and its base field are correctly associated with the model.
        """
        instance = IntegerArrayModel()
        field = instance._meta.get_field("field")
        self.assertEqual(field.model, IntegerArrayModel)
        self.assertEqual(field.base_field.model, IntegerArrayModel)

    def test_nested_nullable_base_field(self):
        """

        Tests the functionality of a nullable base field that is nested within an array.

        This test checks if the field can correctly store and retrieve arrays containing null values.

        """
        instance = NullableIntegerArrayModel.objects.create(
            field_nested=[[None, None], [None, None]],
        )
        self.assertEqual(instance.field_nested, [[None, None], [None, None]])


class TestQuerying(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.objs = NullableIntegerArrayModel.objects.bulk_create(
            [
                NullableIntegerArrayModel(order=1, field=[1]),
                NullableIntegerArrayModel(order=2, field=[2]),
                NullableIntegerArrayModel(order=3, field=[2, 3]),
                NullableIntegerArrayModel(order=4, field=[20, 30, 40]),
                NullableIntegerArrayModel(order=5, field=None),
            ]
        )

    def test_empty_list(self):
        """
        Tests that an empty list stored in the field of a NullableIntegerArrayModel instance is correctly retrieved and matches an annotated empty array.

        The test verifies that when an empty list is stored in the field, it can be successfully filtered using an annotated empty array and that the retrieved object's field matches the expected empty list.

        This test case ensures the correct functionality of storing and retrieving empty lists in the model's field, as well as the proper annotation and filtering of empty arrays in database queries.\"\"\"
        ```
        """
        NullableIntegerArrayModel.objects.create(field=[])
        obj = (
            NullableIntegerArrayModel.objects.annotate(
                empty_array=models.Value(
                    [], output_field=ArrayField(models.IntegerField())
                ),
            )
            .filter(field=models.F("empty_array"))
            .get()
        )
        self.assertEqual(obj.field, [])
        self.assertEqual(obj.empty_array, [])

    def test_exact(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__exact=[1]), self.objs[:1]
        )

    def test_exact_null_only_array(self):
        obj = NullableIntegerArrayModel.objects.create(
            field=[None], field_nested=[None, None]
        )
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__exact=[None]), [obj]
        )
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field_nested__exact=[None, None]),
            [obj],
        )

    def test_exact_null_only_nested_array(self):
        obj1 = NullableIntegerArrayModel.objects.create(field_nested=[[None, None]])
        obj2 = NullableIntegerArrayModel.objects.create(
            field_nested=[[None, None], [None, None]],
        )
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(
                field_nested__exact=[[None, None]],
            ),
            [obj1],
        )
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(
                field_nested__exact=[[None, None], [None, None]],
            ),
            [obj2],
        )

    def test_exact_with_expression(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__exact=[Value(1)]),
            self.objs[:1],
        )

    def test_exact_charfield(self):
        instance = CharArrayModel.objects.create(field=["text"])
        self.assertSequenceEqual(
            CharArrayModel.objects.filter(field=["text"]), [instance]
        )

    def test_exact_nested(self):
        instance = NestedIntegerArrayModel.objects.create(field=[[1, 2], [3, 4]])
        self.assertSequenceEqual(
            NestedIntegerArrayModel.objects.filter(field=[[1, 2], [3, 4]]), [instance]
        )

    def test_isnull(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__isnull=True), self.objs[-1:]
        )

    def test_gt(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__gt=[0]), self.objs[:4]
        )

    def test_lt(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__lt=[2]), self.objs[:1]
        )

    def test_in(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__in=[[1], [2]]),
            self.objs[:2],
        )

    def test_in_subquery(self):
        IntegerArrayModel.objects.create(field=[2, 3])
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(
                field__in=IntegerArrayModel.objects.values_list("field", flat=True)
            ),
            self.objs[2:3],
        )

    @unittest.expectedFailure
    def test_in_including_F_object(self):
        # This test asserts that Array objects passed to filters can be
        # constructed to contain F objects. This currently doesn't work as the
        # psycopg mogrify method that generates the ARRAY() syntax is
        # expecting literals, not column references (#27095).
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__in=[[models.F("id")]]),
            self.objs[:2],
        )

    def test_in_as_F_object(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__in=[models.F("field")]),
            self.objs[:4],
        )

    def test_contained_by(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__contained_by=[1, 2]),
            self.objs[:2],
        )

    def test_contained_by_including_F_object(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(
                field__contained_by=[models.F("order"), 2]
            ),
            self.objs[:3],
        )

    def test_contains(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__contains=[2]),
            self.objs[1:3],
        )

    def test_contains_subquery(self):
        """
        Tests the functionality of filtering models based on subqueries within the \"field\" attribute, which contains integer arrays.

        It verifies two main scenarios:

        1. **Contains subquery**: Checks if an object in the database contains a specific value or values returned from a subquery. 
        2. **Exists subquery with contains filter**: Checks if there exists at least one object in the database that contains a value from another model's field, using a subquery with a contains filter.

        This test ensures that both methods of using subqueries to filter objects based on the \"field\" attribute containing specific values return the expected results.
        """
        IntegerArrayModel.objects.create(field=[2, 3])
        inner_qs = IntegerArrayModel.objects.values_list("field", flat=True)
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__contains=inner_qs[:1]),
            self.objs[2:3],
        )
        inner_qs = IntegerArrayModel.objects.filter(field__contains=OuterRef("field"))
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(Exists(inner_qs)),
            self.objs[1:3],
        )

    def test_contains_including_expression(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(
                field__contains=[2, Value(6) / Value(2)],
            ),
            self.objs[2:3],
        )

    def test_icontains(self):
        # Using the __icontains lookup with ArrayField is inefficient.
        """

        Tests that the icontains lookup works correctly for CharArrayModel fields.

        This test verifies that a case-insensitive search for a substring within a CharArrayModel field returns the expected results.

        """
        instance = CharArrayModel.objects.create(field=["FoO"])
        self.assertSequenceEqual(
            CharArrayModel.objects.filter(field__icontains="foo"), [instance]
        )

    def test_contains_charfield(self):
        # Regression for #22907
        self.assertSequenceEqual(
            CharArrayModel.objects.filter(field__contains=["text"]), []
        )

    def test_contained_by_charfield(self):
        self.assertSequenceEqual(
            CharArrayModel.objects.filter(field__contained_by=["text"]), []
        )

    def test_overlap_charfield(self):
        self.assertSequenceEqual(
            CharArrayModel.objects.filter(field__overlap=["text"]), []
        )

    def test_overlap_charfield_including_expression(self):
        """
        Test the overlap lookup type for CharArrayField with expression inclusion.

        This test case verifies that the overlap lookup correctly returns objects
        where the CharArrayField contains any element of the given list, including
        those that match an expression. The test covers case-sensitive and
        case-insensitive matching using database functions.

        It ensures that objects are retrieved if they contain a matching value,
        regardless of the order or case of the elements in the array. The test
        scenario includes multiple objects with overlapping values to demonstrate
        the lookup's behavior in various conditions.
        """
        obj_1 = CharArrayModel.objects.create(field=["TEXT", "lower text"])
        obj_2 = CharArrayModel.objects.create(field=["lower text", "TEXT"])
        CharArrayModel.objects.create(field=["lower text", "text"])
        self.assertSequenceEqual(
            CharArrayModel.objects.filter(
                field__overlap=[
                    Upper(Value("text")),
                    "other",
                ]
            ),
            [obj_1, obj_2],
        )

    def test_overlap_values(self):
        """

        Tests the overlap functionality of the NullableIntegerArrayModel's field.

        The test checks if the field's overlap lookup type correctly retrieves objects
        that have overlapping values with the specified set of values. The test uses a 
        subset of objects (with order less than 3) to generate the set of values to 
        look for overlaps.

        Two variations of the overlap lookup are tested: one using values_list and 
        another using values. The results of both lookups are verified to be equal 
        and to match the expected set of objects.

        """
        qs = NullableIntegerArrayModel.objects.filter(order__lt=3)
        self.assertCountEqual(
            NullableIntegerArrayModel.objects.filter(
                field__overlap=qs.values_list("field"),
            ),
            self.objs[:3],
        )
        self.assertCountEqual(
            NullableIntegerArrayModel.objects.filter(
                field__overlap=qs.values("field"),
            ),
            self.objs[:3],
        )

    def test_lookups_autofield_array(self):
        qs = (
            NullableIntegerArrayModel.objects.filter(
                field__0__isnull=False,
            )
            .values("field__0")
            .annotate(
                arrayagg=ArrayAgg("id"),
            )
            .order_by("field__0")
        )
        tests = (
            ("contained_by", [self.objs[1].pk, self.objs[2].pk, 0], [2]),
            ("contains", [self.objs[2].pk], [2]),
            ("exact", [self.objs[3].pk], [20]),
            ("overlap", [self.objs[1].pk, self.objs[3].pk], [2, 20]),
        )
        for lookup, value, expected in tests:
            with self.subTest(lookup=lookup):
                self.assertSequenceEqual(
                    qs.filter(
                        **{"arrayagg__" + lookup: value},
                    ).values_list("field__0", flat=True),
                    expected,
                )

    @skipUnlessDBFeature("allows_group_by_select_index")
    def test_group_by_order_by_select_index(self):
        with self.assertNumQueries(1) as ctx:
            self.assertSequenceEqual(
                NullableIntegerArrayModel.objects.filter(
                    field__0__isnull=False,
                )
                .values("field__0")
                .annotate(arrayagg=ArrayAgg("id"))
                .order_by("field__0"),
                [
                    {"field__0": 1, "arrayagg": [self.objs[0].pk]},
                    {"field__0": 2, "arrayagg": [self.objs[1].pk, self.objs[2].pk]},
                    {"field__0": 20, "arrayagg": [self.objs[3].pk]},
                ],
            )
        sql = ctx[0]["sql"]
        self.assertIn("GROUP BY 1", sql)
        self.assertIn("ORDER BY 1", sql)

    def test_order_by_arrayagg_index(self):
        qs = (
            NullableIntegerArrayModel.objects.values("order")
            .annotate(ids=ArrayAgg("id"))
            .order_by("-ids__0")
        )
        self.assertQuerySetEqual(
            qs, [{"order": obj.order, "ids": [obj.id]} for obj in reversed(self.objs)]
        )

    def test_index(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__0=2), self.objs[1:3]
        )

    def test_index_chained(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__0__lt=3), self.objs[0:3]
        )

    def test_index_nested(self):
        """

        Tests the indexing of nested integer arrays.

        Verifies that the model's field can be filtered using nested integer array values.
        In this case, it checks if an instance with a nested array [[1, 2], [3, 4]] can be retrieved 
        by filtering on the first element of the first inner array.

        """
        instance = NestedIntegerArrayModel.objects.create(field=[[1, 2], [3, 4]])
        self.assertSequenceEqual(
            NestedIntegerArrayModel.objects.filter(field__0__0=1), [instance]
        )

    @unittest.expectedFailure
    def test_index_used_on_nested_data(self):
        """
        Tests that the index used on nested data correctly retrieves objects.

        This test case verifies that the filtering functionality works as expected when dealing with nested integer arrays.
        It creates an instance of NestedIntegerArrayModel with a nested field, then checks if filtering on this field using the index returns the correct instance.
        """
        instance = NestedIntegerArrayModel.objects.create(field=[[1, 2], [3, 4]])
        self.assertSequenceEqual(
            NestedIntegerArrayModel.objects.filter(field__0=[1, 2]), [instance]
        )

    def test_index_transform_expression(self):
        """

        Tests the functionality of indexed transform expression with a raw SQL query.

        Verifies that the indexed transform applied to a raw SQL expression containing 
        an array value, can be correctly casted and used to filter model instances. 

        Specifically, it checks that an expression which converts a string to an array 
        and then transforms the first element of the array, returns the expected objects 
        when used as a filter condition.

        This test case ensures that the combination of raw SQL expressions, indexed 
        transforms, and output field casting works as expected, allowing for complex 
        query operations on array fields.

        """
        expr = RawSQL("string_to_array(%s, ';')", ["1;2"])
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(
                field__0=Cast(
                    IndexTransform(1, models.IntegerField, expr),
                    output_field=models.IntegerField(),
                ),
            ),
            self.objs[:1],
        )

    def test_index_annotation(self):
        """

        Tests the annotation of the second element of the NullableIntegerArrayModel field.

        This test case verifies that the annotation of the second element of the field
        works correctly, including handling of null values. It checks that the annotated
        values match the expected results.

        """
        qs = NullableIntegerArrayModel.objects.annotate(second=models.F("field__1"))
        self.assertCountEqual(
            qs.values_list("second", flat=True),
            [None, None, None, 3, 30],
        )

    def test_overlap(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__overlap=[1, 2]),
            self.objs[0:3],
        )

    def test_len(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__len__lte=2), self.objs[0:3]
        )

    def test_len_empty_array(self):
        obj = NullableIntegerArrayModel.objects.create(field=[])
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__len=0), [obj]
        )

    def test_slice(self):
        """
        ..: noindex:
         teaser: Tests filtering of NullableIntegerArrayModel instances based on slice notation.

            This function verifies that the filter method correctly returns instances 
            where the specified slice of the 'field' attribute matches the given values.

            The function checks two distinct cases: 
            1. Filtering with a single element in the slice (e.g., [2]) and 
            2. Filtering with multiple elements in the slice (e.g., [2, 3]). 

            It asserts that the results of these filter operations match the expected 
            sequence of model instances.
        """
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__0_1=[2]), self.objs[1:3]
        )

        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(field__0_2=[2, 3]), self.objs[2:3]
        )

    def test_order_by_slice(self):
        """
        Tests the ordering of NullableIntegerArrayModel instances using slicing on the 'field' attribute.

        The function creates additional model instances with varying 'field' values and asserts that these instances, when ordered by the second element of the 'field' array, match the expected sequence. 

        This test case verifies the correct functionality of the 'order_by' method when used with array fields and integer values. 

        Note: The expected sequence is determined based on the ascending order of the second element in the 'field' array.
        """
        more_objs = (
            NullableIntegerArrayModel.objects.create(field=[1, 637]),
            NullableIntegerArrayModel.objects.create(field=[2, 1]),
            NullableIntegerArrayModel.objects.create(field=[3, -98123]),
            NullableIntegerArrayModel.objects.create(field=[4, 2]),
        )
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.order_by("field__1"),
            [
                more_objs[2],
                more_objs[1],
                more_objs[3],
                self.objs[2],
                self.objs[3],
                more_objs[0],
                self.objs[4],
                self.objs[1],
                self.objs[0],
            ],
        )

    @unittest.expectedFailure
    def test_slice_nested(self):
        """
        Tests the filtering of NestedIntegerArrayModel instances by a nested value within the 'field' attribute.

        The function verifies that a NestedIntegerArrayModel instance can be successfully retrieved when filtering by a specific nested integer array value. 

        It checks that the instance with 'field' set to [[1, 2], [3, 4]] is correctly returned when filtering for instances where the first element of the first nested array is [1]. 

        This test case is expected to fail because the actual behavior may not match the expected outcome due to underlying model or database limitations.
        """
        instance = NestedIntegerArrayModel.objects.create(field=[[1, 2], [3, 4]])
        self.assertSequenceEqual(
            NestedIntegerArrayModel.objects.filter(field__0__0_1=[1]), [instance]
        )

    def test_slice_transform_expression(self):
        """
        Tests the application of SliceTransform to a RawSQL expression for array slicing.

        This test case verifies that the SliceTransform correctly extracts a subset of elements 
        from an array generated by a RawSQL query. It checks if the SliceTransform expression 
        can filter objects based on a specified range of elements in the array.

        The test uses a RawSQL expression that converts a string to an array, and then applies 
        the SliceTransform to this array to filter the results. The filtered results are then 
        compared to the expected output to ensure correctness.

        :raises AssertionError: If the filtered results do not match the expected output.

        """
        expr = RawSQL("string_to_array(%s, ';')", ["9;2;3"])
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(
                field__0_2=SliceTransform(2, 3, expr)
            ),
            self.objs[2:3],
        )

    def test_slice_annotation(self):
        """

        Tests the slicing annotation functionality on a NullableIntegerArrayModel query set.

        This test case verifies that the annotation correctly extracts a slice of the first two elements from the 'field' array 
        and stores it in the 'first_two' annotated field. The test then asserts that the extracted slices match the expected output.

        """
        qs = NullableIntegerArrayModel.objects.annotate(
            first_two=models.F("field__0_2"),
        )
        self.assertCountEqual(
            qs.values_list("first_two", flat=True),
            [None, [1], [2], [2, 3], [20, 30]],
        )

    def test_slicing_of_f_expressions(self):
        """
        Tests the slicing functionality of F expressions on array fields.

        This test case verifies that slicing F expressions, which represent database fields,
        works as expected by checking various slicing scenarios, including extracting 
        sub-arrays from the start, end, or middle of the array, as well as chained slicing 
        operations.

        The test validates the behavior by comparing the result of the slicing operation 
        to the expected output, ensuring that the data is correctly updated in the database.

        Each test case covers a specific slicing scenario, such as:
        - Slicing from the start of the array
        - Slicing from the end of the array
        - Slicing a sub-array from the middle of the array
        - Extracting a single element from the array
        - Chaining slicing operations to extract a sub-array and then another sub-array 
          from the result

        By covering these scenarios, this test ensures that the slicing functionality of 
        F expressions on array fields is working correctly and consistently. 
        """
        tests = [
            (F("field")[:2], [1, 2]),
            (F("field")[2:], [3, 4]),
            (F("field")[1:3], [2, 3]),
            (F("field")[3], [4]),
            (F("field")[:3][1:], [2, 3]),  # Nested slicing.
            (F("field")[:3][1], [2]),  # Slice then index.
        ]
        for expression, expected in tests:
            with self.subTest(expression=expression, expected=expected):
                instance = IntegerArrayModel.objects.create(field=[1, 2, 3, 4])
                instance.field = expression
                instance.save()
                instance.refresh_from_db()
                self.assertEqual(instance.field, expected)

    def test_slicing_of_f_expressions_with_annotate(self):
        IntegerArrayModel.objects.create(field=[1, 2, 3])
        annotated = IntegerArrayModel.objects.annotate(
            first_two=F("field")[:2],
            after_two=F("field")[2:],
            random_two=F("field")[1:3],
        ).get()
        self.assertEqual(annotated.first_two, [1, 2])
        self.assertEqual(annotated.after_two, [3])
        self.assertEqual(annotated.random_two, [2, 3])

    def test_slicing_of_f_expressions_with_len(self):
        """
        Tests the slicing operation on F expressions for a NullableIntegerArrayModel queryset, 
         specifically verifying that the length of a sliced F expression matches the length 
         of the original field, and that the sliced subarray can be filtered correctly.
        """
        queryset = NullableIntegerArrayModel.objects.annotate(
            subarray=F("field")[:1]
        ).filter(field__len=F("subarray__len"))
        self.assertSequenceEqual(queryset, self.objs[:2])

    def test_usage_in_subquery(self):
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.filter(
                id__in=NullableIntegerArrayModel.objects.filter(field__len=3)
            ),
            [self.objs[3]],
        )

    def test_enum_lookup(self):
        """

        Tests the lookup functionality of an enumerated array field.

        This test case verifies that the array of enums field can be properly filtered using the 'contains' lookup type. 
        It creates an instance of a model with an array of enums and then attempts to retrieve this instance from the database 
        using the 'contains' lookup with a value that is present in the array. 

        The test passes if the instance is successfully retrieved, indicating that the lookup functionality is working as expected.

        """
        class TestEnum(enum.Enum):
            VALUE_1 = "value_1"

        instance = ArrayEnumModel.objects.create(array_of_enums=[TestEnum.VALUE_1])
        self.assertSequenceEqual(
            ArrayEnumModel.objects.filter(array_of_enums__contains=[TestEnum.VALUE_1]),
            [instance],
        )

    def test_unsupported_lookup(self):
        msg = (
            "Unsupported lookup '0_bar' for ArrayField or join on the field not "
            "permitted."
        )
        with self.assertRaisesMessage(FieldError, msg):
            list(NullableIntegerArrayModel.objects.filter(field__0_bar=[2]))

        msg = (
            "Unsupported lookup '0bar' for ArrayField or join on the field not "
            "permitted."
        )
        with self.assertRaisesMessage(FieldError, msg):
            list(NullableIntegerArrayModel.objects.filter(field__0bar=[2]))

    def test_grouping_by_annotations_with_array_field_param(self):
        """

        Tests if the model instances can be annotated with a custom function that calculates the length of an array field.

        The function uses the `ARRAY_LENGTH` database function to determine the length of an array field in the model.
        The result is then used to group the model instances and count the number of instances for each array length.

        The test checks if the annotation is correctly applied and the length of the array is calculated as expected.

        """
        value = models.Value([1], output_field=ArrayField(models.IntegerField()))
        self.assertEqual(
            NullableIntegerArrayModel.objects.annotate(
                array_length=models.Func(
                    value,
                    1,
                    function="ARRAY_LENGTH",
                    output_field=models.IntegerField(),
                ),
            )
            .values("array_length")
            .annotate(
                count=models.Count("pk"),
            )
            .get()["array_length"],
            1,
        )

    def test_filter_by_array_subquery(self):
        inner_qs = NullableIntegerArrayModel.objects.filter(
            field__len=models.OuterRef("field__len"),
        ).values("field")
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.alias(
                same_sized_fields=ArraySubquery(inner_qs),
            ).filter(same_sized_fields__len__gt=1),
            self.objs[0:2],
        )

    def test_annotated_array_subquery(self):
        """
        Tests the annotation of a model with a subquery on an array field.

        This test checks that the ArraySubquery annotation correctly retrieves values from a related model, 
        excluding the current object, and assigns them to a new field on the model instance.

        The test case verifies that for a given model instance, the annotated field 'sibling_ids' contains 
        an array of order values from other model instances, excluding the current instance's order value.

        The expected output is an array of sibling order values in ascending order, demonstrating the 
        correct functionality of the ArraySubquery annotation in this context.
        """
        inner_qs = NullableIntegerArrayModel.objects.exclude(
            pk=models.OuterRef("pk")
        ).values("order")
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.annotate(
                sibling_ids=ArraySubquery(inner_qs),
            )
            .get(order=1)
            .sibling_ids,
            [2, 3, 4, 5],
        )

    def test_group_by_with_annotated_array_subquery(self):
        """
        Tests the behavior of the group_by functionality with an annotated array subquery.

         This function checks if the sibling count for each object in the NullableIntegerArrayModel is correctly calculated.
         The sibling count is determined by annotating each object with an array of sibling ids, 
         which are the order values of other objects excluding the current object itself.
         The function then asserts that the sibling count for each object is equal to the total number of objects minus one.
        """
        inner_qs = NullableIntegerArrayModel.objects.exclude(
            pk=models.OuterRef("pk")
        ).values("order")
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.annotate(
                sibling_ids=ArraySubquery(inner_qs),
                sibling_count=models.Max("sibling_ids__len"),
            ).values_list("sibling_count", flat=True),
            [len(self.objs) - 1] * len(self.objs),
        )

    def test_annotated_ordered_array_subquery(self):
        """
        Tests the functionality of annotating a model with an ordered array subquery.

        This test ensures that an ArraySubquery annotation correctly fetches and orders 
        the results from a related model, and assigns them to the annotated field 'ids'. 
        The test validates that the resulting annotated field returns the expected list 
        of ordered values.

        The expected list of values is derived from the original model's 'order' field, 
        ordered in descending order. The test checks for the correct ordering and 
        contents of the annotated 'ids' field in the first object retrieved from the 
        database.\"
        """
        inner_qs = NullableIntegerArrayModel.objects.order_by("-order").values("order")
        self.assertSequenceEqual(
            NullableIntegerArrayModel.objects.annotate(
                ids=ArraySubquery(inner_qs),
            )
            .first()
            .ids,
            [5, 4, 3, 2, 1],
        )

    def test_annotated_array_subquery_with_json_objects(self):
        inner_qs = NullableIntegerArrayModel.objects.exclude(
            pk=models.OuterRef("pk")
        ).values(json=JSONObject(order="order", field="field"))
        siblings_json = (
            NullableIntegerArrayModel.objects.annotate(
                siblings_json=ArraySubquery(inner_qs),
            )
            .values_list("siblings_json", flat=True)
            .get(order=1)
        )
        self.assertSequenceEqual(
            siblings_json,
            [
                {"field": [2], "order": 2},
                {"field": [2, 3], "order": 3},
                {"field": [20, 30, 40], "order": 4},
                {"field": None, "order": 5},
            ],
        )


class TestDateTimeExactQuerying(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class.

        This method creates a set of sample data, including current datetime, date, and time objects.
        It then uses this data to create an instance of DateTimeArrayModel, which is stored as a class attribute.
        The purpose of this method is to provide a common set of test data for all tests in the class, making it easier to write and maintain test cases.

        Attributes set by this method:
            datetimes: A list of datetime objects.
            dates: A list of date objects.
            times: A list of time objects.
            objs: A list of DateTimeArrayModel instances created with the sample data.

        """
        now = timezone.now()
        cls.datetimes = [now]
        cls.dates = [now.date()]
        cls.times = [now.time()]
        cls.objs = [
            DateTimeArrayModel.objects.create(
                datetimes=cls.datetimes, dates=cls.dates, times=cls.times
            ),
        ]

    def test_exact_datetimes(self):
        self.assertSequenceEqual(
            DateTimeArrayModel.objects.filter(datetimes=self.datetimes), self.objs
        )

    def test_exact_dates(self):
        self.assertSequenceEqual(
            DateTimeArrayModel.objects.filter(dates=self.dates), self.objs
        )

    def test_exact_times(self):
        self.assertSequenceEqual(
            DateTimeArrayModel.objects.filter(times=self.times), self.objs
        )


class TestOtherTypesExactQuerying(PostgreSQLTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ips = ["192.168.0.1", "::1"]
        cls.uuids = [uuid.uuid4()]
        cls.decimals = [decimal.Decimal(1.25), 1.75]
        cls.tags = [Tag(1), Tag(2), Tag(3)]
        cls.objs = [
            OtherTypesArrayModel.objects.create(
                ips=cls.ips,
                uuids=cls.uuids,
                decimals=cls.decimals,
                tags=cls.tags,
            )
        ]

    def test_exact_ip_addresses(self):
        self.assertSequenceEqual(
            OtherTypesArrayModel.objects.filter(ips=self.ips), self.objs
        )

    def test_exact_uuids(self):
        self.assertSequenceEqual(
            OtherTypesArrayModel.objects.filter(uuids=self.uuids), self.objs
        )

    def test_exact_decimals(self):
        self.assertSequenceEqual(
            OtherTypesArrayModel.objects.filter(decimals=self.decimals), self.objs
        )

    def test_exact_tags(self):
        self.assertSequenceEqual(
            OtherTypesArrayModel.objects.filter(tags=self.tags), self.objs
        )


@isolate_apps("postgres_tests")
class TestChecks(PostgreSQLSimpleTestCase):
    def test_field_checks(self):
        """
        Tests the validation of model fields to ensure they meet the required criteria.

        Verifies that the check method of a PostgreSQLModel instance correctly identifies
        invalid field configurations, such as a CharField with a negative max_length value,
        and returns the corresponding error with a unique identifier and descriptive message.

        This test case covers a specific scenario where the ArrayField's underlying CharField
        has an invalid max_length value, and asserts that the error detection and reporting
        mechanism functions as expected.
        """
        class MyModel(PostgreSQLModel):
            field = ArrayField(models.CharField(max_length=-1))

        model = MyModel()
        errors = model.check()
        self.assertEqual(len(errors), 1)
        # The inner CharField has a non-positive max_length.
        self.assertEqual(errors[0].id, "postgres.E001")
        self.assertIn("max_length", errors[0].msg)

    def test_invalid_base_fields(self):
        """
        Tests that an invalid base field raises the correct error when checked.

        The function creates a model instance with a ManyToMany field wrapped in an ArrayField,
        which is an invalid combination. It then checks the model for errors and asserts that
        one error is raised, with the expected error id 'postgres.E002'.
        """
        class MyModel(PostgreSQLModel):
            field = ArrayField(
                models.ManyToManyField("postgres_tests.IntegerArrayModel")
            )

        model = MyModel()
        errors = model.check()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "postgres.E002")

    def test_invalid_default(self):
        """

        Tests that an ArrayField with a default value that is not a callable raises a warning.

        ArrayFields should use a callable as their default value, rather than an instance, 
        to prevent the default value from being shared between all field instances. 
        This test checks that a warning is raised when an instance is used as the default value 
        instead of a callable, and verifies that the warning message and hint are correct.

        """
        class MyModel(PostgreSQLModel):
            field = ArrayField(models.IntegerField(), default=[])

        model = MyModel()
        self.assertEqual(
            model.check(),
            [
                checks.Warning(
                    msg=(
                        "ArrayField default should be a callable instead of an "
                        "instance so that it's not shared between all field "
                        "instances."
                    ),
                    hint="Use a callable instead, e.g., use `list` instead of `[]`.",
                    obj=MyModel._meta.get_field("field"),
                    id="fields.E010",
                )
            ],
        )

    def test_valid_default(self):
        """
        Tests that a model with an ArrayField having a default value of an empty list is considered valid when created without explicitly setting the field. 

        This test ensures the default value is correctly applied and does not trigger any validation errors when the model instance is checked. 

        The class `MyModel` is defined with a single `field` of type `ArrayField` containing `IntegerField` instances. The test creates an instance of `MyModel` without specifying the `field` value, then verifies that the model's `check` method returns an empty list, indicating no validation errors.
        """
        class MyModel(PostgreSQLModel):
            field = ArrayField(models.IntegerField(), default=list)

        model = MyModel()
        self.assertEqual(model.check(), [])

    def test_valid_default_none(self):
        """
        Tests the validation behavior of a PostgreSQL model field when its default value is set to None, ensuring that the model validates successfully in this scenario.
        """
        class MyModel(PostgreSQLModel):
            field = ArrayField(models.IntegerField(), default=None)

        model = MyModel()
        self.assertEqual(model.check(), [])

    def test_nested_field_checks(self):
        """
        Nested ArrayFields are permitted.
        """

        class MyModel(PostgreSQLModel):
            field = ArrayField(ArrayField(models.CharField(max_length=-1)))

        model = MyModel()
        errors = model.check()
        self.assertEqual(len(errors), 1)
        # The inner CharField has a non-positive max_length.
        self.assertEqual(errors[0].id, "postgres.E001")
        self.assertIn("max_length", errors[0].msg)

    def test_choices_tuple_list(self):
        """

        Tests the validation of choices for an ArrayField in a PostgreSQLModel.

        Verifies that a field with an ArrayField, containing CharField elements and 
        choices defined as a tuple of lists, passes the internal model validation.

        The choices are structured as a nested list, where the innermost lists contain 
        values, and are grouped under category labels. This test ensures that such 
        complex choices are properly recognized and validated by the model.

        """
        class MyModel(PostgreSQLModel):
            field = ArrayField(
                models.CharField(max_length=16),
                choices=[
                    [
                        "Media",
                        [(["vinyl", "cd"], "Audio"), (("vhs", "dvd"), "Video")],
                    ],
                    (["mp3", "mp4"], "Digital"),
                ],
            )

        self.assertEqual(MyModel._meta.get_field("field").check(), [])


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific tests")
class TestMigrations(TransactionTestCase):
    available_apps = ["postgres_tests"]

    def test_deconstruct(self):
        """
        Tests the deconstruction of an ArrayField instance to ensure it correctly breaks down into its constituent parts and reconstructs a new, independent instance with the same base field type. The test verifies that the new field has the same base field type as the original, but is a distinct object.
        """
        field = ArrayField(models.IntegerField())
        name, path, args, kwargs = field.deconstruct()
        new = ArrayField(*args, **kwargs)
        self.assertEqual(type(new.base_field), type(field.base_field))
        self.assertIsNot(new.base_field, field.base_field)

    def test_deconstruct_with_size(self):
        """

        Test the deconstruction of an ArrayField with a specified size.

        This test verifies that the deconstruct method of an ArrayField correctly 
        preserves its size property when reconstructed. It ensures that the field's 
        original size is retained after deconstruction and reconstruction, confirming 
        the correctness of the deconstruct and reconstruct process.

        """
        field = ArrayField(models.IntegerField(), size=3)
        name, path, args, kwargs = field.deconstruct()
        new = ArrayField(*args, **kwargs)
        self.assertEqual(new.size, field.size)

    def test_deconstruct_args(self):
        """
        Tests the deconstruction of ArrayField arguments to ensure they can be reconstructed into an equivalent field.

        Verifies that the max_length property of the base field remains consistent after deconstruction and reconstruction of the ArrayField.
        """
        field = ArrayField(models.CharField(max_length=20))
        name, path, args, kwargs = field.deconstruct()
        new = ArrayField(*args, **kwargs)
        self.assertEqual(new.base_field.max_length, field.base_field.max_length)

    def test_subclass_deconstruct(self):
        """
        Tests the deconstruction of ArrayField instances, including a subclass.

        Verifies that the deconstruct method correctly returns the path to the class
        definition for both the standard ArrayField and a custom subclass named
        ArrayFieldSubclass. This ensures that model fields can be properly serialized
        and reconstructed, maintaining the correct field type and path during the
        deconstruction process.
        """
        field = ArrayField(models.IntegerField())
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.contrib.postgres.fields.ArrayField")

        field = ArrayFieldSubclass()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "postgres_tests.models.ArrayFieldSubclass")

    @override_settings(
        MIGRATION_MODULES={
            "postgres_tests": "postgres_tests.array_default_migrations",
        }
    )
    def test_adding_field_with_default(self):
        # See #22962
        table_name = "postgres_tests_integerarraydefaultmodel"
        with connection.cursor() as cursor:
            self.assertNotIn(table_name, connection.introspection.table_names(cursor))
        call_command("migrate", "postgres_tests", verbosity=0)
        with connection.cursor() as cursor:
            self.assertIn(table_name, connection.introspection.table_names(cursor))
        call_command("migrate", "postgres_tests", "zero", verbosity=0)
        with connection.cursor() as cursor:
            self.assertNotIn(table_name, connection.introspection.table_names(cursor))

    @override_settings(
        MIGRATION_MODULES={
            "postgres_tests": "postgres_tests.array_index_migrations",
        }
    )
    def test_adding_arrayfield_with_index(self):
        """
        ArrayField shouldn't have varchar_patterns_ops or text_patterns_ops indexes.
        """
        table_name = "postgres_tests_chartextarrayindexmodel"
        call_command("migrate", "postgres_tests", verbosity=0)
        with connection.cursor() as cursor:
            like_constraint_columns_list = [
                v["columns"]
                for k, v in list(
                    connection.introspection.get_constraints(cursor, table_name).items()
                )
                if k.endswith("_like")
            ]
        # Only the CharField should have a LIKE index.
        self.assertEqual(like_constraint_columns_list, [["char2"]])
        # All fields should have regular indexes.
        with connection.cursor() as cursor:
            indexes = [
                c["columns"][0]
                for c in connection.introspection.get_constraints(
                    cursor, table_name
                ).values()
                if c["index"] and len(c["columns"]) == 1
            ]
        self.assertIn("char", indexes)
        self.assertIn("char2", indexes)
        self.assertIn("text", indexes)
        call_command("migrate", "postgres_tests", "zero", verbosity=0)
        with connection.cursor() as cursor:
            self.assertNotIn(table_name, connection.introspection.table_names(cursor))


class TestSerialization(PostgreSQLSimpleTestCase):
    test_data = (
        '[{"fields": {"field": "[\\"1\\", \\"2\\", null]"}, '
        '"model": "postgres_tests.integerarraymodel", "pk": null}]'
    )

    def test_dumping(self):
        """
        Tests the JSON serialization of an IntegerArrayModel instance.

        Verifies that an instance of IntegerArrayModel containing an array field with integers and null values is properly dumped to JSON format.
        The test compares the resulting JSON against a predefined expected output to ensure data integrity and correct serialization. 
        """
        instance = IntegerArrayModel(field=[1, 2, None])
        data = serializers.serialize("json", [instance])
        self.assertEqual(json.loads(data), json.loads(self.test_data))

    def test_loading(self):
        """

        Tests the loading process of deserialized data from JSON.

        Verifies that an instance of an object can be successfully loaded from JSON data 
        and that its attributes are correctly populated. Specifically, checks that the 
        'field' attribute of the loaded instance contains the expected list of values.

        """
        instance = list(serializers.deserialize("json", self.test_data))[0].object
        self.assertEqual(instance.field, [1, 2, None])


class TestValidation(PostgreSQLSimpleTestCase):
    def test_unbounded(self):
        """
        Tests the unbounded array field validation functionality.

        Verifies that an :class:`exceptions.ValidationError` is raised when a null value is encountered in the array.

        Checks that the validation error returned contains the correct error code 'item_invalid' and an informative error message.

        """
        field = ArrayField(models.IntegerField())
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean([1, None], None)
        self.assertEqual(cm.exception.code, "item_invalid")
        self.assertEqual(
            cm.exception.message % cm.exception.params,
            "Item 2 in the array did not validate: This field cannot be null.",
        )

    def test_blank_true(self):
        field = ArrayField(models.IntegerField(blank=True, null=True))
        # This should not raise a validation error
        field.clean([1, None], None)

    def test_with_size(self):
        field = ArrayField(models.IntegerField(), size=3)
        field.clean([1, 2, 3], None)
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean([1, 2, 3, 4], None)
        self.assertEqual(
            cm.exception.messages[0],
            "List contains 4 items, it should contain no more than 3.",
        )

    def test_with_size_singular(self):
        """
        Tests that an ArrayField with a size limit of 1 raises a ValidationError 
        when the list provided contains more than one item. 

        This test ensures that the ArrayField enforces its specified size constraint 
        in a singular case, where only one item is allowed, and that it correctly 
        reports the error message when the constraint is violated.
        """
        field = ArrayField(models.IntegerField(), size=1)
        field.clean([1], None)
        msg = "List contains 2 items, it should contain no more than 1."
        with self.assertRaisesMessage(exceptions.ValidationError, msg):
            field.clean([1, 2], None)

    def test_nested_array_mismatch(self):
        """
        Tests that the ArrayField with nested ArrayField raises a ValidationError when the nested arrays do not have the same length. 

        This test ensures the ArrayField validation correctly checks for uniformity in the lengths of nested arrays, providing a specific error code and message when a mismatch is detected.
        """
        field = ArrayField(ArrayField(models.IntegerField()))
        field.clean([[1, 2], [3, 4]], None)
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean([[1, 2], [3, 4, 5]], None)
        self.assertEqual(cm.exception.code, "nested_array_mismatch")
        self.assertEqual(
            cm.exception.messages[0], "Nested arrays must have the same length."
        )

    def test_with_base_field_error_params(self):
        """
        Tests the validation of an ArrayField with CharField as its base field, ensuring that error parameters are correctly populated when a validation error occurs.

            The test simulates a validation error by attempting to clean an array containing a string longer than the maximum allowed length for the base CharField.
            It then asserts that a ValidationError is raised with the correct error message, code, and parameters, including the position of the invalid item, its value, and the limit value that it exceeded.
        """
        field = ArrayField(models.CharField(max_length=2))
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["abc"], None)
        self.assertEqual(len(cm.exception.error_list), 1)
        exception = cm.exception.error_list[0]
        self.assertEqual(
            exception.message,
            "Item 1 in the array did not validate: Ensure this value has at most 2 "
            "characters (it has 3).",
        )
        self.assertEqual(exception.code, "item_invalid")
        self.assertEqual(
            exception.params,
            {"nth": 1, "value": "abc", "limit_value": 2, "show_value": 3},
        )

    def test_with_validators(self):
        field = ArrayField(
            models.IntegerField(validators=[validators.MinValueValidator(1)])
        )
        field.clean([1, 2], None)
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean([0], None)
        self.assertEqual(len(cm.exception.error_list), 1)
        exception = cm.exception.error_list[0]
        self.assertEqual(
            exception.message,
            "Item 1 in the array did not validate: Ensure this value is greater than "
            "or equal to 1.",
        )
        self.assertEqual(exception.code, "item_invalid")
        self.assertEqual(
            exception.params, {"nth": 1, "value": 0, "limit_value": 1, "show_value": 0}
        )


class TestSimpleFormField(PostgreSQLSimpleTestCase):
    def test_valid(self):
        """
        Tests the validity of the array field by checking if a comma-separated string is correctly split into a list.

        The function verifies that the SimpleArrayField can handle input in the format of a comma-separated string and 
        returns a list of the individual elements, as expected. This ensures the field behaves as intended when cleaned.
        """
        field = SimpleArrayField(forms.CharField())
        value = field.clean("a,b,c")
        self.assertEqual(value, ["a", "b", "c"])

    def test_to_python_fail(self):
        """
        Tests that the SimpleArrayField fails to validate when a non-integer value is provided.

        This function checks that when a string containing a non-integer value is passed to the clean method of a SimpleArrayField, 
        a ValidationError is raised with the expected error message, indicating that the field cannot be converted to a Python object.

        The test verifies that the error message correctly identifies the invalid item in the array and provides a clear error message.

        """
        field = SimpleArrayField(forms.IntegerField())
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean("a,b,9")
        self.assertEqual(
            cm.exception.messages[0],
            "Item 1 in the array did not validate: Enter a whole number.",
        )

    def test_validate_fail(self):
        field = SimpleArrayField(forms.CharField(required=True))
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean("a,b,")
        self.assertEqual(
            cm.exception.messages[0],
            "Item 3 in the array did not validate: This field is required.",
        )

    def test_validate_fail_base_field_error_params(self):
        """

        Tests that the validation of a SimpleArrayField fails with base field errors when its items exceed the maximum length.

        This test case checks that the field raises a ValidationError with a list of errors when the input items are too long.
        Each error in the list corresponds to an item in the array that did not validate, and contains information such as the item's position, value, and the maximum allowed length.
        The test verifies that the error messages, codes, and parameters are correctly generated for each invalid item.

        """
        field = SimpleArrayField(forms.CharField(max_length=2))
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean("abc,c,defg")
        errors = cm.exception.error_list
        self.assertEqual(len(errors), 2)
        first_error = errors[0]
        self.assertEqual(
            first_error.message,
            "Item 1 in the array did not validate: Ensure this value has at most 2 "
            "characters (it has 3).",
        )
        self.assertEqual(first_error.code, "item_invalid")
        self.assertEqual(
            first_error.params,
            {"nth": 1, "value": "abc", "limit_value": 2, "show_value": 3},
        )
        second_error = errors[1]
        self.assertEqual(
            second_error.message,
            "Item 3 in the array did not validate: Ensure this value has at most 2 "
            "characters (it has 4).",
        )
        self.assertEqual(second_error.code, "item_invalid")
        self.assertEqual(
            second_error.params,
            {"nth": 3, "value": "defg", "limit_value": 2, "show_value": 4},
        )

    def test_validators_fail(self):
        field = SimpleArrayField(forms.RegexField("[a-e]{2}"))
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean("a,bc,de")
        self.assertEqual(
            cm.exception.messages[0],
            "Item 1 in the array did not validate: Enter a valid value.",
        )

    def test_delimiter(self):
        """
        Tests the `clean` method of a `SimpleArrayField` instance with a custom delimiter, verifying that it correctly splits a string into a list of substrings using the specified delimiter.
        """
        field = SimpleArrayField(forms.CharField(), delimiter="|")
        value = field.clean("a|b|c")
        self.assertEqual(value, ["a", "b", "c"])

    def test_delimiter_with_nesting(self):
        """

        Test the behaviour of a delimiter within a nested field structure.

        This test case verifies that the delimiter correctly splits the input string
        into sublists, taking into account the nested field structure. It ensures that
        the delimiter is applied recursively, resulting in a nested list of values.

        The test expects the cleaned value to be a list of lists, where each sublist
        contains the individual values separated by the delimiter.

        """
        field = SimpleArrayField(SimpleArrayField(forms.CharField()), delimiter="|")
        value = field.clean("a,b|c,d")
        self.assertEqual(value, [["a", "b"], ["c", "d"]])

    def test_prepare_value(self):
        """
        Tests that the prepare_value method of a SimpleArrayField correctly converts a list of values into a comma-separated string.

        The prepare_value method is used to transform the value of a field into a format suitable for form rendering or other uses. In the case of a SimpleArrayField, this involves joining the list of values into a single string, separated by commas. This test ensures that the method behaves as expected, producing a string that can be used in a form or other context where a single value is required.
        """
        field = SimpleArrayField(forms.CharField())
        value = field.prepare_value(["a", "b", "c"])
        self.assertEqual(value, "a,b,c")

    def test_max_length(self):
        field = SimpleArrayField(forms.CharField(), max_length=2)
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean("a,b,c")
        self.assertEqual(
            cm.exception.messages[0],
            "List contains 3 items, it should contain no more than 2.",
        )

    def test_min_length(self):
        field = SimpleArrayField(forms.CharField(), min_length=4)
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean("a,b,c")
        self.assertEqual(
            cm.exception.messages[0],
            "List contains 3 items, it should contain no fewer than 4.",
        )

    def test_min_length_singular(self):
        field = SimpleArrayField(forms.IntegerField(), min_length=2)
        field.clean([1, 2])
        msg = "List contains 1 item, it should contain no fewer than 2."
        with self.assertRaisesMessage(exceptions.ValidationError, msg):
            field.clean([1])

    def test_required(self):
        """

        Tests that a required field raises a ValidationError when no value is provided.

        Verifies that attempting to clean an empty value for a required field results in a
        ValidationError with the expected error message, indicating that the field must
        have a value to proceed.

        """
        field = SimpleArrayField(forms.CharField(), required=True)
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean("")
        self.assertEqual(cm.exception.messages[0], "This field is required.")

    def test_model_field_formfield(self):
        model_field = ArrayField(models.CharField(max_length=27))
        form_field = model_field.formfield()
        self.assertIsInstance(form_field, SimpleArrayField)
        self.assertIsInstance(form_field.base_field, forms.CharField)
        self.assertEqual(form_field.base_field.max_length, 27)

    def test_model_field_formfield_size(self):
        model_field = ArrayField(models.CharField(max_length=27), size=4)
        form_field = model_field.formfield()
        self.assertIsInstance(form_field, SimpleArrayField)
        self.assertEqual(form_field.max_length, 4)

    def test_model_field_choices(self):
        model_field = ArrayField(models.IntegerField(choices=((1, "A"), (2, "B"))))
        form_field = model_field.formfield()
        self.assertEqual(form_field.clean("1,2"), [1, 2])

    def test_already_converted_value(self):
        """
        Tests that an already converted value is returned as-is by the clean method.

        If the input value is a list and matches the expected format, this method verifies 
        that the field does not alter the input and returns it in its original form. 

        This ensures that the field's clean method is idempotent and does not introduce 
        any unexpected changes to already valid data.
        """
        field = SimpleArrayField(forms.CharField())
        vals = ["a", "b", "c"]
        self.assertEqual(field.clean(vals), vals)

    def test_has_changed(self):
        """
        Tests whether the value of a SimpleArrayField has changed.

        This method checks whether the initial value and the current value of the field are different.
        It handles comparisons between list and string representations of the field's value.

        The test returns False if the field's value has not changed and True otherwise. It considers
        a change in the number of elements or their values as a change in the field's value.
        The comparison is case-sensitive and considers the field's values as a whole, not individual elements.

        The function verifies that the has_changed method of the SimpleArrayField correctly identifies 
        when the field's value has been modified, whether the new value is provided as a list or a string.
        """
        field = SimpleArrayField(forms.IntegerField())
        self.assertIs(field.has_changed([1, 2], [1, 2]), False)
        self.assertIs(field.has_changed([1, 2], "1,2"), False)
        self.assertIs(field.has_changed([1, 2], "1,2,3"), True)
        self.assertIs(field.has_changed([1, 2], "a,b"), True)

    def test_has_changed_empty(self):
        field = SimpleArrayField(forms.CharField())
        self.assertIs(field.has_changed(None, None), False)
        self.assertIs(field.has_changed(None, ""), False)
        self.assertIs(field.has_changed(None, []), False)
        self.assertIs(field.has_changed([], None), False)
        self.assertIs(field.has_changed([], ""), False)


class TestSplitFormField(PostgreSQLSimpleTestCase):
    def test_valid(self):
        """
        ##### Testing Valid Form Data with SplitArrayField

        Tests the validation of a form using the SplitArrayField, ensuring it correctly 
        handles and processes an array of values. Verifies that the form is valid and 
        the cleaned data matches the expected output, correctly splitting the input 
        data into a list of values.
        """
        class SplitForm(forms.Form):
            array = SplitArrayField(forms.CharField(), size=3)

        data = {"array_0": "a", "array_1": "b", "array_2": "c"}
        form = SplitForm(data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data, {"array": ["a", "b", "c"]})

    def test_required(self):
        """
        Tests that the SplitArrayField correctly handles the required parameter.

        When the required parameter is set to True, the field should raise a validation error if all
        subfields are empty. This test case verifies that the expected error message is returned
        when the form is submitted with empty subfields. The validation error should have the message
        'This field is required.' and the field should not be considered valid. 
        """
        class SplitForm(forms.Form):
            array = SplitArrayField(forms.CharField(), required=True, size=3)

        data = {"array_0": "", "array_1": "", "array_2": ""}
        form = SplitForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {"array": ["This field is required."]})

    def test_remove_trailing_nulls(self):
        """

        Tests the functionality of removing trailing nulls from an array field.

        This test case verifies that when the `remove_trailing_nulls` parameter is set to `True`, 
        empty values at the end of the array are removed after form validation. 

        The test creates a form with an array field, populates it with data containing 
        some empty values at the end, and checks that the form is valid and the cleaned 
        data has the trailing empty values removed.

        """
        class SplitForm(forms.Form):
            array = SplitArrayField(
                forms.CharField(required=False), size=5, remove_trailing_nulls=True
            )

        data = {
            "array_0": "a",
            "array_1": "",
            "array_2": "b",
            "array_3": "",
            "array_4": "",
        }
        form = SplitForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data, {"array": ["a", "", "b"]})

    def test_remove_trailing_nulls_not_required(self):
        class SplitForm(forms.Form):
            array = SplitArrayField(
                forms.CharField(required=False),
                size=2,
                remove_trailing_nulls=True,
                required=False,
            )

        data = {"array_0": "", "array_1": ""}
        form = SplitForm(data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data, {"array": []})

    def test_required_field(self):
        class SplitForm(forms.Form):
            array = SplitArrayField(forms.CharField(), size=3)

        data = {"array_0": "a", "array_1": "b", "array_2": ""}
        form = SplitForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {
                "array": [
                    "Item 3 in the array did not validate: This field is required."
                ]
            },
        )

    def test_invalid_integer(self):
        msg = (
            "Item 2 in the array did not validate: Ensure this value is less than or "
            "equal to 100."
        )
        with self.assertRaisesMessage(exceptions.ValidationError, msg):
            SplitArrayField(forms.IntegerField(max_value=100), size=2).clean([0, 101])

    def test_rendering(self):
        class SplitForm(forms.Form):
            array = SplitArrayField(forms.CharField(), size=3)

        self.assertHTMLEqual(
            str(SplitForm()),
            """
            <div>
                <label for="id_array_0">Array:</label>
                <input id="id_array_0" name="array_0" type="text" required>
                <input id="id_array_1" name="array_1" type="text" required>
                <input id="id_array_2" name="array_2" type="text" required>
            </div>
        """,
        )

    def test_invalid_char_length(self):
        field = SplitArrayField(forms.CharField(max_length=2), size=3)
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean(["abc", "c", "defg"])
        self.assertEqual(
            cm.exception.messages,
            [
                "Item 1 in the array did not validate: Ensure this value has at most 2 "
                "characters (it has 3).",
                "Item 3 in the array did not validate: Ensure this value has at most 2 "
                "characters (it has 4).",
            ],
        )

    def test_splitarraywidget_value_omitted_from_data(self):
        class Form(forms.ModelForm):
            field = SplitArrayField(forms.IntegerField(), required=False, size=2)

            class Meta:
                model = IntegerArrayModel
                fields = ("field",)

        form = Form({"field_0": "1", "field_1": "2"})
        self.assertEqual(form.errors, {})
        obj = form.save(commit=False)
        self.assertEqual(obj.field, [1, 2])

    def test_splitarrayfield_has_changed(self):
        """
        Tests the has_changed() method of a form containing a SplitArrayField.

        This test case checks the SplitArrayField's has_changed() method in various scenarios,
        including empty fields, partially filled fields, and fully filled fields with valid and invalid data.

        The test iterates over multiple test cases, each with different initial data and user input,
        and verifies that the has_changed() method returns the expected result based on whether the form data has changed.

        The test cases cover various edge cases, such as empty or None initial values, single-element arrays,
        and arrays with multiple elements, to ensure the has_changed() method behaves correctly in different situations.
        """
        class Form(forms.ModelForm):
            field = SplitArrayField(forms.IntegerField(), required=False, size=2)

            class Meta:
                model = IntegerArrayModel
                fields = ("field",)

        tests = [
            ({}, {"field_0": "", "field_1": ""}, True),
            ({"field": None}, {"field_0": "", "field_1": ""}, True),
            ({"field": [1]}, {"field_0": "", "field_1": ""}, True),
            ({"field": [1]}, {"field_0": "1", "field_1": "0"}, True),
            ({"field": [1, 2]}, {"field_0": "1", "field_1": "2"}, False),
            ({"field": [1, 2]}, {"field_0": "a", "field_1": "b"}, True),
        ]
        for initial, data, expected_result in tests:
            with self.subTest(initial=initial, data=data):
                obj = IntegerArrayModel(**initial)
                form = Form(data, instance=obj)
                self.assertIs(form.has_changed(), expected_result)

    def test_splitarrayfield_remove_trailing_nulls_has_changed(self):
        class Form(forms.ModelForm):
            field = SplitArrayField(
                forms.IntegerField(), required=False, size=2, remove_trailing_nulls=True
            )

            class Meta:
                model = IntegerArrayModel
                fields = ("field",)

        tests = [
            ({}, {"field_0": "", "field_1": ""}, False),
            ({"field": None}, {"field_0": "", "field_1": ""}, False),
            ({"field": []}, {"field_0": "", "field_1": ""}, False),
            ({"field": [1]}, {"field_0": "1", "field_1": ""}, False),
        ]
        for initial, data, expected_result in tests:
            with self.subTest(initial=initial, data=data):
                obj = IntegerArrayModel(**initial)
                form = Form(data, instance=obj)
                self.assertIs(form.has_changed(), expected_result)


class TestSplitFormWidget(PostgreSQLWidgetTestCase):
    def test_get_context(self):
        self.assertEqual(
            SplitArrayWidget(forms.TextInput(), size=2).get_context(
                "name", ["val1", "val2"]
            ),
            {
                "widget": {
                    "name": "name",
                    "is_hidden": False,
                    "required": False,
                    "value": "['val1', 'val2']",
                    "attrs": {},
                    "template_name": "postgres/widgets/split_array.html",
                    "subwidgets": [
                        {
                            "name": "name_0",
                            "is_hidden": False,
                            "required": False,
                            "value": "val1",
                            "attrs": {},
                            "template_name": "django/forms/widgets/text.html",
                            "type": "text",
                        },
                        {
                            "name": "name_1",
                            "is_hidden": False,
                            "required": False,
                            "value": "val2",
                            "attrs": {},
                            "template_name": "django/forms/widgets/text.html",
                            "type": "text",
                        },
                    ],
                }
            },
        )

    def test_checkbox_get_context_attrs(self):
        """
        Checks if the get_context method of SplitArrayWidget returns the correct attributes for a CheckboxInput widget.

        This test verifies that the 'value' attribute in the context is correctly formatted as a string 
        representation of a list, and that the 'checked' attribute is properly applied to the subwidget 
        based on its corresponding value in the input list.

        The expected output includes a 'widget' dictionary with a 'value' key set to a stringified list 
        of the input values, and a 'subwidgets' key containing a list of dictionaries representing 
        each subwidget's attributes, with 'checked' included for subwidgets corresponding to True values.
        """
        context = SplitArrayWidget(
            forms.CheckboxInput(),
            size=2,
        ).get_context("name", [True, False])
        self.assertEqual(context["widget"]["value"], "[True, False]")
        self.assertEqual(
            [subwidget["attrs"] for subwidget in context["widget"]["subwidgets"]],
            [{"checked": True}, {}],
        )

    def test_render(self):
        self.check_html(
            SplitArrayWidget(forms.TextInput(), size=2),
            "array",
            None,
            """
            <input name="array_0" type="text">
            <input name="array_1" type="text">
            """,
        )

    def test_render_attrs(self):
        self.check_html(
            SplitArrayWidget(forms.TextInput(), size=2),
            "array",
            ["val1", "val2"],
            attrs={"id": "foo"},
            html=(
                """
                <input id="foo_0" name="array_0" type="text" value="val1">
                <input id="foo_1" name="array_1" type="text" value="val2">
                """
            ),
        )

    def test_value_omitted_from_data(self):
        """
        lardır\"\"\" 
        Checks whether a value for the specified field is omitted from the provided data.

        This method determines if the field's value is missing from the data by checking for the presence of the field's prefix with any index in the data dictionary.

        Args:
            data (dict): The data dictionary to check.
            files (dict): The files dictionary (not used in this method).
            field (str): The name of the field to check.

        Returns:
            bool: True if the value for the specified field is omitted from the data, False otherwise.

        """
        widget = SplitArrayWidget(forms.TextInput(), size=2)
        self.assertIs(widget.value_omitted_from_data({}, {}, "field"), True)
        self.assertIs(
            widget.value_omitted_from_data({"field_0": "value"}, {}, "field"), False
        )
        self.assertIs(
            widget.value_omitted_from_data({"field_1": "value"}, {}, "field"), False
        )
        self.assertIs(
            widget.value_omitted_from_data(
                {"field_0": "value", "field_1": "value"}, {}, "field"
            ),
            False,
        )


class TestAdminUtils(PostgreSQLTestCase):
    empty_value = "-empty-"

    def test_array_display_for_field(self):
        array_field = ArrayField(models.IntegerField())
        display_value = display_for_field(
            [1, 2],
            array_field,
            self.empty_value,
        )
        self.assertEqual(display_value, "1, 2")

    def test_array_with_choices_display_for_field(self):
        array_field = ArrayField(
            models.IntegerField(),
            choices=[
                ([1, 2, 3], "1st choice"),
                ([1, 2], "2nd choice"),
            ],
        )

        display_value = display_for_field(
            [1, 2],
            array_field,
            self.empty_value,
        )
        self.assertEqual(display_value, "2nd choice")

        display_value = display_for_field(
            [99, 99],
            array_field,
            self.empty_value,
        )
        self.assertEqual(display_value, self.empty_value)
