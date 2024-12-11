from django.apps import apps
from django.db import models
from django.test import SimpleTestCase, TestCase
from django.test.utils import isolate_apps

from .models import ManyToMany


class ManyToManyFieldTests(SimpleTestCase):
    def test_abstract_model_pending_operations(self):
        """
        Many-to-many fields declared on abstract models should not add lazy
        relations to resolve relationship declared as string (#24215).
        """
        pending_ops_before = list(apps._pending_operations.items())

        class AbstractManyToManyModel(models.Model):
            fk = models.ForeignKey("missing.FK", models.CASCADE)

            class Meta:
                abstract = True

        self.assertIs(AbstractManyToManyModel._meta.apps, apps)
        self.assertEqual(
            pending_ops_before,
            list(apps._pending_operations.items()),
            "Pending lookup added for a many-to-many field on an abstract model",
        )

    @isolate_apps("model_fields", "model_fields.tests")
    def test_abstract_model_app_relative_foreign_key(self):
        """

        Tests the resolution of app relative foreign keys in abstract models.

        Verifies that the related model and through model for a ManyToManyField
        defined in an abstract model are correctly resolved when the abstract model
        is subclassed in different apps. This ensures that the abstract model's
        metaclass correctly resolves the app label for the related model and through model.

        The test covers cases where the abstract model's subclass and the related model
        are defined in the same app and in different apps.

        """
        class AbstractReferent(models.Model):
            reference = models.ManyToManyField("Referred", through="Through")

            class Meta:
                app_label = "model_fields"
                abstract = True

        def assert_app_model_resolved(label):
            """

            Verify that the application model is correctly resolved for a given label.

            This function checks the resolution of a model by creating temporary models 
            ('Referred', 'Through', and 'ConcreteReferent') with the specified app label.
            It then asserts that the 'reference' field on 'ConcreteReferent' correctly 
            references the 'Referred' model and uses the 'Through' model as the through table.

            Args:
                label (str): The application label to use for model resolution.

            Returns:
                None

            Raises:
                AssertionError: If the model resolution is incorrect.

            """
            class Referred(models.Model):
                class Meta:
                    app_label = label

            class Through(models.Model):
                referred = models.ForeignKey("Referred", on_delete=models.CASCADE)
                referent = models.ForeignKey(
                    "ConcreteReferent", on_delete=models.CASCADE
                )

                class Meta:
                    app_label = label

            class ConcreteReferent(AbstractReferent):
                class Meta:
                    app_label = label

            self.assertEqual(
                ConcreteReferent._meta.get_field("reference").related_model, Referred
            )
            self.assertEqual(ConcreteReferent.reference.through, Through)

        assert_app_model_resolved("model_fields")
        assert_app_model_resolved("tests")

    def test_invalid_to_parameter(self):
        """
        Tests that a TypeError is raised when the 'to' parameter of a ManyToManyField is invalid.

         The 'to' parameter should be either a model, a model name, or the string 'self'. 
         Any other type of parameter will result in a TypeError with a descriptive error message.

         This test specifically checks that a TypeError is raised when the 'to' parameter is an integer.
        """
        msg = (
            "ManyToManyField(1) is invalid. First parameter to "
            "ManyToManyField must be either a model, a model name, or the "
            "string 'self'"
        )
        with self.assertRaisesMessage(TypeError, msg):

            class MyModel(models.Model):
                m2m = models.ManyToManyField(1)

    @isolate_apps("model_fields")
    def test_through_db_table_mutually_exclusive(self):
        """
        Tests that using an intermediary model with a ManyToManyField and specifying a custom db_table raises a ValueError.

        This test ensures that Django enforces the constraint that when an intermediary model is used with a ManyToManyField,
        it is not possible to specify a custom database table name using the db_table argument.

        :raises ValueError: If db_table is specified with an intermediary model
        """
        class Child(models.Model):
            pass

        class Through(models.Model):
            referred = models.ForeignKey(Child, on_delete=models.CASCADE)
            referent = models.ForeignKey(Child, on_delete=models.CASCADE)

        msg = "Cannot specify a db_table if an intermediary model is used."
        with self.assertRaisesMessage(ValueError, msg):

            class MyModel(models.Model):
                m2m = models.ManyToManyField(
                    Child,
                    through="Through",
                    db_table="custom_name",
                )


class ManyToManyFieldDBTests(TestCase):
    def test_value_from_object_instance_without_pk(self):
        obj = ManyToMany()
        self.assertEqual(obj._meta.get_field("m2m").value_from_object(obj), [])

    def test_value_from_object_instance_with_pk(self):
        """
        Tests that the value_from_object method of a ManyToMany field returns the correct related objects when given an object instance with a primary key.

        This test case verifies that the method correctly retrieves the related objects associated with the given object instance, ensuring that the ManyToMany relationship is properly established and queried.

        Parameters: 
            None

        Returns: 
            None

        Raises: 
            AssertionError: If the value_from_object method does not return the expected related objects.

        Note: 
            This test case assumes that the ManyToMany field 'm2m' has been properly defined in the model, and that the objects are being created and saved correctly.
        """
        obj = ManyToMany.objects.create()
        related_obj = ManyToMany.objects.create()
        obj.m2m.add(related_obj)
        self.assertEqual(
            obj._meta.get_field("m2m").value_from_object(obj), [related_obj]
        )
