from django.db.models import CharField, Value
from django.db.models.functions import Left, Ord
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import Author


class OrdTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class, creating a set of predefined authors for use in tests.

            This method populates the test environment with a selection of authors, including 'John Smith', 'Élena Jordan', and 'Rhonda'.
            Each author is created with a name and, where applicable, an alias. These authors can be accessed as class attributes for use in subsequent tests.

            Attributes:
                john (Author): An author instance with name 'John Smith' and alias 'smithj'.
                elena (Author): An author instance with name 'Élena Jordan' and alias 'elena'.
                rhonda (Author): An author instance with name 'Rhonda' and no alias.

        """
        cls.john = Author.objects.create(name="John Smith", alias="smithj")
        cls.elena = Author.objects.create(name="Élena Jordan", alias="elena")
        cls.rhonda = Author.objects.create(name="Rhonda")

    def test_basic(self):
        authors = Author.objects.annotate(name_part=Ord("name"))
        self.assertCountEqual(
            authors.filter(name_part__gt=Ord(Value("John"))), [self.elena, self.rhonda]
        )
        self.assertCountEqual(
            authors.exclude(name_part__gt=Ord(Value("John"))), [self.john]
        )

    def test_transform(self):
        with register_lookup(CharField, Ord):
            authors = Author.objects.annotate(first_initial=Left("name", 1))
            self.assertCountEqual(
                authors.filter(first_initial__ord=ord("J")), [self.john]
            )
            self.assertCountEqual(
                authors.exclude(first_initial__ord=ord("J")), [self.elena, self.rhonda]
            )
