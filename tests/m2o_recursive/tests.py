from django.test import TestCase

from .models import Category, Person


class ManyToOneRecursiveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for category-related tests, creating a root category and a child category for use in subsequent tests.
        """
        cls.r = Category.objects.create(id=None, name="Root category", parent=None)
        cls.c = Category.objects.create(id=None, name="Child category", parent=cls.r)

    def test_m2o_recursive(self):
        """
        Tests the recursive relationship between parent and child objects in a many-to-one (m2o) scenario.

        Verifies that a parent object can correctly retrieve its child objects, and that a child object can 
        retrieve its parent. Also checks that a child object does not have any children of its own in this 
        recursive relationship, thus ensuring a correct hierarchical structure.

        Specifically, this test case confirms the following:

        * A parent object can fetch all its child objects.
        * A parent object can fetch a specific child object by a given condition.
        * A parent object does not have a parent of its own.
        * A child object does not have any child objects in this recursive relationship.
        * A child object can correctly identify its parent object.

        """
        self.assertSequenceEqual(self.r.child_set.all(), [self.c])
        self.assertEqual(self.r.child_set.get(name__startswith="Child").id, self.c.id)
        self.assertIsNone(self.r.parent)
        self.assertSequenceEqual(self.c.child_set.all(), [])
        self.assertEqual(self.c.parent.id, self.r.id)


class MultipleManyToOneRecursiveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the class, creating a simple family structure for testing purposes.

        This method creates three :class:`Person` instances: a father, a mother, and their child.
        The father and mother have no parents, while the child has both parents assigned.
        These instances are stored as class attributes for use in subsequent tests.

        """
        cls.dad = Person.objects.create(
            full_name="John Smith Senior", mother=None, father=None
        )
        cls.mom = Person.objects.create(
            full_name="Jane Smith", mother=None, father=None
        )
        cls.kid = Person.objects.create(
            full_name="John Smith Junior", mother=cls.mom, father=cls.dad
        )

    def test_m2o_recursive2(self):
        self.assertEqual(self.kid.mother.id, self.mom.id)
        self.assertEqual(self.kid.father.id, self.dad.id)
        self.assertSequenceEqual(self.dad.fathers_child_set.all(), [self.kid])
        self.assertSequenceEqual(self.mom.mothers_child_set.all(), [self.kid])
        self.assertSequenceEqual(self.kid.mothers_child_set.all(), [])
        self.assertSequenceEqual(self.kid.fathers_child_set.all(), [])
