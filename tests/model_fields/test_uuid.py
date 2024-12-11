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
        """
        ..: Tests that loading a UUIDModel instance from the database retains its original UUID value.

            Verifies that creating a UUIDModel instance, saving it to the database, and then retrieving it results in the same UUID value.

            This test case ensures data integrity by confirming that the UUID is correctly persisted and retrieved, which is crucial for any application relying on unique identifiers.
        """
        instance = UUIDModel.objects.create(field=uuid.uuid4())
        loaded = UUIDModel.objects.get()
        self.assertEqual(loaded.field, instance.field)

    def test_str_instance_no_hyphens(self):
        UUIDModel.objects.create(field="550e8400e29b41d4a716446655440000")
        loaded = UUIDModel.objects.get()
        self.assertEqual(loaded.field, uuid.UUID("550e8400e29b41d4a716446655440000"))

    def test_str_instance_hyphens(self):
        """
        Tests whether a string instance with hyphens is correctly parsed and stored as a UUID instance.
        The test case creates a UUIDModel object with a string field containing a UUID value with hyphens, 
        retrieves the object, and verifies that the loaded field value is equivalent to the original UUID without hyphens.
        """
        UUIDModel.objects.create(field="550e8400-e29b-41d4-a716-446655440000")
        loaded = UUIDModel.objects.get()
        self.assertEqual(loaded.field, uuid.UUID("550e8400e29b41d4a716446655440000"))

    def test_str_instance_bad_hyphens(self):
        """
        Tests the handling of a string instance with improperly formatted hyphens in a UUID field, 
        verifying that it is correctly parsed and stored as a valid UUID.
        """
        UUIDModel.objects.create(field="550e84-00-e29b-41d4-a716-4-466-55440000")
        loaded = UUIDModel.objects.get()
        self.assertEqual(loaded.field, uuid.UUID("550e8400e29b41d4a716446655440000"))

    def test_null_handling(self):
        NullableUUIDModel.objects.create(field=None)
        loaded = NullableUUIDModel.objects.get()
        self.assertIsNone(loaded.field)

    def test_pk_validated(self):
        """
        Tests the validation of primary key UUIDs in the PrimaryKeyUUIDModel.

            Checks that getting an object by primary key raises a ValidationError when the provided
            primary key is not a valid UUID, specifically when it is an empty dictionary or list.
            Verifies that the error message correctly indicates that the primary key is not a valid UUID.
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
        Tests the handling of invalid UUID values in the UUIDModel.

        This test case checks that a ValidationError is raised with an appropriate error message
        when attempting to retrieve or create an instance of UUIDModel with a field value that is not a valid UUID.
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

        Checks the conversion of integer values to UUID objects.

        This tests the `to_python` method of the `UUIDField` class by verifying that 
        it correctly converts integer values to their equivalent UUID representations.
        The test covers the conversion of integer values at the lower and upper bounds 
        of the 128-bit range, ensuring that the conversion handles these edge cases 
        as expected.

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
        """
        Tests the exact match lookup for a UUID field.

        Checks that we can retrieve an object with a null UUID field by its exact value, 
        regardless of whether the input string has hyphens or not. 

        The function verifies that there's an exact match between the input UUID string 
        and the stored UUID, supporting both hyphenated and non-hyphenated UUID formats.

        """
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
        """
        Tests the case-insensitive exact matching functionality of the field filter in NullableUUIDModel, ensuring that it correctly returns the expected object regardless of the hyphenation of the UUID. This test covers both hyphenated and non-hyphenated UUID formats.
        """
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
        self.assertSequenceEqualWithoutHyphens(
            NullableUUIDModel.objects.filter(field__contains="8400e29b"),
            [self.objs[1]],
        )
        self.assertSequenceEqual(
            NullableUUIDModel.objects.filter(field__contains="8400-e29b"),
            [self.objs[1]],
        )

    def test_icontains(self):
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

        Tests that the startsWith filter works correctly for NullableUUIDModel objects.

        The test checks that the filter can find objects where the field starts with a given UUID value,
        both with and without hyphens in the UUID.

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

        Tests the filtering of a model with annotated values using database expressions.

        This function ensures that the filter functionality works correctly when using
        annotated values with database expressions such as Concat and Repeat. It
        verifies that filtering by a field containing an annotated value returns the
        expected results.

        The test cases cover the following scenarios:
        - Filtering by a field containing a concatenation of values without hyphens.
        - Filtering by a field containing a concatenation of values with hyphens.
        - Filtering by a field containing a repeated value.

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
        instance = list(serializers.deserialize("json", self.test_data))[0].object
        self.assertEqual(
            instance.field, uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        )

    def test_nullable_loading(self):
        """
        Tests the loading of nullable fields.

        Verifies that fields which are allowed to be null are properly loaded
        from serialized data, resulting in the expected None value when no data
        is present.

        This test is crucial to ensure that the deserialization process handles
        nullable fields correctly, preventing potential errors or inconsistencies
        in the loaded data.

        """
        instance = list(serializers.deserialize("json", self.nullable_test_data))[
            0
        ].object
        self.assertIsNone(instance.field)


class TestValidation(SimpleTestCase):
    def test_invalid_uuid(self):
        """
        Tests a UUID field to ensure it raises a ValidationError when an invalid UUID string is provided. 

        This test case checks that the UUID field correctly identifies a string that does not conform to the UUID format as invalid, 
        and verifies that the expected error message and code are returned.
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

        Tests that a UUID instance is accepted as valid input by the UUIDField.

        This test ensures that a randomly generated UUID object can be successfully
        cleaned and validated by the UUIDField, verifying that the field's cleaning
        mechanism is functioning correctly for UUID instances.

        """
        field = models.UUIDField()
        field.clean(uuid.uuid4(), None)  # no error


class TestAsPrimaryKey(TestCase):
    def test_creation(self):
        """

        Tests the creation of a PrimaryKeyUUIDModel instance.

        Verifies that a new instance can be successfully created and that its primary key
        is a UUID type.

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
        Tests that the primary key UUID is correctly generated and assigned when creating multiple objects using bulk creation.

        This test case verifies that each object in the bulk creation operation is assigned a unique primary key UUID, and that these objects can be successfully retrieved from the database.

        The test checks the following conditions:
        - That each object created in the bulk operation has a primary key UUID.
        - That both objects are successfully stored in the database and can be retrieved.
        - That the total count of objects in the database matches the number of objects created in the bulk operation.
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

        Tests the underlying field of the UUID foreign key relationship.

        Verifies that the primary key of the related object matches the id stored in the foreign key field.
        This ensures that the relationship between the models is correctly established and queried.

        """
        pk_model = PrimaryKeyUUIDModel.objects.create()
        RelatedToUUIDModel.objects.create(uuid_fk=pk_model)
        related = RelatedToUUIDModel.objects.get()
        self.assertEqual(related.uuid_fk.pk, related.uuid_fk_id)

    def test_update_with_related_model_instance(self):
        # regression for #24611
        u1 = PrimaryKeyUUIDModel.objects.create()
        u2 = PrimaryKeyUUIDModel.objects.create()
        r = RelatedToUUIDModel.objects.create(uuid_fk=u1)
        RelatedToUUIDModel.objects.update(uuid_fk=u2)
        r.refresh_from_db()
        self.assertEqual(r.uuid_fk, u2)

    def test_update_with_related_model_id(self):
        u1 = PrimaryKeyUUIDModel.objects.create()
        u2 = PrimaryKeyUUIDModel.objects.create()
        r = RelatedToUUIDModel.objects.create(uuid_fk=u1)
        RelatedToUUIDModel.objects.update(uuid_fk=u2.pk)
        r.refresh_from_db()
        self.assertEqual(r.uuid_fk, u2)

    def test_two_level_foreign_keys(self):
        """
        Tests the functionality of two-level foreign keys by creating an instance of UUIDGrandchild, saving it to the database, and verifying that the uuidchild_ptr_id attribute is correctly assigned a UUID value, both before and after refreshing the object from the database.
        """
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
        """

        Tests that creating a new instance of RelatedToUUIDModel with a foreign key to an unsaved PrimaryKeyUUIDModel instance raises an IntegrityError.

        This test ensures that the database correctly enforces the foreign key constraint when the referenced object has not been persisted.

        """
        u1 = PrimaryKeyUUIDModel()
        with self.assertRaises(IntegrityError):
            RelatedToUUIDModel.objects.create(uuid_fk=u1)
