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

        Tests the transformation of a bilateral lookup with multiple values on a Character Field.

        This function checks the functionality of the UpperBilateral lookup type by performing a
        case-insensitive filter on a set of authors. It verifies that the lookup correctly
        matches authors with names that match the filter values, regardless of case.

        The test covers the following scenarios:

        * Creating authors with and without aliases
        * Performing a case-insensitive filter on the authors by name
        * Verifying the correctness of the filtered results, ordered by name

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
        """
        Tests the functionality of filtering Author objects based on the alias field.

        The test case verifies that the filter function correctly returns Author objects
        where the alias matches the given value (case-insensitive), and also checks the
        exclude function to ensure it returns the expected authors that do not match.

        Specifically, this test covers the use of the Upper function in conjunction with
        database functions, to compare the alias field in a case-insensitive manner.

        The test creates two Author objects, one with an alias and one without, and then
        applies the filter and exclude operations to verify the results match the expected
        output.
        """
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
