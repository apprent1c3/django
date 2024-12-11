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

        The test verifies that attempting to store a value that cannot be serialized to JSON, such as a UUID object, results in an error with a message indicating that the value is not JSON serializable
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
        Tests the custom encoder and decoder functionality for the NullableJSONModel by creating an instance with a UUID value, saving it to the database, and then verifying that the value is correctly retrieved and matches the original value. This ensures that the custom JSON encoding and decoding process works as expected for complex data types such as UUIDs.
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

        Retrieve a registered transform for a JSONField.

        This method checks if a transform with the given name is registered for a JSONField.
        If the transform is found, it returns the corresponding transform class.
        If the transform is not found, it returns a KeyTransformFactory instance.

        It is useful for testing the registration and unregistration of custom transforms for JSONFields.

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
        """
        Tests the validation of KeyTransformTextLookupMixin's constructor.

           Verifies that the mixin raises a TypeError when instantiated with a transform
           that is not an instance of KeyTransform, ensuring correct usage and preventing
           unexpected behavior.
        """
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
        Tests that passing a non-callable object to the encoder parameter of a JSONField raises a ValueError.

        The test verifies that providing a non-callable object, such as an instance of DjangoJSONEncoder, to the encoder parameter results in a ValueError being raised with a descriptive error message.

        Args:
            None

        Returns:
            None

        Raises:
            ValueError: If the encoder parameter is not a callable object.

        """
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
        field = models.JSONField(encoder=DjangoJSONEncoder)
        value = uuid.UUID("{d85e2076-b67c-4ee7-8c3a-2bf5a2cc2475}")
        field.clean({"uuid": value}, None)


class TestFormField(SimpleTestCase):
    def test_formfield(self):
        model_field = models.JSONField()
        form_field = model_field.formfield()
        self.assertIsInstance(form_field, forms.JSONField)

    def test_formfield_custom_encoder_decoder(self):
        """
        Tests the custom encoding and decoding functionality of a form field generated from a model field.

        This test case verifies that the form field properly utilizes a custom JSON encoder and decoder.
        It ensures that the encoder and decoder specified in the model field are correctly propagated to the form field.

        The purpose of this test is to guarantee that the custom encoding and decoding logic is correctly applied when
        converting data between the model field and the form field, allowing for seamless and accurate data representation.

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
        Tests the serialization of JSONModel instances to ensure they are correctly dumped to JSON.

        This test iterates over a predefined set of test values and their corresponding expected serialized representations.
        For each test value, it creates a JSONModel instance and serializes it to JSON, then verifies that the resulting JSON data matches the expected serialized form.

        :raises AssertionError: If the serialized JSON data does not match the expected output for any test value.
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
        Tests the difference between JSON null and SQL null in a nullable JSON field.

        This test verifies that JSON null and SQL null are handled correctly by the database,
        ensuring that they are distinct and can be filtered and retrieved accurately.
        It checks that a JSON null value can be stored, retrieved, and filtered, and that
        it is not equivalent to a SQL null value. The test also ensures that the `isnull`
        lookup type correctly identifies SQL null values, while JSON null values are
        identified by their specific JSON null value.

        The test creates model instances with JSON null and SQL null values, updates and
        refreshes the instances, and then uses various filters to verify the correct
        retrieval of these instances.

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

        Tests the ability to store primitive types (boolean, integer, float, string) in a JSON field.

        Checks that storing and retrieving these primitive types via the model's JSON field 
        correctly preserves their original values. The supported primitive types are tested 
        individually to ensure consistency and accuracy of the stored and retrieved data.

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
        Tests the ordering of objects by a transform value.

        This test verifies that objects are correctly ordered based on the 'ord' key within 
        a JSON field. The test covers different numerical values, including positive, negative, 
        and decimal numbers. It also considers database vendor-specific ordering, ensuring 
        correct results for various database backends.

        The test checks the ordering for two different fields ('value' and 'value_custom') 
        and asserts that the sequence of objects matches the expected order, taking into 
        account the specific ordering rules for certain database vendors (e.g., MariaDB and Oracle).
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
        Tests the ordering and grouping of NullableJSONModel instances by count.

        The function verifies that the objects are correctly filtered to exclude null values, 
        and then grouped by a specific field within the JSON content ('value__d__0'). 
        It checks that the resulting query set is ordered by the count of each group in ascending order.
        The expected result is a sorted list of counts, with the lowest count first.
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
        """

        Tests the filtering of NullableJSONModel instances based on a nested key transformation using a RawSQL expression.

        This function verifies that a KeyTransform operation can be applied to a RawSQL expression,
        allowing for the filtering of model instances based on nested JSON data. The test checks if
        the KeyTransform operation correctly retrieves the value associated with the key 'y' within
        the nested dictionary 'x', and filters the model instances accordingly.

        """
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
        """
        Tests the transformation of keys within a JSONField through the use of annotation expressions.

        This test creates a NullableJSONModel object with a JSON value, then filters and annotates the model to extract a specific key from the JSON value.
        It verifies that the `value__d__0__isnull` filter correctly excludes null values and that the `chain` annotation accurately extracts the first element from the 'd' key.
        Finally, it checks that the `expr` annotation correctly casts the value to a JSONField, allowing for further filtering on the JSON value.
        The test ensures that the resulting filtered objects match the initially created object, demonstrating the correct application of key transformation annotation expressions on JSONFields.
        """
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

        Tests whether NullableJSONModel objects can be filtered based on the presence of a specific key in a nested list.

        This test checks if an object with a nested list containing dictionaries can be successfully queried using various filters,
        including Django's Q objects with nested key lookups and KeyTransform.

        The test verifies that the filter conditions correctly identify the object with the desired key, ensuring the correctness
        of the ORM's key lookup functionality in JSON fields with nested lists.

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
        """

        Tests the containment of primitive values within a JSON field.

        Verifies that the database supports filtering JSON fields to contain
        primitive values, ensuring the presence of at least one matching object
        in the queryset when the JSON field contains the specified value.

        The test iterates over a range of primitive values, checking for each
        one that the queryset returned by the filter exists.

        """
        for value in self.primitives:
            with self.subTest(value=value):
                qs = NullableJSONModel.objects.filter(value__contains=value)
                self.assertIs(qs.exists(), True)

    @skipUnlessDBFeature("supports_json_field_contains")
    def test_contained_by(self):
        """

        Verifies that the 'contained_by' lookup type works correctly with JSON fields.

        The function tests if the 'contained_by' lookup can successfully filter objects
        based on whether their JSON field values are contained by a given dictionary.
        The test includes checking the count and contents of the resulting query set.

        This test is skipped unless the database feature 'supports_json_field_contains' is available.

        """
        qs = NullableJSONModel.objects.filter(
            value__contained_by={"a": "b", "c": 14, "h": True}
        )
        self.assertCountEqual(qs, self.objs[2:4])

    @skipIfDBFeature("supports_json_field_contains")
    def test_contained_by_unsupported(self):
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

        Tests the functionality of filtering NullableJSONModel objects by presence or absence of specific keys in their JSON values.

        This function verifies that the model's manager correctly filters objects based on the existence or non-existence of 'a' and 'j' keys in the JSON value.
        It checks for cases where the keys are null (i.e., the key is missing) and where the keys are not null (i.e., the key is present).
        The tests cover several scenarios to ensure the filtering behavior is consistent and accurate.

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
        Tests that the iexact lookup type within a JSON field is case-insensitive but preserves quotes.
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
        Tests the correct filtering of NullableJSONModel instances based on boolean key values.

        This function verifies that the 'value__h' and 'value__i' lookups correctly filter instances
        where the corresponding boolean values are True or False. It checks the values retrieved
        using the values_list method and ensures they match the expected boolean values.

        The test case covers two specific boolean key-value pairs:
        - 'value__h' with an expected value of True
        - 'value__i' with an expected value of False

        Each lookup is tested individually using a subtest to provide detailed error messages
        in case of failures.
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
        """

        Test the SQL injection protection for the JSON field key lookup.

        Verifies that the key lookup for JSON fields properly escapes and sanitizes user input,
        preventing potential SQL injection attacks. This test ensures that the database query
        generated by the ORM correctly handles malicious input and does not allow unauthorized
        access to data.

        The test checks that an attempt to inject malicious SQL code into the key lookup filter
        results in a sanitized query and does not allow the injection to succeed. It also confirms
        that the query is properly escaped and that the expected SQL syntax is used.

        """
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
        Tests the SQL injection escape functionality in JSON field lookups.

        Verifies that the ORM correctly escapes special characters in key names to prevent SQL injection attacks.
        The test checks if the generated SQL query properly escapes double quotes in key names, ensuring the security of the database operations.

        The test case covers a scenario where a malicious key name is used to attempt an SQL injection, and verifies that the ORM handles this correctly by escaping the special characters.

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
        Tests the filtering functionality of literal annotations on querysets.

        This test verifies that annotating a queryset with a literal JSON value and
        then filtering on that annotation produces the expected results. Specifically,
        it checks that filtering on a specific key-value pair within the annotated JSON
        value returns a queryset containing all original objects when the filter matches
        the annotated value.

        The test case uses a NullableJSONModel queryset to demonstrate this behavior,
        ensuring that the filtering logic is applied correctly to the annotated data.
        """
        all_objects = NullableJSONModel.objects.order_by("id")
        qs = all_objects.annotate(data=Value({"foo": "bar"}, JSONField())).filter(
            data__foo="bar"
        )
        self.assertQuerySetEqual(qs, all_objects)
