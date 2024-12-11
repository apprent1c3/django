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
        with self.assertRaisesMessage(ValueError, "GeneratedField cannot be editable."):
            GeneratedField(
                expression=Lower("name"),
                output_field=CharField(max_length=255),
                editable=True,
                db_persist=False,
            )

    @isolate_apps("model_fields")
    def test_contribute_to_class(self):
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

        Tests that a GeneratedField raises a ValueError when a database default is provided.

        The GeneratedField class does not support database defaults, as its purpose is to
        generate values in the application layer rather than relying on the database to
        provide a default value. This test ensures that attempting to create a
        GeneratedField with a database default results in a ValueError with a clear error
        message.

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
        Tests that the db_persist parameter of GeneratedField is properly validated.

        This test case ensures that the db_persist attribute is either True or False, 
        raising a ValueError if it is not explicitly set to one of these values. 

        It verifies that attempting to create a GeneratedField with db_persist set to 
        None or not specified at all results in an error with a meaningful message, 
        helping to prevent potential issues with database persistence in GeneratedField instances.
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
        """
        Tests the deconstruction of a GeneratedField instance.

        Verifies that the deconstruct method returns the correct path, arguments, and keyword arguments
        for the field, including the expression, output field, and database persistence setting.

        This test ensures that the GeneratedField can be properly serialized and reconstructed,
        which is essential for its usage in Django model definitions.

        """
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

        Retrieve a column object for a model field.

        This method is used to get a column object for a given model field, which can be used to
        access the field's value in a query. The column object is typically used in conjunction
        with a database query to specify the columns to be retrieved.

        The column object returned by this method will have an output field that matches the type
        of the model field. For example, if the model field is an IntegerField, the output field
        of the column object will also be an IntegerField.

        The method takes two parameters: an alias for the column, and an optional field parameter.
        The field parameter is used to specify the field for which to retrieve the column object.
        If the field parameter is not provided, the method will use the field that the method is
        called on.

        Returns:
            A column object with an output field that matches the type of the model field.

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

        Tests the functionality of cached columns for generated fields in models.

        This test case verifies that the `cached_col` property of a generated field
        returns the correct column instance based on the provided table and field.
        It also checks that the cached column is correctly associated with the field
        and has the expected output field type.

        The test covers various scenarios, including retrieving the cached column
        for the model's table, retrieving it with and without specifying the field,
        and checking that it is not retrieved for a different table or field type.

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
        Test that an AttributeError is raised when attempting to access a generated field from an unsaved model instance.

        This test case verifies that the expected error message is raised when trying to read a generated field before the model instance has been saved. The test covers a critical edge case to ensure data integrity and prevent potential issues with unsaved models.

        :raises AttributeError: If a generated field is accessed from an unsaved model instance.
        """
        m = self.base_model(a=1, b=2)
        msg = "Cannot read a generated field from an unsaved model."
        with self.assertRaisesMessage(AttributeError, msg):
            m.field

    def test_full_clean(self):
        m = self.base_model(a=1, b=2)
        # full_clean() ignores GeneratedFields.
        m.full_clean()
        m.save()
        m = self._refresh_if_needed(m)
        self.assertEqual(m.field, 3)

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_full_clean_with_check_constraint(self):
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

        Tests the creation of a new model instance.

        This test case verifies that a model can be successfully created with specified attributes and that the resulting instance has the expected field values. Specifically, it checks that the calculated field value is correctly computed based on the provided attributes.

        """
        m = self.base_model.objects.create(a=1, b=2)
        m = self._refresh_if_needed(m)
        self.assertEqual(m.field, 3)

    def test_non_nullable_create(self):
        with self.assertRaises(IntegrityError):
            self.base_model.objects.create()

    def test_save(self):
        # Insert.
        """

        Tests the functionality of saving model instances to the database.

        This test case covers creating a new model instance, saving it to the database,
        retrieving the saved instance, and verifying its fields. It also tests updating
        an existing instance's fields, saving the changes, and refreshing the instance
        from the database to confirm the changes took effect.

        The test case specifically checks the calculation of the 'field' attribute,
        which is expected to be the sum of 'a' and 'b' attributes. It verifies this
        calculation for both the initial save and a subsequent update to the instance.

        """
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
        fk_object = Foo.objects.create(a="abc", d=Decimal("12.34"))
        m = self.base_model(a=1, b=2, fk=fk_object)
        m.save()
        m = self._refresh_if_needed(m)
        self.assertEqual(m.field, 3)

    def test_generated_fields_can_be_deferred(self):
        """
        Defers the loading of specific fields in a model instance, allowing for lazy loading of certain fields.

        This test case verifies that generated fields can be deferred, which helps to improve database query performance by only loading the necessary fields. 

        It checks that after deferring a specific field, the instance correctly identifies the deferred fields.
        """
        fk_object = Foo.objects.create(a="abc", d=Decimal("12.34"))
        m = self.base_model.objects.create(a=1, b=2, fk=fk_object)
        m = self.base_model.objects.defer("field").get(id=m.id)
        self.assertEqual(m.get_deferred_fields(), {"field"})

    def test_update(self):
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
        """

        Tests the bulk update functionality of the base model.

        Verifies that updating multiple instances of the model in a single database query
        correctly modifies the specified fields. In this case, it checks if updating the 
        field 'a' of an instance results in the expected changes to the related field.

        """
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
        collation = connection.features.test_collations["virtual"]
        m = self.output_field_db_collation_model.objects.create(name="NAME")
        field = m._meta.get_field("lower_name")
        db_parameters = field.db_parameters(connection)
        self.assertEqual(db_parameters["collation"], collation)
        self.assertEqual(db_parameters["type"], field.output_field.db_type(connection))

    def test_db_type_parameters(self):
        """
        Tests the database type parameters for a specific model field.

         This function checks if the database type parameters for the 'lower_name' field of the output field database collation model are correctly configured.

         It verifies that the 'max_length' parameter of the 'lower_name' field is set to 11, ensuring consistency between the model definition and the actual database schema.
        """
        db_type_parameters = self.output_field_db_collation_model._meta.get_field(
            "lower_name"
        ).db_type_parameters(connection)
        self.assertEqual(db_type_parameters["max_length"], 11)

    def test_model_with_params(self):
        m = self.params_model.objects.create()
        m = self._refresh_if_needed(m)
        self.assertEqual(m.field, "Constant")

    def test_nullable(self):
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
