from django.db.models import CharField
from django.db.models import Value as V
from django.db.models.functions import Coalesce, Length, Upper
from django.test import TestCase
from django.test.utils import register_lookup

from .models import Author


class UpperBilateral(Upper):
    bilateral = True


class FunctionTests(TestCase):
    def test_nested_function_ordering(self):
        """
        Tests the ordering of authors by the length of their alias or name, 
        checking both ascending and descending order for correct results.
        """
        Author.objects.create(name="John Smith")
        Author.objects.create(name="Rhonda Simpson", alias="ronny")

        authors = Author.objects.order_by(Length(Coalesce("alias", "name")))
        self.assertQuerySetEqual(
            authors,
            [
                "Rhonda Simpson",
                "John Smith",
            ],
            lambda a: a.name,
        )

        authors = Author.objects.order_by(Length(Coalesce("alias", "name")).desc())
        self.assertQuerySetEqual(
            authors,
            [
                "John Smith",
                "Rhonda Simpson",
            ],
            lambda a: a.name,
        )

    def test_func_transform_bilateral(self):
        """
        Tests the transformation of query lookups on CharField using UpperBilateral, ensuring case-insensitive matching.
        """
        with register_lookup(CharField, UpperBilateral):
            Author.objects.create(name="John Smith", alias="smithj")
            Author.objects.create(name="Rhonda")
            authors = Author.objects.filter(name__upper__exact="john smith")
            self.assertQuerySetEqual(
                authors.order_by("name"),
                [
                    "John Smith",
                ],
                lambda a: a.name,
            )

    def test_func_transform_bilateral_multivalue(self):
        """
        Tests the transformation of bilateral lookups with multivalue fields in a Django model, ensuring that filtering by uppercase equivalent works as expected.
        """
        with register_lookup(CharField, UpperBilateral):
            Author.objects.create(name="John Smith", alias="smithj")
            Author.objects.create(name="Rhonda")
            authors = Author.objects.filter(name__upper__in=["john smith", "rhonda"])
            self.assertQuerySetEqual(
                authors.order_by("name"),
                [
                    "John Smith",
                    "Rhonda",
                ],
                lambda a: a.name,
            )

    def test_function_as_filter(self):
        Author.objects.create(name="John Smith", alias="SMITHJ")
        Author.objects.create(name="Rhonda")
        self.assertQuerySetEqual(
            Author.objects.filter(alias=Upper(V("smithj"))),
            ["John Smith"],
            lambda x: x.name,
        )
        self.assertQuerySetEqual(
            Author.objects.exclude(alias=Upper(V("smithj"))),
            ["Rhonda"],
            lambda x: x.name,
        )
