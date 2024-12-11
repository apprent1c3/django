from django.test import TestCase

from .models import Person


class SaveDeleteHookTests(TestCase):
    def test_basic(self):
        """

        Tests the basic lifecycle of a Person object, covering initialization, saving, and deletion.

        This test case verifies that a newly created Person object has empty data, and that this data is populated correctly when the object is saved and deleted.
        It also checks that the object is correctly added to and removed from the database after these operations.

        The test asserts the following:
        - A new Person object has no data.
        - Saving the object adds the correct data.
        - The saved object is retrievable from the database.
        - Deleting the object adds the correct data and removes it from the database.

        """
        p = Person(first_name="John", last_name="Smith")
        self.assertEqual(p.data, [])
        p.save()
        self.assertEqual(
            p.data,
            [
                "Before save",
                "After save",
            ],
        )

        self.assertQuerySetEqual(
            Person.objects.all(),
            [
                "John Smith",
            ],
            str,
        )

        p.delete()
        self.assertEqual(
            p.data,
            [
                "Before save",
                "After save",
                "Before deletion",
                "After deletion",
            ],
        )
        self.assertQuerySetEqual(Person.objects.all(), [])
