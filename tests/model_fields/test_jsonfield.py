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
        Test that creating a NullableJSONModel instance with a non-JSON serializable value raises a TypeError.

        The test specifically checks that the error message indicates the value is 'not JSON serializable', verifying the correct exception handling for invalid values.
        """
        msg = "is not JSON serializable"
        with self.assertRaisesMessage(TypeError, msg):
            NullableJSONModel.objects.create(
                value={
                    "uuid": uuid.UUID("d85e2076-b67c-4ee7-8c3a-2bf5a2cc2475"),
                }
            )

    def test_custom_encoder_decoder(self):
        value = {"uuid": uuid.UUID("{d85e2076-b67c-4ee7-8c3a-2bf5a2cc2475}")}
        obj = NullableJSONModel(value_custom=value)
        obj.clean_fields()
        obj.save()
        obj.refresh_from_db()
        self.assertEqual(obj.value_custom, value)

    def test_db_check_constraints(self):
        """
        Test that the database check constraints are enforced when attempting to create a NullableJSONModel instance with an invalid JSON value.

        This test verifies that creating a NullableJSONModel instance with a string that cannot be parsed as valid JSON raises an exception, specifically one of IntegrityError, DataError, or OperationalError, indicating that the database constraints are preventing the insertion of invalid data.
        """
        value = "{@!invalid json value 123 $!@#"
        with mock.patch.object(DjangoJSONEncoder, "encode", return_value=value):
            with self.assertRaises((IntegrityError, DataError, OperationalError)):
                NullableJSONModel.objects.create(value_custom=value)


class TestMethods(SimpleTestCase):
    def test_deconstruct(self):
        field = models.JSONField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.JSONField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})

    def test_deconstruct_custom_encoder_decoder(self):
        """

        Test if a custom JSON field correctly deconstructs its encoder and decoder.

        Verifies that when a JSONField is defined with a custom encoder and decoder, 
        the deconstruct method returns the correct encoder and decoder classes.

        """
        field = models.JSONField(encoder=DjangoJSONEncoder, decoder=CustomJSONDecoder)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(kwargs["encoder"], DjangoJSONEncoder)
        self.assertEqual(kwargs["decoder"], CustomJSONDecoder)

    def test_get_transforms(self):
        @models.JSONField.register_lookup
        """

        Retrieves and verifies a custom transformation for a JSONField instance.

        This function tests the ability to register a custom lookup transformation with 
        a JSONField, retrieve it, and then unregister it. It verifies that the 
        registered transformation is correctly retrieved and that an unregistered 
        transform returns a default transformation.

        The test case ensures that the get_transform method of a JSONField instance 
        behaves as expected with both registered and unregistered transformations.

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
        msg = "The encoder parameter must be a callable object."
        with self.assertRaisesMessage(ValueError, msg):
            models.JSONField(encoder=DjangoJSONEncoder())

    def test_invalid_decoder(self):
        msg = "The decoder parameter must be a callable object."
        with self.assertRaisesMessage(ValueError, msg):
            models.JSONField(decoder=CustomJSONDecoder())

    def test_validation_error(self):
        field = models.JSONField()
        msg = "Value must be valid JSON."
        value = uuid.UUID("{d85e2076-b67c-4ee7-8c3a-2bf5a2cc2475}")
        with self.assertRaisesMessage(ValidationError, msg):
            field.clean({"uuid": value}, None)

    def test_custom_encoder(self):
        """
        Tests the custom JSON encoder functionality provided by DjangoJSONEncoder.

        This test case verifies that a Django model field using the custom encoder correctly serializes and deserializes a UUID value. It checks that the UUID object, which is not natively JSON serializable, is properly encoded and cleaned when stored in a JSON field, ensuring data integrity and consistency.
        """
        field = models.JSONField(encoder=DjangoJSONEncoder)
        value = uuid.UUID("{d85e2076-b67c-4ee7-8c3a-2bf5a2cc2475}")
        field.clean({"uuid": value}, None)


class TestFormField(SimpleTestCase):
    def test_formfield(self):
        """

        Tests that a model field of type JSONField generates a form field of type JSONField.

        This test case verifies the form field creation process for a JSONField model field, 
        ensuring that the resulting form field is of the correct type.

        """
        model_field = models.JSONField()
        form_field = model_field.formfield()
        self.assertIsInstance(form_field, forms.JSONField)

    def test_formfield_custom_encoder_decoder(self):
        """
        Tests that a JSON form field correctly utilizes a custom encoder and decoder.

        This test verifies that when a model field with a custom JSON encoder and decoder
        is converted to a form field, the resulting form field retains these custom
        encoding and decoding settings. The test ensures that both the encoder and
        decoder specified at the model field level are correctly propagated to the form
        field, allowing for customized JSON serialization and deserialization behavior
        in form handling scenarios.
        """
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
        Checks the serialization of JSONModel instances to ensure they match expected output.

        This test iterates over a set of predefined test values and their corresponding serialized representations.
        For each value, it creates a JSONModel instance, serializes it to JSON, and then verifies that the resulting JSON data matches the expected serialized form.
        """
        for value, serialized in self.test_values:
            with self.subTest(value=value):
                instance = JSONModel(value=value)
                data = serializers.serialize("json", [instance])
                self.assertJSONEqual(data, self.test_data % serialized)

    def test_loading(self):
        """
        Tests the loading of serialized data into instances.

        This test case verifies that data serialized in JSON format can be correctly deserialized and loaded into class instances.
        It checks that the deserialized instances have the expected value, ensuring that the serialization and deserialization process works as intended.

        The test iterates over a set of test values and their corresponding serialized representations, testing each pair individually.
        If any deserialization or value comparison fails, the test will report the specific value that caused the failure, facilitating debugging and issue identification.
        """
        for value, serialized in self.test_values:
            with self.subTest(value=value):
                instance = list(
                    serializers.deserialize("json", self.test_data % serialized)
                )[0].object
                self.assertEqual(instance.value, value)

    def test_xml_serialization(self):
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
        """
        Tests that a nullable JSON field correctly stores and retrieves a null value.

        This test case verifies that when a nullable JSON field is set to null, the value
        is persisted to the database and can be successfully retrieved, maintaining its
        null state. The test ensures that the data model's behavior aligns with
        expectations when handling null or empty values in its JSON fields.
        """
        obj = NullableJSONModel(value=None)
        obj.save()
        obj.refresh_from_db()
        self.assertIsNone(obj.value)

    @skipUnlessDBFeature("supports_primitives_in_json_field")
    def test_json_null_different_from_sql_null(self):
        """
        Tests the difference between JSON null and SQL null in a model's JSON field.

        This test case checks that JSON null and SQL null are handled correctly and
        distinguished from each other when querying the model. It verifies that
        filtering by JSON null, SQL null, and the `isnull` lookup type produce the
        expected results, ensuring that the model's JSON field behaves as expected
        when dealing with null values.

        The test covers the creation of instances with JSON null and SQL null values,
        updating instances, and querying the model using different filter criteria.
        It asserts that the expected instances are returned when filtering by JSON null,
        SQL null, and `isnull=True`, demonstrating that the model correctly handles
        null values in its JSON field.

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
        """

        Tests the creation and storage of dictionaries in the JSONModel.

        This test case covers a range of dictionary values, including empty dictionaries, 
        dictionaries with simple types (strings, integers, floats), and nested dictionaries 
        with boolean and null values. It ensures that each dictionary is successfully 
        stored and retrieved, with the retrieved value matching the original value.

        """
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
        """

        Set up test data for JSON field model tests.

        This method creates a set of test objects with various JSON values, including
        simple primitives, complex nested structures, and edge cases like null and empty lists.
        The created objects are stored in the `objs` class attribute.

        If the database backend supports storing primitives in JSON fields, additional
        objects with primitive values are created and added to the `objs` list.

        Additionally, a raw SQL template string is generated based on the database vendor,
        which is used to specify the JSON field type in SQL queries.

        """
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
        """

        Tests the ordering of NullableJSONModel instances by a JSON field's 'ord' value.

        This test creates a set of objects with various 'ord' values, both positive, negative, 
        and decimal, and verifies that they are retrieved in the correct order.

        The test considers database vendor-specific behavior, particularly differences 
        between MySQL, MariaDB, and Oracle, to ensure the ordering works as expected 
        across these platforms.

        It checks the ordering for both 'value' and 'value_custom' fields, to ensure 
        consistency in the behavior. The test includes sub-tests for each field, 
        allowing for more detailed analysis of any failures.

        """
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

        Tests the ordering of a queryset by the count of a specific field.

        This test case verifies that a queryset can be correctly ordered by the count of 
        a specific field within a JSON model. The field of interest is 'value__d__0' 
        within the NullableJSONModel. The test checks if the resulting queryset is ordered 
        in ascending order by the count of 'value__d__0'.

        The expected result is that the queryset is ordered such that the item with the 
        smallest count is first, followed by the item with the next smallest count.

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
        Tests the grouping and ordering of NullableJSONModel instances filtered by custom decoder values.

        This test case verifies that instances with non-null custom decoder values can be properly grouped and ordered based on the values within the custom decoder.

        It checks that the count of instances is accurately calculated and that the results are ordered as expected, ensuring correct functionality of the filtering and aggregation operations on the custom decoder values.
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
        """
        Tests the key transformation of a raw SQL expression by filtering NullableJSONModel objects based on the 'foo' key, which is transformed from the 'x' key of a JSON object within a raw SQL query, verifying that the result matches the expected object.
        """
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
        Test a complex query on a JSONField that involves nested key transformations and expression annotations.

        This test case verifies the correctness of a query that filters objects based on a nested key in a JSON field, annotates the result with additional fields derived from the JSON data, and then filters the annotated result based on another nested key.

        The test covers various aspects of query functionality, including:

        * Filtering objects based on nested keys in a JSON field
        * Annotating query results with new fields derived from the JSON data using database functions
        * Casting annotated fields to specific data types
        * Filtering annotated results based on additional conditions

        It ensures that the query correctly identifies objects that match the specified criteria and that the annotated fields are correctly computed and used in the filtering process.
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

        Tests the functionality of the KeyTextTransform lookup by transforming a JSON key's value 
        and filtering the results. 

        The test checks for the ability to transform a key's value using a string key and 
        verifies the correct object is returned. It also checks for the ability to nest 
        KeyTextTransform lookups, using the result of one transformation as the key for 
        another, and verifies the correct object is returned.

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
        Tests the :meth:`has_key` lookup for JSONField values in the NullableJSONModel.

        Verifies that the lookup correctly filters objects based on the presence of a key
        in a nested JSON field. The test covers various usage scenarios, including the use
        of :class:`~django.db.models.Q`, :class:`~django.db.models.KeyTransform`, and 
        :class:`~django.db.models.F` expressions to construct the lookup conditions.

        Ensures that the :meth:`filter` method returns the expected results for different
        lookup combinations, confirming the correctness of the :meth:`has_key` lookup
        implementation.
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

        Tests that the model's JSONField supports querying with has_key lookup.

        This test case creates a model instance with a JSONField containing a list
        of dictionaries and then checks various query conditions to verify that the
        has_key lookup works as expected. The test queries use different approaches
        to check for the existence of a specific key within the JSON data structure.

        The test ensures that the model instance is correctly retrieved when querying
        for the presence of a key in the JSON data, validating the functionality of
        the has_key lookup in different scenarios.

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
        Tests the filtering of nullable JSON fields based on the 'contained_by' lookup.

        Checks if the value of the JSON field is contained by a given dictionary. The 
        function uses a query set to filter objects from the NullableJSONModel where 
        the 'value' field contains the specified dictionary. It then asserts that the 
        resulting query set is equal to a subset of the objects being tested.

        The test case verifies the correct functionality of the 'contained_by' lookup 
        for JSON fields, ensuring that it returns the expected results when used in a 
        database query. It covers the scenario where the dictionary contains different 
        data types, including strings, integers, and booleans. The test relies on the 
        database feature 'supports_json_field_contains' being supported to run the test 
        successfully.
        """
        qs = NullableJSONModel.objects.filter(
            value__contained_by={"a": "b", "c": 14, "h": True}
        )
        self.assertCountEqual(qs, self.objs[2:4])

    @skipIfDBFeature("supports_json_field_contains")
    def test_contained_by_unsupported(self):
        """

        Tests that a NotSupportedError is raised when attempting to use the 'contained_by' lookup on a JSON field in a database backend that does not support it.

        This test ensures that the ORM correctly identifies and handles the limitation of the underlying database, providing a clear error message to the user.

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
        Tests that the ORM can correctly perform a distinct query on a deeply nested field, specifically on the 'l' field within 'k' within 'value' in the NullableJSONModel. 

        The query returns a list of tuples containing the distinct values of 'l' and verifies that the result matches the expected output, taking into account whether the database orders null values as largest or not.
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
        Tests the filtering of NullableJSONModel objects based on the presence or absence of specific keys in their JSON values.

        The test covers various scenarios, including:

        * Filtering objects where a key is null or missing
        * Filtering objects where a key is present and not null
        * Verifying the correctness of the filtered results by comparing them to the expected sets of objects

        The test checks the behavior of the `isnull` lookup type for JSON fields, ensuring that it correctly identifies objects with null or missing keys.
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
        """
        Test whether the 'value__a' key in a NullableJSONModel object is handled correctly when it is either null or None.

        This test verifies that the object is correctly filtered when the 'value__a' key is null and when it is explicitly set to None, checking that the correct set of objects are returned from the database.
        """
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
        """

        Tests the exclusion of objects from a query based on a None key in a JSON field.

        This test ensures that when using the ``exclude`` method with a ``value__j=None`` filter,
        the correct objects are excluded from the results. The behavior of this filter is
        dependent on the database vendor, with Oracle handling the None key differently than other vendors.

        """
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

        Tests the functionality of lookup on subqueries in the NullableJSONModel objects.

        This test case verifies that the correct objects are retrieved when using a subquery 
        to filter on a nested field within a JSONField, specifically checks the 
        filtering on 'a' key within the 'value' JSON field.

        The test creates an annotated query set that includes a subquery for the 'value' 
        field, filters on a specific value ('b') for the 'a' key within that 'value' 
        field, and then asserts that the resulting query set matches the expected list 
        of objects.

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
        """

        Tests the deep lookup transformation functionality of the NullableJSONModel.

        This function verifies that the model can correctly filter objects based on nested JSON values.
        It checks that objects with a nested value greater than a specified threshold are returned,
        and that objects with a nested value less than a specified threshold are not returned.
        The function also tests that the filtering works with both integer and floating-point threshold values.

        The tests cover the following scenarios:
        - Filtering objects with a nested value greater than an integer threshold
        - Filtering objects with a nested value greater than a floating-point threshold
        - Checking the non-existence of objects with a nested value less than a specified threshold

        """
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
        Tests the lookup exclusion functionality of NullableJSONModel.

        This test case verifies that the exclude method correctly filters out objects 
        based on the provided conditions and that the result is equivalent to using 
        the filter method with a negated condition. 

        It checks the correctness of the exclude method by comparing the results with 
        predefined expected outcomes for different conditions, ensuring that the 
        excluded objects match the expected ones.

        The test uses query conditions to filter objects based on specific values in 
        their JSON fields and checks the count of remaining objects after exclusion 
        against the expected counts, ensuring the correctness of the exclude method
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

        Tests the 'contains' lookup on an array key within a JSON field.

        Checks that the 'contains' filter behaves as expected when applied to an array key within a JSON field.
        The test covers various scenarios, including empty arrays, strings, and lists, to ensure the filter returns the correct results.

        The test asserts that the filtered queryset matches the expected objects for each test case.

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
        """
        Tests the filtering of NullableJSONModel instances based on key values.

        This function verifies that the values associated with specific keys in the JSON field can be queried correctly.
        It checks various data types, including strings, integers, lists, dictionaries, booleans, and null values, to ensure that the filtering works as expected.
        The test cases cover a range of scenarios to provide robust coverage of the functionality, including the handling of nested data structures and numeric values.
        The function ensures that the results of the queries match the expected values, providing confidence in the correctness of the filtering logic.
        """
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

        This test case verifies that the correct boolean values are retrieved when filtering 
        NullableJSONModel instances using the 'value__h' and 'value__i' lookups. It checks 
        that the resulting query set contains the expected boolean values for the specified 
        lookups.

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
        """

        Test if JSON key names are properly escaped to prevent SQL injection attacks.

        Verifies that Django's ORM correctly escapes JSON key names when constructing SQL queries,
        preventing potential SQL injection vulnerabilities when filtering on JSON fields.

        The test checks if special characters in JSON key names are properly escaped in the resulting SQL query.

        """
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
        Tests the functionality of lookups on the NullableJSONModel with key transformations.

        This test suite covers different types of lookups, including checking for the presence of a specific key, multiple keys, and any key within a list.
        It verifies that the objects can be successfully filtered using these lookups, ensuring the expected results are returned.

        The following lookup types are tested:
        - Checking if a key is present
        - Checking if multiple keys are present
        - Checking if any key from a list is present
        - Checking if a transformed key is present

        Each test case ensures that the filtered query returns at least one object, validating the correctness of the lookup functionality.
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

        Tests the 'contains' and 'contained_by' lookup types with JSON fields 
        and various key transformations.

        This test case covers different scenarios where the 'contains' and 'contained_by' 
        lookups are used with JSON fields and key transformations such as KeyTransform and F expressions.
        It verifies that the filter queries with these lookups correctly return the expected results.

        The test checks the following scenarios:
        - Using 'contains' with simple values and JSON objects
        - Using 'contained_by' with JSON objects
        - Using key transformations such as KeyTransform and F expressions with 'contains'
        - Handling cases where JSON key contains list matching requires a list

        Each test case is run with the specified lookup type and value, and the test asserts 
        that at least one object exists in the database that matches the filter query.

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

        Tests the transformation of a JSON field using annotation expressions.
        Verifies that the join operation on related models returns the expected object
        when applying a filter on a chain of JSON field keys.

        The test case creates two related JSON model objects with nested JSON data
        and then uses annotation expressions to extract and compare specific values
        from the JSON fields. The result is filtered based on a chain of keys,
        demonstrating the correct application of join and filtering operations.

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
        qs = NullableJSONModel.objects.annotate(b=KT("value__bax__foo")).filter(
            b__contains="ar",
        )
        self.assertSequenceEqual(qs, [self.objs[7]])
        qs = NullableJSONModel.objects.annotate(c=KT("value__o")).filter(
            c__contains="uot",
        )
        self.assertSequenceEqual(qs, [self.objs[4]])

    def test_key_text_transform_from_lookup_invalid(self):
        msg = "Lookup must contain key or index transforms."
        with self.assertRaisesMessage(ValueError, msg):
            KT("value")
        with self.assertRaisesMessage(ValueError, msg):
            KT("")

    def test_literal_annotation_filtering(self):
        """

        Tests whether literal annotations can be properly filtered in a query.

        This test case verifies that when using a literal value in an annotation,
        the subsequent filter operation correctly narrows down the results based
        on the annotated field. Specifically, it checks if the filter criterion
        applied to the annotated JSON field successfully identifies the expected
        data subset.

        The test covers the scenario where all objects are expected to pass the
        filtering condition due to the literal annotation, ensuring the resulting
        queryset matches the original unordered set of objects.

        """
        all_objects = NullableJSONModel.objects.order_by("id")
        qs = all_objects.annotate(data=Value({"foo": "bar"}, JSONField())).filter(
            data__foo="bar"
        )
        self.assertQuerySetEqual(qs, all_objects)
