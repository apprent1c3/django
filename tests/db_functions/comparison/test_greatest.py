from datetime import datetime, timedelta
from decimal import Decimal
from unittest import skipUnless

from django.db import connection
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce, Greatest
from django.test import TestCase, skipIfDBFeature, skipUnlessDBFeature
from django.utils import timezone

from ..models import Article, Author, DecimalModel, Fan


class GreatestTests(TestCase):
    def test_basic(self):
        now = timezone.now()
        before = now - timedelta(hours=1)
        Article.objects.create(
            title="Testing with Django", written=before, published=now
        )
        articles = Article.objects.annotate(
            last_updated=Greatest("written", "published")
        )
        self.assertEqual(articles.first().last_updated, now)

    @skipUnlessDBFeature("greatest_least_ignores_nulls")
    def test_ignores_null(self):
        """
        Tests the behavior of the GREATEST function when ignoring NULL values.
        This test ensures that when using the GREATEST function with a NULL value, 
        it returns the non-NULL value, rather than treating the NULL as the greatest value.
        The test case creates an article with a written timestamp but no published timestamp, 
        then annotates the article with the GREATEST of these two timestamps. 
        Verifies that the resulting last_updated timestamp is the written timestamp, 
        as expected when ignoring NULL values.
        """
        now = timezone.now()
        Article.objects.create(title="Testing with Django", written=now)
        articles = Article.objects.annotate(
            last_updated=Greatest("written", "published")
        )
        self.assertEqual(articles.first().last_updated, now)

    @skipIfDBFeature("greatest_least_ignores_nulls")
    def test_propagates_null(self):
        Article.objects.create(title="Testing with Django", written=timezone.now())
        articles = Article.objects.annotate(
            last_updated=Greatest("written", "published")
        )
        self.assertIsNone(articles.first().last_updated)

    def test_coalesce_workaround(self):
        past = datetime(1900, 1, 1)
        now = timezone.now()
        Article.objects.create(title="Testing with Django", written=now)
        articles = Article.objects.annotate(
            last_updated=Greatest(
                Coalesce("written", past),
                Coalesce("published", past),
            ),
        )
        self.assertEqual(articles.first().last_updated, now)

    @skipUnless(connection.vendor == "mysql", "MySQL-specific workaround")
    def test_coalesce_workaround_mysql(self):
        """

        Tests a workaround for MySQL to ensure correct usage of the COALESCE function 
        in conjunction with the GREATEST function for annotating Article objects.

        This test verifies that when an Article object has a 'written' date and no 'published' date,
        the 'last_updated' field is correctly annotated with the 'written' date.
        It checks the behavior when the 'written' date is more recent than the 'published' date,
        by comparing the annotated 'last_updated' field with the expected 'written' date.

        The test is specific to MySQL due to differences in how the database vendor handles 
        certain date and time operations.

        """
        past = datetime(1900, 1, 1)
        now = timezone.now()
        Article.objects.create(title="Testing with Django", written=now)
        past_sql = RawSQL("cast(%s as datetime)", (past,))
        articles = Article.objects.annotate(
            last_updated=Greatest(
                Coalesce("written", past_sql),
                Coalesce("published", past_sql),
            ),
        )
        self.assertEqual(articles.first().last_updated, now)

    def test_all_null(self):
        """

        Test that the last_updated field is null for an article with no published or updated date.

        Checks the initialization of an article with default dates, and verifies that the 
        annotated last_updated field is None when the article has not been published or updated.

        """
        Article.objects.create(title="Testing with Django", written=timezone.now())
        articles = Article.objects.annotate(
            last_updated=Greatest("published", "updated")
        )
        self.assertIsNone(articles.first().last_updated)

    def test_one_expressions(self):
        with self.assertRaisesMessage(
            ValueError, "Greatest must take at least two expressions"
        ):
            Greatest("written")

    def test_related_field(self):
        """

        Tests the related field 'fans' in the Author model by creating an author and a fan,
        and verifying that the annotated 'highest_age' field returns the highest age between
        the author and their fan. This ensures that the relationship between authors and fans
        is correctly established and that the Greatest aggregation function works as expected.

        """
        author = Author.objects.create(name="John Smith", age=45)
        Fan.objects.create(name="Margaret", age=50, author=author)
        authors = Author.objects.annotate(highest_age=Greatest("age", "fans__age"))
        self.assertEqual(authors.first().highest_age, 50)

    def test_update(self):
        """

        Tests the automatic update of the author's alias attribute.

        This test case verifies that the alias of an author is correctly updated based on the 
        author's name and goes_by attributes, with the alias being set to the shorter of the two.

        The test creates a new author, updates the alias using a database function, and then 
        checks if the author's alias has been correctly updated.

        """
        author = Author.objects.create(name="James Smith", goes_by="Jim")
        Author.objects.update(alias=Greatest("name", "goes_by"))
        author.refresh_from_db()
        self.assertEqual(author.alias, "Jim")

    def test_decimal_filter(self):
        obj = DecimalModel.objects.create(n1=Decimal("1.1"), n2=Decimal("1.2"))
        self.assertCountEqual(
            DecimalModel.objects.annotate(
                greatest=Greatest("n1", "n2"),
            ).filter(greatest=Decimal("1.2")),
            [obj],
        )
