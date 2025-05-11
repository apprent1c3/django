from datetime import datetime

from django.db.models import Avg
from django.test import TestCase

from .models import Article, Comment, IndexErrorArticle, Person


class EarliestOrLatestTests(TestCase):
    """Tests for the earliest() and latest() objects methods"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._article_get_latest_by = Article._meta.get_latest_by

    def tearDown(self):
        Article._meta.get_latest_by = self._article_get_latest_by

    def test_earliest(self):
        # Because no Articles exist yet, earliest() raises ArticleDoesNotExist.
        """
        Tests the earliest method of the Article queryset.

        This method ensures that the earliest method behaves correctly when
        given no model instances, when given model instances with different
        dates, and when given model instances with the same date but 
        different secondary order fields.

        It also tests the earliest method when 'get_latest_by' is not specified
        in the model's Meta and when it is specified, as well as with 
        POSITIONAL arguments and with ascending/descending order.
        """
        with self.assertRaises(Article.DoesNotExist):
            Article.objects.earliest()

        a1 = Article.objects.create(
            headline="Article 1",
            pub_date=datetime(2005, 7, 26),
            expire_date=datetime(2005, 9, 1),
        )
        a2 = Article.objects.create(
            headline="Article 2",
            pub_date=datetime(2005, 7, 27),
            expire_date=datetime(2005, 7, 28),
        )
        a3 = Article.objects.create(
            headline="Article 3",
            pub_date=datetime(2005, 7, 28),
            expire_date=datetime(2005, 8, 27),
        )
        a4 = Article.objects.create(
            headline="Article 4",
            pub_date=datetime(2005, 7, 28),
            expire_date=datetime(2005, 7, 30),
        )

        # Get the earliest Article.
        self.assertEqual(Article.objects.earliest(), a1)
        # Get the earliest Article that matches certain filters.
        self.assertEqual(
            Article.objects.filter(pub_date__gt=datetime(2005, 7, 26)).earliest(), a2
        )

        # Pass a custom field name to earliest() to change the field that's used
        # to determine the earliest object.
        self.assertEqual(Article.objects.earliest("expire_date"), a2)
        self.assertEqual(
            Article.objects.filter(pub_date__gt=datetime(2005, 7, 26)).earliest(
                "expire_date"
            ),
            a2,
        )

        # earliest() overrides any other ordering specified on the query.
        # Refs #11283.
        self.assertEqual(Article.objects.order_by("id").earliest(), a1)

        # Error is raised if the user forgot to add a get_latest_by
        # in the Model.Meta
        Article.objects.model._meta.get_latest_by = None
        with self.assertRaisesMessage(
            ValueError,
            "earliest() and latest() require either fields as positional "
            "arguments or 'get_latest_by' in the model's Meta.",
        ):
            Article.objects.earliest()

        # Earliest publication date, earliest expire date.
        self.assertEqual(
            Article.objects.filter(pub_date=datetime(2005, 7, 28)).earliest(
                "pub_date", "expire_date"
            ),
            a4,
        )
        # Earliest publication date, latest expire date.
        self.assertEqual(
            Article.objects.filter(pub_date=datetime(2005, 7, 28)).earliest(
                "pub_date", "-expire_date"
            ),
            a3,
        )

        # Meta.get_latest_by may be a tuple.
        Article.objects.model._meta.get_latest_by = ("pub_date", "expire_date")
        self.assertEqual(
            Article.objects.filter(pub_date=datetime(2005, 7, 28)).earliest(), a4
        )

    def test_earliest_sliced_queryset(self):
        msg = "Cannot change a query once a slice has been taken."
        with self.assertRaisesMessage(TypeError, msg):
            Article.objects.all()[0:5].earliest()

    def test_latest(self):
        # Because no Articles exist yet, latest() raises ArticleDoesNotExist.
        """
        Test the model's latest method to ensure it returns the most recent object based on the model's get_latest_by field or the provided field names, with correct handling of filtering, ordering, and error cases.
        """
        with self.assertRaises(Article.DoesNotExist):
            Article.objects.latest()

        a1 = Article.objects.create(
            headline="Article 1",
            pub_date=datetime(2005, 7, 26),
            expire_date=datetime(2005, 9, 1),
        )
        a2 = Article.objects.create(
            headline="Article 2",
            pub_date=datetime(2005, 7, 27),
            expire_date=datetime(2005, 7, 28),
        )
        a3 = Article.objects.create(
            headline="Article 3",
            pub_date=datetime(2005, 7, 27),
            expire_date=datetime(2005, 8, 27),
        )
        a4 = Article.objects.create(
            headline="Article 4",
            pub_date=datetime(2005, 7, 28),
            expire_date=datetime(2005, 7, 30),
        )

        # Get the latest Article.
        self.assertEqual(Article.objects.latest(), a4)
        # Get the latest Article that matches certain filters.
        self.assertEqual(
            Article.objects.filter(pub_date__lt=datetime(2005, 7, 27)).latest(), a1
        )

        # Pass a custom field name to latest() to change the field that's used
        # to determine the latest object.
        self.assertEqual(Article.objects.latest("expire_date"), a1)
        self.assertEqual(
            Article.objects.filter(pub_date__gt=datetime(2005, 7, 26)).latest(
                "expire_date"
            ),
            a3,
        )

        # latest() overrides any other ordering specified on the query (#11283).
        self.assertEqual(Article.objects.order_by("id").latest(), a4)

        # Error is raised if get_latest_by isn't in Model.Meta.
        Article.objects.model._meta.get_latest_by = None
        with self.assertRaisesMessage(
            ValueError,
            "earliest() and latest() require either fields as positional "
            "arguments or 'get_latest_by' in the model's Meta.",
        ):
            Article.objects.latest()

        # Latest publication date, latest expire date.
        self.assertEqual(
            Article.objects.filter(pub_date=datetime(2005, 7, 27)).latest(
                "pub_date", "expire_date"
            ),
            a3,
        )
        # Latest publication date, earliest expire date.
        self.assertEqual(
            Article.objects.filter(pub_date=datetime(2005, 7, 27)).latest(
                "pub_date", "-expire_date"
            ),
            a2,
        )

        # Meta.get_latest_by may be a tuple.
        Article.objects.model._meta.get_latest_by = ("pub_date", "expire_date")
        self.assertEqual(
            Article.objects.filter(pub_date=datetime(2005, 7, 27)).latest(), a3
        )

    def test_latest_sliced_queryset(self):
        msg = "Cannot change a query once a slice has been taken."
        with self.assertRaisesMessage(TypeError, msg):
            Article.objects.all()[0:5].latest()

    def test_latest_manual(self):
        # You can still use latest() with a model that doesn't have
        # "get_latest_by" set -- just pass in the field name manually.
        """
        Tests the latest() method of the model's queryset, ensuring it raises a ValueError when called without specifying a field or 'get_latest_by' in the model's Meta, and returns the correct object when called with a field.
        """
        Person.objects.create(name="Ralph", birthday=datetime(1950, 1, 1))
        p2 = Person.objects.create(name="Stephanie", birthday=datetime(1960, 2, 3))
        msg = (
            "earliest() and latest() require either fields as positional arguments "
            "or 'get_latest_by' in the model's Meta."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Person.objects.latest()
        self.assertEqual(Person.objects.latest("birthday"), p2)


class TestFirstLast(TestCase):
    def test_first(self):
        """
        Tests the functionality of retrieving the first object from a queryset of Person objects, 
        ensuring correct ordering and filtering behavior.
        """
        p1 = Person.objects.create(name="Bob", birthday=datetime(1950, 1, 1))
        p2 = Person.objects.create(name="Alice", birthday=datetime(1961, 2, 3))
        self.assertEqual(Person.objects.first(), p1)
        self.assertEqual(Person.objects.order_by("name").first(), p2)
        self.assertEqual(
            Person.objects.filter(birthday__lte=datetime(1955, 1, 1)).first(), p1
        )
        self.assertIsNone(
            Person.objects.filter(birthday__lte=datetime(1940, 1, 1)).first()
        )

    def test_last(self):
        """

        Tests the last() method of the Person queryset.

        Verifies that last() returns the last object in the queryset based on the default ordering,
        and that it works correctly with custom ordering and filtering.

        """
        p1 = Person.objects.create(name="Alice", birthday=datetime(1950, 1, 1))
        p2 = Person.objects.create(name="Bob", birthday=datetime(1960, 2, 3))
        # Note: by default PK ordering.
        self.assertEqual(Person.objects.last(), p2)
        self.assertEqual(Person.objects.order_by("-name").last(), p1)
        self.assertEqual(
            Person.objects.filter(birthday__lte=datetime(1955, 1, 1)).last(), p1
        )
        self.assertIsNone(
            Person.objects.filter(birthday__lte=datetime(1940, 1, 1)).last()
        )

    def test_index_error_not_suppressed(self):
        """
        #23555 -- Unexpected IndexError exceptions in QuerySet iteration
        shouldn't be suppressed.
        """

        def check():
            # We know that we've broken the __iter__ method, so the queryset
            # should always raise an exception.
            """
            Tests that querying IndexErrorArticle objects raises an IndexError.

             Verifies that attempting to slice, retrieve the first, or retrieve the last 
             IndexErrorArticle object results in an IndexError being raised, as expected.
            """
            with self.assertRaises(IndexError):
                IndexErrorArticle.objects.all()[:10:2]
            with self.assertRaises(IndexError):
                IndexErrorArticle.objects.first()
            with self.assertRaises(IndexError):
                IndexErrorArticle.objects.last()

        check()

        # And it does not matter if there are any records in the DB.
        IndexErrorArticle.objects.create(
            headline="Article 1",
            pub_date=datetime(2005, 7, 26),
            expire_date=datetime(2005, 9, 1),
        )
        check()

    def test_first_last_unordered_qs_aggregation_error(self):
        """
        Tests that attempting to call `first()` or `last()` on a queryset performing aggregation raises a TypeError when the queryset is unordered.
        """
        a1 = Article.objects.create(
            headline="Article 1",
            pub_date=datetime(2005, 7, 26),
            expire_date=datetime(2005, 9, 1),
        )
        Comment.objects.create(article=a1, likes_count=5)

        qs = Comment.objects.values("article").annotate(avg_likes=Avg("likes_count"))
        msg = (
            "Cannot use QuerySet.%s() on an unordered queryset performing aggregation. "
            "Add an ordering with order_by()."
        )
        with self.assertRaisesMessage(TypeError, msg % "first"):
            qs.first()
        with self.assertRaisesMessage(TypeError, msg % "last"):
            qs.last()
