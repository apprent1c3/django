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
        """
        :param self: Test case instance
        :raises AssertionError: If the test fails
        :test: This test checks the functionality of the LEAST function in Django's ORM 
               when one of the fields is null, ensuring it ignores the null value and returns the other value.
        """
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
        Tests a workaround for a MySQL-specific issue with the Coalesce function.

        This test case verifies that the least of two dates, 'written' and 'published', 
        is correctly determined when using the Coalesce function in conjunction with 
        Django's ORM on a MySQL database. 

        It creates an Article instance with a 'written' date and no 'published' date, 
        then annotates the instance with the least of the 'written' and 'published' 
        dates, defaulting to a future date if either is null.

        The test passes if the annotated 'last_updated' date matches the 'written' date. 
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
        Tests the scenario where both published and updated dates are null.

        Verifies that when an Article instance is created without published and updated dates,
        the `first_updated` attribute, which represents the earliest of these two dates,
        is correctly identified as None.

        This test ensures that the `Least` annotation function behaves as expected
        when dealing with null values, providing a robust check for this edge case.

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
