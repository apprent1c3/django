from datetime import datetime, timedelta
from decimal import Decimal
from unittest import skipUnless

from django.db import connection
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce, Least
from django.test import TestCase, skipIfDBFeature, skipUnlessDBFeature
from django.utils import timezone

from ..models import Article, Author, DecimalModel, Fan


class LeastTests(TestCase):
    def test_basic(self):
        now = timezone.now()
        before = now - timedelta(hours=1)
        Article.objects.create(
            title="Testing with Django", written=before, published=now
        )
        articles = Article.objects.annotate(first_updated=Least("written", "published"))
        self.assertEqual(articles.first().first_updated, before)

    @skipUnlessDBFeature("greatest_least_ignores_nulls")
    def test_ignores_null(self):
        now = timezone.now()
        Article.objects.create(title="Testing with Django", written=now)
        articles = Article.objects.annotate(
            first_updated=Least("written", "published"),
        )
        self.assertEqual(articles.first().first_updated, now)

    @skipIfDBFeature("greatest_least_ignores_nulls")
    def test_propagates_null(self):
        Article.objects.create(title="Testing with Django", written=timezone.now())
        articles = Article.objects.annotate(first_updated=Least("written", "published"))
        self.assertIsNone(articles.first().first_updated)

    def test_coalesce_workaround(self):
        future = datetime(2100, 1, 1)
        now = timezone.now()
        Article.objects.create(title="Testing with Django", written=now)
        articles = Article.objects.annotate(
            last_updated=Least(
                Coalesce("written", future),
                Coalesce("published", future),
            ),
        )
        self.assertEqual(articles.first().last_updated, now)

    @skipUnless(connection.vendor == "mysql", "MySQL-specific workaround")
    def test_coalesce_workaround_mysql(self):
        """

        Tests a workaround for using the Coalesce function with MySQL to avoid incorrect date comparisons.

        The Coalesce function is used to provide a default value if a field is null. However, MySQL has limitations when
        comparing dates with Coalesce, which can lead to incorrect results. This test case creates a sample Article object
        and checks if the last_updated field is correctly set to the written date when the published date is null.

        The test uses a future date as a default value and verifies that the last_updated field is set to the written date,
        which is the expected behavior. This test is MySQL-specific and is skipped for other database vendors.

        """
        future = datetime(2100, 1, 1)
        now = timezone.now()
        Article.objects.create(title="Testing with Django", written=now)
        future_sql = RawSQL("cast(%s as datetime)", (future,))
        articles = Article.objects.annotate(
            last_updated=Least(
                Coalesce("written", future_sql),
                Coalesce("published", future_sql),
            ),
        )
        self.assertEqual(articles.first().last_updated, now)

    def test_all_null(self):
        """
        Tests that all articles have null 'first_updated' field when no 'published' or 'updated' dates are set.

        This test verifies the expected behavior of the 'first_updated' field in the Article model,
        which is annotated with the earliest of 'published' and 'updated' dates. 
        It checks that when neither 'published' nor 'updated' dates are provided for an article,
        the 'first_updated' field is correctly set to None.
        """
        Article.objects.create(title="Testing with Django", written=timezone.now())
        articles = Article.objects.annotate(first_updated=Least("published", "updated"))
        self.assertIsNone(articles.first().first_updated)

    def test_one_expressions(self):
        with self.assertRaisesMessage(
            ValueError, "Least must take at least two expressions"
        ):
            Least("written")

    def test_related_field(self):
        author = Author.objects.create(name="John Smith", age=45)
        Fan.objects.create(name="Margaret", age=50, author=author)
        authors = Author.objects.annotate(lowest_age=Least("age", "fans__age"))
        self.assertEqual(authors.first().lowest_age, 45)

    def test_update(self):
        author = Author.objects.create(name="James Smith", goes_by="Jim")
        Author.objects.update(alias=Least("name", "goes_by"))
        author.refresh_from_db()
        self.assertEqual(author.alias, "James Smith")

    def test_decimal_filter(self):
        obj = DecimalModel.objects.create(n1=Decimal("1.1"), n2=Decimal("1.2"))
        self.assertCountEqual(
            DecimalModel.objects.annotate(
                least=Least("n1", "n2"),
            ).filter(least=Decimal("1.1")),
            [obj],
        )
