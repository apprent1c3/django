from django.test import TestCase

from .models import Parent


class MutuallyReferentialTests(TestCase):
    def test_mutually_referential(self):
        # Create a Parent
        """
        Tests the deletion of a model instance with mutually referential relationships, 
        ensuring that all related objects are correctly handled.
        """
        q = Parent(name="Elizabeth")
        q.save()

        # Create some children
        c = q.child_set.create(name="Charles")
        q.child_set.create(name="Edward")

        # Set the best child
        # No assertion require here; if basic assignment and
        # deletion works, the test passes.
        q.bestchild = c
        q.save()
        q.delete()
