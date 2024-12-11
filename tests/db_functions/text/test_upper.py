from django.db.models import CharField
from django.db.models.functions import Upper
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import Author


class UpperTests(TestCase):
    def test_basic(self):
        """
        Tests basic annotation functionality for author names.

        This test case verifies that author names can be annotated with their uppercase equivalents
        and that these annotated values can be used for ordering and comparison.
        It also ensures that updating the author names to their uppercase equivalents results in the
        expected outcome, demonstrating the success of both annotation and subsequent data modification.

        """
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="Rhonda")
        authors = Author.objects.annotate(upper_name=Upper("name"))
        self.assertQuerySetEqual(
            authors.order_by("name"),
            [
                "JOHN SMITH",
                "RHONDA",
            ],
            lambda a: a.upper_name,
        )
        Author.objects.update(name=Upper("name"))
        self.assertQuerySetEqual(
            authors.order_by("name"),
            [
                ("JOHN SMITH", "JOHN SMITH"),
                ("RHONDA", "RHONDA"),
            ],
            lambda a: (a.upper_name, a.name),
        )

    def test_transform(self):
        """

        Test the transformation of model fields to upper case.

        This test verifies that the Upper lookup is correctly applied to model fields.
        It creates instances of the Author model, then queries the database using the __upper__exact lookup.
        The test asserts that the query correctly filters the results based on the upper case field values.

        The purpose of this test is to ensure that the transformation functionality works as expected,
        allowing for case-insensitive queries to be performed on model fields.

        """
        with register_lookup(CharField, Upper):
            Author.objects.create(name="John Smith", alias="smithj")
            Author.objects.create(name="Rhonda")
            authors = Author.objects.filter(name__upper__exact="JOHN SMITH")
            self.assertQuerySetEqual(
                authors.order_by("name"),
                [
                    "John Smith",
                ],
                lambda a: a.name,
            )
