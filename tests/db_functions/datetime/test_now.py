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

        Tests basic functionality of publishing articles.

        Verifies that an article can be updated with a publication date and time, 
        and that only unpublished articles can be updated in this manner. 
        Also checks that the publication date is correctly stored and retrieved 
        from the database, and that it is of the correct data type.

        Furthermore, tests that published articles can be filtered by their 
        publication date, ensuring that articles with a publication date in 
        the past or present are correctly identified, and those in the future 
        are not.

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
