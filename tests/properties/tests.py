from django.test import TestCase

from .models import Person


class PropertyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Person.objects.create(first_name="John", last_name="Lennon")

    def test_getter(self):
        self.assertEqual(self.a.full_name, "John Lennon")

    def test_setter(self):
        # The "full_name" property hasn't provided a "set" method.
        """

        Tests the functionality of property setter methods for the Person class.

        Verifies that attempting to set the 'full_name' attribute directly raises an AttributeError,
        both when using setattr on an existing instance and when passing the attribute as a keyword argument
        to the class constructor.

        Additionally, tests that setting the 'full_name_2' attribute and then saving the instance
        correctly populates the 'first_name' attribute.

        """
        with self.assertRaises(AttributeError):
            setattr(self.a, "full_name", "Paul McCartney")

        # And cannot be used to initialize the class.
        with self.assertRaises(AttributeError):
            Person(full_name="Paul McCartney")

        # But "full_name_2" has, and it can be used to initialize the class.
        a2 = Person(full_name_2="Paul McCartney")
        a2.save()
        self.assertEqual(a2.first_name, "Paul")
