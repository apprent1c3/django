from django.db import DatabaseError, IntegrityError, models, transaction
from django.test import TestCase

from .models import (
    Counter,
    DiamondSubSubCounter,
    InheritedCounter,
    OtherSubCounter,
    ProxyCounter,
    SubCounter,
    SubSubCounter,
    WithCustomPK,
)


class ForceTests(TestCase):
    def test_force_update(self):
        """
        Tests the forced update behavior of the model's save method.

        Checks that:
            * A model instance can be updated using the save method with force_update.
            * Saving with both force_insert and force_update raises an error.
            * Forcing an update on an unsaved instance (without primary key) raises an error.
            * Forcing an insert on an instance with primary key raises an integrity error.
            * Forcing an update on an unsaved custom primary key model instance raises a database error.
        """
        c = Counter.objects.create(name="one", value=1)

        # The normal case
        c.value = 2
        c.save()
        # Same thing, via an update
        c.value = 3
        c.save(force_update=True)

        # Won't work because force_update and force_insert are mutually
        # exclusive
        c.value = 4
        msg = "Cannot force both insert and updating in model saving."
        with self.assertRaisesMessage(ValueError, msg):
            c.save(force_insert=True, force_update=True)

        # Try to update something that doesn't have a primary key in the first
        # place.
        c1 = Counter(name="two", value=2)
        msg = "Cannot force an update in save() with no primary key."
        with self.assertRaisesMessage(ValueError, msg):
            with transaction.atomic():
                c1.save(force_update=True)
        c1.save(force_insert=True)

        # Won't work because we can't insert a pk of the same value.
        c.value = 5
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                c.save(force_insert=True)

        # Trying to update should still fail, even with manual primary keys, if
        # the data isn't in the database already.
        obj = WithCustomPK(name=1, value=1)
        msg = "Forced update did not affect any rows."
        with self.assertRaisesMessage(DatabaseError, msg):
            with transaction.atomic():
                obj.save(force_update=True)


class InheritanceTests(TestCase):
    def test_force_update_on_inherited_model(self):
        a = InheritedCounter(name="count", value=1, tag="spam")
        a.save()
        a.save(force_update=True)

    def test_force_update_on_proxy_model(self):
        a = ProxyCounter(name="count", value=1)
        a.save()
        a.save(force_update=True)

    def test_force_update_on_inherited_model_without_fields(self):
        """
        Issue 13864: force_update fails on subclassed models, if they don't
        specify custom fields.
        """
        a = SubCounter(name="count", value=1)
        a.save()
        a.value = 2
        a.save(force_update=True)


class ForceInsertInheritanceTests(TestCase):
    def test_force_insert_not_bool_or_tuple(self):
        """

         Tests that the force_insert argument of the save method raises a TypeError when its value is not a boolean or a tuple, 
         ensuring that only valid input is accepted. This helps prevent unexpected behavior 
         by enforcing strict type checking for this parameter.

        """
        msg = "force_insert must be a bool or tuple."
        with self.assertRaisesMessage(TypeError, msg), transaction.atomic():
            Counter().save(force_insert=1)
        with self.assertRaisesMessage(TypeError, msg), transaction.atomic():
            Counter().save(force_insert="test")
        with self.assertRaisesMessage(TypeError, msg), transaction.atomic():
            Counter().save(force_insert=[])

    def test_force_insert_not_model(self):
        """
        Tests the save method of a model when the force_insert parameter contains an invalid value.

        Ensures that a TypeError is raised when the force_insert parameter contains an object
        that is not a model subclass. This can occur when a general object or an instance of a model
        is passed to the force_insert parameter, helping to prevent potential data inconsistencies.

        The test scenarios verify that the error message includes information about the invalid
        object that was provided, allowing for easier identification and correction of the issue.

        This test covers two main scenarios:

        * Passing a general object to the force_insert parameter
        * Passing an instance of a model to the force_insert parameter

        In both cases, the test validates that a TypeError is raised with a descriptive error message.
        """
        msg = f"Invalid force_insert member. {object!r} must be a model subclass."
        with self.assertRaisesMessage(TypeError, msg), transaction.atomic():
            Counter().save(force_insert=(object,))
        instance = Counter()
        msg = f"Invalid force_insert member. {instance!r} must be a model subclass."
        with self.assertRaisesMessage(TypeError, msg), transaction.atomic():
            Counter().save(force_insert=(instance,))

    def test_force_insert_not_base(self):
        """
        Tests that attempting to force insert a non-base Counter model raises a TypeError. 
        Checks that the error message correctly indicates that the provided model (SubCounter) must be a base of the Counter model.
        """
        msg = "Invalid force_insert member. SubCounter must be a base of Counter."
        with self.assertRaisesMessage(TypeError, msg):
            Counter().save(force_insert=(SubCounter,))

    def test_force_insert_false(self):
        """
        Tests the behavior of the save method when `force_insert=False` to ensure that the object is updated instead of inserted as a new record.

        Checks that when an object with the same primary key exists in the database, the save method updates the existing object instead of creating a new one. This test case verifies that the `value` attribute of the object is updated correctly in the database.

        The test also checks the number of database queries executed during the save operations to ensure that the expected queries are performed. The test validates the behavior for different `force_insert` values to ensure correctness in various scenarios.
        """
        with self.assertNumQueries(3):
            obj = SubCounter.objects.create(pk=1, value=0)
        with self.assertNumQueries(2):
            SubCounter(pk=obj.pk, value=1).save()
        obj.refresh_from_db()
        self.assertEqual(obj.value, 1)
        with self.assertNumQueries(2):
            SubCounter(pk=obj.pk, value=2).save(force_insert=False)
        obj.refresh_from_db()
        self.assertEqual(obj.value, 2)
        with self.assertNumQueries(2):
            SubCounter(pk=obj.pk, value=3).save(force_insert=())
        obj.refresh_from_db()
        self.assertEqual(obj.value, 3)

    def test_force_insert_false_with_existing_parent(self):
        """
        Tests the behavior of creating a SubCounter object when force_insert is False and the parent object already exists.

        This test case verifies that the creation of a SubCounter object succeeds without raising any exceptions and that the number of database queries is as expected.

        It ensures that the SubCounter object is correctly created with the provided parent object, which already exists in the database, by checking the number of queries executed during the creation process.

        The test provides assurance that the SubCounter object can be created without attempting to re-insert the existing parent object, thus preventing any potential errors or inconsistencies in the database. 
        """
        parent = Counter.objects.create(pk=1, value=1)
        with self.assertNumQueries(2):
            SubCounter.objects.create(pk=parent.pk, value=2)

    def test_force_insert_parent(self):
        """

        Tests the forced insertion of a parent model when saving a SubCounter instance.

        This test case verifies that the correct number of database queries are executed
        when the force_insert parameter is used to specify the parent model. It checks
        three scenarios: forcing insertion without specifying a parent model, forcing
        insertion with a specific parent model (Counter), and forcing insertion with a
        base parent model (models.Model).

        """
        with self.assertNumQueries(3):
            SubCounter(pk=1, value=1).save(force_insert=True)
        # Force insert a new parent and don't UPDATE first.
        with self.assertNumQueries(2):
            SubCounter(pk=2, value=1).save(force_insert=(Counter,))
        with self.assertNumQueries(2):
            SubCounter(pk=3, value=1).save(force_insert=(models.Model,))

    def test_force_insert_with_grandparent(self):
        """

        Tests the behavior of the force_insert parameter when saving a model instance.

        This test case covers different scenarios where force_insert is set to True or a tuple of related models.
        It verifies the expected number of database queries are executed in each case, ensuring that the force_insert mechanism behaves as expected.

        The test specifically examines the impact of force_insert on the save operation of a SubSubCounter model instance,
        considering its relationships with parent models, including Counter and SubCounter.

        """
        with self.assertNumQueries(4):
            SubSubCounter(pk=1, value=1).save(force_insert=True)
        # Force insert parents on all levels and don't UPDATE first.
        with self.assertNumQueries(3):
            SubSubCounter(pk=2, value=1).save(force_insert=(models.Model,))
        with self.assertNumQueries(3):
            SubSubCounter(pk=3, value=1).save(force_insert=(Counter,))
        # Force insert only the last parent.
        with self.assertNumQueries(4):
            SubSubCounter(pk=4, value=1).save(force_insert=(SubCounter,))

    def test_force_insert_with_existing_grandparent(self):
        # Force insert only the last child.
        grandparent = Counter.objects.create(pk=1, value=1)
        with self.assertNumQueries(4):
            SubSubCounter(pk=grandparent.pk, value=1).save(force_insert=True)
        # Force insert a parent, and don't force insert a grandparent.
        grandparent = Counter.objects.create(pk=2, value=1)
        with self.assertNumQueries(3):
            SubSubCounter(pk=grandparent.pk, value=1).save(force_insert=(SubCounter,))
        # Force insert parents on all levels, grandparent conflicts.
        grandparent = Counter.objects.create(pk=3, value=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SubSubCounter(pk=grandparent.pk, value=1).save(force_insert=(Counter,))

    def test_force_insert_diamond_mti(self):
        # Force insert all parents.
        """

        Tests the forced insertion of a DiamondSubSubCounter model instance.

        This test case verifies the correct behavior of the save method when force_insert is used with different model classes.
        It checks the number of database queries executed and ensures that the forced insertion works as expected in various scenarios,
        including when the model has existing related objects and when the force_insert argument includes different model classes.

        The test covers different use cases, such as:
        - Forcing insertion with specific related models (Counter, SubCounter, OtherSubCounter)
        - Forcing insertion with the base model class (models.Model)
        - Forcing insertion when a related object already exists
        - Attempting to force insertion with an existing related object, which should raise an IntegrityError

        """
        with self.assertNumQueries(4):
            DiamondSubSubCounter(pk=1, value=1).save(
                force_insert=(Counter, SubCounter, OtherSubCounter)
            )
        with self.assertNumQueries(4):
            DiamondSubSubCounter(pk=2, value=1).save(force_insert=(models.Model,))
        # Force insert parents, and don't force insert a common grandparent.
        with self.assertNumQueries(5):
            DiamondSubSubCounter(pk=3, value=1).save(
                force_insert=(SubCounter, OtherSubCounter)
            )
        grandparent = Counter.objects.create(pk=4, value=1)
        with self.assertNumQueries(4):
            DiamondSubSubCounter(pk=grandparent.pk, value=1).save(
                force_insert=(SubCounter, OtherSubCounter),
            )
        # Force insert all parents, grandparent conflicts.
        grandparent = Counter.objects.create(pk=5, value=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DiamondSubSubCounter(pk=grandparent.pk, value=1).save(
                force_insert=(models.Model,)
            )
