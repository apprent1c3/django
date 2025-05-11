from decimal import Decimal

from django.apps import apps
from django.core import checks
from django.core.exceptions import FieldError
from django.db import models
from django.test import TestCase, skipIfDBFeature
from django.test.utils import isolate_apps

from .models import Bar, FkToChar, Foo, PrimaryKeyCharModel


class ForeignKeyTests(TestCase):
    def test_callable_default(self):
        """A lazy callable may be used for ForeignKey.default."""
        a = Foo.objects.create(id=1, a="abc", d=Decimal("12.34"))
        b = Bar.objects.create(b="bcd")
        self.assertEqual(b.a, a)

    @skipIfDBFeature("interprets_empty_strings_as_nulls")
    def test_empty_string_fk(self):
        """
        Tests that empty string foreign key values are not converted to None, validating the correct behavior as per issue #19299.
        """
        char_model_empty = PrimaryKeyCharModel.objects.create(string="")
        fk_model_empty = FkToChar.objects.create(out=char_model_empty)
        fk_model_empty = FkToChar.objects.select_related("out").get(
            id=fk_model_empty.pk
        )
        self.assertEqual(fk_model_empty.out, char_model_empty)

    @isolate_apps("model_fields")
    def test_warning_when_unique_true_on_fk(self):
        """
        Tests that a warning is raised when a ForeignKey field has unique=True set, as this is equivalent to using a OneToOneField.
        """
        class Foo(models.Model):
            pass

        class FKUniqueTrue(models.Model):
            fk_field = models.ForeignKey(Foo, models.CASCADE, unique=True)

        model = FKUniqueTrue()
        expected_warnings = [
            checks.Warning(
                "Setting unique=True on a ForeignKey has the same effect as using a "
                "OneToOneField.",
                hint=(
                    "ForeignKey(unique=True) is usually better served by a "
                    "OneToOneField."
                ),
                obj=FKUniqueTrue.fk_field.field,
                id="fields.W342",
            )
        ]
        warnings = model.check()
        self.assertEqual(warnings, expected_warnings)

    def test_related_name_converted_to_text(self):
        rel_name = Bar._meta.get_field("a").remote_field.related_name
        self.assertIsInstance(rel_name, str)

    def test_abstract_model_pending_operations(self):
        """
        Verify that foreign key fields on abstract models do not create pending operations to resolve relationships declared as strings.
        """
        pending_ops_before = list(apps._pending_operations.items())

        class AbstractForeignKeyModel(models.Model):
            fk = models.ForeignKey("missing.FK", models.CASCADE)

            class Meta:
                abstract = True

        self.assertIs(AbstractForeignKeyModel._meta.apps, apps)
        self.assertEqual(
            pending_ops_before,
            list(apps._pending_operations.items()),
            "Pending lookup added for a foreign key on an abstract model",
        )

    @isolate_apps("model_fields", "model_fields.tests")
    def test_abstract_model_app_relative_foreign_key(self):
        """

        Tests resolution of abstract model app relative foreign keys.
        Verifies that foreign key relationships are correctly established 
        when using abstract models with relative references.

        """
        class AbstractReferent(models.Model):
            reference = models.ForeignKey("Referred", on_delete=models.CASCADE)

            class Meta:
                app_label = "model_fields"
                abstract = True

        def assert_app_model_resolved(label):
            """
            /assert_app_model_resolved
            Checks if the application model is correctly resolved for a given label.
            The function verifies that the foreign key reference in the ConcreteReferent model is properly set to the Referred model, ensuring correct app model resolution.
            """
            class Referred(models.Model):
                class Meta:
                    app_label = label

            class ConcreteReferent(AbstractReferent):
                class Meta:
                    app_label = label

            self.assertEqual(
                ConcreteReferent._meta.get_field("reference").related_model, Referred
            )

        assert_app_model_resolved("model_fields")
        assert_app_model_resolved("tests")

    @isolate_apps("model_fields")
    def test_to_python(self):
        """
        Verifies that the to_python method correctly converts a foreign key value to a Python object.
        """
        class Foo(models.Model):
            pass

        class Bar(models.Model):
            fk = models.ForeignKey(Foo, models.CASCADE)

        self.assertEqual(Bar._meta.get_field("fk").to_python("1"), 1)

    @isolate_apps("model_fields")
    def test_fk_to_fk_get_col_output_field(self):
        """
        Tests the output field of a foreign key to a foreign key model field using the get_col method, verifying it correctly returns the primary key of the underlying model.
        """
        class Foo(models.Model):
            pass

        class Bar(models.Model):
            foo = models.ForeignKey(Foo, models.CASCADE, primary_key=True)

        class Baz(models.Model):
            bar = models.ForeignKey(Bar, models.CASCADE, primary_key=True)

        col = Baz._meta.get_field("bar").get_col("alias")
        self.assertIs(col.output_field, Foo._meta.pk)

    @isolate_apps("model_fields")
    def test_recursive_fks_get_col(self):
        """
        Tests that a ValueError is raised when attempting to get a column from a recursive foreign key field, as this is not a resolvable output field.
        """
        class Foo(models.Model):
            bar = models.ForeignKey("Bar", models.CASCADE, primary_key=True)

        class Bar(models.Model):
            foo = models.ForeignKey(Foo, models.CASCADE, primary_key=True)

        with self.assertRaisesMessage(ValueError, "Cannot resolve output_field"):
            Foo._meta.get_field("bar").get_col("alias")

    @isolate_apps("model_fields")
    def test_non_local_to_field(self):
        """
        Tests that a ForeignKey in a model raises a FieldError when referencing a field that is not local to the related model.
        """
        class Parent(models.Model):
            key = models.IntegerField(unique=True)

        class Child(Parent):
            pass

        class Related(models.Model):
            child = models.ForeignKey(Child, on_delete=models.CASCADE, to_field="key")

        msg = (
            "'model_fields.Related.child' refers to field 'key' which is not "
            "local to model 'model_fields.Child'."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Related._meta.get_field("child").related_fields

    def test_invalid_to_parameter(self):
        """
        Checks that a TypeError is raised when an invalid argument is passed as the first parameter to a ForeignKey field, ensuring that it must be a model, a model name, or the string 'self'.
        """
        msg = (
            "ForeignKey(1) is invalid. First parameter to ForeignKey must be "
            "either a model, a model name, or the string 'self'"
        )
        with self.assertRaisesMessage(TypeError, msg):

            class MyModel(models.Model):
                child = models.ForeignKey(1, models.CASCADE)

    def test_manager_class_getitem(self):
        self.assertIs(models.ForeignKey["Foo"], models.ForeignKey)
