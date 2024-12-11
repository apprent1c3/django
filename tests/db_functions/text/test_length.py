from django.db.models import CharField
from django.db.models.functions import Length
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import Author


class LengthTests(TestCase):
    def test_basic(self):
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
        Test that the ordering of author instances is correct.

        This function ensures that authors are ordered first by the length of their name
        and then by the length of their alias. The expected ordering is from shortest to 
        longest, with authors having identical name lengths being sub-sorted by their 
        alias lengths. The test covers cases where authors share the same name but have 
        different aliases.
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
        """
        Attempts to test the transformation of a model field by applying a custom lookup to it, in this case, verifying that the Length lookup works correctly with CharField.

        This test creates two Author instances and then queries for authors whose names have a length greater than 7 characters. The expected result is that only the author 'John Smith' should be returned, demonstrating the successful application of the Length lookup.
        """
        with register_lookup(CharField, Length):
            Author.objects.create(name="John Smith", alias="smithj")
            Author.objects.create(name="Rhonda")
            authors = Author.objects.filter(name__length__gt=7)
            self.assertQuerySetEqual(
                authors.order_by("name"), ["John Smith"], lambda a: a.name
            )
