from datetime import date

from django.test import TestCase

from .models import Article


class MethodsTests(TestCase):
    def test_custom_methods(self):
        """

        Tests the custom methods of the Article model.

        This test case covers the functionality of the `was_published_today` method 
        and the `articles_from_same_day_1` and `articles_from_same_day_2` methods. 
        It creates two article objects with the same publication date, then checks 
        that the `was_published_today` method returns False, and that the 
        `articles_from_same_day_1` and `articles_from_same_day_2` methods return 
        the other article object created on the same day.

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
