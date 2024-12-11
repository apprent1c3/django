from django.test import TestCase

from .models import Empty


class EmptyModelTests(TestCase):
    def test_empty(self):
        """
        Tests the creation and saving of an Empty object.

        Verifies that an Empty object is created without an ID, saves correctly, 
        and retrieves the correct ID after saving. Additionally, it checks 
        that multiple Empty objects can be created and saved, and that 
        retrieving an existing object by ID allows for subsequent saving.

        """
        m = Empty()
        self.assertIsNone(m.id)
        m.save()
        Empty.objects.create()
        self.assertEqual(len(Empty.objects.all()), 2)
        self.assertIsNotNone(m.id)
        existing = Empty(m.id)
        existing.save()
