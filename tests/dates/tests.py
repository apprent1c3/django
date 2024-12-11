import datetime
from unittest import skipUnless

from django.core.exceptions import FieldError
from django.db import connection
from django.test import TestCase, override_settings

from .models import Article, Category, Comment


class DatesTests(TestCase):
    def test_related_model_traverse(self):
        a1 = Article.objects.create(
            title="First one",
            pub_date=datetime.date(2005, 7, 28),
        )
        a2 = Article.objects.create(
            title="Another one",
            pub_date=datetime.date(2010, 7, 28),
        )
        a3 = Article.objects.create(
            title="Third one, in the first day",
            pub_date=datetime.date(2005, 7, 28),
        )

        a1.comments.create(
            text="Im the HULK!",
            pub_date=datetime.date(2005, 7, 28),
        )
        a1.comments.create(
            text="HULK SMASH!",
            pub_date=datetime.date(2005, 7, 29),
        )
        a2.comments.create(
            text="LMAO",
            pub_date=datetime.date(2010, 7, 28),
        )
        a3.comments.create(
            text="+1",
            pub_date=datetime.date(2005, 8, 29),
        )

        c = Category.objects.create(name="serious-news")
        c.articles.add(a1, a3)

        self.assertSequenceEqual(
            Comment.objects.dates("article__pub_date", "year"),
            [
                datetime.date(2005, 1, 1),
                datetime.date(2010, 1, 1),
            ],
        )
        self.assertSequenceEqual(
            Comment.objects.dates("article__pub_date", "month"),
            [
                datetime.date(2005, 7, 1),
                datetime.date(2010, 7, 1),
            ],
        )
        self.assertSequenceEqual(
            Comment.objects.dates("article__pub_date", "week"),
            [
                datetime.date(2005, 7, 25),
                datetime.date(2010, 7, 26),
            ],
        )
        self.assertSequenceEqual(
            Comment.objects.dates("article__pub_date", "day"),
            [
                datetime.date(2005, 7, 28),
                datetime.date(2010, 7, 28),
            ],
        )
        self.assertSequenceEqual(
            Article.objects.dates("comments__pub_date", "day"),
            [
                datetime.date(2005, 7, 28),
                datetime.date(2005, 7, 29),
                datetime.date(2005, 8, 29),
                datetime.date(2010, 7, 28),
            ],
        )
        self.assertSequenceEqual(
            Article.objects.dates("comments__approval_date", "day"), []
        )
        self.assertSequenceEqual(
            Category.objects.dates("articles__pub_date", "day"),
            [
                datetime.date(2005, 7, 28),
            ],
        )

    def test_dates_fails_when_no_arguments_are_provided(self):
        """
        Tests that calling the dates method on Article objects without arguments raises a TypeError.

        This test case ensures that the dates method behaves correctly when no arguments are provided, 
        by verifying that it raises the expected TypeError exception. This helps prevent potential 
        bugs or misuses of the dates method by enforcing the provision of required arguments.
        """
        with self.assertRaises(TypeError):
            Article.objects.dates()

    def test_dates_fails_when_given_invalid_field_argument(self):
        """

        Tests that a FieldError is raised when an invalid field is provided to the dates method.
        The test verifies that attempting to retrieve dates from a non-existent field results in an error,
        providing a helpful error message with available field options.

        """
        with self.assertRaisesMessage(
            FieldError,
            "Cannot resolve keyword 'invalid_field' into field. Choices are: "
            "categories, comments, id, pub_date, pub_datetime, title",
        ):
            Article.objects.dates("invalid_field", "year")

    def test_dates_fails_when_given_invalid_kind_argument(self):
        """
        Tests that the dates method of Article objects raises a ValueError when an invalid 'kind' argument is provided, ensuring that only 'year', 'month', 'week', or 'day' are accepted as valid date kinds.
        """
        msg = "'kind' must be one of 'year', 'month', 'week', or 'day'."
        with self.assertRaisesMessage(ValueError, msg):
            Article.objects.dates("pub_date", "bad_kind")

    def test_dates_fails_when_given_invalid_order_argument(self):
        """

        Tests that the dates method raises a ValueError when an invalid order argument is provided.

        The order argument is expected to be either 'ASC' for ascending or 'DESC' for descending.
        If any other value is passed, the method should raise an exception with a message indicating the valid order options.

        This test ensures that the dates method properly validates its input and handles invalid order arguments as expected.

        """
        msg = "'order' must be either 'ASC' or 'DESC'."
        with self.assertRaisesMessage(ValueError, msg):
            Article.objects.dates("pub_date", "year", order="bad order")

    @override_settings(USE_TZ=False)
    def test_dates_trunc_datetime_fields(self):
        """

        Tests that the dates method correctly truncates datetime fields to the specified interval.

        In this case, it verifies that the dates are truncated to the day level, and that the results are ordered in ascending order.

        It creates multiple Article objects with different publication dates and times, then checks that the dates method returns the expected date values, ignoring the time component.

        """
        Article.objects.bulk_create(
            Article(pub_date=pub_datetime.date(), pub_datetime=pub_datetime)
            for pub_datetime in [
                datetime.datetime(2015, 10, 21, 18, 1),
                datetime.datetime(2015, 10, 21, 18, 2),
                datetime.datetime(2015, 10, 22, 18, 1),
                datetime.datetime(2015, 10, 22, 18, 2),
            ]
        )
        self.assertSequenceEqual(
            Article.objects.dates("pub_datetime", "day", order="ASC"),
            [
                datetime.date(2015, 10, 21),
                datetime.date(2015, 10, 22),
            ],
        )

    @skipUnless(connection.vendor == "mysql", "Test checks MySQL query syntax")
    def test_dates_avoid_datetime_cast(self):
        """

        Tests the syntax of MySQL queries for date functionality, specifically checking 
        that the ORM generates the correct query when using the `dates` method on a 
        DateTimeField, avoiding unnecessary datetime casts.

        This test case creates an Article instance with a specific publication date, 
        then verifies the generated SQL queries for different date parts (day, month, 
        year) to ensure they use the correct MySQL date functions.

        The goal is to confirm that the generated queries do not include unnecessary 
        casts to datetime when extracting date parts, which could impact performance.

        """
        Article.objects.create(pub_date=datetime.date(2015, 10, 21))
        for kind in ["day", "month", "year"]:
            qs = Article.objects.dates("pub_date", kind)
            if kind == "day":
                self.assertIn("DATE(", str(qs.query))
            else:
                self.assertIn(" AS DATE)", str(qs.query))
