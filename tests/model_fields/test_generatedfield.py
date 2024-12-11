import uuid
from decimal import Decimal

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.db.models import (
    CharField,
    F,
    FloatField,
    GeneratedField,
    IntegerField,
    Model,
)
from django.db.models.functions import Lower
from django.test import SimpleTestCase, TestCase, skipUnlessDBFeature
from django.test.utils import isolate_apps

from .models import (
    Foo,
    GeneratedModel,
    GeneratedModelCheckConstraint,
    GeneratedModelCheckConstraintVirtual,
    GeneratedModelFieldWithConverters,
    GeneratedModelNull,
    GeneratedModelNullVirtual,
    GeneratedModelOutputFieldDbCollation,
    GeneratedModelOutputFieldDbCollationVirtual,
    GeneratedModelParams,
    GeneratedModelParamsVirtual,
    GeneratedModelUniqueConstraint,
    GeneratedModelUniqueConstraintVirtual,
    GeneratedModelVirtual,
)


class BaseGeneratedFieldTests(SimpleTestCase):
    def test_editable_unsupported(self):
        """
        Tests that attempting to create a GeneratedField with editable set to True raises a ValueError.

        The GeneratedField class does not support being editable, and this test ensures that
        the expected error message is raised when an attempt is made to set editable to True.

        :raises ValueError: If the GeneratedField is created with editable set to True.

        """
        with self.assertRaisesMessage(ValueError, "GeneratedField cannot be editable."):
            GeneratedField(
                expression=Lower("name"),
                output_field=CharField(max_length=255),
                editable=True,
                db_persist=False,
            )

    @isolate_apps("model_fields")
    def test_contribute_to_class(self):
        """

         Tests if a generated field can successfully contribute to a model class.

         Checks that when a generated field is added to a model, it is properly registered
         in the model's metadata and can be retrieved using the model's _meta interface.

         This test ensures that the field is correctly associated with the model and that
         its properties, such as expression and output field, are preserved during the
         contribution process.

         The test also verifies that the contribution process is properly isolated and
         does not interfere with the global state of the application, specifically the
         models_ready flag.

        """
        class BareModel(Model):
            pass

        new_field = GeneratedField(
            expression=Lower("nonexistent"),
            output_field=IntegerField(),
            db_persist=True,
        )
        apps.models_ready = False
        try:
            # GeneratedField can be added to the model even when apps are not
            # fully loaded.
            new_field.contribute_to_class(BareModel, "name")
            self.assertEqual(BareModel._meta.get_field("name"), new_field)
        finally:
            apps.models_ready = True

    def test_blank_unsupported(self):
        with self.assertRaisesMessage(ValueError, "GeneratedField must be blank."):
            GeneratedField(
                expression=Lower("name"),
                output_field=CharField(max_length=255),
                blank=False,
                db_persist=False,
            )

    def test_default_unsupported(self):
        """
        Tests that attempting to set a default value on a GeneratedField raises a ValueError.

        The GeneratedField class is designed to handle calculated fields, and as such, 
        does not support default values. This test checks that an appropriate error message 
        is raised when a default is provided, ensuring the class behaves as expected in this scenario.

        Args: 
            None

        Returns: 
            None

        Raises:
            ValueError: If a default value is provided for a GeneratedField
        """
        msg = "GeneratedField cannot have a default."
        with self.assertRaisesMessage(ValueError, msg):
            GeneratedField(
                expression=Lower("name"),
                output_field=CharField(max_length=255),
                default="",
                db_persist=False,
            )

    def test_database_default_unsupported(self):
        """
        #: Raises a ValueError when attempting to set a database default on a GeneratedField.
        #: 
        #: A GeneratedField in the database is determined by its expression and cannot have a 
        #: predefined default value set at the database level. This function tests that 
        #: setting db_default on a GeneratedField raises an exception with a descriptive error 
        #: message, ensuring consistent behavior and preventing potential data inconsistencies.
        """
        msg = "GeneratedField cannot have a database default."
        with self.assertRaisesMessage(ValueError, msg):
            GeneratedField(
                expression=Lower("name"),
                output_field=CharField(max_length=255),
                db_default="",
                db_persist=False,
            )

    def test_db_persist_required(self):
        """
        Tests that the `db_persist` attribute of a GeneratedField is either True or False.

        Verifies that attempting to create a GeneratedField with `db_persist` set to any value other than True or False raises a ValueError.

        The test covers two specific cases:
        - Omitting the `db_persist` attribute altogether.
        - Explicitly setting `db_persist` to None.

        This ensures that the `db_persist` attribute is always properly validated, preventing incorrect configurations that could lead to unexpected behavior or errors elsewhere in the application.
        """
        msg = "GeneratedField.db_persist must be True or False."
        with self.assertRaisesMessage(ValueError, msg):
            GeneratedField(
                expression=Lower("name"), output_field=CharField(max_length=255)
            )
        with self.assertRaisesMessage(ValueError, msg):
            GeneratedField(
                expression=Lower("name"),
                output_field=CharField(max_length=255),
                db_persist=None,
            )

    def test_deconstruct(self):
        field = GeneratedField(
            expression=F("a") + F("b"), output_field=IntegerField(), db_persist=True
        )
        _, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.GeneratedField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs["db_persist"], True)
        self.assertEqual(kwargs["expression"], F("a") + F("b"))
        self.assertEqual(
            kwargs["output_field"].deconstruct(), IntegerField().deconstruct()
        )

    @isolate_apps("model_fields")
    def test_get_col(self):
        """
        Return a column object representation of the field.

        This method is used to get a column object that represents the generated field.
        It can be used to access the output field of the generated field, which
        determines the data type of the generated column in the database.
        The method can take an optional `field` parameter, which is used to generate the
        column object.

        The returned column object has an `output_field` attribute that specifies the
        type of the generated column, such as IntegerField or FloatField.

        The method is commonly used in database queries and operations to access the
        generated fields of a model.

        :param field: Optional field object to generate the column from
        :returns: A column object representing the generated field
        """
        class Square(Model):
            side = IntegerField()
            area = GeneratedField(
                expression=F("side") * F("side"),
                output_field=IntegerField(),
                db_persist=True,
            )

        field = Square._meta.get_field("area")

        col = field.get_col("alias")
        self.assertIsInstance(col.output_field, IntegerField)

        col = field.get_col("alias", field)
        self.assertIsInstance(col.output_field, IntegerField)

        class FloatSquare(Model):
            side = IntegerField()
            area = GeneratedField(
                expression=F("side") * F("side"),
                db_persist=True,
                output_field=FloatField(),
            )

        field = FloatSquare._meta.get_field("area")

        col = field.get_col("alias")
        self.assertIsInstance(col.output_field, FloatField)

        col = field.get_col("alias", field)
        self.assertIsInstance(col.output_field, FloatField)

    @isolate_apps("model_fields")
    def test_cached_col(self):
        """
        Verifies the correctness of the cached column for a generated field.

        Checks that the cached column is correctly retrieved for a generated field, 
        tests that it is associated with the correct target field, output field type, 
        and that it is not confused with other fields or table aliases.

        Ensures that the cached column is distinct when different parameters 
        such as table alias or field type are provided. 

        This test case prevents regressions in the generated field's 
        cached column functionality, ensuring accurate database interactions and 
        correct field resolution in various scenarios.
        """
        class Sum(Model):
            a = IntegerField()
            b = IntegerField()
            total = GeneratedField(
                expression=F("a") + F("b"), output_field=IntegerField(), db_persist=True
            )

        field = Sum._meta.get_field("total")
        cached_col = field.cached_col
        self.assertIs(field.get_col(Sum._meta.db_table), cached_col)
        self.assertIs(field.get_col(Sum._meta.db_table, field), cached_col)
        self.assertIsNot(field.get_col("alias"), cached_col)
        self.assertIsNot(field.get_col(Sum._meta.db_table, IntegerField()), cached_col)
        self.assertIs(cached_col.target, field)
        self.assertIsInstance(cached_col.output_field, IntegerField)


class GeneratedFieldTestMixin:
    def _refresh_if_needed(self, m):
        if not connection.features.can_return_columns_from_insert:
            m.refresh_from_db()
        return m

    def test_unsaved_error(self):
        """

        Tests that attempting to access a generated field from an unsaved model raises an AttributeError.

        The test creates a new instance of the base model with specified attributes and then attempts to access the 'field' attribute, 
        which is a generated field. This should result in an AttributeError with the message 'Cannot read a generated field from an unsaved model.'.

        """
        m = self.base_model(a=1, b=2)
        msg = "Cannot read a generated field from an unsaved model."
        with self.assertRaisesMessage(AttributeError, msg):
            m.field

    def test_full_clean(self):
        """
        Tests the full_clean method of the model.

        Verifies that the full_clean method performs the expected validation and 
        processing, resulting in the correct value being saved to the 'field' attribute.

        The test creates an instance of the base model with specific attribute values,
        calls the full_clean method to trigger validation and processing, saves the 
        instance, and then checks that the resulting 'field' value matches the expected 
        output.

        """
        m = self.base_model(a=1, b=2)
        # full_clean() ignores GeneratedFields.
        m.full_clean()
        m.save()
        m = self._refresh_if_needed(m)
        self.assertEqual(m.field, 3)

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_full_clean_with_check_constraint(self):
        """
        Test that a model's full clean method correctly enforces check constraints.

        This test case covers the scenario where a model instance is validated using the
        full clean method, which checks for any constraints defined on the model, such as
        check constraints. It verifies that the model instance is saved and its fields
        are correctly validated when the constraint is satisfied, and that a ValidationError
        is raised when the constraint is violated.

        The test specifically checks that the check constraint defined on the model is
        enforced when the full clean method is called, and that the error message
        returned in case of a constraint violation is accurate and informative, including
        the name of the model and the specific constraint that was violated.
        """
        model_name = self.check_constraint_model._meta.verbose_name.capitalize()

        m = self.check_constraint_model(a=2)
        m.full_clean()
        m.save()
        m = self._refresh_if_needed(m)
        self.assertEqual(m.a_squared, 4)

        m = self.check_constraint_model(a=-1)
        with self.assertRaises(ValidationError) as cm:
            m.full_clean()
        self.assertEqual(
            cm.exception.message_dict,
            {"__all__": [f"Constraint “{model_name} a > 0” is violated."]},
        )

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_full_clean_with_unique_constraint_expression(self):
        """

        Tests the full_clean method of a model instance with a unique constraint expression.

        This test case ensures that the full_clean method correctly validates the model instance
        when a unique constraint is defined on an expression. The test creates an instance of the
        model, calls full_clean, saves the instance, and verifies that the expected value is
        calculated. It then attempts to create another instance with the same value, which should
        raise a ValidationError due to the unique constraint.

        The test covers the following scenarios:
        - Successful validation and saving of a model instance
        - Validation error when trying to save a duplicate value
        - Correct error message when the unique constraint is violated

        """
        model_name = self.unique_constraint_model._meta.verbose_name.capitalize()

        m = self.unique_constraint_model(a=2)
        m.full_clean()
        m.save()
        m = self._refresh_if_needed(m)
        self.assertEqual(m.a_squared, 4)

        m = self.unique_constraint_model(a=2)
        with self.assertRaises(ValidationError) as cm:
            m.full_clean()
        self.assertEqual(
            cm.exception.message_dict,
            {"__all__": [f"Constraint “{model_name} a” is violated."]},
        )

    def test_create(self):
        """

        Tests the creation of a new instance of the base model.

        Verifies that the instance is successfully created with the specified attributes
        and that the calculated field is correctly computed based on the input values.

        """
        m = self.base_model.objects.create(a=1, b=2)
        m = self._refresh_if_needed(m)
        self.assertEqual(m.field, 3)

    def test_non_nullable_create(self):
        """
        Tests that creating an instance of the base model without providing required non-nullable fields raises an IntegrityError.

        This test case ensures that the database correctly enforces the non-nullable constraints defined in the model, preventing the creation of invalid data.

        Raises:
            IntegrityError: If the creation is successful without providing the required fields.

        """
        with self.assertRaises(IntegrityError):
            self.base_model.objects.create()

    def test_save(self):
        # Insert.
        m = self.base_model(a=2, b=4)
        m.save()
        m = self._refresh_if_needed(m)
        self.assertEqual(m.field, 6)
        # Update.
        m.a = 4
        m.save()
        m.refresh_from_db()
        self.assertEqual(m.field, 8)

    def test_save_model_with_pk(self):
        m = self.base_model(pk=1, a=1, b=2)
        m.save()
        m = self._refresh_if_needed(m)
        self.assertEqual(m.field, 3)

    def test_save_model_with_foreign_key(self):
        """
        …..}/>Tests the saving of a model instance that contains a foreign key.

        Checks that when a model with a foreign key is saved, the instance's fields are populated correctly after the save operation.

        Verifies the correctness of the model's foreign key handling by comparing the expected and actual values of the instance's field after saving.
        """
        fk_object = Foo.objects.create(a="abc", d=Decimal("12.34"))
        m = self.base_model(a=1, b=2, fk=fk_object)
        m.save()
        m = self._refresh_if_needed(m)
        self.assertEqual(m.field, 3)

    def test_generated_fields_can_be_deferred(self):
        """
        Tests that generated fields can be deferred when retrieving model instances.

        Verifies that when a model instance is fetched with deferred fields, 
        the deferred fields are correctly identified and can be retrieved later. 
        This ensures that the model's deferred loading mechanism is functioning as expected.

        The test creates a model instance with a foreign key reference, 
        then retrieves the instance with a deferred field and checks that 
        the field is correctly marked as deferred.
        """
        fk_object = Foo.objects.create(a="abc", d=Decimal("12.34"))
        m = self.base_model.objects.create(a=1, b=2, fk=fk_object)
        m = self.base_model.objects.defer("field").get(id=m.id)
        self.assertEqual(m.get_deferred_fields(), {"field"})

    def test_update(self):
        """

        Tests the update functionality of the base model by creating an instance, updating its attributes, and verifying the changes.

        The test case ensures that when an attribute of the model is updated, the corresponding field is correctly calculated and updated. Specifically, it checks that when attribute 'b' is updated from 2 to 3, the 'field' attribute is updated to the expected value of 4.

        This test provides assurance that the update mechanism is working as intended, allowing for seamless modification of model instances.

        """
        m = self.base_model.objects.create(a=1, b=2)
        self.base_model.objects.update(b=3)
        m = self.base_model.objects.get(pk=m.pk)
        self.assertEqual(m.field, 4)

    def test_bulk_create(self):
        m = self.base_model(a=3, b=4)
        (m,) = self.base_model.objects.bulk_create([m])
        if not connection.features.can_return_rows_from_bulk_insert:
            m = self.base_model.objects.get()
        self.assertEqual(m.field, 7)

    def test_bulk_update(self):
        m = self.base_model.objects.create(a=1, b=2)
        m.a = 3
        self.base_model.objects.bulk_update([m], fields=["a"])
        m = self.base_model.objects.get(pk=m.pk)
        self.assertEqual(m.field, 5)

    def test_output_field_lookups(self):
        """Lookups from the output_field are available on GeneratedFields."""
        internal_type = IntegerField().get_internal_type()
        min_value, max_value = connection.ops.integer_field_range(internal_type)
        if min_value is None:
            self.skipTest("Backend doesn't define an integer min value.")
        if max_value is None:
            self.skipTest("Backend doesn't define an integer max value.")

        does_not_exist = self.base_model.DoesNotExist
        underflow_value = min_value - 1
        with self.assertNumQueries(0), self.assertRaises(does_not_exist):
            self.base_model.objects.get(field=underflow_value)
        with self.assertNumQueries(0), self.assertRaises(does_not_exist):
            self.base_model.objects.get(field__lt=underflow_value)
        with self.assertNumQueries(0), self.assertRaises(does_not_exist):
            self.base_model.objects.get(field__lte=underflow_value)

        overflow_value = max_value + 1
        with self.assertNumQueries(0), self.assertRaises(does_not_exist):
            self.base_model.objects.get(field=overflow_value)
        with self.assertNumQueries(0), self.assertRaises(does_not_exist):
            self.base_model.objects.get(field__gt=overflow_value)
        with self.assertNumQueries(0), self.assertRaises(does_not_exist):
            self.base_model.objects.get(field__gte=overflow_value)

    def test_output_field_db_collation(self):
        """
        Tests that the database collation for an output field is correctly applied.

        This test case creates an instance of a model that includes an output field,
        verifies the collation of the field's database parameters, and checks that it
        matches the expected collation. The test also confirms that the database type of
        the output field matches the expected type.
        """
        collation = connection.features.test_collations["virtual"]
        m = self.output_field_db_collation_model.objects.create(name="NAME")
        field = m._meta.get_field("lower_name")
        db_parameters = field.db_parameters(connection)
        self.assertEqual(db_parameters["collation"], collation)
        self.assertEqual(db_parameters["type"], field.output_field.db_type(connection))

    def test_db_type_parameters(self):
        db_type_parameters = self.output_field_db_collation_model._meta.get_field(
            "lower_name"
        ).db_type_parameters(connection)
        self.assertEqual(db_type_parameters["max_length"], 11)

    def test_model_with_params(self):
        """

        Tests a model instance with predefined parameters.

        Verifies that a newly created model instance has the expected field value.
        The test creates a model instance using the params_model, refreshes it if necessary, 
        and then asserts that the 'field' attribute of the model instance equals 'Constant'.

        """
        m = self.params_model.objects.create()
        m = self._refresh_if_needed(m)
        self.assertEqual(m.field, "Constant")

    def test_nullable(self):
        """
        Tests the behavior of nullable fields in the model, specifically ensuring correct handling of null and empty string values.

         The test covers two scenarios: 
          - creating a model instance without specifying a value for the nullable field, and verifying that the resulting value is correctly interpreted as null (or an empty string, depending on the database backend).
          - creating a model instance with a non-null value for the nullable field, and verifying that the value is correctly processed and stored.
        """
        m1 = self.nullable_model.objects.create()
        m1 = self._refresh_if_needed(m1)
        none_val = "" if connection.features.interprets_empty_strings_as_nulls else None
        self.assertEqual(m1.lower_name, none_val)
        m2 = self.nullable_model.objects.create(name="NaMe")
        m2 = self._refresh_if_needed(m2)
        self.assertEqual(m2.lower_name, "name")


@skipUnlessDBFeature("supports_stored_generated_columns")
class StoredGeneratedFieldTests(GeneratedFieldTestMixin, TestCase):
    base_model = GeneratedModel
    nullable_model = GeneratedModelNull
    check_constraint_model = GeneratedModelCheckConstraint
    unique_constraint_model = GeneratedModelUniqueConstraint
    output_field_db_collation_model = GeneratedModelOutputFieldDbCollation
    params_model = GeneratedModelParams

    def test_create_field_with_db_converters(self):
        obj = GeneratedModelFieldWithConverters.objects.create(field=uuid.uuid4())
        obj = self._refresh_if_needed(obj)
        self.assertEqual(obj.field, obj.field_copy)


@skipUnlessDBFeature("supports_virtual_generated_columns")
class VirtualGeneratedFieldTests(GeneratedFieldTestMixin, TestCase):
    base_model = GeneratedModelVirtual
    nullable_model = GeneratedModelNullVirtual
    check_constraint_model = GeneratedModelCheckConstraintVirtual
    unique_constraint_model = GeneratedModelUniqueConstraintVirtual
    output_field_db_collation_model = GeneratedModelOutputFieldDbCollationVirtual
    params_model = GeneratedModelParamsVirtual
