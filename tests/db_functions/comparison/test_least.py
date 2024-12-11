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
        """

        Tests the basic functionality of annotating articles with their first updated timestamp.

        This test ensures that the first updated timestamp of an article is correctly
        determined as the least of its written and published dates. It creates an article
        with a written date prior to its published date, annotates the article with its
        first updated timestamp, and then verifies that the annotated timestamp matches
        the expected value.


        """
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
        Tests that the Least aggregate function ignores NULL values when determining the minimum value.

        This test case creates an Article object with a written time and then uses the Least function to
        annotate the Article objects with the earliest of the 'written' and 'published' times. It then
        asserts that the earliest time for the created Article is the 'written' time, as the 'published'
        time is NULL.

        This test requires a database feature where the greatest and least functions ignore NULL values.
        """
        now = timezone.now()
        Article.objects.create(title="Testing with Django", written=now)
        articles = Article.objects.annotate(
            first_updated=Least("written", "published"),
        )
        self.assertEqual(articles.first().first_updated, now)

    @skipIfDBFeature("greatest_least_ignores_nulls")
    def test_propagates_null(self):
        """

        Tests that the Least database function propagates null when one of the input fields is null.

        This test case ensures that when using the Least function to annotate a queryset,
        the resulting annotation is null if either of the input fields is null.
        It verifies this behavior by creating an article with a written date but no published date,
        then using the Least function to annotate the queryset with the earliest of the two dates.
        The test passes if the annotated field is null, as expected.

        """
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

        Tests the Coalesce function with a MySQL-specific workaround to prevent future dates from being returned when there are no published articles.

        This test case simulates the creation of an article and verifies that the correct 'last_updated' date is returned when using the Coalesce function with MySQL.

        It checks that the 'last_updated' date matches the current date if the article does not have a published date, ensuring the Coalesce function behaves correctly with MySQL's datetime casting.

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

        Tests if the first_updated field is null when both published and updated fields are null.

        This test case creates an Article instance and annotates the queryset with the first_updated field,
        which is the least of the published and updated fields. It then asserts that the first_updated field
        is None for the created article, verifying the expected behavior when both published and updated
        fields are null.

        """
        Article.objects.create(title="Testing with Django", written=timezone.now())
        articles = Article.objects.annotate(first_updated=Least("published", "updated"))
        self.assertIsNone(articles.first().first_updated)

    def test_one_expressions(self):
        """
        Tests that the Least class raises a ValueError when passed a single expression.

        The function verifies that an appropriate error message is provided when the Least class
        is initialized with only one expression, as it requires at least two expressions to operate.

        Raises:
            ValueError: With the message 'Least must take at least two expressions'
        """
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
        """

        Tests the update functionality of the Author model, specifically the 
        automatic assignment of an alias based on the 'name' and 'goes_by' fields.

        Verifies that the alias is correctly updated to be the shorter of 'name' and 'goes_by' 
        after an update operation.

        """
        author = Author.objects.create(name="James Smith", goes_by="Jim")
        Author.objects.update(alias=Least("name", "goes_by"))
        author.refresh_from_db()
        self.assertEqual(author.alias, "James Smith")

    def test_decimal_filter(self):
        """

        Tests the usage of the decimal filter in the DecimalModel.

        This test creates an instance of DecimalModel with two decimal fields, 
        annotates the model with the least value between the two fields, 
        and then filters the results to ensure that the annotation and filter are applied correctly.

        Checks that the filtered result matches the expected object, 
        verifying the correct functionality of the decimal filter.

        """
        obj = DecimalModel.objects.create(n1=Decimal("1.1"), n2=Decimal("1.2"))
        self.assertCountEqual(
            DecimalModel.objects.annotate(
                least=Least("n1", "n2"),
            ).filter(least=Decimal("1.1")),
            [obj],
        )
