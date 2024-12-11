from django.db.models import CharField, Value
from django.db.models.functions import Left, Ord
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import Author


class OrdTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class, creating a set of authors with predefined names and aliases, 
        enabling consistent testing across multiple test cases.

        :return: None
        """
        cls.john = Author.objects.create(name="John Smith", alias="smithj")
        cls.elena = Author.objects.create(name="Élena Jordan", alias="elena")
        cls.rhonda = Author.objects.create(name="Rhonda")

    def test_basic(self):
        """
        Tests the basic functionality of author name ordering.

        This test case checks if the authors are correctly ordered based on their names.
        It verifies that the authors with names greater than 'John' are filtered and excluded correctly.

        The test uses the Ord function to perform lexicographic ordering on the author names, 
        and then asserts that the filtered results match the expected output, 
        specifically that 'Elena' and 'Rhonda' have names greater than 'John', 
        and only 'John' has a name less than or equal to 'John'.
        """
        authors = Author.objects.annotate(name_part=Ord("name"))
        self.assertCountEqual(
            authors.filter(name_part__gt=Ord(Value("John"))), [self.elena, self.rhonda]
        )
        self.assertCountEqual(
            authors.exclude(name_part__gt=Ord(Value("John"))), [self.john]
        )

    def test_transform(self):
        """

        Tests the transformation of character fields to their corresponding ordinal values.

        This test case verifies that the transformation is applied correctly by filtering
        a queryset of authors based on the ordinal value of the first initial of their name.
        It checks that the expected authors are returned when filtering for a specific
        initial and when excluding authors with that initial.

        """
        with register_lookup(CharField, Ord):
            authors = Author.objects.annotate(first_initial=Left("name", 1))
            self.assertCountEqual(
                authors.filter(first_initial__ord=ord("J")), [self.john]
            )
            self.assertCountEqual(
                authors.exclude(first_initial__ord=ord("J")), [self.elena, self.rhonda]
            )
