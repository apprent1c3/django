from django.core import serializers
from django.db import connection
from django.test import TestCase

from .models import (
    Child,
    FKAsPKNoNaturalKey,
    FKDataNaturalKey,
    NaturalKeyAnchor,
    NaturalKeyThing,
    NaturalPKWithDefault,
)
from .tests import register_tests


class NaturalKeySerializerTests(TestCase):
    pass


def natural_key_serializer_test(self, format):
    # Create all the objects defined in the test data
    """

    Tests serialization and deserialization of objects using natural foreign keys.
    Verifies that the data remains consistent after serializing and deserializing.
    The test covers objects with and without foreign key relationships.

    """
    with connection.constraint_checks_disabled():
        objects = [
            NaturalKeyAnchor.objects.create(id=1100, data="Natural Key Anghor"),
            FKDataNaturalKey.objects.create(id=1101, data_id=1100),
            FKDataNaturalKey.objects.create(id=1102, data_id=None),
        ]
    # Serialize the test database
    serialized_data = serializers.serialize(
        format, objects, indent=2, use_natural_foreign_keys=True
    )

    for obj in serializers.deserialize(format, serialized_data):
        obj.save()

    # Assert that the deserialized data is the same
    # as the original source
    for obj in objects:
        instance = obj.__class__.objects.get(id=obj.pk)
        self.assertEqual(
            obj.data,
            instance.data,
            "Objects with PK=%d not equal; expected '%s' (%s), got '%s' (%s)"
            % (
                obj.pk,
                obj.data,
                type(obj.data),
                instance,
                type(instance.data),
            ),
        )


def natural_key_test(self, format):
    """
    Tests serialization and deserialization of natural keys, verifying object relationships are preserved and deleted objects are handled correctly.
    """
    book1 = {
        "data": "978-1590597255",
        "title": "The Definitive Guide to Django: Web Development Done Right",
    }
    book2 = {"data": "978-1590599969", "title": "Practical Django Projects"}

    # Create the books.
    adrian = NaturalKeyAnchor.objects.create(**book1)
    james = NaturalKeyAnchor.objects.create(**book2)

    # Serialize the books.
    string_data = serializers.serialize(
        format,
        NaturalKeyAnchor.objects.all(),
        indent=2,
        use_natural_foreign_keys=True,
        use_natural_primary_keys=True,
    )

    # Delete one book (to prove that the natural key generation will only
    # restore the primary keys of books found in the database via the
    # get_natural_key manager method).
    james.delete()

    # Deserialize and test.
    books = list(serializers.deserialize(format, string_data))
    self.assertCountEqual(
        [(book.object.title, book.object.pk) for book in books],
        [
            (book1["title"], adrian.pk),
            (book2["title"], None),
        ],
    )


def natural_pk_mti_test(self, format):
    """
    Tests the serialization and deserialization of objects in a multi-table inheritance relationship using natural primary keys, ensuring that the natural foreign key for the parent is correctly output and used to relate the child to the parent.
    """
    child_1 = Child.objects.create(parent_data="1", child_data="1")
    child_2 = Child.objects.create(parent_data="2", child_data="2")
    string_data = serializers.serialize(
        format,
        [child_1.parent_ptr, child_2.parent_ptr, child_2, child_1],
        use_natural_foreign_keys=True,
        use_natural_primary_keys=True,
    )
    child_1.delete()
    child_2.delete()
    for obj in serializers.deserialize(format, string_data):
        obj.save()
    children = Child.objects.all()
    self.assertEqual(len(children), 2)
    for child in children:
        # If it's possible to find the superclass from the subclass and it's
        # the correct superclass, it's working.
        self.assertEqual(child.child_data, child.parent_data)


def forward_ref_fk_test(self, format):
    """
    Tests serialization and deserialization with forward references in foreign keys.

    Ensures that objects with circular dependencies can be successfully serialized, 
    deserialized, and saved, with their relationships intact, using natural primary 
    and foreign keys. Verifies that deferred fields are properly handled during this process.
    """
    t1 = NaturalKeyThing.objects.create(key="t1")
    t2 = NaturalKeyThing.objects.create(key="t2", other_thing=t1)
    t1.other_thing = t2
    t1.save()
    string_data = serializers.serialize(
        format,
        [t1, t2],
        use_natural_primary_keys=True,
        use_natural_foreign_keys=True,
    )
    NaturalKeyThing.objects.all().delete()
    objs_with_deferred_fields = []
    for obj in serializers.deserialize(
        format, string_data, handle_forward_references=True
    ):
        obj.save()
        if obj.deferred_fields:
            objs_with_deferred_fields.append(obj)
    for obj in objs_with_deferred_fields:
        obj.save_deferred_fields()
    t1 = NaturalKeyThing.objects.get(key="t1")
    t2 = NaturalKeyThing.objects.get(key="t2")
    self.assertEqual(t1.other_thing, t2)
    self.assertEqual(t2.other_thing, t1)


def forward_ref_fk_with_error_test(self, format):
    """
    Tests deserialization of forward references with foreign keys in the specified format.

    This test case creates objects with circular references, serializes them, and then attempts to deserialize and save the data, 
    verifying that a DeserializationError is raised with the correct message when trying to save deferred fields on a deserialized object.
    """
    t1 = NaturalKeyThing.objects.create(key="t1")
    t2 = NaturalKeyThing.objects.create(key="t2", other_thing=t1)
    t1.other_thing = t2
    t1.save()
    string_data = serializers.serialize(
        format,
        [t1],
        use_natural_primary_keys=True,
        use_natural_foreign_keys=True,
    )
    NaturalKeyThing.objects.all().delete()
    objs_with_deferred_fields = []
    for obj in serializers.deserialize(
        format, string_data, handle_forward_references=True
    ):
        obj.save()
        if obj.deferred_fields:
            objs_with_deferred_fields.append(obj)
    obj = objs_with_deferred_fields[0]
    msg = "NaturalKeyThing matching query does not exist"
    with self.assertRaisesMessage(serializers.base.DeserializationError, msg):
        obj.save_deferred_fields()


def forward_ref_m2m_test(self, format):
    """
    Tests serialization and deserialization of many-to-many relationships using natural keys.

    Verifies that forward references are correctly handled during deserialization and that
    relationships are properly restored after saving deferred fields.
    """
    t1 = NaturalKeyThing.objects.create(key="t1")
    t2 = NaturalKeyThing.objects.create(key="t2")
    t3 = NaturalKeyThing.objects.create(key="t3")
    t1.other_things.set([t2, t3])
    string_data = serializers.serialize(
        format,
        [t1, t2, t3],
        use_natural_primary_keys=True,
        use_natural_foreign_keys=True,
    )
    NaturalKeyThing.objects.all().delete()
    objs_with_deferred_fields = []
    for obj in serializers.deserialize(
        format, string_data, handle_forward_references=True
    ):
        obj.save()
        if obj.deferred_fields:
            objs_with_deferred_fields.append(obj)
    for obj in objs_with_deferred_fields:
        obj.save_deferred_fields()
    t1 = NaturalKeyThing.objects.get(key="t1")
    t2 = NaturalKeyThing.objects.get(key="t2")
    t3 = NaturalKeyThing.objects.get(key="t3")
    self.assertCountEqual(t1.other_things.all(), [t2, t3])


def forward_ref_m2m_with_error_test(self, format):
    """
    Tests deserialization of models with many-to-many relationships using forward references to detect deserialization errors when a related object is missing.
    """
    t1 = NaturalKeyThing.objects.create(key="t1")
    t2 = NaturalKeyThing.objects.create(key="t2")
    t3 = NaturalKeyThing.objects.create(key="t3")
    t1.other_things.set([t2, t3])
    t1.save()
    string_data = serializers.serialize(
        format,
        [t1, t2],
        use_natural_primary_keys=True,
        use_natural_foreign_keys=True,
    )
    NaturalKeyThing.objects.all().delete()
    objs_with_deferred_fields = []
    for obj in serializers.deserialize(
        format, string_data, handle_forward_references=True
    ):
        obj.save()
        if obj.deferred_fields:
            objs_with_deferred_fields.append(obj)
    obj = objs_with_deferred_fields[0]
    msg = "NaturalKeyThing matching query does not exist"
    with self.assertRaisesMessage(serializers.base.DeserializationError, msg):
        obj.save_deferred_fields()


def pk_with_default(self, format):
    """
    Tests that the deserializer correctly handles natural primary keys with default values, ensuring data integrity and consistency during serialization and deserialization processes.
    """
    obj = NaturalPKWithDefault.objects.create(name="name")
    string_data = serializers.serialize(
        format,
        NaturalPKWithDefault.objects.all(),
        use_natural_foreign_keys=True,
        use_natural_primary_keys=True,
    )
    objs = list(serializers.deserialize(format, string_data))
    self.assertEqual(len(objs), 1)
    self.assertEqual(objs[0].object.pk, obj.pk)


def fk_as_pk_natural_key_not_called(self, format):
    """
    Verifies that deserialization works correctly when a model has a custom primary key that is a foreign key, by checking that the deserialized objects have the correct primary key.
    """
    o1 = NaturalKeyAnchor.objects.create(data="978-1590599969")
    o2 = FKAsPKNoNaturalKey.objects.create(pk_fk=o1)
    serialized_data = serializers.serialize(format, [o1, o2])
    deserialized_objects = list(serializers.deserialize(format, serialized_data))
    self.assertEqual(len(deserialized_objects), 2)
    for obj in deserialized_objects:
        self.assertEqual(obj.object.pk, o1.pk)


# Dynamically register tests for each serializer
register_tests(
    NaturalKeySerializerTests,
    "test_%s_natural_key_serializer",
    natural_key_serializer_test,
)
register_tests(
    NaturalKeySerializerTests, "test_%s_serializer_natural_keys", natural_key_test
)
register_tests(
    NaturalKeySerializerTests, "test_%s_serializer_natural_pks_mti", natural_pk_mti_test
)
register_tests(
    NaturalKeySerializerTests, "test_%s_forward_references_fks", forward_ref_fk_test
)
register_tests(
    NaturalKeySerializerTests,
    "test_%s_forward_references_fk_errors",
    forward_ref_fk_with_error_test,
)
register_tests(
    NaturalKeySerializerTests, "test_%s_forward_references_m2ms", forward_ref_m2m_test
)
register_tests(
    NaturalKeySerializerTests,
    "test_%s_forward_references_m2m_errors",
    forward_ref_m2m_with_error_test,
)
register_tests(NaturalKeySerializerTests, "test_%s_pk_with_default", pk_with_default)
register_tests(
    NaturalKeySerializerTests,
    "test_%s_fk_as_pk_natural_key_not_called",
    fk_as_pk_natural_key_not_called,
)
