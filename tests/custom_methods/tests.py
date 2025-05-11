from datetime import date

from django.test import TestCase

from .models import Article


class MethodsTests(TestCase):
    def test_custom_methods(self):
        """
        Tests custom methods on the Article model, specifically the 
        was_published_today and articles_from_same_day methods, to ensure 
        correct publication date and article retrieval functionality.
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
