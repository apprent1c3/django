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
        Tests the Article.objects.earliest() method to retrieve the earliest articles based on the model's Meta.get_latest_by fields or the specified field names.

        This test covers various scenarios, including:
        - Retrieving the earliest article when no articles exist
        - Retrieving the earliest article with default ordering (publication date)
        - Retrieving the earliest article with custom ordering (expire date)
        - Retrieving the earliest article with a filter
        - Retrieving the earliest article with custom ordering and a filter
        - Passing the get_latest_by fields as positional arguments
        - Using the negate field name to order in descending order

        It also checks that ValueError is raised when get_latest_by is not defined in the model's Meta and no fields are provided as positional arguments.
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
        Tests the functionality of the :meth:`latest` method of the Article model's manager, 
        verifying that it correctly retrieves the latest article based on the model's ``get_latest_by`` 
        field or the specified field(s), and that it raises an exception when this field is not defined.
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

        Tests the latest() method on the Person model, verifying that it correctly 
        returns the latest object based on the specified field, and raises a ValueError 
        when no field or 'get_latest_by' is provided.

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
        Tests the functionality of retrieving the first object from a Django ORM queryset, including default ordering, custom ordering, and filtering. Verifies that the correct object is returned in various scenarios and that None is returned when no objects match the filter criteria.
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
        Tests the correctness of the last() method on a QuerySet of Person objects, ensuring it returns the last object based on the default ordering, a custom ordering, and filtered results, or None if no objects match the filter criteria.
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
        Tests that IndexError exceptions are not suppressed when iterating over QuerySet results, specifically when slicing, getting the first, or getting the last object.
        """

        def check():
            # We know that we've broken the __iter__ method, so the queryset
            # should always raise an exception.
            """
            Tests that querying IndexErrorArticle objects raises an IndexError.

            Verifies that attempting to slice, retrieve the first, or retrieve the last object from the queryset results in an IndexError being raised.
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
        _Test that first and last methods on unordered QuerySets with aggregation raise a TypeError._
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
