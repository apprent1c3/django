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

        Tests the basic functionality of article publication.

        This test case covers the creation of articles, updating their publication status,
        and filtering articles based on their publication date. It verifies that articles
        can be published and unpublished correctly, and that the publication date is stored
        as a datetime object.

        The test also checks that articles can be filtered by their publication date, ensuring
        that only articles with a publication date less than or equal to the current time
        are returned when using the 'published__lte' filter, and only articles with a
        publication date greater than the current time are returned when using the 'published__gt' filter.

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
