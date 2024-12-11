import json
import uuid

from django.core import exceptions, serializers
from django.db import IntegrityError, connection, models
from django.db.models import CharField, F, Value
from django.db.models.functions import Concat, Repeat
from django.test import (
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    skipUnlessDBFeature,
)

from .models import (
    NullableUUIDModel,
    PrimaryKeyUUIDModel,
    RelatedToUUIDModel,
    UUIDGrandchild,
    UUIDModel,
)


class TestSaveLoad(TestCase):
    def test_uuid_instance(self):
        instance = UUIDModel.objects.create(field=uuid.uuid4())
        loaded = UUIDModel.objects.get()
        self.assertEqual(loaded.field, instance.field)

    def test_str_instance_no_hyphens(self):
        UUIDModel.objects.create(field="550e8400e29b41d4a716446655440000")
        loaded = UUIDModel.objects.get()
        self.assertEqual(loaded.field, uuid.UUID("550e8400e29b41d4a716446655440000"))

    def test_str_instance_hyphens(self):
        """
        Tests that a UUID field with hyphens is correctly stored and loaded by the UUIDModel, ensuring that the hyphens are removed from the stored UUID value. 

        This test case covers the scenario where a UUID string with hyphens is created, retrieved from the database, and then compared to the expected UUID value without hyphens, confirming the successful processing and storage of the UUID.
        """
        UUIDModel.objects.create(field="550e8400-e29b-41d4-a716-446655440000")
        loaded = UUIDModel.objects.get()
        self.assertEqual(loaded.field, uuid.UUID("550e8400e29b41d4a716446655440000"))

    def test_str_instance_bad_hyphens(self):
        """

        Tests the handling of a UUID string instance with hyphens in an invalid position.

        Verifies that the stored UUID value has the hyphens correctly removed and compacted,
        according to the UUID standard, when retrieved from the database.

        """
        UUIDModel.objects.create(field="550e84-00-e29b-41d4-a716-4-466-55440000")
        loaded = UUIDModel.objects.get()
        self.assertEqual(loaded.field, uuid.UUID("550e8400e29b41d4a716446655440000"))

    def test_null_handling(self):
        """

        Tests the handling of null values in the NullableUUIDModel.

        Verifies that a null value can be successfully stored and retrieved from the database,
        ensuring that the field remains null after loading the object from the database.

        """
        NullableUUIDModel.objects.create(field=None)
        loaded = NullableUUIDModel.objects.get()
        self.assertIsNone(loaded.field)

    def test_pk_validated(self):
        """

        Tests that attempting to retrieve a PrimaryKeyUUIDModel instance with an invalid primary key raises a ValidationError.

        The function verifies that passing an empty dictionary or list as the primary key to the model's get method results in a ValidationError, 
        indicating that the provided primary key is not a valid UUID. 

        Raises:
            exceptions.ValidationError: When an invalid primary key is used to retrieve a PrimaryKeyUUIDModel instance.

        """
        with self.assertRaisesMessage(
            exceptions.ValidationError, "is not a valid UUID"
        ):
            PrimaryKeyUUIDModel.objects.get(pk={})

        with self.assertRaisesMessage(
            exceptions.ValidationError, "is not a valid UUID"
        ):
            PrimaryKeyUUIDModel.objects.get(pk=[])

    def test_wrong_value(self):
        """
        Tests the validation of UUID values in the model.

        Verifies that attempting to retrieve or create a model instance with an
        invalid UUID value raises a ValidationError with a descriptive error message.

        Specifically, this test covers the following scenarios:

        * Retrieving a model instance with an invalid UUID value
        * Creating a new model instance with an invalid UUID value

        Ensures that the model properly enforces UUID validation and provides
        informative error messages for invalid input values.
        """
        with self.assertRaisesMessage(
            exceptions.ValidationError, "is not a valid UUID"
        ):
            UUIDModel.objects.get(field="not-a-uuid")

        with self.assertRaisesMessage(
            exceptions.ValidationError, "is not a valid UUID"
        ):
            UUIDModel.objects.create(field="not-a-uuid")


class TestMethods(SimpleTestCase):
    def test_deconstruct(self):
        field = models.UUIDField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(kwargs, {})

    def test_to_python(self):
        self.assertIsNone(models.UUIDField().to_python(None))

    def test_to_python_int_values(self):
        """
        Tests the conversion of integer values to UUID objects using the to_python method of a UUIDField instance.

        This function checks that integer values are correctly converted to their corresponding UUID representations, 
        covering both the minimum (0) and maximum (2^128 - 1) possible integer values. It verifies that the resulting UUIDs 
        match the expected values, ensuring the accuracy of the to_python method in handling integer inputs.
        """
        self.assertEqual(
            models.UUIDField().to_python(0),
            uuid.UUID("00000000-0000-0000-0000-000000000000"),
        )
        # Works for integers less than 128 bits.
        self.assertEqual(
            models.UUIDField().to_python((2**128) - 1),
            uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        )

    def test_to_python_int_too_large(self):
        # Fails for integers larger than 128 bits.
        """
        Tests that :meth:`to_python` method of UUIDField raises a ValidationError when given an integer that exceeds the maximum allowed value for a 128-bit integer.
        """
        with self.assertRaises(exceptions.ValidationError):
            models.UUIDField().to_python(2**128)


class TestQuerying(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.objs = [
            NullableUUIDModel.objects.create(
                field=uuid.UUID("25d405be-4895-4d50-9b2e-d6695359ce47"),
            ),
            NullableUUIDModel.objects.create(field="550e8400e29b41d4a716446655440000"),
            NullableUUIDModel.objects.create(field=None),
        ]

    def assertSequenceEqualWithoutHyphens(self, qs, result):
        """
        Backends with a native datatype for UUID don't support fragment lookups
        without hyphens because they store values with them.
        """
        self.assertSequenceEqual(
            qs,
            [] if connection.features.has_native_uuid_field else result,
        )

    def test_exact(self):
        self.assertSequenceEqual(
            NullableUUIDModel.objects.filter(
                field__exact="550e8400e29b41d4a716446655440000"
            ),
            [self.objs[1]],
        )
        self.assertSequenceEqual(
            NullableUUIDModel.objects.filter(
                field__exact="550e8400-e29b-41d4-a716-446655440000"
            ),
            [self.objs[1]],
        )

    def test_iexact(self):
        self.assertSequenceEqualWithoutHyphens(
            NullableUUIDModel.objects.filter(
                field__iexact="550E8400E29B41D4A716446655440000"
            ),
            [self.objs[1]],
        )
        self.assertSequenceEqual(
            NullableUUIDModel.objects.filter(
                field__iexact="550E8400-E29B-41D4-A716-446655440000"
            ),
            [self.objs[1]],
        )

    def test_isnull(self):
        self.assertSequenceEqual(
            NullableUUIDModel.objects.filter(field__isnull=True), [self.objs[2]]
        )

    def test_contains(self):
        """
        Tests that the 'contains' filter works correctly with NullableUUIDModel.

        This test case ensures that the 'contains' lookup can find objects by matching a substring
        within a UUID field, regardless of whether the UUID is represented in its hyphenated or
        unhyphenated form. The test verifies that the expected object is returned when querying
        with both forms of the UUID substring.

        The test consists of two assertions: one for a hyphenated UUID substring and one for an
        unhyphenated UUID substring, confirming that the filter behaves as expected in both cases.
        """
        self.assertSequenceEqualWithoutHyphens(
            NullableUUIDModel.objects.filter(field__contains="8400e29b"),
            [self.objs[1]],
        )
        self.assertSequenceEqual(
            NullableUUIDModel.objects.filter(field__contains="8400-e29b"),
            [self.objs[1]],
        )

    def test_icontains(self):
        """
        Tests whether the icontains lookup is correctly applied to a nullable UUID field.

        The icontains lookup is tested with both hyphenated and non-hyphenated UUID values.
        The function verifies that the correct objects are returned from the database
        when using icontains with UUID fields, ensuring case-insensitive substring matching
        behaves as expected. 
        """
        self.assertSequenceEqualWithoutHyphens(
            NullableUUIDModel.objects.filter(field__icontains="8400E29B"),
            [self.objs[1]],
        )
        self.assertSequenceEqual(
            NullableUUIDModel.objects.filter(field__icontains="8400-E29B"),
            [self.objs[1]],
        )

    def test_startswith(self):
        """
        Tests the startswith lookup type on a nullable UUID field.

        Verifies that the field can be correctly filtered using both hyphenated and unhyphenated UUID prefixes.
        The test ensures that the correct object is returned when the lookup is performed, 
        regardless of whether the UUID prefix contains hyphens or not.
        """
        self.assertSequenceEqualWithoutHyphens(
            NullableUUIDModel.objects.filter(field__startswith="550e8400e29b4"),
            [self.objs[1]],
        )
        self.assertSequenceEqual(
            NullableUUIDModel.objects.filter(field__startswith="550e8400-e29b-4"),
            [self.objs[1]],
        )

    def test_istartswith(self):
        self.assertSequenceEqualWithoutHyphens(
            NullableUUIDModel.objects.filter(field__istartswith="550E8400E29B4"),
            [self.objs[1]],
        )
        self.assertSequenceEqual(
            NullableUUIDModel.objects.filter(field__istartswith="550E8400-E29B-4"),
            [self.objs[1]],
        )

    def test_endswith(self):
        self.assertSequenceEqualWithoutHyphens(
            NullableUUIDModel.objects.filter(field__endswith="a716446655440000"),
            [self.objs[1]],
        )
        self.assertSequenceEqual(
            NullableUUIDModel.objects.filter(field__endswith="a716-446655440000"),
            [self.objs[1]],
        )

    def test_iendswith(self):
        self.assertSequenceEqualWithoutHyphens(
            NullableUUIDModel.objects.filter(field__iendswith="A716446655440000"),
            [self.objs[1]],
        )
        self.assertSequenceEqual(
            NullableUUIDModel.objects.filter(field__iendswith="A716-446655440000"),
            [self.objs[1]],
        )

    def test_filter_with_expr(self):
        """

        Tests the filtering functionality of a Django model with an expression.
        This method ensures that a model instance can be filtered based on a value 
        constructed using different database functions, such as concatenation and 
        repetition. The test checks for exact matches when the expression contains 
        hyphens and when it does not, verifying that the filtering works correctly 
        in both scenarios.

        """
        self.assertSequenceEqualWithoutHyphens(
            NullableUUIDModel.objects.annotate(
                value=Concat(Value("8400"), Value("e29b"), output_field=CharField()),
            ).filter(field__contains=F("value")),
            [self.objs[1]],
        )
        self.assertSequenceEqual(
            NullableUUIDModel.objects.annotate(
                value=Concat(
                    Value("8400"), Value("-"), Value("e29b"), output_field=CharField()
                ),
            ).filter(field__contains=F("value")),
            [self.objs[1]],
        )
        self.assertSequenceEqual(
            NullableUUIDModel.objects.annotate(
                value=Repeat(Value("0"), 4, output_field=CharField()),
            ).filter(field__contains=F("value")),
            [self.objs[1]],
        )


class TestSerialization(SimpleTestCase):
    test_data = (
        '[{"fields": {"field": "550e8400-e29b-41d4-a716-446655440000"}, '
        '"model": "model_fields.uuidmodel", "pk": null}]'
    )
    nullable_test_data = (
        '[{"fields": {"field": null}, '
        '"model": "model_fields.nullableuuidmodel", "pk": null}]'
    )

    def test_dumping(self):
        instance = UUIDModel(field=uuid.UUID("550e8400e29b41d4a716446655440000"))
        data = serializers.serialize("json", [instance])
        self.assertEqual(json.loads(data), json.loads(self.test_data))

    def test_loading(self):
        """

        Tests the loading of an instance from JSON serialized data.

        Verifies that the deserialized instance has the correct field value, 
        specifically a UUID that matches the expected value.

        """
        instance = list(serializers.deserialize("json", self.test_data))[0].object
        self.assertEqual(
            instance.field, uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        )

    def test_nullable_loading(self):
        """

        Tests that a nullable field is correctly loaded as None when its value is missing from the serialized data.

        Verifies that the deserialization process correctly handles null or missing values for a field that is defined as nullable.

        """
        instance = list(serializers.deserialize("json", self.nullable_test_data))[
            0
        ].object
        self.assertIsNone(instance.field)


class TestValidation(SimpleTestCase):
    def test_invalid_uuid(self):
        """
        Tests that a ValueError is raised when attempting to clean an invalid UUID string with the UUIDField. 

        The function checks that the error code 'invalid' is returned and that the error message correctly identifies the input as an invalid UUID. 

        This test ensures that the UUIDField properly validates UUID strings and raises informative errors for invalid inputs.
        """
        field = models.UUIDField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean("550e8400", None)
        self.assertEqual(cm.exception.code, "invalid")
        self.assertEqual(
            cm.exception.message % cm.exception.params,
            "“550e8400” is not a valid UUID.",
        )

    def test_uuid_instance_ok(self):
        """
        Tests that a UUIDField instance successfully validates a random UUID.

        This test ensures that a UUIDField can properly clean and validate a
        UUID instance generated by the uuid module, confirming that the field
        functions as expected with valid input.
        """
        field = models.UUIDField()
        field.clean(uuid.uuid4(), None)  # no error


class TestAsPrimaryKey(TestCase):
    def test_creation(self):
        """
        Tests the successful creation of a PrimaryKeyUUIDModel instance.

        Verifies that a new instance can be created and subsequently retrieved, 
        with its primary key being a UUID object as expected.
        """
        PrimaryKeyUUIDModel.objects.create()
        loaded = PrimaryKeyUUIDModel.objects.get()
        self.assertIsInstance(loaded.pk, uuid.UUID)

    def test_uuid_pk_on_save(self):
        saved = PrimaryKeyUUIDModel.objects.create(id=None)
        loaded = PrimaryKeyUUIDModel.objects.get()
        self.assertIsNotNone(loaded.id, None)
        self.assertEqual(loaded.id, saved.id)

    def test_uuid_pk_on_bulk_create(self):
        """

        Tests the successful creation of multiple PrimaryKeyUUIDModel instances using bulk_create,
        verifying that each instance receives a unique UUID primary key.

        This test case checks that both instances with an explicitly set UUID and those without
        one can be created in bulk, ensuring that the database correctly assigns a unique UUID
        to instances that do not have one explicitly set. The test then verifies that both instances
        can be successfully retrieved from the database, confirming their creation and the correct
        assignment of UUID primary keys.

        """
        u1 = PrimaryKeyUUIDModel()
        u2 = PrimaryKeyUUIDModel(id=None)
        PrimaryKeyUUIDModel.objects.bulk_create([u1, u2])
        # The two objects were correctly created.
        u1_found = PrimaryKeyUUIDModel.objects.filter(id=u1.id).exists()
        u2_found = PrimaryKeyUUIDModel.objects.exclude(id=u1.id).exists()
        self.assertTrue(u1_found)
        self.assertTrue(u2_found)
        self.assertEqual(PrimaryKeyUUIDModel.objects.count(), 2)

    def test_underlying_field(self):
        """

        Tests the underlying field of the uuid_fk relationship in RelatedToUUIDModel.

        Verifies that the primary key of the related PrimaryKeyUUIDModel instance matches 
        the uuid_fk_id attribute of the RelatedToUUIDModel instance, ensuring that the 
        relationship is correctly established and the foreign key is properly set.

        """
        pk_model = PrimaryKeyUUIDModel.objects.create()
        RelatedToUUIDModel.objects.create(uuid_fk=pk_model)
        related = RelatedToUUIDModel.objects.get()
        self.assertEqual(related.uuid_fk.pk, related.uuid_fk_id)

    def test_update_with_related_model_instance(self):
        # regression for #24611
        """
        Tests that updating related model instances with a new foreign key works as expected.

        This test case creates two primary key UUID model instances and one related model instance.
        It then updates the related model instance to reference the second primary key UUID model instance.
        The test validates that the related model instance is successfully updated by checking its foreign key reference after refreshing from the database.
        """
        u1 = PrimaryKeyUUIDModel.objects.create()
        u2 = PrimaryKeyUUIDModel.objects.create()
        r = RelatedToUUIDModel.objects.create(uuid_fk=u1)
        RelatedToUUIDModel.objects.update(uuid_fk=u2)
        r.refresh_from_db()
        self.assertEqual(r.uuid_fk, u2)

    def test_update_with_related_model_id(self):
        """
        Tests that updating a model with a related model's ID correctly updates the foreign key reference.

        Checks that when a new instance of PrimaryKeyUUIDModel is created and assigned to a RelatedToUUIDModel instance, 
        subsequent updates using the primary key of a different PrimaryKeyUUIDModel instance will correctly update the 
        foreign key reference in the RelatedToUUIDModel instance. 

        The test verifies the update by refreshing the RelatedToUUIDModel instance from the database and asserting 
        that its foreign key reference matches the updated PrimaryKeyUUIDModel instance.
        """
        u1 = PrimaryKeyUUIDModel.objects.create()
        u2 = PrimaryKeyUUIDModel.objects.create()
        r = RelatedToUUIDModel.objects.create(uuid_fk=u1)
        RelatedToUUIDModel.objects.update(uuid_fk=u2.pk)
        r.refresh_from_db()
        self.assertEqual(r.uuid_fk, u2)

    def test_two_level_foreign_keys(self):
        gc = UUIDGrandchild()
        # exercises ForeignKey.get_db_prep_value()
        gc.save()
        self.assertIsInstance(gc.uuidchild_ptr_id, uuid.UUID)
        gc.refresh_from_db()
        self.assertIsInstance(gc.uuidchild_ptr_id, uuid.UUID)


class TestAsPrimaryKeyTransactionTests(TransactionTestCase):
    # Need a TransactionTestCase to avoid deferring FK constraint checking.
    available_apps = ["model_fields"]

    @skipUnlessDBFeature("supports_foreign_keys")
    def test_unsaved_fk(self):
        u1 = PrimaryKeyUUIDModel()
        with self.assertRaises(IntegrityError):
            RelatedToUUIDModel.objects.create(uuid_fk=u1)
