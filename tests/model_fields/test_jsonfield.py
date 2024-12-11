import operator
import uuid
from unittest import mock

from django import forms
from django.core import serializers
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import (
    DataError,
    IntegrityError,
    NotSupportedError,
    OperationalError,
    connection,
    models,
)
from django.db.models import (
    Count,
    ExpressionWrapper,
    F,
    IntegerField,
    JSONField,
    OuterRef,
    Q,
    Subquery,
    Transform,
    Value,
)
from django.db.models.expressions import RawSQL
from django.db.models.fields.json import (
    KT,
    KeyTextTransform,
    KeyTransform,
    KeyTransformFactory,
    KeyTransformTextLookupMixin,
)
from django.db.models.functions import Cast
from django.test import SimpleTestCase, TestCase, skipIfDBFeature, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext

from .models import CustomJSONDecoder, JSONModel, NullableJSONModel, RelatedJSONModel


@skipUnlessDBFeature("supports_json_field")
class JSONFieldTests(TestCase):
    def test_invalid_value(self):
        """

            Verifies that creating a NullableJSONModel instance with a non-JSON serializable value raises a TypeError.

            This test ensures that the model correctly handles invalid data by checking that a TypeError is raised when attempting to create an instance with a value that cannot be serialized to JSON.

            :raises TypeError: If the provided value is not JSON serializable

        """
        msg = "is not JSON serializable"
        with self.assertRaisesMessage(TypeError, msg):
            NullableJSONModel.objects.create(
                value={
                    "uuid": uuid.UUID("d85e2076-b67c-4ee7-8c3a-2bf5a2cc2475"),
                }
            )

    def test_custom_encoder_decoder(self):
        """
        Tests the custom encoder and decoder functionality for serializing and deserializing a NullableJSONModel instance.

        Verifies that a JSON-serializable value with a UUID attribute can be successfully stored in the database, retrieved, and compared to its original value, ensuring data integrity and correct deserialization.

        The test case covers the full lifecycle of the object, from creation and saving to retrieval and comparison, providing assurance that the custom encoder and decoder are working correctly in a real-world scenario.
        """
        value = {"uuid": uuid.UUID("{d85e2076-b67c-4ee7-8c3a-2bf5a2cc2475}")}
        obj = NullableJSONModel(value_custom=value)
        obj.clean_fields()
        obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.value_custom, value)

    def test_db_check_constraints(self):
        value = "{@!invalid json value 123 $!@#"
        with mock.patch.object(DjangoJSONEncoder, "encode", return_value=value):
            with self.assertRaises((IntegrityError, DataError, OperationalError)):
                NullableJSONModel.objects.create(value_custom=value)


class TestMethods(SimpleTestCase):
    def test_deconstruct(self):
        """
        Tests the deconstruction of a JSONField instance.

        Verifies that the deconstruct method of JSONField returns the correct path,
        arguments, and keyword arguments.

        The test checks that the deconstructed path matches the expected path
        'django.db.models.JSONField' and that no arguments or keyword arguments are
        returned.
        """
        field = models.JSONField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.JSONField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})

    def test_deconstruct_custom_encoder_decoder(self):
        field = models.JSONField(encoder=DjangoJSONEncoder, decoder=CustomJSONDecoder)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(kwargs["encoder"], DjangoJSONEncoder)
        self.assertEqual(kwargs["decoder"], CustomJSONDecoder)

    def test_get_transforms(self):
        @models.JSONField.register_lookup
        """
        Tests the retrieval of transforms for a JSONField.

        Verifies that a custom transform registered with a given name can be successfully
        retrieved by the field, and that unregistering the transform results in the return
        of a default KeyTransformFactory instance instead.

        Checks the functionality of the get_transform method in handling both registered
        and unregistered lookup names, ensuring correct instance types are returned in
        each case.
        """
        class MyTransform(Transform):
            lookup_name = "my_transform"

        field = models.JSONField()
        transform = field.get_transform("my_transform")
        self.assertIs(transform, MyTransform)
        models.JSONField._unregister_lookup(MyTransform)
        transform = field.get_transform("my_transform")
        self.assertIsInstance(transform, KeyTransformFactory)

    def test_key_transform_text_lookup_mixin_non_key_transform(self):
        transform = Transform("test")
        msg = (
            "Transform should be an instance of KeyTransform in order to use "
            "this lookup."
        )
        with self.assertRaisesMessage(TypeError, msg):
            KeyTransformTextLookupMixin(transform)

    def test_get_prep_value(self):
        class JSONFieldGetPrepValue(models.JSONField):
            def get_prep_value(self, value):
                if value is True:
                    return {"value": True}
                return value

        def noop_adapt_json_value(value, encoder):
            return value

        field = JSONFieldGetPrepValue()
        with mock.patch.object(
            connection.ops, "adapt_json_value", noop_adapt_json_value
        ):
            self.assertEqual(
                field.get_db_prep_value(True, connection, prepared=False),
                {"value": True},
            )
            self.assertIs(
                field.get_db_prep_value(True, connection, prepared=True), True
            )
            self.assertEqual(field.get_db_prep_value(1, connection, prepared=False), 1)


class TestValidation(SimpleTestCase):
    def test_invalid_encoder(self):
        """
        Tests that an invalid encoder passed to a JSONField raises a ValueError.

        The JSONField requires an encoder to be a callable object. This test ensures that
        passing a non-callable object, such as an instance of DjangoJSONEncoder, results
        in a ValueError with a descriptive error message.

        Raises:
            ValueError: If the encoder is not a callable object.

        """
        msg = "The encoder parameter must be a callable object."
        with self.assertRaisesMessage(ValueError, msg):
            models.JSONField(encoder=DjangoJSONEncoder())

    def test_invalid_decoder(self):
        msg = "The decoder parameter must be a callable object."
        with self.assertRaisesMessage(ValueError, msg):
            models.JSONField(decoder=CustomJSONDecoder())

    def test_validation_error(self):
        """
        Tests that a JSONField raises a ValidationError when passed an invalid JSON value, specifically a UUID object that cannot be serialized to JSON.
        """
        field = models.JSONField()
        msg = "Value must be valid JSON."
        value = uuid.UUID("{d85e2076-b67c-4ee7-8c3a-2bf5a2cc2475}")
        with self.assertRaisesMessage(ValidationError, msg):
            field.clean({"uuid": value}, None)

    def test_custom_encoder(self):
        """

        Tests the custom encoder for a JSONField with a UUID value.

        This test verifies that a custom JSON encoder (DjangoJSONEncoder) can successfully
        process a UUID object when cleaning a JSON field. The test creates a JSON field
        with the custom encoder and then attempts to clean a dictionary containing a UUID
        value. If the encoder is functioning correctly, the cleaning process should not
        raise any errors.


        """
        field = models.JSONField(encoder=DjangoJSONEncoder)
        value = uuid.UUID("{d85e2076-b67c-4ee7-8c3a-2bf5a2cc2475}")
        field.clean({"uuid": value}, None)


class TestFormField(SimpleTestCase):
    def test_formfield(self):
        model_field = models.JSONField()
        form_field = model_field.formfield()
        self.assertIsInstance(form_field, forms.JSONField)

    def test_formfield_custom_encoder_decoder(self):
        model_field = models.JSONField(
            encoder=DjangoJSONEncoder, decoder=CustomJSONDecoder
        )
        form_field = model_field.formfield()
        self.assertIs(form_field.encoder, DjangoJSONEncoder)
        self.assertIs(form_field.decoder, CustomJSONDecoder)


class TestSerialization(SimpleTestCase):
    test_data = (
        '[{"fields": {"value": %s}, "model": "model_fields.jsonmodel", "pk": null}]'
    )
    test_values = (
        # (Python value, serialized value),
        ({"a": "b", "c": None}, '{"a": "b", "c": null}'),
        ("abc", '"abc"'),
        ('{"a": "a"}', '"{\\"a\\": \\"a\\"}"'),
    )

    def test_dumping(self):
        """
        Tests the serialization of JSONModel instances through the dump procedure.

        This test case iterates over a set of predefined test values, creates a JSONModel instance for each value, 
        and then serializes it using the JSON serializer. The serialized output is then compared to the expected 
        serialized data to ensure that the serialization process is working correctly.

        The test uses sub-tests to provide detailed information about which specific test value is being processed 
        in case of a failure, allowing for easier debugging and identification of issues.
        """
        for value, serialized in self.test_values:
            with self.subTest(value=value):
                instance = JSONModel(value=value)
                data = serializers.serialize("json", [instance])
                self.assertJSONEqual(data, self.test_data % serialized)

    def test_loading(self):
        for value, serialized in self.test_values:
            with self.subTest(value=value):
                instance = list(
                    serializers.deserialize("json", self.test_data % serialized)
                )[0].object
                self.assertEqual(instance.value, value)

    def test_xml_serialization(self):
        """

        Tests the serialization and deserialization of the NullableJSONModel class to and from XML.

        This test verifies that instances of NullableJSONModel can be successfully serialized to XML and then deserialized back into a new instance, preserving the original data. It checks for correct serialization by comparing the produced XML data with an expected template, and then verifies that the deserialized instance has the same value as the original instance.

        The test covers a range of input values to ensure serialization and deserialization work correctly for different types of data.

        """
        test_xml_data = (
            '<django-objects version="1.0">'
            '<object model="model_fields.nullablejsonmodel">'
            '<field name="value" type="JSONField">%s'
            "</field></object></django-objects>"
        )
        for value, serialized in self.test_values:
            with self.subTest(value=value):
                instance = NullableJSONModel(value=value)
                data = serializers.serialize("xml", [instance], fields=["value"])
                self.assertXMLEqual(data, test_xml_data % serialized)
                new_instance = list(serializers.deserialize("xml", data))[0].object
                self.assertEqual(new_instance.value, instance.value)


@skipUnlessDBFeature("supports_json_field")
class TestSaveLoad(TestCase):
    def test_null(self):
        obj = NullableJSONModel(value=None)
        obj.save()
        obj.refresh_from_db()
        self.assertIsNone(obj.value)

    @skipUnlessDBFeature("supports_primitives_in_json_field")
    def test_json_null_different_from_sql_null(self):
        """

        Tests the difference between JSON null and SQL null in a JSON field.

        This test ensures that JSON null (represented as 'null' in JSON) and SQL null
        (represented as None in Python and NULL in SQL) are handled correctly in a JSON
        field. It verifies that filtering on JSON null and SQL null returns the expected
        results, and that the values are correctly refreshed from the database.

        The test covers the following scenarios:

        * Creating a model instance with JSON null and SQL null values
        * Updating a model instance to have a JSON null value
        * Filtering on JSON null and SQL null values
        * Verifying that the filtered results match the expected instances
        * Checking that the JSON null and SQL null values are correctly refreshed from the database

        """
        json_null = NullableJSONModel.objects.create(value=Value(None, JSONField()))
        NullableJSONModel.objects.update(value=Value(None, JSONField()))
        json_null.refresh_from_db()
        sql_null = NullableJSONModel.objects.create(value=None)
        sql_null.refresh_from_db()
        # 'null' is not equal to NULL in the database.
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value=Value(None, JSONField())),
            [json_null],
        )
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value=None),
            [json_null],
        )
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__isnull=True),
            [sql_null],
        )
        # 'null' is equal to NULL in Python (None).
        self.assertEqual(json_null.value, sql_null.value)

    @skipUnlessDBFeature("supports_primitives_in_json_field")
    def test_primitives(self):
        """

        Tests the support for primitives in JSON fields by storing and retrieving various data types.

        This test case ensures that the model can successfully store and retrieve primitive values,
        including booleans, integers, floats, and strings, from a JSON field. The test verifies that
        the value retrieved from the database matches the original value stored.

        """
        values = [
            True,
            1,
            1.45,
            "String",
            "",
        ]
        for value in values:
            with self.subTest(value=value):
                obj = JSONModel(value=value)
                obj.save()
                obj.refresh_from_db()
                self.assertEqual(obj.value, value)

    def test_dict(self):
        values = [
            {},
            {"name": "John", "age": 20, "height": 180.3},
            {"a": True, "b": {"b1": False, "b2": None}},
        ]
        for value in values:
            with self.subTest(value=value):
                obj = JSONModel.objects.create(value=value)
                obj.refresh_from_db()
                self.assertEqual(obj.value, value)

    def test_list(self):
        """
        Tests the creation and retrieval of JSONModel objects with varying list values, ensuring data fidelity and accuracy during persistence and retrieval from the database. The test iterates over a range of list values, including empty lists, lists containing strings and numeric values, and lists with nested boolean and null values.
        """
        values = [
            [],
            ["John", 20, 180.3],
            [True, [False, None]],
        ]
        for value in values:
            with self.subTest(value=value):
                obj = JSONModel.objects.create(value=value)
                obj.refresh_from_db()
                self.assertEqual(obj.value, value)

    def test_realistic_object(self):
        """

        Test the creation of a realistic JSON object and verify its validity.

        This test case checks the creation of a JSON object with complex data structure,
        including nested objects and arrays, and ensures that the stored data matches
        the original input. The test covers the following data types:
        - Nested objects (e.g., a person with pets)
        - Arrays of objects (e.g., pets)
        - Arrays of strings (e.g., courses)

        The test validates the object's creation and data integrity by comparing the
        original input data with the data retrieved from the database.

        """
        value = {
            "name": "John",
            "age": 20,
            "pets": [
                {"name": "Kit", "type": "cat", "age": 2},
                {"name": "Max", "type": "dog", "age": 1},
            ],
            "courses": [
                ["A1", "A2", "A3"],
                ["B1", "B2"],
                ["C1"],
            ],
        }
        obj = JSONModel.objects.create(value=value)
        obj.refresh_from_db()
        self.assertEqual(obj.value, value)


@skipUnlessDBFeature("supports_json_field")
class TestQuerying(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.primitives = [True, False, "yes", 7, 9.6]
        values = [
            None,
            [],
            {},
            {"a": "b", "c": 14},
            {
                "a": "b",
                "c": 14,
                "d": ["e", {"f": "g"}],
                "h": True,
                "i": False,
                "j": None,
                "k": {"l": "m"},
                "n": [None, True, False],
                "o": '"quoted"',
                "p": 4.2,
                "r": {"s": True, "t": False},
            },
            [1, [2]],
            {"k": True, "l": False, "foo": "bax"},
            {
                "foo": "bar",
                "baz": {"a": "b", "c": "d"},
                "bar": ["foo", "bar"],
                "bax": {"foo": "bar"},
            },
        ]
        cls.objs = [NullableJSONModel.objects.create(value=value) for value in values]
        if connection.features.supports_primitives_in_json_field:
            cls.objs.extend(
                [
                    NullableJSONModel.objects.create(value=value)
                    for value in cls.primitives
                ]
            )
        cls.raw_sql = "%s::jsonb" if connection.vendor == "postgresql" else "%s"

    def test_exact(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__exact={}),
            [self.objs[2]],
        )

    def test_exact_complex(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__exact={"a": "b", "c": 14}),
            [self.objs[3]],
        )

    def test_icontains(self):
        self.assertCountEqual(
            NullableJSONModel.objects.filter(value__icontains="BaX"),
            self.objs[6:8],
        )

    def test_isnull(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__isnull=True),
            [self.objs[0]],
        )

    def test_ordering_by_transform(self):
        mariadb = connection.vendor == "mysql" and connection.mysql_is_mariadb
        values = [
            {"ord": 93, "name": "bar"},
            {"ord": 22.1, "name": "foo"},
            {"ord": -1, "name": "baz"},
            {"ord": 21.931902, "name": "spam"},
            {"ord": -100291029, "name": "eggs"},
        ]
        for field_name in ["value", "value_custom"]:
            with self.subTest(field=field_name):
                objs = [
                    NullableJSONModel.objects.create(**{field_name: value})
                    for value in values
                ]
                query = NullableJSONModel.objects.filter(
                    **{"%s__name__isnull" % field_name: False},
                ).order_by("%s__ord" % field_name)
                expected = [objs[4], objs[2], objs[3], objs[1], objs[0]]
                if mariadb or connection.vendor == "oracle":
                    # MariaDB and Oracle return JSON values as strings.
                    expected = [objs[2], objs[4], objs[3], objs[1], objs[0]]
                self.assertSequenceEqual(query, expected)

    def test_ordering_grouping_by_key_transform(self):
        """
        Tests the ordering and grouping of querysets using a key transform.

        This function verifies that a queryset of objects can be ordered and grouped by a
        specific key within a JSON field. It checks two different methods of achieving
        this: direct ordering by the JSON field key and annotation using a key transform.
        The test case covers both cases where the JSON field key is not null and where it
        is. It also checks the behavior when interpreting empty strings as nulls is
        enabled or disabled in the database connection features.

        The function asserts that the results of both ordering methods match the expected
        result, and that the grouping and counting of keys in the annotated queryset
        yields the correct output. The test data includes a mix of null and non-null JSON
        field values to ensure robustness of the queryset operations.
        """
        base_qs = NullableJSONModel.objects.filter(value__d__0__isnull=False)
        for qs in (
            base_qs.order_by("value__d__0"),
            base_qs.annotate(
                key=KeyTransform("0", KeyTransform("d", "value"))
            ).order_by("key"),
        ):
            self.assertSequenceEqual(qs, [self.objs[4]])
        none_val = "" if connection.features.interprets_empty_strings_as_nulls else None
        qs = NullableJSONModel.objects.filter(value__isnull=False)
        self.assertQuerySetEqual(
            qs.filter(value__isnull=False)
            .annotate(key=KT("value__d__1__f"))
            .values("key")
            .annotate(count=Count("key"))
            .order_by("count"),
            [(none_val, 0), ("g", 1)],
            operator.itemgetter("key", "count"),
        )

    def test_ordering_grouping_by_count(self):
        """
        Checks that the NullableJSONModel instances are filtered, grouped, and ordered by the count of 'value__d__0' values. 

        The test verifies that the QuerySet is filtered to exclude instances with null 'value' fields, and that the results are grouped by 'value__d__0' and ordered in ascending order by count. The expected result is a QuerySet with two elements, representing the counts of 'value__d__0' being 0 and 1 respectively, in ascending order of their counts.
        """
        qs = (
            NullableJSONModel.objects.filter(
                value__isnull=False,
            )
            .values("value__d__0")
            .annotate(count=Count("value__d__0"))
            .order_by("count")
        )
        self.assertQuerySetEqual(qs, [0, 1], operator.itemgetter("count"))

    def test_order_grouping_custom_decoder(self):
        """
        Tests the grouping of a queryset based on a custom JSON decoder.

        The function creates an instance of NullableJSONModel with a custom JSON value and then queries the model to retrieve instances where the custom JSON value is not null. 
        It then checks if the resulting queryset, when ordered by a specific key in the custom JSON value and annotated with a count of matching instances, returns the expected result.

        This test ensures that the custom JSON decoder is working correctly and that the queryset can be properly grouped and ordered based on the decoded values.
        """
        NullableJSONModel.objects.create(value_custom={"a": "b"})
        qs = NullableJSONModel.objects.filter(value_custom__isnull=False)
        self.assertSequenceEqual(
            qs.values(
                "value_custom__a",
            )
            .annotate(
                count=Count("id"),
            )
            .order_by("value_custom__a"),
            [{"value_custom__a": "b", "count": 1}],
        )

    def test_key_transform_raw_expression(self):
        expr = RawSQL(self.raw_sql, ['{"x": "bar"}'])
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__foo=KeyTransform("x", expr)),
            [self.objs[7]],
        )

    def test_nested_key_transform_raw_expression(self):
        expr = RawSQL(self.raw_sql, ['{"x": {"y": "bar"}}'])
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(
                value__foo=KeyTransform("y", KeyTransform("x", expr))
            ),
            [self.objs[7]],
        )

    def test_key_transform_expression(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__d__0__isnull=False)
            .annotate(
                key=KeyTransform("d", "value"),
                chain=KeyTransform("0", "key"),
                expr=KeyTransform("0", Cast("key", models.JSONField())),
            )
            .filter(chain=F("expr")),
            [self.objs[4]],
        )

    def test_key_transform_annotation_expression(self):
        obj = NullableJSONModel.objects.create(value={"d": ["e", "e"]})
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__d__0__isnull=False)
            .annotate(
                key=F("value__d"),
                chain=F("key__0"),
                expr=Cast("key", models.JSONField()),
            )
            .filter(chain=F("expr__1")),
            [obj],
        )

    def test_nested_key_transform_expression(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__d__0__isnull=False)
            .annotate(
                key=KeyTransform("d", "value"),
                chain=KeyTransform("f", KeyTransform("1", "key")),
                expr=KeyTransform(
                    "f", KeyTransform("1", Cast("key", models.JSONField()))
                ),
            )
            .filter(chain=F("expr")),
            [self.objs[4]],
        )

    def test_nested_key_transform_annotation_expression(self):
        """
        Tests annotation and filtering of a model instance with a nested JSON field.

        This test case exercises the ability to filter and annotate models that contain
        nested JSON fields. Specifically, it creates a model instance with a JSON field
        containing a nested list and dictionary structure, and then uses the Django ORM
        to filter and annotate the instance based on values within the nested structure.

        The test verifies that the correct instance is retrieved when using a combination
        of sequence equality assertion, null checks, and field casting to JSONField,
        demonstrating the usage of Django's built-in filtering and annotation capabilities
        for working with complex JSON data in models.
        """
        obj = NullableJSONModel.objects.create(
            value={"d": ["e", {"f": "g"}, {"f": "g"}]},
        )
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__d__0__isnull=False)
            .annotate(
                key=F("value__d"),
                chain=F("key__1__f"),
                expr=Cast("key", models.JSONField()),
            )
            .filter(chain=F("expr__2__f")),
            [obj],
        )

    def test_nested_key_transform_on_subquery(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__d__0__isnull=False)
            .annotate(
                subquery_value=Subquery(
                    NullableJSONModel.objects.filter(pk=OuterRef("pk")).values("value")
                ),
                key=KeyTransform("d", "subquery_value"),
                chain=KeyTransform("f", KeyTransform("1", "key")),
            )
            .filter(chain="g"),
            [self.objs[4]],
        )

    def test_key_text_transform_char_lookup(self):
        """
        Tests the functionality of KeyTextTransform to extract specific character values from JSON data.

        This function checks if KeyTextTransform can correctly lookup and transform characters from a JSON object and filter results based on the transformed values.

        Two test scenarios are covered: one with a direct key lookup and the other with a nested KeyTextTransform lookup. The function verifies that the expected objects are returned after applying the transformation and filtering criteria.

        The test ensures that the KeyTextTransform functionality works as expected for both straightforward and nested lookup scenarios, providing a way to extract and filter data based on specific character values within JSON objects.
        """
        qs = NullableJSONModel.objects.annotate(
            char_value=KeyTextTransform("foo", "value"),
        ).filter(char_value__startswith="bar")
        self.assertSequenceEqual(qs, [self.objs[7]])

        qs = NullableJSONModel.objects.annotate(
            char_value=KeyTextTransform(1, KeyTextTransform("bar", "value")),
        ).filter(char_value__startswith="bar")
        self.assertSequenceEqual(qs, [self.objs[7]])

    def test_expression_wrapper_key_transform(self):
        self.assertCountEqual(
            NullableJSONModel.objects.annotate(
                expr=ExpressionWrapper(
                    KeyTransform("c", "value"),
                    output_field=IntegerField(),
                ),
            ).filter(expr__isnull=False),
            self.objs[3:5],
        )

    def test_has_key(self):
        self.assertCountEqual(
            NullableJSONModel.objects.filter(value__has_key="a"),
            [self.objs[3], self.objs[4]],
        )

    def test_has_key_null_value(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__has_key="j"),
            [self.objs[4]],
        )

    def test_has_key_deep(self):
        """

        Tests the functionality of the 'has_key' lookup for deep, nested dictionary keys.

        The function creates a series of test cases that verify the ability to filter
        objects based on the presence of a specific key within a nested dictionary
        structure. It checks various ways of constructing the 'has_key' lookup, including
        using string notation, KeyTransform, and F expressions.

        Each test case checks that the correct object is returned when filtering using
        the specified condition. The function ensures that the filter works correctly
        for different levels of nesting and key paths.

        """
        tests = [
            (Q(value__baz__has_key="a"), self.objs[7]),
            (
                Q(value__has_key=KeyTransform("a", KeyTransform("baz", "value"))),
                self.objs[7],
            ),
            (Q(value__has_key=F("value__baz__a")), self.objs[7]),
            (
                Q(value__has_key=KeyTransform("c", KeyTransform("baz", "value"))),
                self.objs[7],
            ),
            (Q(value__has_key=F("value__baz__c")), self.objs[7]),
            (Q(value__d__1__has_key="f"), self.objs[4]),
            (
                Q(
                    value__has_key=KeyTransform(
                        "f", KeyTransform("1", KeyTransform("d", "value"))
                    )
                ),
                self.objs[4],
            ),
            (Q(value__has_key=F("value__d__1__f")), self.objs[4]),
        ]
        for condition, expected in tests:
            with self.subTest(condition=condition):
                self.assertSequenceEqual(
                    NullableJSONModel.objects.filter(condition),
                    [expected],
                )

    def test_has_key_list(self):
        """
        Tests that a Django model instance can be filtered by the presence of specific keys within a list stored in a JSONField.

        This function verifies that various query conditions, including those using nested KeyTransform expressions, can correctly identify a model instance that contains a specific key within a nested JSON list. It checks that only the instance with the matching key is returned in the filtered results.

        The test cases cover different ways to construct the query condition, ensuring that the model instance can be successfully retrieved regardless of the specific syntax used in the query. The goal is to confirm that the supported query syntax behaves as expected and returns the correct results in a variety of scenarios.
        """
        obj = NullableJSONModel.objects.create(value=[{"a": 1}, {"b": "x"}])
        tests = [
            Q(value__1__has_key="b"),
            Q(value__has_key=KeyTransform("b", KeyTransform(1, "value"))),
            Q(value__has_key=KeyTransform("b", KeyTransform("1", "value"))),
            Q(value__has_key=F("value__1__b")),
        ]
        for condition in tests:
            with self.subTest(condition=condition):
                self.assertSequenceEqual(
                    NullableJSONModel.objects.filter(condition),
                    [obj],
                )

    def test_has_keys(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__has_keys=["a", "c", "h"]),
            [self.objs[4]],
        )

    def test_has_any_keys(self):
        self.assertCountEqual(
            NullableJSONModel.objects.filter(value__has_any_keys=["c", "l"]),
            [self.objs[3], self.objs[4], self.objs[6]],
        )

    def test_has_key_number(self):
        """
        #: Test that NullableJSONModel instances can be filtered based on the presence of specific keys in their JSON values.
        #: 
        #: The function tests various scenarios including:
        #:     - Filtering by a single key at the root level or nested within the JSON data.
        #:     - Filtering by multiple keys at the root level or nested within the JSON data.
        #:     - Filtering by any of the specified keys, allowing for at least one key to be present.
        #: 
        #: The test creates a sample NullableJSONModel instance with a complex JSON value and then applies different filter conditions to verify that the correct instance is returned.
        """
        obj = NullableJSONModel.objects.create(
            value={
                "123": "value",
                "nested": {"456": "bar", "lorem": "abc", "999": True},
                "array": [{"789": "baz", "777": "def", "ipsum": 200}],
                "000": "val",
            }
        )
        tests = [
            Q(value__has_key="123"),
            Q(value__nested__has_key="456"),
            Q(value__array__0__has_key="789"),
            Q(value__has_keys=["nested", "123", "array", "000"]),
            Q(value__nested__has_keys=["lorem", "999", "456"]),
            Q(value__array__0__has_keys=["789", "ipsum", "777"]),
            Q(value__has_any_keys=["000", "nonexistent"]),
            Q(value__nested__has_any_keys=["999", "nonexistent"]),
            Q(value__array__0__has_any_keys=["777", "nonexistent"]),
        ]
        for condition in tests:
            with self.subTest(condition=condition):
                self.assertSequenceEqual(
                    NullableJSONModel.objects.filter(condition),
                    [obj],
                )

    @skipUnlessDBFeature("supports_json_field_contains")
    def test_contains(self):
        tests = [
            ({}, self.objs[2:5] + self.objs[6:8]),
            ({"baz": {"a": "b", "c": "d"}}, [self.objs[7]]),
            ({"baz": {"a": "b"}}, [self.objs[7]]),
            ({"baz": {"c": "d"}}, [self.objs[7]]),
            ({"k": True, "l": False}, [self.objs[6]]),
            ({"d": ["e", {"f": "g"}]}, [self.objs[4]]),
            ({"d": ["e"]}, [self.objs[4]]),
            ({"d": [{"f": "g"}]}, [self.objs[4]]),
            ([1, [2]], [self.objs[5]]),
            ([1], [self.objs[5]]),
            ([[2]], [self.objs[5]]),
            ({"n": [None, True, False]}, [self.objs[4]]),
            ({"j": None}, [self.objs[4]]),
        ]
        for value, expected in tests:
            with self.subTest(value=value):
                qs = NullableJSONModel.objects.filter(value__contains=value)
                self.assertCountEqual(qs, expected)

    @skipIfDBFeature("supports_json_field_contains")
    def test_contains_unsupported(self):
        """

        Tests that a NotSupportedError is raised when attempting to use the 'contains' lookup on a JSON field with a database backend that does not support it.

        The test verifies that the expected error message is returned when trying to filter a model based on a JSON field containing a specific value.

        Raises:
            NotSupportedError: If the database backend does not support the 'contains' lookup on JSON fields.

        """
        msg = "contains lookup is not supported on this database backend."
        with self.assertRaisesMessage(NotSupportedError, msg):
            NullableJSONModel.objects.filter(
                value__contains={"baz": {"a": "b", "c": "d"}},
            ).get()

    @skipUnlessDBFeature(
        "supports_primitives_in_json_field",
        "supports_json_field_contains",
    )
    def test_contains_primitives(self):
        for value in self.primitives:
            with self.subTest(value=value):
                qs = NullableJSONModel.objects.filter(value__contains=value)
                self.assertIs(qs.exists(), True)

    @skipUnlessDBFeature("supports_json_field_contains")
    def test_contained_by(self):
        """

        Tests whether the :meth:`contained_by` lookup works as expected for JSON fields.

        This test checks if objects can be filtered based on whether their JSON field is 
        contained by a given JSON value. It verifies that only objects with JSON fields 
        that are supersets of the specified value are returned in the query.

        """
        qs = NullableJSONModel.objects.filter(
            value__contained_by={"a": "b", "c": 14, "h": True}
        )
        self.assertCountEqual(qs, self.objs[2:4])

    @skipIfDBFeature("supports_json_field_contains")
    def test_contained_by_unsupported(self):
        """
        Tests the behavior of the Django ORM when using the 'contained_by' lookup on a database backend that does not support it.
        The test case verifies that a NotSupportedError is raised with a specific error message when attempting to filter objects based on the 'contained_by' lookup.
        """
        msg = "contained_by lookup is not supported on this database backend."
        with self.assertRaisesMessage(NotSupportedError, msg):
            NullableJSONModel.objects.filter(value__contained_by={"a": "b"}).get()

    def test_deep_values(self):
        qs = NullableJSONModel.objects.values_list("value__k__l").order_by("pk")
        expected_objs = [(None,)] * len(self.objs)
        expected_objs[4] = ("m",)
        self.assertSequenceEqual(qs, expected_objs)

    @skipUnlessDBFeature("can_distinct_on_fields")
    def test_deep_distinct(self):
        """
        Test that the ORM can correctly handle distinct queries on nested fields within a JSONField.

        This test case verifies that a distinct query on a nested field returns the expected values, 
        considering the database's null ordering behavior. It checks if the query correctly 
        handles null values and whether they are ordered as the largest or smallest values.
        """
        query = NullableJSONModel.objects.distinct("value__k__l").values_list(
            "value__k__l"
        )
        expected = [("m",), (None,)]
        if not connection.features.nulls_order_largest:
            expected.reverse()
        self.assertSequenceEqual(query, expected)

    def test_isnull_key(self):
        # key__isnull=False works the same as has_key='key'.
        """

        Tests filtering of NullableJSONModel instances based on null values in nested JSON fields.

        This test case verifies that the correct objects are returned when filtering on null values
        in the 'a' and 'j' keys of the JSON field 'value'. It checks both cases where the key is null
        and where it is not null, ensuring that the expected objects are included or excluded from the results.

        """
        self.assertCountEqual(
            NullableJSONModel.objects.filter(value__a__isnull=True),
            self.objs[:3] + self.objs[5:],
        )
        self.assertCountEqual(
            NullableJSONModel.objects.filter(value__j__isnull=True),
            self.objs[:4] + self.objs[5:],
        )
        self.assertCountEqual(
            NullableJSONModel.objects.filter(value__a__isnull=False),
            [self.objs[3], self.objs[4]],
        )
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__j__isnull=False),
            [self.objs[4]],
        )

    def test_isnull_key_or_none(self):
        obj = NullableJSONModel.objects.create(value={"a": None})
        self.assertCountEqual(
            NullableJSONModel.objects.filter(
                Q(value__a__isnull=True) | Q(value__a=None)
            ),
            self.objs[:3] + self.objs[5:] + [obj],
        )

    def test_none_key(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__j=None),
            [self.objs[4]],
        )

    def test_none_key_exclude(self):
        obj = NullableJSONModel.objects.create(value={"j": 1})
        if connection.vendor == "oracle":
            # Oracle supports filtering JSON objects with NULL keys, but the
            # current implementation doesn't support it.
            self.assertSequenceEqual(
                NullableJSONModel.objects.exclude(value__j=None),
                self.objs[1:4] + self.objs[5:] + [obj],
            )
        else:
            self.assertSequenceEqual(
                NullableJSONModel.objects.exclude(value__j=None), [obj]
            )

    def test_shallow_list_lookup(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__0=1),
            [self.objs[5]],
        )

    def test_shallow_obj_lookup(self):
        self.assertCountEqual(
            NullableJSONModel.objects.filter(value__a="b"),
            [self.objs[3], self.objs[4]],
        )

    def test_obj_subquery_lookup(self):
        """
        Tests if a subquery lookup on a nullable JSON field works correctly, ensuring the query returns the expected objects that match the specified condition.
        """
        qs = NullableJSONModel.objects.annotate(
            field=Subquery(
                NullableJSONModel.objects.filter(pk=OuterRef("pk")).values("value")
            ),
        ).filter(field__a="b")
        self.assertCountEqual(qs, [self.objs[3], self.objs[4]])

    def test_deep_lookup_objs(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__k__l="m"),
            [self.objs[4]],
        )

    def test_shallow_lookup_obj_target(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__k={"l": "m"}),
            [self.objs[4]],
        )

    def test_deep_lookup_array(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__1__0=2),
            [self.objs[5]],
        )

    def test_deep_lookup_mixed(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__d__1__f="g"),
            [self.objs[4]],
        )

    def test_deep_lookup_transform(self):
        self.assertCountEqual(
            NullableJSONModel.objects.filter(value__c__gt=2),
            [self.objs[3], self.objs[4]],
        )
        self.assertCountEqual(
            NullableJSONModel.objects.filter(value__c__gt=2.33),
            [self.objs[3], self.objs[4]],
        )
        self.assertIs(NullableJSONModel.objects.filter(value__c__lt=5).exists(), False)

    def test_lookup_exclude(self):
        """
        Test lookup exclude functionality on NullableJSONModel instances.

        This test case verifies that the exclude method correctly filters out objects 
        based on a given condition and that the result is equivalent to using the 
        filter method with a negated condition.

        The test covers various query conditions to ensure the correctness of the 
        exclude method in different scenarios, including complex queries involving 
        nested JSON fields. It validates that the expected objects are returned when 
        filtering out objects that match the specified conditions.
        """
        tests = [
            (Q(value__a="b"), [self.objs[0]]),
            (Q(value__foo="bax"), [self.objs[0], self.objs[7]]),
        ]
        for condition, expected in tests:
            self.assertCountEqual(
                NullableJSONModel.objects.exclude(condition),
                expected,
            )
            self.assertCountEqual(
                NullableJSONModel.objects.filter(~condition),
                expected,
            )

    def test_lookup_exclude_nonexistent_key(self):
        # Values without the key are ignored.
        """

        Tests the lookup and exclusion of objects based on a specific condition.

        The test checks the following scenarios:
        - Excluding objects that match a condition
        - Excluding objects that do not match a condition (inverse of a condition)
        - Filtering objects that match either a condition or its inverse
        - Excluding objects that match a condition that is always false (condition and its inverse)
        - Excluding objects that match a condition and an additional filter
        - Filtering objects that match a condition and an additional filter

        Verifies that the correct objects are returned or excluded in each scenario.

        """
        condition = Q(value__foo="bax")
        objs_with_value = [self.objs[6]]
        objs_with_different_value = [self.objs[0], self.objs[7]]
        self.assertCountEqual(
            NullableJSONModel.objects.exclude(condition),
            objs_with_different_value,
        )
        self.assertSequenceEqual(
            NullableJSONModel.objects.exclude(~condition),
            objs_with_value,
        )
        self.assertCountEqual(
            NullableJSONModel.objects.filter(condition | ~condition),
            objs_with_value + objs_with_different_value,
        )
        self.assertCountEqual(
            NullableJSONModel.objects.exclude(condition & ~condition),
            objs_with_value + objs_with_different_value,
        )
        # Add the __isnull lookup to get an exhaustive set.
        self.assertCountEqual(
            NullableJSONModel.objects.exclude(condition & Q(value__foo__isnull=False)),
            self.objs[0:6] + self.objs[7:],
        )
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(condition & Q(value__foo__isnull=False)),
            objs_with_value,
        )

    def test_usage_in_subquery(self):
        self.assertCountEqual(
            NullableJSONModel.objects.filter(
                id__in=NullableJSONModel.objects.filter(value__c=14),
            ),
            self.objs[3:5],
        )

    @skipUnlessDBFeature("supports_json_field_contains")
    def test_array_key_contains(self):
        """

        Tests the Django ORM's ability to filter JSON fields for contains queries on array keys.

        This test case verifies that the database correctly handles filtering of JSON fields
        when the search value is contained within an array key. It checks various scenarios,
        including exact matches, partial matches, and no matches.

        The test uses a set of predefined test cases, each consisting of a value to search for
        and the expected result set. It then uses the Django ORM's filter method to query the
        database and asserts that the returned results match the expected outcome.

        """
        tests = [
            ([], [self.objs[7]]),
            ("bar", [self.objs[7]]),
            (["bar"], [self.objs[7]]),
            ("ar", []),
        ]
        for value, expected in tests:
            with self.subTest(value=value):
                self.assertSequenceEqual(
                    NullableJSONModel.objects.filter(value__bar__contains=value),
                    expected,
                )

    def test_key_iexact(self):
        """

        Tests the iexact lookup on a JSONField, ensuring that it matches values in a case-insensitive manner.

        The test verifies that the lookup ignores the case of the string being searched for, 
        but does not strip any quotes from the search term, treating 'BaR' and '\"BaR\"' as distinct values.

        """
        self.assertIs(
            NullableJSONModel.objects.filter(value__foo__iexact="BaR").exists(), True
        )
        self.assertIs(
            NullableJSONModel.objects.filter(value__foo__iexact='"BaR"').exists(), False
        )

    def test_key_in(self):
        tests = [
            ("value__c__in", [14], self.objs[3:5]),
            ("value__c__in", [14, 15], self.objs[3:5]),
            ("value__0__in", [1], [self.objs[5]]),
            ("value__0__in", [1, 3], [self.objs[5]]),
            ("value__foo__in", ["bar"], [self.objs[7]]),
            (
                "value__foo__in",
                [KeyTransform("foo", KeyTransform("bax", "value"))],
                [self.objs[7]],
            ),
            ("value__foo__in", [F("value__bax__foo")], [self.objs[7]]),
            (
                "value__foo__in",
                [KeyTransform("foo", KeyTransform("bax", "value")), "baz"],
                [self.objs[7]],
            ),
            ("value__foo__in", [F("value__bax__foo"), "baz"], [self.objs[7]]),
            ("value__foo__in", ["bar", "baz"], [self.objs[7]]),
            ("value__bar__in", [["foo", "bar"]], [self.objs[7]]),
            ("value__bar__in", [["foo", "bar"], ["a"]], [self.objs[7]]),
            ("value__bax__in", [{"foo": "bar"}, {"a": "b"}], [self.objs[7]]),
            ("value__h__in", [True, "foo"], [self.objs[4]]),
            ("value__i__in", [False, "foo"], [self.objs[4]]),
        ]
        for lookup, value, expected in tests:
            with self.subTest(lookup=lookup, value=value):
                self.assertCountEqual(
                    NullableJSONModel.objects.filter(**{lookup: value}),
                    expected,
                )

    def test_key_values(self):
        qs = NullableJSONModel.objects.filter(value__h=True)
        tests = [
            ("value__a", "b"),
            ("value__c", 14),
            ("value__d", ["e", {"f": "g"}]),
            ("value__h", True),
            ("value__i", False),
            ("value__j", None),
            ("value__k", {"l": "m"}),
            ("value__n", [None, True, False]),
            ("value__p", 4.2),
            ("value__r", {"s": True, "t": False}),
        ]
        for lookup, expected in tests:
            with self.subTest(lookup=lookup):
                self.assertEqual(qs.values_list(lookup, flat=True).get(), expected)

    def test_key_values_boolean(self):
        """
        Tests the filtering of NullableJSONModel instances based on boolean key values.

        Checks if the specified boolean key values are correctly retrieved from the filtered queryset.

        The function verifies that the queryset returned by the filter method contains the expected boolean values 
        for the specified keys, ensuring that the database query is executed as expected.
        """
        qs = NullableJSONModel.objects.filter(value__h=True, value__i=False)
        tests = [
            ("value__h", True),
            ("value__i", False),
        ]
        for lookup, expected in tests:
            with self.subTest(lookup=lookup):
                self.assertIs(qs.values_list(lookup, flat=True).get(), expected)

    @skipUnlessDBFeature("supports_json_field_contains")
    def test_key_contains(self):
        self.assertIs(
            NullableJSONModel.objects.filter(value__foo__contains="ar").exists(), False
        )
        self.assertIs(
            NullableJSONModel.objects.filter(value__foo__contains="bar").exists(), True
        )

    def test_key_icontains(self):
        self.assertIs(
            NullableJSONModel.objects.filter(value__foo__icontains="Ar").exists(), True
        )

    def test_key_startswith(self):
        self.assertIs(
            NullableJSONModel.objects.filter(value__foo__startswith="b").exists(), True
        )

    def test_key_istartswith(self):
        self.assertIs(
            NullableJSONModel.objects.filter(value__foo__istartswith="B").exists(), True
        )

    def test_key_endswith(self):
        self.assertIs(
            NullableJSONModel.objects.filter(value__foo__endswith="r").exists(), True
        )

    def test_key_iendswith(self):
        self.assertIs(
            NullableJSONModel.objects.filter(value__foo__iendswith="R").exists(), True
        )

    def test_key_regex(self):
        self.assertIs(
            NullableJSONModel.objects.filter(value__foo__regex=r"^bar$").exists(), True
        )

    def test_key_iregex(self):
        self.assertIs(
            NullableJSONModel.objects.filter(value__foo__iregex=r"^bAr$").exists(), True
        )

    def test_key_quoted_string(self):
        self.assertEqual(
            NullableJSONModel.objects.filter(value__o='"quoted"').get(),
            self.objs[4],
        )

    @skipUnlessDBFeature("has_json_operators")
    def test_key_sql_injection(self):
        with CaptureQueriesContext(connection) as queries:
            self.assertIs(
                NullableJSONModel.objects.filter(
                    **{
                        """value__test' = '"a"') OR 1 = 1 OR ('d""": "x",
                    }
                ).exists(),
                False,
            )
        self.assertIn(
            """."value" -> 'test'' = ''"a"'') OR 1 = 1 OR (''d') = '"x"'""",
            queries[0]["sql"],
        )

    @skipIfDBFeature("has_json_operators")
    def test_key_sql_injection_escape(self):
        query = str(
            JSONModel.objects.filter(
                **{
                    """value__test") = '"a"' OR 1 = 1 OR ("d""": "x",
                }
            ).query
        )
        self.assertIn('"test\\"', query)
        self.assertIn('\\"d', query)

    def test_key_escape(self):
        """

        Tests that the database can correctly filter JSON fields when the key is escaped.

        Verifies that a model instance with a nested JSON field containing a key 
        starting with a percentage sign can be successfully retrieved using the 
        filter method. This ensures that the key is properly escaped and the 
        query is executed as intended. 

        The test covers creation of an instance and its subsequent retrieval 
        based on the value associated with the escaped key, confirming the 
        correctness of the filtering mechanism in the database.

        """
        obj = NullableJSONModel.objects.create(value={"%total": 10})
        self.assertEqual(
            NullableJSONModel.objects.filter(**{"value__%total": 10}).get(), obj
        )

    def test_none_key_and_exact_lookup(self):
        self.assertSequenceEqual(
            NullableJSONModel.objects.filter(value__a="b", value__j=None),
            [self.objs[4]],
        )

    def test_lookups_with_key_transform(self):
        """

        Tests the filter lookups on the NullableJSONModel with key transformation.

        This test case ensures that various filter lookups are correctly applied to the model 
        when the keys in the lookup are transformed. It checks the existence of objects in 
        the database that match the defined lookups with different types of values, such as 
        single keys and lists of keys.

        The test covers the following lookup types: 
        - 'value__baz__has_key' to check for a single key presence
        - 'value__baz__has_keys' to check for multiple keys presence
        - 'value__baz__has_any_keys' to check for any of the given keys presence
        - 'value__has_key' to check for a key presence with a custom key transformation 
          using KeyTextTransform.

        """
        tests = (
            ("value__baz__has_key", "c"),
            ("value__baz__has_keys", ["a", "c"]),
            ("value__baz__has_any_keys", ["a", "x"]),
            ("value__has_key", KeyTextTransform("foo", "value")),
        )
        for lookup, value in tests:
            with self.subTest(lookup=lookup):
                self.assertIs(
                    NullableJSONModel.objects.filter(
                        **{lookup: value},
                    ).exists(),
                    True,
                )

    @skipUnlessDBFeature("supports_json_field_contains")
    def test_contains_contained_by_with_key_transform(self):
        """
        Tests the 'contains' and 'contained_by' lookups on JSON fields with key transformations.

        This test covers various scenarios for using 'contains' and 'contained_by' lookups on JSON fields,
        including using key transformations, F expressions, and RawSQL queries.
        It verifies that the lookups correctly match the expected values and return the relevant objects.
        The test cases include checks for list matching requirements and support for different data types.
        It ensures that the 'contains' and 'contained_by' lookups work as expected in different contexts,
        providing a comprehensive test of these features in the NullableJSONModel class.
        """
        tests = [
            ("value__d__contains", "e"),
            ("value__d__contains", [{"f": "g"}]),
            ("value__contains", KeyTransform("bax", "value")),
            ("value__contains", F("value__bax")),
            ("value__baz__contains", {"a": "b"}),
            ("value__baz__contained_by", {"a": "b", "c": "d", "e": "f"}),
            (
                "value__contained_by",
                KeyTransform(
                    "x",
                    RawSQL(
                        self.raw_sql,
                        ['{"x": {"a": "b", "c": 1, "d": "e"}}'],
                    ),
                ),
            ),
        ]
        # For databases where {'f': 'g'} (without surrounding []) matches
        # [{'f': 'g'}].
        if not connection.features.json_key_contains_list_matching_requires_list:
            tests.append(("value__d__contains", {"f": "g"}))
        for lookup, value in tests:
            with self.subTest(lookup=lookup, value=value):
                self.assertIs(
                    NullableJSONModel.objects.filter(
                        **{lookup: value},
                    ).exists(),
                    True,
                )

    def test_join_key_transform_annotation_expression(self):
        """

        Registers a test for validating the join key transformation and annotation expression.

        This test case verifies that the annotation of a related JSON model with a join key expression correctly filters the related objects based on the transformation of their JSON values.

        Specifically, it checks that the annotation of a JSON model with a key derived from its 'value__d' field, and the corresponding related key from the 'json_model__value__d' field, correctly matches the first element of the related key ('related_key__0') with the second element of the key ('key__1').

        The test ensures that only the related object with the matching key is returned, demonstrating the correct application of the annotation and filtering expressions.

        """
        related_obj = RelatedJSONModel.objects.create(
            value={"d": ["f", "e"]},
            json_model=self.objs[4],
        )
        RelatedJSONModel.objects.create(
            value={"d": ["e", "f"]},
            json_model=self.objs[4],
        )
        self.assertSequenceEqual(
            RelatedJSONModel.objects.annotate(
                key=F("value__d"),
                related_key=F("json_model__value__d"),
                chain=F("key__1"),
                expr=Cast("key", models.JSONField()),
            ).filter(chain=F("related_key__0")),
            [related_obj],
        )

    def test_key_text_transform_from_lookup(self):
        """
        Tests the transformation of text fields using the KeyText transformer.
        The function verifies that the KeyText transformer correctly extracts and filters specific values from JSON data in the NullableJSONModel objects.
        It checks for the presence of specific substrings within the transformed text and asserts that the resulting query sets match the expected objects.
        """
        qs = NullableJSONModel.objects.annotate(b=KT("value__bax__foo")).filter(
            b__contains="ar",
        )
        self.assertSequenceEqual(qs, [self.objs[7]])
        qs = NullableJSONModel.objects.annotate(c=KT("value__o")).filter(
            c__contains="uot",
        )
        self.assertSequenceEqual(qs, [self.objs[4]])

    def test_key_text_transform_from_lookup_invalid(self):
        """
        Tests the key text transform functionality when given an invalid lookup.

        Verifies that a ValueError is raised with a descriptive message when attempting 
        to create a key text transform (KT) instance with an empty string or a string 
        value, indicating that the lookup must contain either a key or index transforms.

        Ensures the function behaves as expected in error scenarios, helping to 
        prevent incorrect usage and providing clear guidance for users on how to 
        correctly utilize the key text transform functionality.
        """
        msg = "Lookup must contain key or index transforms."
        with self.assertRaisesMessage(ValueError, msg):
            KT("value")
        with self.assertRaisesMessage(ValueError, msg):
            KT("")

    def test_literal_annotation_filtering(self):
        """

        Tests literal annotation filtering using JSONField.

        Verifies that annotated JSON data can be used as a filter criterion, ensuring 
        that the filtering process correctly matches the annotated data. The test 
        ensures that when all objects are annotated with a specific JSON value and 
        then filtered based on that value, the result set includes all original objects.

        This test case covers the combination of annotation and filtering in a Django 
         ORM query, highlighting the capability to apply filters on annotated JSON 
         fields as a crucial aspect of data querying and manipulation.

        """
        all_objects = NullableJSONModel.objects.order_by("id")
        qs = all_objects.annotate(data=Value({"foo": "bar"}, JSONField())).filter(
            data__foo="bar"
        )
        self.assertQuerySetEqual(qs, all_objects)
