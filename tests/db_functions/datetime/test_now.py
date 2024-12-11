from datetime import datetime, timedelta

from django.db import connection
from django.db.models import TextField
from django.db.models.functions import Cast, Now
from django.test import TestCase
from django.utils import timezone

from ..models import Article

lorem_ipsum = """
    Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod
    tempor incididunt ut labore et dolore magna aliqua."""


class NowTests(TestCase):
    def test_basic(self):
        """
        Tests basic functionality of the Article model's publish feature.

        Checks that marking an unpublished article as published works correctly, 
        and that attempting to publish an already published article has no effect. 
        Verifies that the published attribute is updated correctly in the database. 
        Also tests filtering of articles by their publication date, ensuring that 
        published articles are retrieved correctly based on their publication time.

        Validates that articles can be saved with a future publication date, 
        and that these articles are not included in queries for currently published articles.
        """
        a1 = Article.objects.create(
            title="How to Django",
            text=lorem_ipsum,
            written=timezone.now(),
        )
        a2 = Article.objects.create(
            title="How to Time Travel",
            text=lorem_ipsum,
            written=timezone.now(),
        )
        num_updated = Article.objects.filter(id=a1.id, published=None).update(
            published=Now()
        )
        self.assertEqual(num_updated, 1)
        num_updated = Article.objects.filter(id=a1.id, published=None).update(
            published=Now()
        )
        self.assertEqual(num_updated, 0)
        a1.refresh_from_db()
        self.assertIsInstance(a1.published, datetime)
        a2.published = Now() + timedelta(days=2)
        a2.save()
        a2.refresh_from_db()
        self.assertIsInstance(a2.published, datetime)
        self.assertQuerySetEqual(
            Article.objects.filter(published__lte=Now()),
            ["How to Django"],
            lambda a: a.title,
        )
        self.assertQuerySetEqual(
            Article.objects.filter(published__gt=Now()),
            ["How to Time Travel"],
            lambda a: a.title,
        )

    def test_microseconds(self):
        """

        Tests the precision of microseconds in the current timestamp.

        Verifies that the 'now()' database function returns a string representation 
        of the current timestamp with the correct number of microseconds, as defined 
        by the database connection's time cast precision.

        The test creates a temporary Article object, annotates it with the current 
        timestamp as a string, and then checks if the resulting string matches the 
        expected format, including the correct number of microseconds.

        """
        Article.objects.create(
            title="How to Django",
            text=lorem_ipsum,
            written=timezone.now(),
        )
        now_string = (
            Article.objects.annotate(now_string=Cast(Now(), TextField()))
            .get()
            .now_string
        )
        precision = connection.features.time_cast_precision
        self.assertRegex(now_string, rf"^.*\.\d{{1,{precision}}}")
