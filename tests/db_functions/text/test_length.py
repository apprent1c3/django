from django.db.models import CharField
from django.db.models.functions import Length
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import Author


class LengthTests(TestCase):
    def test_basic(self):
        """
        Tests the basic functionality of annotating and querying Author objects.

        Verifies that authors can be created with or without an alias, and that queries
        can be made to retrieve authors ordered by name. Additionally, checks that the
        length of an author's name and alias can be annotated and used in filtering
        queries. The test also ensures that the filtering works correctly when
        comparing the length of the alias to the length of the name.

        The test covers the following scenarios:

        * Creating authors with and without an alias
        * Ordering authors by name
        * Annotating author objects with name and alias lengths
        * Filtering authors based on alias length compared to name length
        """
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="Rhonda")
        authors = Author.objects.annotate(
            name_length=Length("name"),
            alias_length=Length("alias"),
        )
        self.assertQuerySetEqual(
            authors.order_by("name"),
            [(10, 6), (6, None)],
            lambda a: (a.name_length, a.alias_length),
        )
        self.assertEqual(authors.filter(alias_length__lte=Length("name")).count(), 1)

    def test_ordering(self):
        """

        Tests the ordering of Author objects by the length of their name and alias.

        This function verifies that the Author objects are ordered first by the length of their name and then by the length of their alias.
        It creates several test authors with varying name and alias lengths, retrieves them in the specified order, and asserts that the result matches the expected ordering.

        The expected ordering is based on the length of the name and alias, with shorter names and aliases coming first.

        """
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="John Smith", alias="smithj1")
        Author.objects.create(name="Rhonda", alias="ronny")
        authors = Author.objects.order_by(Length("name"), Length("alias"))
        self.assertQuerySetEqual(
            authors,
            [
                ("Rhonda", "ronny"),
                ("John Smith", "smithj"),
                ("John Smith", "smithj1"),
            ],
            lambda a: (a.name, a.alias),
        )

    def test_transform(self):
        with register_lookup(CharField, Length):
            Author.objects.create(name="John Smith", alias="smithj")
            Author.objects.create(name="Rhonda")
            authors = Author.objects.filter(name__length__gt=7)
            self.assertQuerySetEqual(
                authors.order_by("name"), ["John Smith"], lambda a: a.name
            )
