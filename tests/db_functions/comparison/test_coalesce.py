from django.db.models import Subquery, TextField
from django.db.models.functions import Coalesce, Lower
from django.test import TestCase
from django.utils import timezone

from ..models import Article, Author

lorem_ipsum = """
    Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod
    tempor incididunt ut labore et dolore magna aliqua."""


class CoalesceTests(TestCase):
    def test_basic(self):
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="Rhonda")
        authors = Author.objects.annotate(display_name=Coalesce("alias", "name"))
        self.assertQuerySetEqual(
            authors.order_by("name"), ["smithj", "Rhonda"], lambda a: a.display_name
        )

    def test_gt_two_expressions(self):
        with self.assertRaisesMessage(
            ValueError, "Coalesce must take at least two expressions"
        ):
            Author.objects.annotate(display_name=Coalesce("alias"))

    def test_mixed_values(self):
        """
        Tests the Coalesce database function with mixed values in Articles, 
        ensuring it correctly selects a non-null value for the headline annotation.
        """
        a1 = Author.objects.create(name="John Smith", alias="smithj")
        a2 = Author.objects.create(name="Rhonda")
        ar1 = Article.objects.create(
            title="How to Django",
            text=lorem_ipsum,
            written=timezone.now(),
        )
        ar1.authors.add(a1)
        ar1.authors.add(a2)
        # mixed Text and Char
        article = Article.objects.annotate(
            headline=Coalesce("summary", "text", output_field=TextField()),
        )
        self.assertQuerySetEqual(
            article.order_by("title"), [lorem_ipsum], lambda a: a.headline
        )
        # mixed Text and Char wrapped
        article = Article.objects.annotate(
            headline=Coalesce(
                Lower("summary"), Lower("text"), output_field=TextField()
            ),
        )
        self.assertQuerySetEqual(
            article.order_by("title"), [lorem_ipsum.lower()], lambda a: a.headline
        )

    def test_ordering(self):
        """

        Tests the ordering of authors using Coalesce function, ensuring that authors are ordered correctly 
        when either alias or name is used as the ordering criteria, supporting both ascending and descending order.

        """
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="Rhonda")
        authors = Author.objects.order_by(Coalesce("alias", "name"))
        self.assertQuerySetEqual(authors, ["Rhonda", "John Smith"], lambda a: a.name)
        authors = Author.objects.order_by(Coalesce("alias", "name").asc())
        self.assertQuerySetEqual(authors, ["Rhonda", "John Smith"], lambda a: a.name)
        authors = Author.objects.order_by(Coalesce("alias", "name").desc())
        self.assertQuerySetEqual(authors, ["John Smith", "Rhonda"], lambda a: a.name)

    def test_empty_queryset(self):
        """
        Tests that an annotation using an empty queryset will return a default value.

        This test case ensures that the Coalesce function behaves as expected when the subquery is empty, returning the specified default value instead of raising an error.
        """
        Author.objects.create(name="John Smith")
        queryset = Author.objects.values("id")
        tests = [
            (queryset.none(), "QuerySet.none()"),
            (queryset.filter(id=0), "QuerySet.filter(id=0)"),
            (Subquery(queryset.none()), "Subquery(QuerySet.none())"),
            (Subquery(queryset.filter(id=0)), "Subquery(Queryset.filter(id=0)"),
        ]
        for empty_query, description in tests:
            with self.subTest(description), self.assertNumQueries(1):
                qs = Author.objects.annotate(annotation=Coalesce(empty_query, 42))
                self.assertEqual(qs.first().annotation, 42)
