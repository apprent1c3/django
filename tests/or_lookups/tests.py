from datetime import datetime
from operator import attrgetter

from django.db.models import Q
from django.test import TestCase

from .models import Article


class OrLookupsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a1 = Article.objects.create(
            headline="Hello", pub_date=datetime(2005, 11, 27)
        ).pk
        cls.a2 = Article.objects.create(
            headline="Goodbye", pub_date=datetime(2005, 11, 28)
        ).pk
        cls.a3 = Article.objects.create(
            headline="Hello and goodbye", pub_date=datetime(2005, 11, 29)
        ).pk

    def test_filter_or(self):
        self.assertQuerySetEqual(
            (
                Article.objects.filter(headline__startswith="Hello")
                | Article.objects.filter(headline__startswith="Goodbye")
            ),
            ["Hello", "Goodbye", "Hello and goodbye"],
            attrgetter("headline"),
        )

        self.assertQuerySetEqual(
            Article.objects.filter(headline__contains="Hello")
            | Article.objects.filter(headline__contains="bye"),
            ["Hello", "Goodbye", "Hello and goodbye"],
            attrgetter("headline"),
        )

        self.assertQuerySetEqual(
            Article.objects.filter(headline__iexact="Hello")
            | Article.objects.filter(headline__contains="ood"),
            ["Hello", "Goodbye", "Hello and goodbye"],
            attrgetter("headline"),
        )

        self.assertQuerySetEqual(
            Article.objects.filter(
                Q(headline__startswith="Hello") | Q(headline__startswith="Goodbye")
            ),
            ["Hello", "Goodbye", "Hello and goodbye"],
            attrgetter("headline"),
        )

    def test_stages(self):
        # You can shorten this syntax with code like the following,  which is
        # especially useful if building the query in stages:
        articles = Article.objects.all()
        self.assertQuerySetEqual(
            articles.filter(headline__startswith="Hello")
            & articles.filter(headline__startswith="Goodbye"),
            [],
        )
        self.assertQuerySetEqual(
            articles.filter(headline__startswith="Hello")
            & articles.filter(headline__contains="bye"),
            ["Hello and goodbye"],
            attrgetter("headline"),
        )

    def test_pk_q(self):
        self.assertQuerySetEqual(
            Article.objects.filter(Q(pk=self.a1) | Q(pk=self.a2)),
            ["Hello", "Goodbye"],
            attrgetter("headline"),
        )

        self.assertQuerySetEqual(
            Article.objects.filter(Q(pk=self.a1) | Q(pk=self.a2) | Q(pk=self.a3)),
            ["Hello", "Goodbye", "Hello and goodbye"],
            attrgetter("headline"),
        )

    def test_pk_in(self):
        self.assertQuerySetEqual(
            Article.objects.filter(pk__in=[self.a1, self.a2, self.a3]),
            ["Hello", "Goodbye", "Hello and goodbye"],
            attrgetter("headline"),
        )

        self.assertQuerySetEqual(
            Article.objects.filter(pk__in=(self.a1, self.a2, self.a3)),
            ["Hello", "Goodbye", "Hello and goodbye"],
            attrgetter("headline"),
        )

        self.assertQuerySetEqual(
            Article.objects.filter(pk__in=[self.a1, self.a2, self.a3, 40000]),
            ["Hello", "Goodbye", "Hello and goodbye"],
            attrgetter("headline"),
        )

    def test_q_repr(self):
        or_expr = Q(baz=Article(headline="Foö"))
        self.assertEqual(repr(or_expr), "<Q: (AND: ('baz', <Article: Foö>))>")
        negated_or = ~Q(baz=Article(headline="Foö"))
        self.assertEqual(repr(negated_or), "<Q: (NOT (AND: ('baz', <Article: Foö>)))>")

    def test_q_negated(self):
        # Q objects can be negated
        """

        Tests how Django's Q objects handle negation when filtering Article objects.

        The function checks three scenarios:
        - Retrieving articles that match either a specific article or do not match another specific article.
        - Retrieving articles that do not match two specific articles.
        - Retrieving articles that match a specific article and either do not match another article or match a third article.

        These tests cover combinations of logical OR and AND operations, with and without negation, ensuring the correct application of Q objects in filtering Article querysets.

        """
        self.assertQuerySetEqual(
            Article.objects.filter(Q(pk=self.a1) | ~Q(pk=self.a2)),
            ["Hello", "Hello and goodbye"],
            attrgetter("headline"),
        )

        self.assertQuerySetEqual(
            Article.objects.filter(~Q(pk=self.a1) & ~Q(pk=self.a2)),
            ["Hello and goodbye"],
            attrgetter("headline"),
        )
        # This allows for more complex queries than filter() and exclude()
        # alone would allow
        self.assertQuerySetEqual(
            Article.objects.filter(Q(pk=self.a1) & (~Q(pk=self.a2) | Q(pk=self.a3))),
            ["Hello"],
            attrgetter("headline"),
        )

    def test_complex_filter(self):
        # The 'complex_filter' method supports framework features such as
        # 'limit_choices_to' which normally take a single dictionary of lookup
        # arguments but need to support arbitrary queries via Q objects too.
        """

        Tests the complex_filter method on a QuerySet of Article objects.

        The complex_filter method applies a given filter to the QuerySet and returns the filtered results.
        It accepts a dictionary or a django.db.models.Q object as the filter.

        This test case checks two scenarios:
        - Filtering by a single object's primary key
        - Filtering by a combination of two objects' primary keys using the 'or' operator.

        It verifies that the filtered results match the expected headlines.

        """
        self.assertQuerySetEqual(
            Article.objects.complex_filter({"pk": self.a1}),
            ["Hello"],
            attrgetter("headline"),
        )

        self.assertQuerySetEqual(
            Article.objects.complex_filter(Q(pk=self.a1) | Q(pk=self.a2)),
            ["Hello", "Goodbye"],
            attrgetter("headline"),
        )

    def test_empty_in(self):
        # Passing "in" an empty list returns no results ...
        self.assertQuerySetEqual(Article.objects.filter(pk__in=[]), [])
        # ... but can return results if we OR it with another query.
        self.assertQuerySetEqual(
            Article.objects.filter(Q(pk__in=[]) | Q(headline__icontains="goodbye")),
            ["Goodbye", "Hello and goodbye"],
            attrgetter("headline"),
        )

    def test_q_and(self):
        # Q arg objects are ANDed
        self.assertQuerySetEqual(
            Article.objects.filter(
                Q(headline__startswith="Hello"), Q(headline__contains="bye")
            ),
            ["Hello and goodbye"],
            attrgetter("headline"),
        )
        # Q arg AND order is irrelevant
        self.assertQuerySetEqual(
            Article.objects.filter(
                Q(headline__contains="bye"), headline__startswith="Hello"
            ),
            ["Hello and goodbye"],
            attrgetter("headline"),
        )

        self.assertQuerySetEqual(
            Article.objects.filter(
                Q(headline__startswith="Hello") & Q(headline__startswith="Goodbye")
            ),
            [],
        )

    def test_q_exclude(self):
        self.assertQuerySetEqual(
            Article.objects.exclude(Q(headline__startswith="Hello")),
            ["Goodbye"],
            attrgetter("headline"),
        )

    def test_other_arg_queries(self):
        # Try some arg queries with operations other than filter.
        self.assertEqual(
            Article.objects.get(
                Q(headline__startswith="Hello"), Q(headline__contains="bye")
            ).headline,
            "Hello and goodbye",
        )

        self.assertEqual(
            Article.objects.filter(
                Q(headline__startswith="Hello") | Q(headline__contains="bye")
            ).count(),
            3,
        )

        self.assertSequenceEqual(
            Article.objects.filter(
                Q(headline__startswith="Hello"), Q(headline__contains="bye")
            ).values(),
            [
                {
                    "headline": "Hello and goodbye",
                    "id": self.a3,
                    "pub_date": datetime(2005, 11, 29),
                },
            ],
        )

        self.assertEqual(
            Article.objects.filter(Q(headline__startswith="Hello")).in_bulk(
                [self.a1, self.a2]
            ),
            {self.a1: Article.objects.get(pk=self.a1)},
        )
