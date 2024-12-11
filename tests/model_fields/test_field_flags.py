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
        """

        Setup the class by initializing fields and related objects for testing purposes.

        This method is a class-level setup hook that prepares the necessary data structures for 
        testing. It populates class attributes with fields, many-to-many fields, and related objects 
        from the AllFieldsModel, providing a comprehensive set of fields for further testing.

        The following class attributes are populated:
            - fields: A list of fields (including private fields) from the AllFieldsModel.
            - all_fields: An extended list of fields, including many-to-many fields and private fields.
            - fields_and_reverse_objects: A comprehensive list of all fields, many-to-many fields, 
              private fields, and related objects from the AllFieldsModel.

        """
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
        for field in self.fields:
            if type(field) in NON_CONCRETE_FIELDS:
                self.assertFalse(field.concrete)
            else:
                self.assertTrue(field.concrete)

    def test_non_editable_fields(self):
        """
        Tests that non-editable fields are correctly marked as non-editable.

        This function checks each field in the collection to ensure that fields of known non-editable types are not marked as editable, 
        and that all other fields are marked as editable.

        The test covers all fields, verifying that their editable status matches their expected behavior based on their type.
        """
        for field in self.all_fields:
            if type(field) in NON_EDITABLE_FIELDS:
                self.assertFalse(field.editable)
            else:
                self.assertTrue(field.editable)

    def test_related_fields(self):
        for field in self.all_fields:
            if type(field) in RELATION_FIELDS:
                self.assertTrue(field.is_relation)
            else:
                self.assertFalse(field.is_relation)

    def test_field_names_should_always_be_available(self):
        """

        Checks that all field names are available.

        This test iterates over a collection of fields and their corresponding reverse objects,
        verifying that each field has a valid name assigned to it.

        """
        for field in self.fields_and_reverse_objects:
            self.assertTrue(field.name)

    def test_all_field_types_should_have_flags(self):
        """

        Verifies that all field types have the required flags and, for relation fields, 
        ensures exactly one cardinality flag is set to True.

        Checks each field in the collection for the presence of all flags defined in FLAG_PROPERTIES. 
        Additionally, for fields representing relations, it validates that precisely one of the relation-specific 
        cardinality flags (as specified in FLAG_PROPERTIES_FOR_RELATIONS) is set to True, ensuring correct 
        cardinality configuration for these fields.

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

        Tests the cardinality of one-to-many relationships between model fields.

        Verifies that all one-to-many fields are of the expected class type and that their
        reverse relationships are indeed many-to-one. This ensures data consistency and
        integrity in the model's relationships.

        Checks the following conditions:
        - All one-to-many fields are of the correct class type.
        - For each concrete one-to-many field, its reverse relationship is a many-to-one field.

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

        Tests the cardinality of many-to-one (m2o) relationships in the fields and reverse objects.

        This test verifies that all m2o type fields are instances of the expected classes 
        and that their corresponding reverse fields are one-to-many relationships.

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

        Verify that one-to-one relationship fields are properly set up.

        This test checks that all one-to-one type fields in the model are instances of the expected classes.
        It then ensures that each one-to-one field has a corresponding reverse field that is also a one-to-one relationship.

        The test confirms the correct cardinality of one-to-one relationships by verifying the following conditions:
        - All one-to-one fields are instances of the specified one-to-one classes.
        - Each one-to-one field has a reverse field that is also a one-to-one relationship.

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
        """
        Tests the hidden flag on model fields.

        This test case verifies that fields marked as hidden are correctly excluded from the list
        of fields when `include_hidden` is set to `False`. It checks that each field's hidden
        attribute accurately reflects whether it should be hidden or not.

        The test covers all fields of the `AllFieldsModel`, ensuring that only the fields intended
        to be hidden are actually hidden, while all other fields remain visible.

        """
        incl_hidden = set(AllFieldsModel._meta.get_fields(include_hidden=True))
        no_hidden = set(AllFieldsModel._meta.get_fields())
        fields_that_should_be_hidden = incl_hidden - no_hidden
        for f in incl_hidden:
            self.assertEqual(f in fields_that_should_be_hidden, f.hidden)

    def test_model_and_reverse_model_should_equal_on_relations(self):
        """
        Tests whether the model and its reverse model are correctly related for all fields.

        This test case iterates over each field in the AllFieldsModel and checks if the field
        is a concrete forward relation (i.e., it has a related model). If so, it verifies
        that the model and its reverse model are correctly associated, ensuring that the
        relationships between models are symmetrical and consistent.

        The test covers all fields in the model, providing assurance that the model's
        relationships are correctly defined and can be traversed in both directions.
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
        self.assertFalse(AllFieldsModel._meta.get_field("m2m").null)
        self.assertTrue(AllFieldsModel._meta.get_field("reverse2").null)
