from django import test
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.db import models

from .models import AllFieldsModel

NON_CONCRETE_FIELDS = (
    models.ForeignObject,
    GenericForeignKey,
    GenericRelation,
)

NON_EDITABLE_FIELDS = (
    models.BinaryField,
    GenericForeignKey,
    GenericRelation,
)

RELATION_FIELDS = (
    models.ForeignKey,
    models.ForeignObject,
    models.ManyToManyField,
    models.OneToOneField,
    GenericForeignKey,
    GenericRelation,
)

MANY_TO_MANY_CLASSES = {
    models.ManyToManyField,
}

MANY_TO_ONE_CLASSES = {
    models.ForeignObject,
    models.ForeignKey,
    GenericForeignKey,
}

ONE_TO_MANY_CLASSES = {
    models.ForeignObjectRel,
    models.ManyToOneRel,
    GenericRelation,
}

ONE_TO_ONE_CLASSES = {
    models.OneToOneField,
}

FLAG_PROPERTIES = (
    "concrete",
    "editable",
    "is_relation",
    "model",
    "hidden",
    "one_to_many",
    "many_to_one",
    "many_to_many",
    "one_to_one",
    "related_model",
)

FLAG_PROPERTIES_FOR_RELATIONS = (
    "one_to_many",
    "many_to_one",
    "many_to_many",
    "one_to_one",
)


class FieldFlagsTests(test.SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fields = [
            *AllFieldsModel._meta.fields,
            *AllFieldsModel._meta.private_fields,
        ]

        cls.all_fields = [
            *cls.fields,
            *AllFieldsModel._meta.many_to_many,
            *AllFieldsModel._meta.private_fields,
        ]

        cls.fields_and_reverse_objects = [
            *cls.all_fields,
            *AllFieldsModel._meta.related_objects,
        ]

    def test_each_field_should_have_a_concrete_attribute(self):
        self.assertTrue(all(f.concrete.__class__ == bool for f in self.fields))

    def test_each_field_should_have_an_editable_attribute(self):
        self.assertTrue(all(f.editable.__class__ == bool for f in self.all_fields))

    def test_each_field_should_have_a_has_rel_attribute(self):
        self.assertTrue(all(f.is_relation.__class__ == bool for f in self.all_fields))

    def test_each_object_should_have_auto_created(self):
        self.assertTrue(
            all(
                f.auto_created.__class__ == bool
                for f in self.fields_and_reverse_objects
            )
        )

    def test_non_concrete_fields(self):
        """

        Tests that non-concrete fields are correctly identified as non-concrete.

        This test iterates over all fields in the current object and checks if the field type
        is in the list of known non-concrete fields. If it is, the test asserts that the field's
        concrete attribute is False; otherwise, it asserts that the concrete attribute is True.

        This ensures that the distinction between concrete and non-concrete fields is correctly
        maintained, which is crucial for proper handling of these fields in subsequent operations.

        """
        for field in self.fields:
            if type(field) in NON_CONCRETE_FIELDS:
                self.assertFalse(field.concrete)
            else:
                self.assertTrue(field.concrete)

    def test_non_editable_fields(self):
        for field in self.all_fields:
            if type(field) in NON_EDITABLE_FIELDS:
                self.assertFalse(field.editable)
            else:
                self.assertTrue(field.editable)

    def test_related_fields(self):
        """

        Checks that fields in the collection are correctly identified as relation fields.
        Verifies that fields of relation types (as defined in RELATION_FIELDS) have their 'is_relation' attribute set to True, 
        while non-relation fields have it set to False. 

        This test ensures the integrity of the field collection by validating the classification of each field based on its type. 

        """
        for field in self.all_fields:
            if type(field) in RELATION_FIELDS:
                self.assertTrue(field.is_relation)
            else:
                self.assertFalse(field.is_relation)

    def test_field_names_should_always_be_available(self):
        """
        Verifies that all field names are available.

        This test checks that each field in the fields_and_reverse_objects collection
        has a valid name property. It ensures that field names can be reliably accessed
        and used within the application, without encountering any missing or undefined
        field name values.

        The test iterates over all fields, asserting the presence of a name attribute
        for each one, thus guaranteeing the availability of field names throughout
        the system.
        """
        for field in self.fields_and_reverse_objects:
            self.assertTrue(field.name)

    def test_all_field_types_should_have_flags(self):
        """

        Tests that all field types have the required flags and that relation fields have a single valid cardinality flag.

        This test ensures that each field contains all the properties defined in FLAG_PROPERTIES.
        Additionally, for fields that represent relationships between objects (i.e., fields with is_relation set to True),
        it verifies that exactly one of the relational flags (defined in FLAG_PROPERTIES_FOR_RELATIONS) is set to True,
        thus enforcing a valid cardinality constraint.

        """
        for field in self.fields_and_reverse_objects:
            for flag in FLAG_PROPERTIES:
                self.assertTrue(
                    hasattr(field, flag),
                    "Field %s does not have flag %s" % (field, flag),
                )
            if field.is_relation:
                true_cardinality_flags = sum(
                    getattr(field, flag) is True
                    for flag in FLAG_PROPERTIES_FOR_RELATIONS
                )
                # If the field has a relation, there should be only one of the
                # 4 cardinality flags available.
                self.assertEqual(1, true_cardinality_flags)

    def test_cardinality_m2m(self):
        """
        Tests the cardinality of many-to-many (m2m) fields in the model.

        Verifies that the many-to-many fields defined in the model match the expected classes,
        and that the reverse relationship for each field is correctly configured as a many-to-many relationship.

        Checks the following conditions:
        - All many-to-many fields are instances of the expected classes.
        - Each many-to-many field has a valid reverse relationship.
        - The reverse relationship of each many-to-many field is also a many-to-many relationship.
        - The related model for each reverse relationship is properly defined.
        """
        m2m_type_fields = [
            f for f in self.all_fields if f.is_relation and f.many_to_many
        ]
        # Test classes are what we expect
        self.assertEqual(MANY_TO_MANY_CLASSES, {f.__class__ for f in m2m_type_fields})

        # Ensure all m2m reverses are m2m
        for field in m2m_type_fields:
            reverse_field = field.remote_field
            self.assertTrue(reverse_field.is_relation)
            self.assertTrue(reverse_field.many_to_many)
            self.assertTrue(reverse_field.related_model)

    def test_cardinality_o2m(self):
        """
        Tests the cardinality of one-to-many (o2m) relationships.

        Verifies that all one-to-many relationship fields are instances of the expected classes.
        Additionally, for each concrete one-to-many field, checks that the corresponding reverse field is a many-to-one relationship.

        Ensures that the defined one-to-many relationships conform to the expected structure and behavior, providing a foundation for reliable data modeling and queries.
        """
        o2m_type_fields = [
            f
            for f in self.fields_and_reverse_objects
            if f.is_relation and f.one_to_many
        ]
        # Test classes are what we expect
        self.assertEqual(ONE_TO_MANY_CLASSES, {f.__class__ for f in o2m_type_fields})

        # Ensure all o2m reverses are m2o
        for field in o2m_type_fields:
            if field.concrete:
                reverse_field = field.remote_field
                self.assertTrue(reverse_field.is_relation and reverse_field.many_to_one)

    def test_cardinality_m2o(self):
        """

        Tests the cardinality of many-to-one relationships in the model.

        Verifies that the many-to-one type fields are instances of the expected classes.
        Additionally, checks that each many-to-one relationship has a corresponding one-to-many reverse relationship.

        Raises AssertionError if any of the checks fail.

        """
        m2o_type_fields = [
            f
            for f in self.fields_and_reverse_objects
            if f.is_relation and f.many_to_one
        ]
        # Test classes are what we expect
        self.assertEqual(MANY_TO_ONE_CLASSES, {f.__class__ for f in m2o_type_fields})

        # Ensure all m2o reverses are o2m
        for obj in m2o_type_fields:
            if hasattr(obj, "field"):
                reverse_field = obj.field
                self.assertTrue(reverse_field.is_relation and reverse_field.one_to_many)

    def test_cardinality_o2o(self):
        """

        Verifies the cardinality of one-to-one relationships between objects.

        This test checks that all one-to-one type fields have the expected class types and 
        that their reverse fields also define one-to-one relationships. It ensures that 
        the relationship is properly established in both directions, validating the 
        consistency of the object's structure.

        """
        o2o_type_fields = [f for f in self.all_fields if f.is_relation and f.one_to_one]
        # Test classes are what we expect
        self.assertEqual(ONE_TO_ONE_CLASSES, {f.__class__ for f in o2o_type_fields})

        # Ensure all o2o reverses are o2o
        for obj in o2o_type_fields:
            if hasattr(obj, "field"):
                reverse_field = obj.field
                self.assertTrue(reverse_field.is_relation and reverse_field.one_to_one)

    def test_hidden_flag(self):
        incl_hidden = set(AllFieldsModel._meta.get_fields(include_hidden=True))
        no_hidden = set(AllFieldsModel._meta.get_fields())
        fields_that_should_be_hidden = incl_hidden - no_hidden
        for f in incl_hidden:
            self.assertEqual(f in fields_that_should_be_hidden, f.hidden)

    def test_model_and_reverse_model_should_equal_on_relations(self):
        """

        Verifies that the model relationships in AllFieldsModel are correctly defined.

        This test checks that for each field in the model, if the field is a concrete forward relation (i.e., it has a related model),
        the forward and reverse relations are correctly paired. Specifically, it checks that the model of the forward field matches
        the related model of the reverse field, and vice versa. This ensures that the relationships between models are symmetric
        and correctly defined.

        """
        for field in AllFieldsModel._meta.get_fields():
            is_concrete_forward_field = field.concrete and field.related_model
            if is_concrete_forward_field:
                reverse_field = field.remote_field
                self.assertEqual(field.model, reverse_field.related_model)
                self.assertEqual(field.related_model, reverse_field.model)

    def test_null(self):
        # null isn't well defined for a ManyToManyField, but changing it to
        # True causes backwards compatibility problems (#25320).
        """

        Verifies the nullability of specific fields in the AllFieldsModel.

        This test checks that the 'm2m' field does not allow null values, while the 'reverse2' field does.

        """
        self.assertFalse(AllFieldsModel._meta.get_field("m2m").null)
        self.assertTrue(AllFieldsModel._meta.get_field("reverse2").null)
