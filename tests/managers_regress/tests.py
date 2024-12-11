from django.db import models
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import isolate_apps

from .models import (
    AbstractBase1,
    AbstractBase2,
    AbstractBase3,
    Child1,
    Child2,
    Child3,
    Child4,
    Child5,
    Child6,
    Child7,
    RelatedModel,
    RelationModel,
)


class ManagersRegressionTests(TestCase):
    def test_managers(self):
        a1 = Child1.objects.create(name="fred", data="a1")
        a2 = Child1.objects.create(name="barney", data="a2")
        b1 = Child2.objects.create(name="fred", data="b1", value=1)
        b2 = Child2.objects.create(name="barney", data="b2", value=42)
        c1 = Child3.objects.create(name="fred", data="c1", comment="yes")
        c2 = Child3.objects.create(name="barney", data="c2", comment="no")
        d1 = Child4.objects.create(name="fred", data="d1")
        d2 = Child4.objects.create(name="barney", data="d2")
        fred1 = Child5.objects.create(name="fred", comment="yes")
        Child5.objects.create(name="barney", comment="no")
        f1 = Child6.objects.create(name="fred", data="f1", value=42)
        f2 = Child6.objects.create(name="barney", data="f2", value=42)
        fred2 = Child7.objects.create(name="fred")
        barney = Child7.objects.create(name="barney")

        self.assertSequenceEqual(Child1.manager1.all(), [a1])
        self.assertSequenceEqual(Child1.manager2.all(), [a2])
        self.assertSequenceEqual(Child1._default_manager.all(), [a1])

        self.assertSequenceEqual(Child2._default_manager.all(), [b1])
        self.assertSequenceEqual(Child2.restricted.all(), [b2])

        self.assertSequenceEqual(Child3._default_manager.all(), [c1])
        self.assertSequenceEqual(Child3.manager1.all(), [c1])
        self.assertSequenceEqual(Child3.manager2.all(), [c2])

        # Since Child6 inherits from Child4, the corresponding rows from f1 and
        # f2 also appear here. This is the expected result.
        self.assertSequenceEqual(
            Child4._default_manager.order_by("data"),
            [d1, d2, f1.child4_ptr, f2.child4_ptr],
        )
        self.assertCountEqual(Child4.manager1.all(), [d1, f1.child4_ptr])
        self.assertCountEqual(Child5._default_manager.all(), [fred1])
        self.assertCountEqual(Child6._default_manager.all(), [f1, f2])
        self.assertSequenceEqual(
            Child7._default_manager.order_by("name"),
            [barney, fred2],
        )

    def test_abstract_manager(self):
        # Accessing the manager on an abstract model should
        # raise an attribute error with an appropriate message.
        # This error message isn't ideal, but if the model is abstract and
        # a lot of the class instantiation logic isn't invoked; if the
        # manager is implied, then we don't get a hook to install the
        # error-raising manager.
        """

        Tests that an abstract base model does not have an 'objects' attribute.

        Verifies that attempting to access the 'objects' manager on an abstract base model raises an AttributeError,
        as it is not a valid operation on abstract models.

        """
        msg = "type object 'AbstractBase3' has no attribute 'objects'"
        with self.assertRaisesMessage(AttributeError, msg):
            AbstractBase3.objects.all()

    def test_custom_abstract_manager(self):
        # Accessing the manager on an abstract model with a custom
        # manager should raise an attribute error with an appropriate
        # message.
        """
        Tests that an abstract manager cannot be instantiated.

        Verifies that attempting to access the 'restricted' manager on an abstract base class
        raises an AttributeError with the expected message, indicating that the manager
        is not available due to the abstract nature of the class.

        This test ensures that the correct error handling is in place when trying to
        access a manager on an abstract class that does not support it.
        """
        msg = "Manager isn't available; AbstractBase2 is abstract"
        with self.assertRaisesMessage(AttributeError, msg):
            AbstractBase2.restricted.all()

    def test_explicit_abstract_manager(self):
        # Accessing the manager on an abstract model with an explicit
        # manager should raise an attribute error with an appropriate
        # message.
        msg = "Manager isn't available; AbstractBase1 is abstract"
        with self.assertRaisesMessage(AttributeError, msg):
            AbstractBase1.objects.all()

    @override_settings(TEST_SWAPPABLE_MODEL="managers_regress.Parent")
    @isolate_apps("managers_regress")
    def test_swappable_manager(self):
        """
        Tests a swappable model with a manager to ensure that it raises an AttributeError when attempting to access the objects manager after the model has been swapped.

        The test case verifies that the expected error message is raised when trying to access the 'objects' manager of a swappable model that has been swapped with a different model. This ensures that the swappable model behaves correctly in this scenario and provides a clear error message when the manager is not available due to the model swap.

        This test is specific to the 'TEST_SWAPPABLE_MODEL' setting, which determines the model to swap with the swappable model being tested. In this case, the test is configured to swap the swappable model with the 'managers_regress.Parent' model.

        The test outcome indicates that the swappable model's manager is correctly identified as unavailable after the model swap, and the expected error message is raised with the correct details about the model swap.
        """
        class SwappableModel(models.Model):
            class Meta:
                swappable = "TEST_SWAPPABLE_MODEL"

        # Accessing the manager on a swappable model should
        # raise an attribute error with a helpful message
        msg = (
            "Manager isn't available; 'managers_regress.SwappableModel' "
            "has been swapped for 'managers_regress.Parent'"
        )
        with self.assertRaisesMessage(AttributeError, msg):
            SwappableModel.objects.all()

    @override_settings(TEST_SWAPPABLE_MODEL="managers_regress.Parent")
    @isolate_apps("managers_regress")
    def test_custom_swappable_manager(self):
        class SwappableModel(models.Model):
            stuff = models.Manager()

            class Meta:
                swappable = "TEST_SWAPPABLE_MODEL"

        # Accessing the manager on a swappable model with an
        # explicit manager should raise an attribute error with a
        # helpful message
        msg = (
            "Manager isn't available; 'managers_regress.SwappableModel' "
            "has been swapped for 'managers_regress.Parent'"
        )
        with self.assertRaisesMessage(AttributeError, msg):
            SwappableModel.stuff.all()

    @override_settings(TEST_SWAPPABLE_MODEL="managers_regress.Parent")
    @isolate_apps("managers_regress")
    def test_explicit_swappable_manager(self):
        class SwappableModel(models.Model):
            objects = models.Manager()

            class Meta:
                swappable = "TEST_SWAPPABLE_MODEL"

        # Accessing the manager on a swappable model with an
        # explicit manager should raise an attribute error with a
        # helpful message
        msg = (
            "Manager isn't available; 'managers_regress.SwappableModel' "
            "has been swapped for 'managers_regress.Parent'"
        )
        with self.assertRaisesMessage(AttributeError, msg):
            SwappableModel.objects.all()

    def test_regress_3871(self):
        """

        Tests the regression issue 3871 by verifying the proper rendering of related objects in a template.

        This test case creates an instance of RelatedModel, establishes relationships with RelationModel through foreign key and generic foreign key,
        and adds the related object to a many-to-many field. It then renders a template that accesses the related objects and checks that the rendered
        output matches the expected result, ensuring that the relationships are correctly resolved and rendered.

        """
        related = RelatedModel.objects.create()

        relation = RelationModel()
        relation.fk = related
        relation.gfk = related
        relation.save()
        relation.m2m.add(related)

        t = Template(
            "{{ related.test_fk.all.0 }}{{ related.test_gfk.all.0 }}"
            "{{ related.test_m2m.all.0 }}"
        )

        self.assertEqual(
            t.render(Context({"related": related})),
            "".join([str(relation.pk)] * 3),
        )

    def test_field_can_be_called_exact(self):
        # Make sure related managers core filters don't include an
        # explicit `__exact` lookup that could be interpreted as a
        # reference to a foreign `exact` field. refs #23940.
        """
        Tests that a field can be retrieved exactly as it was previously saved.

        This test case verifies that a related field can be called exactly, ensuring 
        that the relationship between models is correctly established and retrieved.
        The test checks if the retrieved relation matches the initially created relation. 

        Checks the following:
        - A related model instance is created.
        - A new relation is created for the related model instance.
        - The exact relation is retrieved from the related model instance.

        Verifies that the retrieved relation is the same as the initially created one.

        """
        related = RelatedModel.objects.create(exact=False)
        relation = related.test_fk.create()
        self.assertEqual(related.test_fk.get(), relation)


@isolate_apps("managers_regress")
class TestManagerInheritance(SimpleTestCase):
    def test_implicit_inheritance(self):
        """

        Test the implicit inheritance of managers from parent models.

        This test case verifies that managers are correctly inherited from parent models
        in various scenarios, including abstract base classes, proxy models, and 
        multi-table inheritance (MTI) models. It checks that the base manager and 
        default manager are correctly set on the model and its subclasses.

        The test covers the following scenarios:
        - Models with custom managers
        - Models with abstract base classes
        - Proxy models
        - Models with multi-table inheritance

        """
        class CustomManager(models.Manager):
            pass

        class AbstractModel(models.Model):
            custom_manager = CustomManager()

            class Meta:
                abstract = True

        class PlainModel(models.Model):
            custom_manager = CustomManager()

        self.assertIsInstance(PlainModel._base_manager, models.Manager)
        self.assertIsInstance(PlainModel._default_manager, CustomManager)

        class ModelWithAbstractParent(AbstractModel):
            pass

        self.assertIsInstance(ModelWithAbstractParent._base_manager, models.Manager)
        self.assertIsInstance(ModelWithAbstractParent._default_manager, CustomManager)

        class ProxyModel(PlainModel):
            class Meta:
                proxy = True

        self.assertIsInstance(ProxyModel._base_manager, models.Manager)
        self.assertIsInstance(ProxyModel._default_manager, CustomManager)

        class MTIModel(PlainModel):
            pass

        self.assertIsInstance(MTIModel._base_manager, models.Manager)
        self.assertIsInstance(MTIModel._default_manager, CustomManager)

    def test_default_manager_inheritance(self):
        """
        Tests that default manager inheritance works as expected.

        Checks that the default manager is correctly set for models that inherit from
        abstract models or have a custom default manager specified. Verifies that
        models with abstract parents, proxy models, and models using multi-table
        inheritance (MTI) all inherit the default manager correctly.

        Ensures that the `_default_manager` attribute of the model is an instance of
        the expected manager class, in this case `CustomManager`, when the
        `default_manager_name` is specified in the model's Meta class or inherited
        from an abstract parent model.
        """
        class CustomManager(models.Manager):
            pass

        class AbstractModel(models.Model):
            another_manager = models.Manager()
            custom_manager = CustomManager()

            class Meta:
                default_manager_name = "custom_manager"
                abstract = True

        class PlainModel(models.Model):
            another_manager = models.Manager()
            custom_manager = CustomManager()

            class Meta:
                default_manager_name = "custom_manager"

        self.assertIsInstance(PlainModel._default_manager, CustomManager)

        class ModelWithAbstractParent(AbstractModel):
            pass

        self.assertIsInstance(ModelWithAbstractParent._default_manager, CustomManager)

        class ProxyModel(PlainModel):
            class Meta:
                proxy = True

        self.assertIsInstance(ProxyModel._default_manager, CustomManager)

        class MTIModel(PlainModel):
            pass

        self.assertIsInstance(MTIModel._default_manager, CustomManager)

    def test_base_manager_inheritance(self):
        """

        Tests the inheritance behavior of the base manager in Django models.

        This test case covers the scenario where a custom manager is defined as the base manager
        in an abstract model and its subclasses, including proxy models and models using multi-table inheritance.
        It verifies that the correct base manager class (CustomManager) is used in all cases.

        """
        class CustomManager(models.Manager):
            pass

        class AbstractModel(models.Model):
            another_manager = models.Manager()
            custom_manager = CustomManager()

            class Meta:
                base_manager_name = "custom_manager"
                abstract = True

        class PlainModel(models.Model):
            another_manager = models.Manager()
            custom_manager = CustomManager()

            class Meta:
                base_manager_name = "custom_manager"

        self.assertIsInstance(PlainModel._base_manager, CustomManager)

        class ModelWithAbstractParent(AbstractModel):
            pass

        self.assertIsInstance(ModelWithAbstractParent._base_manager, CustomManager)

        class ProxyModel(PlainModel):
            class Meta:
                proxy = True

        self.assertIsInstance(ProxyModel._base_manager, CustomManager)

        class MTIModel(PlainModel):
            pass

        self.assertIsInstance(MTIModel._base_manager, CustomManager)

    def test_manager_no_duplicates(self):
        """
        Tests that a model's manager does not duplicate when a custom manager with the same name as the default manager is defined, ensuring that the model's meta managers attribute and managers map are correctly set.
        """
        class CustomManager(models.Manager):
            pass

        class AbstractModel(models.Model):
            custom_manager = models.Manager()

            class Meta:
                abstract = True

        class TestModel(AbstractModel):
            custom_manager = CustomManager()

        self.assertEqual(TestModel._meta.managers, (TestModel.custom_manager,))
        self.assertEqual(
            TestModel._meta.managers_map, {"custom_manager": TestModel.custom_manager}
        )

    def test_manager_class_getitem(self):
        self.assertIs(models.Manager[Child1], models.Manager)
