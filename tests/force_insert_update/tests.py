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
        """

        Tests if the force_update parameter updates a saved ProxyCounter model instance.

        This test case checks the behavior of the save method with force_update set to True
        on a ProxyCounter object that has already been saved to the database. It verifies
        that the object is updated correctly and any changes are persisted.

        :param None:
        :returns: None

        """
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
        ``` 
        Checks that the force_insert parameter of the save method must be either a boolean value or a tuple, and raises a TypeError otherwise.

        The test ensures that passing invalid force_insert values, such as integers, strings, or empty lists, results in a TypeError with a descriptive error message.
        ```
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
        Tests that the force_insert argument in the save method of a model instance raises a TypeError when not provided with a model subclass.

        This test ensures that the save method correctly validates the force_insert parameter to prevent incorrect usage. It checks two scenarios: 
        - when a non-model object is provided as part of the force_insert parameter, and 
        - when an instance of a model is provided as part of the force_insert parameter. 

        The test expects a TypeError to be raised with a specific error message in both cases, verifying that the save method handles invalid input correctly.
        """
        msg = f"Invalid force_insert member. {object!r} must be a model subclass."
        with self.assertRaisesMessage(TypeError, msg), transaction.atomic():
            Counter().save(force_insert=(object,))
        instance = Counter()
        msg = f"Invalid force_insert member. {instance!r} must be a model subclass."
        with self.assertRaisesMessage(TypeError, msg), transaction.atomic():
            Counter().save(force_insert=(instance,))

    def test_force_insert_not_base(self):
        msg = "Invalid force_insert member. SubCounter must be a base of Counter."
        with self.assertRaisesMessage(TypeError, msg):
            Counter().save(force_insert=(SubCounter,))

    def test_force_insert_false(self):
        """

        Tests that the model instance can be updated instead of inserted when force_insert is set to False.

        This test case verifies that when a model instance with an existing primary key is saved,
        it updates the existing record in the database instead of attempting to insert a new one.
        The test checks the number of database queries executed during the save operation and
        validates that the updated values are persisted correctly.

        The test covers different scenarios, including saving an object with an existing primary key,
        and saving an object with force_insert set to False. It ensures that the model instance is
        updated correctly in each case, and that the expected number of database queries is executed.

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

        Test that creating a new instance of SubCounter with an existing parent does not trigger a recursive creation of the parent.

        This test case verifies that when force_insert is set to False, the existing parent instance is reused instead of attempting to create a new one.

        """
        parent = Counter.objects.create(pk=1, value=1)
        with self.assertNumQueries(2):
            SubCounter.objects.create(pk=parent.pk, value=2)

    def test_force_insert_parent(self):
        with self.assertNumQueries(3):
            SubCounter(pk=1, value=1).save(force_insert=True)
        # Force insert a new parent and don't UPDATE first.
        with self.assertNumQueries(2):
            SubCounter(pk=2, value=1).save(force_insert=(Counter,))
        with self.assertNumQueries(2):
            SubCounter(pk=3, value=1).save(force_insert=(models.Model,))

    def test_force_insert_with_grandparent(self):
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
