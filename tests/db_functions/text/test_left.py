from django.db.models import IntegerField, Value
from django.db.models.functions import Left, Lower
from django.test import TestCase

from ..models import Author


class LeftTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="Rhonda")

    def test_basic(self):
        """

        Tests the basic functionality of author data manipulation.

        This test case checks the ability to annotate and order author objects based on partial names.
        It also verifies the correct updating of author aliases for names without an existing alias.

        The test performs the following checks:
        - Annotates authors with the first 5 characters of their name.
        - Orders authors by their full name and verifies the correctness of the annotated partial names.
        - Updates the aliases of authors without an existing alias to the first 2 characters of their name in lowercase.
        - Reorders authors by their full name and verifies the correctness of the updated aliases.

        """
        authors = Author.objects.annotate(name_part=Left("name", 5))
        self.assertQuerySetEqual(
            authors.order_by("name"), ["John ", "Rhond"], lambda a: a.name_part
        )
        # If alias is null, set it to the first 2 lower characters of the name.
        Author.objects.filter(alias__isnull=True).update(alias=Lower(Left("name", 2)))
        self.assertQuerySetEqual(
            authors.order_by("name"), ["smithj", "rh"], lambda a: a.alias
        )

    def test_invalid_length(self):
        with self.assertRaisesMessage(ValueError, "'length' must be greater than 0"):
            Author.objects.annotate(raises=Left("name", 0))

    def test_expressions(self):
        authors = Author.objects.annotate(
            name_part=Left("name", Value(3, output_field=IntegerField()))
        )
        self.assertQuerySetEqual(
            authors.order_by("name"), ["Joh", "Rho"], lambda a: a.name_part
        )
