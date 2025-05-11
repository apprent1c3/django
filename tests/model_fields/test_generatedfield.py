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
        """
        Tests that a generated field can be successfully contributed to a model class.
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
        msg = "GeneratedField cannot have a default."
        with self.assertRaisesMessage(ValueError, msg):
            GeneratedField(
                expression=Lower("name"),
                output_field=CharField(max_length=255),
                default="",
                db_persist=False,
            )

    def test_database_default_unsupported(self):
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
        Tests that the db_persist parameter of a GeneratedField is either True or False, raising a ValueError for invalid values.
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
        Tests that the deconstruct method of a GeneratedField instance correctly returns its path, arguments, and keyword arguments, ensuring proper serialization and reconstruction of the field.
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
        Tests the get_col method of Model fields, specifically for generated fields with different output field types, to ensure correct column generation and output field type handling.
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
        Tests the functionality of a generated field's cached column.

        Verifies that the cached column is correctly retrieved and handles different 
        scenarios, including table aliases and field types.
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
        m = self.base_model(a=1, b=2)
        msg = "Cannot read a generated field from an unsaved model."
        with self.assertRaisesMessage(AttributeError, msg):
            m.field

    def test_full_clean(self):
        """
        Tests the full_clean method of the base model, verifying that it correctly calculates the field value based on inputs a and b, and saves the result successfully.
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
        Tests the full_clean method on a model instance with a check constraint.

        Verifies that a model instance with valid data can be cleaned and saved successfully,
        and that an instance with invalid data raises a ValidationError with the expected message.
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
        Tests that a model instance's full clean method correctly handles unique constraint 
        expressions and raises a ValidationError when the constraint is violated.
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
        m = self.base_model.objects.create(a=1, b=2)
        m = self._refresh_if_needed(m)
        self.assertEqual(m.field, 3)

    def test_non_nullable_create(self):
        with self.assertRaises(IntegrityError):
            self.base_model.objects.create()

    def test_save(self):
        # Insert.
        """
        Verifies the correct saving of model instances by testing the persistence of attribute changes and recalculated fields.
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
        """
        Checks that a model instance can be saved successfully when it contains a foreign key field, and verifies that the saved instance has the expected field value after refresh.
        """
        fk_object = Foo.objects.create(a="abc", d=Decimal("12.34"))
        m = self.base_model(a=1, b=2, fk=fk_object)
        m.save()
        m = self._refresh_if_needed(m)
        self.assertEqual(m.field, 3)

    def test_generated_fields_can_be_deferred(self):
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
        """

        Tests the bulk creation of model instances to verify the correct computation of a field.

        The test case creates a model instance, saves it using bulk creation, and then
        asserts that the field value is correctly calculated.

        """
        m = self.base_model(a=3, b=4)
        (m,) = self.base_model.objects.bulk_create([m])
        if not connection.features.can_return_rows_from_bulk_insert:
            m = self.base_model.objects.get()
        self.assertEqual(m.field, 7)

    def test_bulk_update(self):
        """
        Tests the bulk update functionality of the model, verifying that it correctly updates the specified fields and triggers any necessary post-update calculations.
        """
        m = self.base_model.objects.create(a=1, b=2)
        m.a = 3
        self.base_model.objects.bulk_update([m], fields=["a"])
        m = self.base_model.objects.get(pk=m.pk)
        self.assertEqual(m.field, 5)

    def test_output_field_lookups(self):
        """
        Tests that lookups from the output_field are correctly handled by GeneratedFields, 
        including underflow and overflow conditions that raise a model DoesNotExist error.
        """
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
        Tests that the database collation for an output field is correctly set to the test collation when the field is used in a Django model. Verifies that the collation and type of the output field match the expected values when retrieved from the database parameters.
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
        m = self.params_model.objects.create()
        m = self._refresh_if_needed(m)
        self.assertEqual(m.field, "Constant")

    def test_nullable(self):
        """
        Tests the behavior of a nullable field, ensuring it correctly handles null and non-null values, and checks the conversion of the input string to lowercase.
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
