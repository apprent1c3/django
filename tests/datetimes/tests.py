import datetime

from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Article, Category, Comment


class DateTimesTests(TestCase):
    def test_related_model_traverse(self):
        """
        Tests traversal of related models using the datetimes() method.

        This test creates multiple Articles with related Comments, and associates some
        Articles with a Category. It then verifies that the datetimes() method
        correctly returns a list of dates for various date parts (year, month, week, day)
        when traversing from one model to a related model. The tests cover traversals
        from Comments to Articles and from Articles to Comments, as well as from
        Categories to Articles. The expected dates are compared with the results of the
        datetimes() method to ensure that the traversal is correct and returns the
        expected dates.
        """
        a1 = Article.objects.create(
            title="First one",
            pub_date=datetime.datetime(2005, 7, 28, 9, 0, 0),
        )
        a2 = Article.objects.create(
            title="Another one",
            pub_date=datetime.datetime(2010, 7, 28, 10, 0, 0),
        )
        a3 = Article.objects.create(
            title="Third one, in the first day",
            pub_date=datetime.datetime(2005, 7, 28, 17, 0, 0),
        )

        a1.comments.create(
            text="Im the HULK!",
            pub_date=datetime.datetime(2005, 7, 28, 9, 30, 0),
        )
        a1.comments.create(
            text="HULK SMASH!",
            pub_date=datetime.datetime(2005, 7, 29, 1, 30, 0),
        )
        a2.comments.create(
            text="LMAO",
            pub_date=datetime.datetime(2010, 7, 28, 10, 10, 10),
        )
        a3.comments.create(
            text="+1",
            pub_date=datetime.datetime(2005, 8, 29, 10, 10, 10),
        )

        c = Category.objects.create(name="serious-news")
        c.articles.add(a1, a3)

        self.assertSequenceEqual(
            Comment.objects.datetimes("article__pub_date", "year"),
            [
                datetime.datetime(2005, 1, 1),
                datetime.datetime(2010, 1, 1),
            ],
        )
        self.assertSequenceEqual(
            Comment.objects.datetimes("article__pub_date", "month"),
            [
                datetime.datetime(2005, 7, 1),
                datetime.datetime(2010, 7, 1),
            ],
        )
        self.assertSequenceEqual(
            Comment.objects.datetimes("article__pub_date", "week"),
            [
                datetime.datetime(2005, 7, 25),
                datetime.datetime(2010, 7, 26),
            ],
        )
        self.assertSequenceEqual(
            Comment.objects.datetimes("article__pub_date", "day"),
            [
                datetime.datetime(2005, 7, 28),
                datetime.datetime(2010, 7, 28),
            ],
        )
        self.assertSequenceEqual(
            Article.objects.datetimes("comments__pub_date", "day"),
            [
                datetime.datetime(2005, 7, 28),
                datetime.datetime(2005, 7, 29),
                datetime.datetime(2005, 8, 29),
                datetime.datetime(2010, 7, 28),
            ],
        )
        self.assertSequenceEqual(
            Article.objects.datetimes("comments__approval_date", "day"), []
        )
        self.assertSequenceEqual(
            Category.objects.datetimes("articles__pub_date", "day"),
            [
                datetime.datetime(2005, 7, 28),
            ],
        )

    @override_settings(USE_TZ=True)
    def test_21432(self):
        now = timezone.localtime(timezone.now().replace(microsecond=0))
        Article.objects.create(title="First one", pub_date=now)
        qs = Article.objects.datetimes("pub_date", "second")
        self.assertEqual(qs[0], now)

    def test_datetimes_returns_available_dates_for_given_scope_and_given_field(self):
        pub_dates = [
            datetime.datetime(2005, 7, 28, 12, 15),
            datetime.datetime(2005, 7, 29, 2, 15),
            datetime.datetime(2005, 7, 30, 5, 15),
            datetime.datetime(2005, 7, 31, 19, 15),
        ]
        for i, pub_date in enumerate(pub_dates):
            Article(pub_date=pub_date, title="title #{}".format(i)).save()

        self.assertSequenceEqual(
            Article.objects.datetimes("pub_date", "year"),
            [datetime.datetime(2005, 1, 1, 0, 0)],
        )
        self.assertSequenceEqual(
            Article.objects.datetimes("pub_date", "month"),
            [datetime.datetime(2005, 7, 1, 0, 0)],
        )
        self.assertSequenceEqual(
            Article.objects.datetimes("pub_date", "week"),
            [datetime.datetime(2005, 7, 25, 0, 0)],
        )
        self.assertSequenceEqual(
            Article.objects.datetimes("pub_date", "day"),
            [
                datetime.datetime(2005, 7, 28, 0, 0),
                datetime.datetime(2005, 7, 29, 0, 0),
                datetime.datetime(2005, 7, 30, 0, 0),
                datetime.datetime(2005, 7, 31, 0, 0),
            ],
        )
        self.assertSequenceEqual(
            Article.objects.datetimes("pub_date", "day", order="ASC"),
            [
                datetime.datetime(2005, 7, 28, 0, 0),
                datetime.datetime(2005, 7, 29, 0, 0),
                datetime.datetime(2005, 7, 30, 0, 0),
                datetime.datetime(2005, 7, 31, 0, 0),
            ],
        )
        self.assertSequenceEqual(
            Article.objects.datetimes("pub_date", "day", order="DESC"),
            [
                datetime.datetime(2005, 7, 31, 0, 0),
                datetime.datetime(2005, 7, 30, 0, 0),
                datetime.datetime(2005, 7, 29, 0, 0),
                datetime.datetime(2005, 7, 28, 0, 0),
            ],
        )

    def test_datetimes_has_lazy_iterator(self):
        pub_dates = [
            datetime.datetime(2005, 7, 28, 12, 15),
            datetime.datetime(2005, 7, 29, 2, 15),
            datetime.datetime(2005, 7, 30, 5, 15),
            datetime.datetime(2005, 7, 31, 19, 15),
        ]
        for i, pub_date in enumerate(pub_dates):
            Article(pub_date=pub_date, title="title #{}".format(i)).save()
        # Use iterator() with datetimes() to return a generator that lazily
        # requests each result one at a time, to save memory.
        dates = []
        with self.assertNumQueries(0):
            article_datetimes_iterator = Article.objects.datetimes(
                "pub_date", "day", order="DESC"
            ).iterator()

        with self.assertNumQueries(1):
            for article in article_datetimes_iterator:
                dates.append(article)
        self.assertEqual(
            dates,
            [
                datetime.datetime(2005, 7, 31, 0, 0),
                datetime.datetime(2005, 7, 30, 0, 0),
                datetime.datetime(2005, 7, 29, 0, 0),
                datetime.datetime(2005, 7, 28, 0, 0),
            ],
        )

    def test_datetimes_disallows_date_fields(self):
        dt = datetime.datetime(2005, 7, 28, 12, 15)
        Article.objects.create(
            pub_date=dt,
            published_on=dt.date(),
            title="Don't put dates into datetime functions!",
        )
        with self.assertRaisesMessage(
            ValueError, "Cannot truncate DateField 'published_on' to DateTimeField"
        ):
            list(Article.objects.datetimes("published_on", "second"))

    def test_datetimes_fails_when_given_invalid_kind_argument(self):
        """
        Test that the datetimes method on the Article manager fails when passed an invalid 'kind' argument.

        The datetimes method is expected to raise a ValueError when the 'kind' argument does not match one of the following values: 'year', 'month', 'week', 'day', 'hour', 'minute', or 'second'. This test verifies that the appropriate error message is provided when an invalid 'kind' argument is supplied.
        """
        msg = (
            "'kind' must be one of 'year', 'month', 'week', 'day', 'hour', "
            "'minute', or 'second'."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Article.objects.datetimes("pub_date", "bad_kind")

    def test_datetimes_fails_when_given_invalid_order_argument(self):
        """

        Tests that the datetimes method raises a ValueError when an invalid order argument is provided.

        The datetimes method is expected to accept an 'order' parameter that is either 'ASC' for ascending order or 'DESC' for descending order. 
        This test case verifies that passing any other value results in a ValueError with a descriptive error message.

        """
        msg = "'order' must be either 'ASC' or 'DESC'."
        with self.assertRaisesMessage(ValueError, msg):
            Article.objects.datetimes("pub_date", "year", order="bad order")
