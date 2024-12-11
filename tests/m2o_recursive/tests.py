from django.test import TestCase

from .models import Category, Person


class ManyToOneRecursiveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.r = Category.objects.create(id=None, name="Root category", parent=None)
        cls.c = Category.objects.create(id=None, name="Child category", parent=cls.r)

    def test_m2o_recursive(self):
        self.assertSequenceEqual(self.r.child_set.all(), [self.c])
        self.assertEqual(self.r.child_set.get(name__startswith="Child").id, self.c.id)
        self.assertIsNone(self.r.parent)
        self.assertSequenceEqual(self.c.child_set.all(), [])
        self.assertEqual(self.c.parent.id, self.r.id)


class MultipleManyToOneRecursiveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
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
        """

        Tests the many-to-one (m2o) recursive relationships between family members.

        This test case verifies that the relationships between a child, their mother, and their father are correctly established.
        It checks that the child's mother and father are correctly assigned, and that the parents' child sets contain the expected child.
        Additionally, it ensures that the child's own child sets for mothers and fathers are empty, as expected in a many-to-one recursive relationship.

        """
        self.assertEqual(self.kid.mother.id, self.mom.id)
        self.assertEqual(self.kid.father.id, self.dad.id)
        self.assertSequenceEqual(self.dad.fathers_child_set.all(), [self.kid])
        self.assertSequenceEqual(self.mom.mothers_child_set.all(), [self.kid])
        self.assertSequenceEqual(self.kid.mothers_child_set.all(), [])
        self.assertSequenceEqual(self.kid.fathers_child_set.all(), [])
