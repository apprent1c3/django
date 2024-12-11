from datetime import date

from django.test import TestCase

from .models import Article


class MethodsTests(TestCase):
    def test_custom_methods(self):
        """
        Tests custom methods for Article objects.

        This test case covers the functionality of two custom methods: 
        :func:`~core.models.Article.was_published_today` and 
        :func:`~core.models.Article.articles_from_same_day_1`/:func:`~core.models.Article.articles_from_same_day_2`.
        It verifies that these methods return correct results by creating two Article objects 
        with the same publication date, and then checking the output of the methods for these objects.

        The test checks that the :func:`~core.models.Article.was_published_today` method correctly identifies 
        if an article was published on the current day. It also verifies that the 
        :func:`~core.models.Article.articles_from_same_day_1` and :func:`~core.models.Article.articles_from_same_day_2` 
        methods return a list of articles that were published on the same day as the article object they are called on.

        """
        a = Article.objects.create(
            headline="Parrot programs in Python", pub_date=date(2005, 7, 27)
        )
        b = Article.objects.create(
            headline="Beatles reunite", pub_date=date(2005, 7, 27)
        )

        self.assertFalse(a.was_published_today())
        self.assertQuerySetEqual(
            a.articles_from_same_day_1(),
            [
                "Beatles reunite",
            ],
            lambda a: a.headline,
        )
        self.assertQuerySetEqual(
            a.articles_from_same_day_2(),
            [
                "Beatles reunite",
            ],
            lambda a: a.headline,
        )

        self.assertQuerySetEqual(
            b.articles_from_same_day_1(),
            [
                "Parrot programs in Python",
            ],
            lambda a: a.headline,
        )
        self.assertQuerySetEqual(
            b.articles_from_same_day_2(),
            [
                "Parrot programs in Python",
            ],
            lambda a: a.headline,
        )
