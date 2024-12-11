import collections.abc
from datetime import datetime
from math import ceil
from operator import attrgetter
from unittest import skipUnless

from django.core.exceptions import FieldError
from django.db import connection, models
from django.db.models import (
    BooleanField,
    Case,
    Exists,
    ExpressionWrapper,
    F,
    Max,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Abs, Cast, Length, Substr
from django.db.models.lookups import (
    Exact,
    GreaterThan,
    GreaterThanOrEqual,
    IsNull,
    LessThan,
    LessThanOrEqual,
)
from django.test import TestCase, skipUnlessDBFeature
from django.test.utils import isolate_apps, register_lookup

from .models import (
    Article,
    Author,
    Freebie,
    Game,
    IsNullWithNoneAsRHS,
    Player,
    Product,
    Season,
    Stock,
    Tag,
)


class LookupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a few Authors.
        """

        Sets up test data for the application, including authors, articles, and tags.

        This method creates two authors, seven articles, and three tags, and associates the articles with the authors and tags.
        The created data includes variations in publication dates and tag assignments to support comprehensive testing.
        The test data is stored as class attributes, allowing it to be accessed and used throughout the test suite.

        """
        cls.au1 = Author.objects.create(name="Author 1", alias="a1", bio="x" * 4001)
        cls.au2 = Author.objects.create(name="Author 2", alias="a2")
        # Create a few Articles.
        cls.a1 = Article.objects.create(
            headline="Article 1",
            pub_date=datetime(2005, 7, 26),
            author=cls.au1,
            slug="a1",
        )
        cls.a2 = Article.objects.create(
            headline="Article 2",
            pub_date=datetime(2005, 7, 27),
            author=cls.au1,
            slug="a2",
        )
        cls.a3 = Article.objects.create(
            headline="Article 3",
            pub_date=datetime(2005, 7, 27),
            author=cls.au1,
            slug="a3",
        )
        cls.a4 = Article.objects.create(
            headline="Article 4",
            pub_date=datetime(2005, 7, 28),
            author=cls.au1,
            slug="a4",
        )
        cls.a5 = Article.objects.create(
            headline="Article 5",
            pub_date=datetime(2005, 8, 1, 9, 0),
            author=cls.au2,
            slug="a5",
        )
        cls.a6 = Article.objects.create(
            headline="Article 6",
            pub_date=datetime(2005, 8, 1, 8, 0),
            author=cls.au2,
            slug="a6",
        )
        cls.a7 = Article.objects.create(
            headline="Article 7",
            pub_date=datetime(2005, 7, 27),
            author=cls.au2,
            slug="a7",
        )
        # Create a few Tags.
        cls.t1 = Tag.objects.create(name="Tag 1")
        cls.t1.articles.add(cls.a1, cls.a2, cls.a3)
        cls.t2 = Tag.objects.create(name="Tag 2")
        cls.t2.articles.add(cls.a3, cls.a4, cls.a5)
        cls.t3 = Tag.objects.create(name="Tag 3")
        cls.t3.articles.add(cls.a5, cls.a6, cls.a7)

    def test_exists(self):
        # We can use .exists() to check that there are some
        self.assertTrue(Article.objects.exists())
        for a in Article.objects.all():
            a.delete()
        # There should be none now!
        self.assertFalse(Article.objects.exists())

    def test_lookup_int_as_str(self):
        # Integer value can be queried using string
        self.assertSequenceEqual(
            Article.objects.filter(id__iexact=str(self.a1.id)),
            [self.a1],
        )

    @skipUnlessDBFeature("supports_date_lookup_using_string")
    def test_lookup_date_as_str(self):
        # A date lookup can be performed using a string search
        self.assertSequenceEqual(
            Article.objects.filter(pub_date__startswith="2005"),
            [self.a5, self.a6, self.a4, self.a2, self.a3, self.a7, self.a1],
        )

    def test_iterator(self):
        # Each QuerySet gets iterator(), which is a generator that "lazily"
        # returns results using database-level iteration.
        self.assertIsInstance(Article.objects.iterator(), collections.abc.Iterator)

        self.assertQuerySetEqual(
            Article.objects.iterator(),
            [
                "Article 5",
                "Article 6",
                "Article 4",
                "Article 2",
                "Article 3",
                "Article 7",
                "Article 1",
            ],
            transform=attrgetter("headline"),
        )
        # iterator() can be used on any QuerySet.
        self.assertQuerySetEqual(
            Article.objects.filter(headline__endswith="4").iterator(),
            ["Article 4"],
            transform=attrgetter("headline"),
        )

    def test_count(self):
        # count() returns the number of objects matching search criteria.
        self.assertEqual(Article.objects.count(), 7)
        self.assertEqual(
            Article.objects.filter(pub_date__exact=datetime(2005, 7, 27)).count(), 3
        )
        self.assertEqual(
            Article.objects.filter(headline__startswith="Blah blah").count(), 0
        )

        # count() should respect sliced query sets.
        articles = Article.objects.all()
        self.assertEqual(articles.count(), 7)
        self.assertEqual(articles[:4].count(), 4)
        self.assertEqual(articles[1:100].count(), 6)
        self.assertEqual(articles[10:100].count(), 0)

        # Date and date/time lookups can also be done with strings.
        self.assertEqual(
            Article.objects.filter(pub_date__exact="2005-07-27 00:00:00").count(), 3
        )

    def test_in_bulk(self):
        # in_bulk() takes a list of IDs and returns a dictionary mapping IDs to objects.
        arts = Article.objects.in_bulk([self.a1.id, self.a2.id])
        self.assertEqual(arts[self.a1.id], self.a1)
        self.assertEqual(arts[self.a2.id], self.a2)
        self.assertEqual(
            Article.objects.in_bulk(),
            {
                self.a1.id: self.a1,
                self.a2.id: self.a2,
                self.a3.id: self.a3,
                self.a4.id: self.a4,
                self.a5.id: self.a5,
                self.a6.id: self.a6,
                self.a7.id: self.a7,
            },
        )
        self.assertEqual(Article.objects.in_bulk([self.a3.id]), {self.a3.id: self.a3})
        self.assertEqual(Article.objects.in_bulk({self.a3.id}), {self.a3.id: self.a3})
        self.assertEqual(
            Article.objects.in_bulk(frozenset([self.a3.id])), {self.a3.id: self.a3}
        )
        self.assertEqual(Article.objects.in_bulk((self.a3.id,)), {self.a3.id: self.a3})
        self.assertEqual(Article.objects.in_bulk([1000]), {})
        self.assertEqual(Article.objects.in_bulk([]), {})
        self.assertEqual(
            Article.objects.in_bulk(iter([self.a1.id])), {self.a1.id: self.a1}
        )
        self.assertEqual(Article.objects.in_bulk(iter([])), {})
        with self.assertRaises(TypeError):
            Article.objects.in_bulk(headline__startswith="Blah")

    def test_in_bulk_lots_of_ids(self):
        """
        Tests the in_bulk method of the Author model when retrieving a large number of objects by ID.

        This test ensures that the in_bulk method can efficiently handle a large number of IDs and
        performs the expected number of database queries. The test creates a large number of Author
        objects in the database, then uses the in_bulk method to retrieve all of them in bulk,
        verifying that the method returns the correct objects and performs the expected number of queries.

        The test takes into account the maximum number of query parameters allowed by the database
        connection, and adjusts the expected number of queries accordingly. This ensures that the test
        is robust and works correctly with different database configurations.
        """
        test_range = 2000
        max_query_params = connection.features.max_query_params
        expected_num_queries = (
            ceil(test_range / max_query_params) if max_query_params else 1
        )
        Author.objects.bulk_create(
            [Author() for i in range(test_range - Author.objects.count())]
        )
        authors = {author.pk: author for author in Author.objects.all()}
        with self.assertNumQueries(expected_num_queries):
            self.assertEqual(Author.objects.in_bulk(authors), authors)

    def test_in_bulk_with_field(self):
        self.assertEqual(
            Article.objects.in_bulk(
                [self.a1.slug, self.a2.slug, self.a3.slug], field_name="slug"
            ),
            {
                self.a1.slug: self.a1,
                self.a2.slug: self.a2,
                self.a3.slug: self.a3,
            },
        )

    def test_in_bulk_meta_constraint(self):
        season_2011 = Season.objects.create(year=2011)
        season_2012 = Season.objects.create(year=2012)
        Season.objects.create(year=2013)
        self.assertEqual(
            Season.objects.in_bulk(
                [season_2011.year, season_2012.year],
                field_name="year",
            ),
            {season_2011.year: season_2011, season_2012.year: season_2012},
        )

    def test_in_bulk_non_unique_field(self):
        """
        Tests that in_bulk() raises a ValueError when the specified field_name is not unique.

            This test case ensures that the in_bulk() method correctly validates its input parameters.
            Specifically, it checks that a ValueError is raised when the field_name parameter refers to
            a non-unique field, as in_bulk() requires unique fields to operate correctly.

            :raises ValueError: if the field_name parameter is not a unique field
        """
        msg = "in_bulk()'s field_name must be a unique field but 'author' isn't."
        with self.assertRaisesMessage(ValueError, msg):
            Article.objects.in_bulk([self.au1], field_name="author")

    @skipUnlessDBFeature("can_distinct_on_fields")
    def test_in_bulk_preserve_ordering(self):
        articles = (
            Article.objects.order_by("author_id", "-pub_date")
            .distinct("author_id")
            .in_bulk([self.au1.id, self.au2.id], field_name="author_id")
        )
        self.assertEqual(
            articles,
            {self.au1.id: self.a4, self.au2.id: self.a5},
        )

    @skipUnlessDBFeature("can_distinct_on_fields")
    def test_in_bulk_preserve_ordering_with_batch_size(self):
        """

        Tests that the in_bulk() method preserves the specified ordering when 
        retrieving objects in batches, with the distinct() method applied to 
        specific fields. The test ensures that when the database connection has 
        limited query parameters, the method correctly retrieves the objects 
        while maintaining the order specified by the order_by() method and 
        preserving distinct values based on the specified field name.

        """
        old_max_query_params = connection.features.max_query_params
        connection.features.max_query_params = 1
        try:
            articles = (
                Article.objects.order_by("author_id", "-pub_date")
                .distinct("author_id")
                .in_bulk([self.au1.id, self.au2.id], field_name="author_id")
            )
            self.assertEqual(
                articles,
                {self.au1.id: self.a4, self.au2.id: self.a5},
            )
        finally:
            connection.features.max_query_params = old_max_query_params

    @skipUnlessDBFeature("can_distinct_on_fields")
    def test_in_bulk_distinct_field(self):
        self.assertEqual(
            Article.objects.order_by("headline")
            .distinct("headline")
            .in_bulk(
                [self.a1.headline, self.a5.headline],
                field_name="headline",
            ),
            {self.a1.headline: self.a1, self.a5.headline: self.a5},
        )

    @skipUnlessDBFeature("can_distinct_on_fields")
    def test_in_bulk_multiple_distinct_field(self):
        """
        Tests that in_bulk() raises a ValueError when the specified field_name is not unique.

            This test case checks that an exception is raised when attempting to use a non-unique
            field to retrieve objects in bulk, ensuring that the method enforces its constraints
            correctly. It verifies that the error message includes the name of the non-unique field.

            The test covers a scenario where a model's QuerySet is ordered by multiple fields and
            then filtered to include distinct results based on those fields. It then attempts to
            retrieve the objects in bulk using a field that is not guaranteed to be unique, which
            should result in a ValueError being raised.
        """
        msg = "in_bulk()'s field_name must be a unique field but 'pub_date' isn't."
        with self.assertRaisesMessage(ValueError, msg):
            Article.objects.order_by("headline", "pub_date").distinct(
                "headline",
                "pub_date",
            ).in_bulk(field_name="pub_date")

    @isolate_apps("lookup")
    def test_in_bulk_non_unique_meta_constaint(self):
        """

        Tests that the in_bulk method raises a ValueError when the field_name is not a unique field.

        This test case covers non-unique meta constraint validation, specifically scenarios where
        the specified field_name is part of a unique constraint but not the only field in that constraint.
        It verifies that attempting to call in_bulk with such a field_name results in a ValueError with
        an informative error message.

        """
        class Model(models.Model):
            ean = models.CharField(max_length=100)
            brand = models.CharField(max_length=100)
            name = models.CharField(max_length=80)

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["ean"],
                        name="partial_ean_unique",
                        condition=models.Q(is_active=True),
                    ),
                    models.UniqueConstraint(
                        fields=["brand", "name"],
                        name="together_brand_name_unique",
                    ),
                ]

        msg = "in_bulk()'s field_name must be a unique field but '%s' isn't."
        for field_name in ["brand", "ean"]:
            with self.subTest(field_name=field_name):
                with self.assertRaisesMessage(ValueError, msg % field_name):
                    Model.objects.in_bulk(field_name=field_name)

    def test_in_bulk_sliced_queryset(self):
        """
        Tests that using the 'in_bulk' method on a sliced QuerySet raises a TypeError.

         The function attempts to retrieve a subset of objects from a QuerySet using slicing and then applies 'in_bulk' to fetch the objects with specified IDs. It verifies that this operation raises a TypeError with the expected error message, as 'in_bulk' does not support 'limit' or 'offset' operations.
        """
        msg = "Cannot use 'limit' or 'offset' with in_bulk()."
        with self.assertRaisesMessage(TypeError, msg):
            Article.objects.all()[0:5].in_bulk([self.a1.id, self.a2.id])

    def test_values(self):
        # values() returns a list of dictionaries instead of object instances --
        # and you can specify which fields you want to retrieve.
        """

        Tests various usage scenarios of the Django ORM values() method.

        This test case verifies that the values() method can be used to retrieve
        specific fields from the database, including fields from related models.
        It also checks that the extra() method can be used in conjunction with values()
        to perform database-level calculations.

        Additionally, this test case covers the usage of values() with filter() and
        order_by() methods, as well as the behavior of values() when used with
        iterator() or when the model instance is filtered to a single object.

        Furthermore, it tests that the FieldError exception is raised when an invalid
        field name is used with the values() method.

        """
        self.assertSequenceEqual(
            Article.objects.values("headline"),
            [
                {"headline": "Article 5"},
                {"headline": "Article 6"},
                {"headline": "Article 4"},
                {"headline": "Article 2"},
                {"headline": "Article 3"},
                {"headline": "Article 7"},
                {"headline": "Article 1"},
            ],
        )
        self.assertSequenceEqual(
            Article.objects.filter(pub_date__exact=datetime(2005, 7, 27)).values("id"),
            [{"id": self.a2.id}, {"id": self.a3.id}, {"id": self.a7.id}],
        )
        self.assertSequenceEqual(
            Article.objects.values("id", "headline"),
            [
                {"id": self.a5.id, "headline": "Article 5"},
                {"id": self.a6.id, "headline": "Article 6"},
                {"id": self.a4.id, "headline": "Article 4"},
                {"id": self.a2.id, "headline": "Article 2"},
                {"id": self.a3.id, "headline": "Article 3"},
                {"id": self.a7.id, "headline": "Article 7"},
                {"id": self.a1.id, "headline": "Article 1"},
            ],
        )
        # You can use values() with iterator() for memory savings,
        # because iterator() uses database-level iteration.
        self.assertSequenceEqual(
            list(Article.objects.values("id", "headline").iterator()),
            [
                {"headline": "Article 5", "id": self.a5.id},
                {"headline": "Article 6", "id": self.a6.id},
                {"headline": "Article 4", "id": self.a4.id},
                {"headline": "Article 2", "id": self.a2.id},
                {"headline": "Article 3", "id": self.a3.id},
                {"headline": "Article 7", "id": self.a7.id},
                {"headline": "Article 1", "id": self.a1.id},
            ],
        )
        # The values() method works with "extra" fields specified in extra(select).
        self.assertSequenceEqual(
            Article.objects.extra(select={"id_plus_one": "id + 1"}).values(
                "id", "id_plus_one"
            ),
            [
                {"id": self.a5.id, "id_plus_one": self.a5.id + 1},
                {"id": self.a6.id, "id_plus_one": self.a6.id + 1},
                {"id": self.a4.id, "id_plus_one": self.a4.id + 1},
                {"id": self.a2.id, "id_plus_one": self.a2.id + 1},
                {"id": self.a3.id, "id_plus_one": self.a3.id + 1},
                {"id": self.a7.id, "id_plus_one": self.a7.id + 1},
                {"id": self.a1.id, "id_plus_one": self.a1.id + 1},
            ],
        )
        data = {
            "id_plus_one": "id+1",
            "id_plus_two": "id+2",
            "id_plus_three": "id+3",
            "id_plus_four": "id+4",
            "id_plus_five": "id+5",
            "id_plus_six": "id+6",
            "id_plus_seven": "id+7",
            "id_plus_eight": "id+8",
        }
        self.assertSequenceEqual(
            Article.objects.filter(id=self.a1.id).extra(select=data).values(*data),
            [
                {
                    "id_plus_one": self.a1.id + 1,
                    "id_plus_two": self.a1.id + 2,
                    "id_plus_three": self.a1.id + 3,
                    "id_plus_four": self.a1.id + 4,
                    "id_plus_five": self.a1.id + 5,
                    "id_plus_six": self.a1.id + 6,
                    "id_plus_seven": self.a1.id + 7,
                    "id_plus_eight": self.a1.id + 8,
                }
            ],
        )
        # You can specify fields from forward and reverse relations, just like filter().
        self.assertSequenceEqual(
            Article.objects.values("headline", "author__name"),
            [
                {"headline": self.a5.headline, "author__name": self.au2.name},
                {"headline": self.a6.headline, "author__name": self.au2.name},
                {"headline": self.a4.headline, "author__name": self.au1.name},
                {"headline": self.a2.headline, "author__name": self.au1.name},
                {"headline": self.a3.headline, "author__name": self.au1.name},
                {"headline": self.a7.headline, "author__name": self.au2.name},
                {"headline": self.a1.headline, "author__name": self.au1.name},
            ],
        )
        self.assertSequenceEqual(
            Author.objects.values("name", "article__headline").order_by(
                "name", "article__headline"
            ),
            [
                {"name": self.au1.name, "article__headline": self.a1.headline},
                {"name": self.au1.name, "article__headline": self.a2.headline},
                {"name": self.au1.name, "article__headline": self.a3.headline},
                {"name": self.au1.name, "article__headline": self.a4.headline},
                {"name": self.au2.name, "article__headline": self.a5.headline},
                {"name": self.au2.name, "article__headline": self.a6.headline},
                {"name": self.au2.name, "article__headline": self.a7.headline},
            ],
        )
        self.assertSequenceEqual(
            (
                Author.objects.values(
                    "name", "article__headline", "article__tag__name"
                ).order_by("name", "article__headline", "article__tag__name")
            ),
            [
                {
                    "name": self.au1.name,
                    "article__headline": self.a1.headline,
                    "article__tag__name": self.t1.name,
                },
                {
                    "name": self.au1.name,
                    "article__headline": self.a2.headline,
                    "article__tag__name": self.t1.name,
                },
                {
                    "name": self.au1.name,
                    "article__headline": self.a3.headline,
                    "article__tag__name": self.t1.name,
                },
                {
                    "name": self.au1.name,
                    "article__headline": self.a3.headline,
                    "article__tag__name": self.t2.name,
                },
                {
                    "name": self.au1.name,
                    "article__headline": self.a4.headline,
                    "article__tag__name": self.t2.name,
                },
                {
                    "name": self.au2.name,
                    "article__headline": self.a5.headline,
                    "article__tag__name": self.t2.name,
                },
                {
                    "name": self.au2.name,
                    "article__headline": self.a5.headline,
                    "article__tag__name": self.t3.name,
                },
                {
                    "name": self.au2.name,
                    "article__headline": self.a6.headline,
                    "article__tag__name": self.t3.name,
                },
                {
                    "name": self.au2.name,
                    "article__headline": self.a7.headline,
                    "article__tag__name": self.t3.name,
                },
            ],
        )
        # However, an exception FieldDoesNotExist will be thrown if you specify
        # a nonexistent field name in values() (a field that is neither in the
        # model nor in extra(select)).
        msg = (
            "Cannot resolve keyword 'id_plus_two' into field. Choices are: "
            "author, author_id, headline, id, id_plus_one, pub_date, slug, tag"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Article.objects.extra(select={"id_plus_one": "id + 1"}).values(
                "id", "id_plus_two"
            )
        # If you don't specify field names to values(), all are returned.
        self.assertSequenceEqual(
            Article.objects.filter(id=self.a5.id).values(),
            [
                {
                    "id": self.a5.id,
                    "author_id": self.au2.id,
                    "headline": "Article 5",
                    "pub_date": datetime(2005, 8, 1, 9, 0),
                    "slug": "a5",
                }
            ],
        )

    def test_values_list(self):
        # values_list() is similar to values(), except that the results are
        # returned as a list of tuples, rather than a list of dictionaries.
        # Within each tuple, the order of the elements is the same as the order
        # of fields in the values_list() call.
        """
        Tests various ways of using values_list() to retrieve values or ordered lists of values from the database.

            This function performs several tests on a database of Article objects, 
            including ordering and retrieving values for 'headline' and 'id', 
            as well as performing extra selects and joins on the database. 

            It also tests for edge cases, such as the use of flat=True with multiple field names, 
            which should raise a TypeError. 

            The function does not return any values, but rather uses assertSequenceEqual 
            to check that the retrieved values match the expected output.
        """
        self.assertSequenceEqual(
            Article.objects.values_list("headline"),
            [
                ("Article 5",),
                ("Article 6",),
                ("Article 4",),
                ("Article 2",),
                ("Article 3",),
                ("Article 7",),
                ("Article 1",),
            ],
        )
        self.assertSequenceEqual(
            Article.objects.values_list("id").order_by("id"),
            [
                (self.a1.id,),
                (self.a2.id,),
                (self.a3.id,),
                (self.a4.id,),
                (self.a5.id,),
                (self.a6.id,),
                (self.a7.id,),
            ],
        )
        self.assertSequenceEqual(
            Article.objects.values_list("id", flat=True).order_by("id"),
            [
                self.a1.id,
                self.a2.id,
                self.a3.id,
                self.a4.id,
                self.a5.id,
                self.a6.id,
                self.a7.id,
            ],
        )
        self.assertSequenceEqual(
            Article.objects.extra(select={"id_plus_one": "id+1"})
            .order_by("id")
            .values_list("id"),
            [
                (self.a1.id,),
                (self.a2.id,),
                (self.a3.id,),
                (self.a4.id,),
                (self.a5.id,),
                (self.a6.id,),
                (self.a7.id,),
            ],
        )
        self.assertSequenceEqual(
            Article.objects.extra(select={"id_plus_one": "id+1"})
            .order_by("id")
            .values_list("id_plus_one", "id"),
            [
                (self.a1.id + 1, self.a1.id),
                (self.a2.id + 1, self.a2.id),
                (self.a3.id + 1, self.a3.id),
                (self.a4.id + 1, self.a4.id),
                (self.a5.id + 1, self.a5.id),
                (self.a6.id + 1, self.a6.id),
                (self.a7.id + 1, self.a7.id),
            ],
        )
        self.assertSequenceEqual(
            Article.objects.extra(select={"id_plus_one": "id+1"})
            .order_by("id")
            .values_list("id", "id_plus_one"),
            [
                (self.a1.id, self.a1.id + 1),
                (self.a2.id, self.a2.id + 1),
                (self.a3.id, self.a3.id + 1),
                (self.a4.id, self.a4.id + 1),
                (self.a5.id, self.a5.id + 1),
                (self.a6.id, self.a6.id + 1),
                (self.a7.id, self.a7.id + 1),
            ],
        )
        args = ("name", "article__headline", "article__tag__name")
        self.assertSequenceEqual(
            Author.objects.values_list(*args).order_by(*args),
            [
                (self.au1.name, self.a1.headline, self.t1.name),
                (self.au1.name, self.a2.headline, self.t1.name),
                (self.au1.name, self.a3.headline, self.t1.name),
                (self.au1.name, self.a3.headline, self.t2.name),
                (self.au1.name, self.a4.headline, self.t2.name),
                (self.au2.name, self.a5.headline, self.t2.name),
                (self.au2.name, self.a5.headline, self.t3.name),
                (self.au2.name, self.a6.headline, self.t3.name),
                (self.au2.name, self.a7.headline, self.t3.name),
            ],
        )
        with self.assertRaises(TypeError):
            Article.objects.values_list("id", "headline", flat=True)

    def test_get_next_previous_by(self):
        # Every DateField and DateTimeField creates get_next_by_FOO() and
        # get_previous_by_FOO() methods. In the case of identical date values,
        # these methods will use the ID as a fallback check. This guarantees
        # that no records are skipped or duplicated.
        self.assertEqual(repr(self.a1.get_next_by_pub_date()), "<Article: Article 2>")
        self.assertEqual(repr(self.a2.get_next_by_pub_date()), "<Article: Article 3>")
        self.assertEqual(
            repr(self.a2.get_next_by_pub_date(headline__endswith="6")),
            "<Article: Article 6>",
        )
        self.assertEqual(repr(self.a3.get_next_by_pub_date()), "<Article: Article 7>")
        self.assertEqual(repr(self.a4.get_next_by_pub_date()), "<Article: Article 6>")
        with self.assertRaises(Article.DoesNotExist):
            self.a5.get_next_by_pub_date()
        self.assertEqual(repr(self.a6.get_next_by_pub_date()), "<Article: Article 5>")
        self.assertEqual(repr(self.a7.get_next_by_pub_date()), "<Article: Article 4>")

        self.assertEqual(
            repr(self.a7.get_previous_by_pub_date()), "<Article: Article 3>"
        )
        self.assertEqual(
            repr(self.a6.get_previous_by_pub_date()), "<Article: Article 4>"
        )
        self.assertEqual(
            repr(self.a5.get_previous_by_pub_date()), "<Article: Article 6>"
        )
        self.assertEqual(
            repr(self.a4.get_previous_by_pub_date()), "<Article: Article 7>"
        )
        self.assertEqual(
            repr(self.a3.get_previous_by_pub_date()), "<Article: Article 2>"
        )
        self.assertEqual(
            repr(self.a2.get_previous_by_pub_date()), "<Article: Article 1>"
        )

    def test_escaping(self):
        # Underscores, percent signs and backslashes have special meaning in the
        # underlying SQL code, but Django handles the quoting of them automatically.
        a8 = Article.objects.create(
            headline="Article_ with underscore", pub_date=datetime(2005, 11, 20)
        )

        self.assertSequenceEqual(
            Article.objects.filter(headline__startswith="Article"),
            [a8, self.a5, self.a6, self.a4, self.a2, self.a3, self.a7, self.a1],
        )
        self.assertSequenceEqual(
            Article.objects.filter(headline__startswith="Article_"),
            [a8],
        )
        a9 = Article.objects.create(
            headline="Article% with percent sign", pub_date=datetime(2005, 11, 21)
        )
        self.assertSequenceEqual(
            Article.objects.filter(headline__startswith="Article"),
            [a9, a8, self.a5, self.a6, self.a4, self.a2, self.a3, self.a7, self.a1],
        )
        self.assertSequenceEqual(
            Article.objects.filter(headline__startswith="Article%"),
            [a9],
        )
        a10 = Article.objects.create(
            headline="Article with \\ backslash", pub_date=datetime(2005, 11, 22)
        )
        self.assertSequenceEqual(
            Article.objects.filter(headline__contains="\\"),
            [a10],
        )

    def test_exclude(self):
        """
        Tests the exclude method for querying Article objects.

        This test case creates several Article objects with varying headlines 
        and checks that the exclude method correctly filters out objects 
        based on the provided criteria, such as headlines containing 
        specific strings or starting with certain patterns, as well as 
        excluding exact headline matches. The results are verified against 
        expected sequences of Article objects.

        The test covers the following scenarios:
        - Excluding headlines containing a specific string
        - Excluding headlines starting with a certain pattern
        - Excluding exact headline matches
        """
        a8 = Article.objects.create(
            headline="Article_ with underscore", pub_date=datetime(2005, 11, 20)
        )
        a9 = Article.objects.create(
            headline="Article% with percent sign", pub_date=datetime(2005, 11, 21)
        )
        a10 = Article.objects.create(
            headline="Article with \\ backslash", pub_date=datetime(2005, 11, 22)
        )
        # exclude() is the opposite of filter() when doing lookups:
        self.assertSequenceEqual(
            Article.objects.filter(headline__contains="Article").exclude(
                headline__contains="with"
            ),
            [self.a5, self.a6, self.a4, self.a2, self.a3, self.a7, self.a1],
        )
        self.assertSequenceEqual(
            Article.objects.exclude(headline__startswith="Article_"),
            [a10, a9, self.a5, self.a6, self.a4, self.a2, self.a3, self.a7, self.a1],
        )
        self.assertSequenceEqual(
            Article.objects.exclude(headline="Article 7"),
            [a10, a9, a8, self.a5, self.a6, self.a4, self.a2, self.a3, self.a1],
        )

    def test_none(self):
        # none() returns a QuerySet that behaves like any other QuerySet object
        self.assertSequenceEqual(Article.objects.none(), [])
        self.assertSequenceEqual(
            Article.objects.none().filter(headline__startswith="Article"), []
        )
        self.assertSequenceEqual(
            Article.objects.filter(headline__startswith="Article").none(), []
        )
        self.assertEqual(Article.objects.none().count(), 0)
        self.assertEqual(
            Article.objects.none().update(headline="This should not take effect"), 0
        )
        self.assertSequenceEqual(list(Article.objects.none().iterator()), [])

    def test_in(self):
        self.assertSequenceEqual(
            Article.objects.exclude(id__in=[]),
            [self.a5, self.a6, self.a4, self.a2, self.a3, self.a7, self.a1],
        )

    def test_in_empty_list(self):
        self.assertSequenceEqual(Article.objects.filter(id__in=[]), [])

    def test_in_different_database(self):
        """
        Raises a ValueError when attempting to use subqueries across different databases.

        This test case demonstrates the restriction imposed by the ORM when a subquery references a different database than the main query.

        It verifies that a ValueError is raised with an informative message, suggesting a possible workaround by forcing the inner query to be evaluated as a list.
        """
        with self.assertRaisesMessage(
            ValueError,
            "Subqueries aren't allowed across different databases. Force the "
            "inner query to be evaluated using `list(inner_query)`.",
        ):
            list(Article.objects.filter(id__in=Article.objects.using("other").all()))

    def test_in_keeps_value_ordering(self):
        query = (
            Article.objects.filter(slug__in=["a%d" % i for i in range(1, 8)])
            .values("pk")
            .query
        )
        self.assertIn(" IN (a1, a2, a3, a4, a5, a6, a7) ", str(query))

    def test_in_ignore_none(self):
        """
        Test that the database query properly ignores None values when using the 'in' operator to filter objects by id.

        The function verifies that a query filtering objects by id, where one of the ids is None, returns the expected results and that the generated SQL query correctly handles the None value.
        """
        with self.assertNumQueries(1) as ctx:
            self.assertSequenceEqual(
                Article.objects.filter(id__in=[None, self.a1.id]),
                [self.a1],
            )
        sql = ctx.captured_queries[0]["sql"]
        self.assertIn("IN (%s)" % self.a1.pk, sql)

    def test_in_ignore_solo_none(self):
        with self.assertNumQueries(0):
            self.assertSequenceEqual(Article.objects.filter(id__in=[None]), [])

    def test_in_ignore_none_with_unhashable_items(self):
        class UnhashableInt(int):
            __hash__ = None

        with self.assertNumQueries(1) as ctx:
            self.assertSequenceEqual(
                Article.objects.filter(id__in=[None, UnhashableInt(self.a1.id)]),
                [self.a1],
            )
        sql = ctx.captured_queries[0]["sql"]
        self.assertIn("IN (%s)" % self.a1.pk, sql)

    def test_error_messages(self):
        # Programming errors are pointed out with nice error messages
        """
        Tests error messages raised when attempting to filter articles by an invalid field.

        Verifies that a FieldError is raised with a descriptive message when trying to filter articles using a non-existent field ('pub_date_year'), providing a list of available fields as part of the error message.
        """
        with self.assertRaisesMessage(
            FieldError,
            "Cannot resolve keyword 'pub_date_year' into field. Choices are: "
            "author, author_id, headline, id, pub_date, slug, tag",
        ):
            Article.objects.filter(pub_date_year="2005").count()

    def test_unsupported_lookups(self):
        """
        Tests the behavior of Django's ORM when attempting to use unsupported lookup types on model fields.

        The function verifies that the correct FieldError is raised for various invalid lookup types, including:

        - Using a lookup type that is not supported by the field (e.g. 'starts' on a CharField)
        - Using a lookup type that is not recognized by Django (e.g. 'is_null', 'gobbledygook')
        - Incorrectly using double underscores to chain lookups (e.g. 'gt__foo')
        - Using a lookup type that is almost correct, but not quite (e.g. 'gt__', 'gt__lt')

        This test case helps ensure that the ORM correctly validates and raises informative errors for users when they attempt to use invalid lookup types.
        """
        with self.assertRaisesMessage(
            FieldError,
            "Unsupported lookup 'starts' for CharField or join on the field "
            "not permitted, perhaps you meant startswith or istartswith?",
        ):
            Article.objects.filter(headline__starts="Article")

        with self.assertRaisesMessage(
            FieldError,
            "Unsupported lookup 'is_null' for DateTimeField or join on the field "
            "not permitted, perhaps you meant isnull?",
        ):
            Article.objects.filter(pub_date__is_null=True)

        with self.assertRaisesMessage(
            FieldError,
            "Unsupported lookup 'gobbledygook' for DateTimeField or join on the field "
            "not permitted.",
        ):
            Article.objects.filter(pub_date__gobbledygook="blahblah")

        with self.assertRaisesMessage(
            FieldError,
            "Unsupported lookup 'gt__foo' for DateTimeField or join on the field "
            "not permitted, perhaps you meant gt or gte?",
        ):
            Article.objects.filter(pub_date__gt__foo="blahblah")

        with self.assertRaisesMessage(
            FieldError,
            "Unsupported lookup 'gt__' for DateTimeField or join on the field "
            "not permitted, perhaps you meant gt or gte?",
        ):
            Article.objects.filter(pub_date__gt__="blahblah")

        with self.assertRaisesMessage(
            FieldError,
            "Unsupported lookup 'gt__lt' for DateTimeField or join on the field "
            "not permitted, perhaps you meant gt or gte?",
        ):
            Article.objects.filter(pub_date__gt__lt="blahblah")

        with self.assertRaisesMessage(
            FieldError,
            "Unsupported lookup 'gt__lt__foo' for DateTimeField or join"
            " on the field not permitted, perhaps you meant gt or gte?",
        ):
            Article.objects.filter(pub_date__gt__lt__foo="blahblah")

    def test_unsupported_lookups_custom_lookups(self):
        slug_field = Article._meta.get_field("slug")
        msg = (
            "Unsupported lookup 'lengtp' for SlugField or join on the field not "
            "permitted, perhaps you meant length?"
        )
        with self.assertRaisesMessage(FieldError, msg):
            with register_lookup(slug_field, Length):
                Article.objects.filter(slug__lengtp=20)

    def test_relation_nested_lookup_error(self):
        # An invalid nested lookup on a related field raises a useful error.
        """

        Tests that attempting to perform a nested lookup using a ForeignKey or join 
        on a field that does not permit it raises a FieldError with a descriptive 
        error message.

        The test checks this behavior for both a lookup across a single relationship 
        (in this case, an article's author's editor's name) and a lookup using an 
        invalid field name ('foo') on a relationship (in this case, between tags 
        and articles).

        The expected error messages are verified to ensure they provide useful 
        feedback to the user about the cause of the error.

        """
        msg = (
            "Unsupported lookup 'editor__name' for ForeignKey or join on the field not "
            "permitted."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Article.objects.filter(author__editor__name="James")
        msg = (
            "Unsupported lookup 'foo' for ForeignKey or join on the field not "
            "permitted."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Tag.objects.filter(articles__foo="bar")

    def test_unsupported_lookup_reverse_foreign_key(self):
        """

        Tests that an unsupported lookup on a reverse foreign key raises a FieldError.

        Verifies that attempting to filter on a related object's field using an unsupported
        lookup type (in this case, 'title') raises an exception with the expected error message.

        This test ensures that the ORM correctly handles invalid lookup types and provides
        informative error messages to help with debugging.

        """
        msg = (
            "Unsupported lookup 'title' for ManyToOneRel or join on the field not "
            "permitted."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.filter(article__title="Article 1")

    def test_unsupported_lookup_reverse_foreign_key_custom_lookups(self):
        """
        Tests that attempting to use an unsupported lookup type on a reverse foreign key raises the correct FieldError.

        This test verifies that when a custom lookup is applied to a field, attempting to use a different lookup name that is not supported for ManyToOneRel or joins will result in a FieldError with a helpful error message that suggests the correct lookup name to use.
        """
        msg = (
            "Unsupported lookup 'abspl' for ManyToOneRel or join on the field not "
            "permitted, perhaps you meant abspk?"
        )
        fk_field = Article._meta.get_field("author")
        with self.assertRaisesMessage(FieldError, msg):
            with register_lookup(fk_field, Abs, lookup_name="abspk"):
                Author.objects.filter(article__abspl=2)

    def test_filter_by_reverse_related_field_transform(self):
        fk_field = Article._meta.get_field("author")
        with register_lookup(fk_field, Abs):
            self.assertSequenceEqual(
                Author.objects.filter(article__abs=self.a1.pk), [self.au1]
            )

    def test_regex(self):
        # Create some articles with a bit more interesting headlines for
        # testing field lookups.
        """
        Tests the functionality of Django's ORM regular expression lookups, 
        including the following use cases:
            * Matching article headlines against various regular expressions
            * Testing case-sensitive and case-insensitive matching
            * Using character classes, optional characters, and start/end of string anchors
            * Using groups and alternatives in regular expressions
            * Ensuring correct matching and non-matching of articles against a variety of patterns

        The test covers a range of scenarios to ensure that the ORM's regex 
        filtering behaves as expected and returns the correct results.
        """
        Article.objects.all().delete()
        now = datetime.now()
        Article.objects.bulk_create(
            [
                Article(pub_date=now, headline="f"),
                Article(pub_date=now, headline="fo"),
                Article(pub_date=now, headline="foo"),
                Article(pub_date=now, headline="fooo"),
                Article(pub_date=now, headline="hey-Foo"),
                Article(pub_date=now, headline="bar"),
                Article(pub_date=now, headline="AbBa"),
                Article(pub_date=now, headline="baz"),
                Article(pub_date=now, headline="baxZ"),
            ]
        )
        # zero-or-more
        self.assertQuerySetEqual(
            Article.objects.filter(headline__regex=r"fo*"),
            Article.objects.filter(headline__in=["f", "fo", "foo", "fooo"]),
        )
        self.assertQuerySetEqual(
            Article.objects.filter(headline__iregex=r"fo*"),
            Article.objects.filter(headline__in=["f", "fo", "foo", "fooo", "hey-Foo"]),
        )
        # one-or-more
        self.assertQuerySetEqual(
            Article.objects.filter(headline__regex=r"fo+"),
            Article.objects.filter(headline__in=["fo", "foo", "fooo"]),
        )
        # wildcard
        self.assertQuerySetEqual(
            Article.objects.filter(headline__regex=r"fooo?"),
            Article.objects.filter(headline__in=["foo", "fooo"]),
        )
        # leading anchor
        self.assertQuerySetEqual(
            Article.objects.filter(headline__regex=r"^b"),
            Article.objects.filter(headline__in=["bar", "baxZ", "baz"]),
        )
        self.assertQuerySetEqual(
            Article.objects.filter(headline__iregex=r"^a"),
            Article.objects.filter(headline="AbBa"),
        )
        # trailing anchor
        self.assertQuerySetEqual(
            Article.objects.filter(headline__regex=r"z$"),
            Article.objects.filter(headline="baz"),
        )
        self.assertQuerySetEqual(
            Article.objects.filter(headline__iregex=r"z$"),
            Article.objects.filter(headline__in=["baxZ", "baz"]),
        )
        # character sets
        self.assertQuerySetEqual(
            Article.objects.filter(headline__regex=r"ba[rz]"),
            Article.objects.filter(headline__in=["bar", "baz"]),
        )
        self.assertQuerySetEqual(
            Article.objects.filter(headline__regex=r"ba.[RxZ]"),
            Article.objects.filter(headline="baxZ"),
        )
        self.assertQuerySetEqual(
            Article.objects.filter(headline__iregex=r"ba[RxZ]"),
            Article.objects.filter(headline__in=["bar", "baxZ", "baz"]),
        )

        # and more articles:
        Article.objects.bulk_create(
            [
                Article(pub_date=now, headline="foobar"),
                Article(pub_date=now, headline="foobaz"),
                Article(pub_date=now, headline="ooF"),
                Article(pub_date=now, headline="foobarbaz"),
                Article(pub_date=now, headline="zoocarfaz"),
                Article(pub_date=now, headline="barfoobaz"),
                Article(pub_date=now, headline="bazbaRFOO"),
            ]
        )

        # alternation
        self.assertQuerySetEqual(
            Article.objects.filter(headline__regex=r"oo(f|b)"),
            Article.objects.filter(
                headline__in=[
                    "barfoobaz",
                    "foobar",
                    "foobarbaz",
                    "foobaz",
                ]
            ),
        )
        self.assertQuerySetEqual(
            Article.objects.filter(headline__iregex=r"oo(f|b)"),
            Article.objects.filter(
                headline__in=[
                    "barfoobaz",
                    "foobar",
                    "foobarbaz",
                    "foobaz",
                    "ooF",
                ]
            ),
        )
        self.assertQuerySetEqual(
            Article.objects.filter(headline__regex=r"^foo(f|b)"),
            Article.objects.filter(headline__in=["foobar", "foobarbaz", "foobaz"]),
        )

        # greedy matching
        self.assertQuerySetEqual(
            Article.objects.filter(headline__regex=r"b.*az"),
            Article.objects.filter(
                headline__in=[
                    "barfoobaz",
                    "baz",
                    "bazbaRFOO",
                    "foobarbaz",
                    "foobaz",
                ]
            ),
        )
        self.assertQuerySetEqual(
            Article.objects.filter(headline__iregex=r"b.*ar"),
            Article.objects.filter(
                headline__in=[
                    "bar",
                    "barfoobaz",
                    "bazbaRFOO",
                    "foobar",
                    "foobarbaz",
                ]
            ),
        )

    @skipUnlessDBFeature("supports_regex_backreferencing")
    def test_regex_backreferencing(self):
        # grouping and backreferences
        """

        Tests the functionality of regular expression backreferencing in the database.

        This test creates a set of Article objects with varying headlines and then uses a regular expression to filter the objects.
        The regular expression 'b(.).*b\\1' matches any string that contains a sequence 'b', followed by any character (captured as group 1), 
        then any characters, and finally 'b' and the captured character again (backreferenced as \\1).

        The test asserts that the filter returns the expected headlines, demonstrating that the database supports backreferencing in regular expressions.

        """
        now = datetime.now()
        Article.objects.bulk_create(
            [
                Article(pub_date=now, headline="foobar"),
                Article(pub_date=now, headline="foobaz"),
                Article(pub_date=now, headline="ooF"),
                Article(pub_date=now, headline="foobarbaz"),
                Article(pub_date=now, headline="zoocarfaz"),
                Article(pub_date=now, headline="barfoobaz"),
                Article(pub_date=now, headline="bazbaRFOO"),
            ]
        )
        self.assertQuerySetEqual(
            Article.objects.filter(headline__regex=r"b(.).*b\1").values_list(
                "headline", flat=True
            ),
            ["barfoobaz", "bazbaRFOO", "foobarbaz"],
        )

    def test_regex_null(self):
        """
        A regex lookup does not fail on null/None values
        """
        Season.objects.create(year=2012, gt=None)
        self.assertQuerySetEqual(Season.objects.filter(gt__regex=r"^$"), [])

    def test_textfield_exact_null(self):
        with self.assertNumQueries(1) as ctx:
            self.assertSequenceEqual(Author.objects.filter(bio=None), [self.au2])
        # Columns with IS NULL condition are not wrapped (except PostgreSQL).
        bio_column = connection.ops.quote_name(Author._meta.get_field("bio").column)
        self.assertIn(f"{bio_column} IS NULL", ctx.captured_queries[0]["sql"])

    def test_regex_non_string(self):
        """
        A regex lookup does not fail on non-string fields
        """
        s = Season.objects.create(year=2013, gt=444)
        self.assertQuerySetEqual(Season.objects.filter(gt__regex=r"^444$"), [s])

    def test_regex_non_ascii(self):
        """
        A regex lookup does not trip on non-ASCII characters.
        """
        Player.objects.create(name="\u2660")
        Player.objects.get(name__regex="\u2660")

    def test_nonfield_lookups(self):
        """
        A lookup query containing non-fields raises the proper exception.
        """
        msg = (
            "Unsupported lookup 'blahblah' for CharField or join on the field not "
            "permitted."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Article.objects.filter(headline__blahblah=99)
        msg = (
            "Unsupported lookup 'blahblah__exact' for CharField or join "
            "on the field not permitted."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Article.objects.filter(headline__blahblah__exact=99)
        msg = (
            "Cannot resolve keyword 'blahblah' into field. Choices are: "
            "author, author_id, headline, id, pub_date, slug, tag"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Article.objects.filter(blahblah=99)

    def test_lookup_collision(self):
        """
        Genuine field names don't collide with built-in lookup types
        ('year', 'gt', 'range', 'in' etc.) (#11670).
        """
        # 'gt' is used as a code number for the year, e.g. 111=>2009.
        season_2009 = Season.objects.create(year=2009, gt=111)
        season_2009.games.create(home="Houston Astros", away="St. Louis Cardinals")
        season_2010 = Season.objects.create(year=2010, gt=222)
        season_2010.games.create(home="Houston Astros", away="Chicago Cubs")
        season_2010.games.create(home="Houston Astros", away="Milwaukee Brewers")
        season_2010.games.create(home="Houston Astros", away="St. Louis Cardinals")
        season_2011 = Season.objects.create(year=2011, gt=333)
        season_2011.games.create(home="Houston Astros", away="St. Louis Cardinals")
        season_2011.games.create(home="Houston Astros", away="Milwaukee Brewers")
        hunter_pence = Player.objects.create(name="Hunter Pence")
        hunter_pence.games.set(Game.objects.filter(season__year__in=[2009, 2010]))
        pudge = Player.objects.create(name="Ivan Rodriquez")
        pudge.games.set(Game.objects.filter(season__year=2009))
        pedro_feliz = Player.objects.create(name="Pedro Feliz")
        pedro_feliz.games.set(Game.objects.filter(season__year__in=[2011]))
        johnson = Player.objects.create(name="Johnson")
        johnson.games.set(Game.objects.filter(season__year__in=[2011]))

        # Games in 2010
        self.assertEqual(Game.objects.filter(season__year=2010).count(), 3)
        self.assertEqual(Game.objects.filter(season__year__exact=2010).count(), 3)
        self.assertEqual(Game.objects.filter(season__gt=222).count(), 3)
        self.assertEqual(Game.objects.filter(season__gt__exact=222).count(), 3)

        # Games in 2011
        self.assertEqual(Game.objects.filter(season__year=2011).count(), 2)
        self.assertEqual(Game.objects.filter(season__year__exact=2011).count(), 2)
        self.assertEqual(Game.objects.filter(season__gt=333).count(), 2)
        self.assertEqual(Game.objects.filter(season__gt__exact=333).count(), 2)
        self.assertEqual(Game.objects.filter(season__year__gt=2010).count(), 2)
        self.assertEqual(Game.objects.filter(season__gt__gt=222).count(), 2)

        # Games played in 2010 and 2011
        self.assertEqual(Game.objects.filter(season__year__in=[2010, 2011]).count(), 5)
        self.assertEqual(Game.objects.filter(season__year__gt=2009).count(), 5)
        self.assertEqual(Game.objects.filter(season__gt__in=[222, 333]).count(), 5)
        self.assertEqual(Game.objects.filter(season__gt__gt=111).count(), 5)

        # Players who played in 2009
        self.assertEqual(
            Player.objects.filter(games__season__year=2009).distinct().count(), 2
        )
        self.assertEqual(
            Player.objects.filter(games__season__year__exact=2009).distinct().count(), 2
        )
        self.assertEqual(
            Player.objects.filter(games__season__gt=111).distinct().count(), 2
        )
        self.assertEqual(
            Player.objects.filter(games__season__gt__exact=111).distinct().count(), 2
        )

        # Players who played in 2010
        self.assertEqual(
            Player.objects.filter(games__season__year=2010).distinct().count(), 1
        )
        self.assertEqual(
            Player.objects.filter(games__season__year__exact=2010).distinct().count(), 1
        )
        self.assertEqual(
            Player.objects.filter(games__season__gt=222).distinct().count(), 1
        )
        self.assertEqual(
            Player.objects.filter(games__season__gt__exact=222).distinct().count(), 1
        )

        # Players who played in 2011
        self.assertEqual(
            Player.objects.filter(games__season__year=2011).distinct().count(), 2
        )
        self.assertEqual(
            Player.objects.filter(games__season__year__exact=2011).distinct().count(), 2
        )
        self.assertEqual(
            Player.objects.filter(games__season__gt=333).distinct().count(), 2
        )
        self.assertEqual(
            Player.objects.filter(games__season__year__gt=2010).distinct().count(), 2
        )
        self.assertEqual(
            Player.objects.filter(games__season__gt__gt=222).distinct().count(), 2
        )

    def test_chain_date_time_lookups(self):
        self.assertCountEqual(
            Article.objects.filter(pub_date__month__gt=7),
            [self.a5, self.a6],
        )
        self.assertCountEqual(
            Article.objects.filter(pub_date__day__gte=27),
            [self.a2, self.a3, self.a4, self.a7],
        )
        self.assertCountEqual(
            Article.objects.filter(pub_date__hour__lt=8),
            [self.a1, self.a2, self.a3, self.a4, self.a7],
        )
        self.assertCountEqual(
            Article.objects.filter(pub_date__minute__lte=0),
            [self.a1, self.a2, self.a3, self.a4, self.a5, self.a6, self.a7],
        )

    def test_exact_none_transform(self):
        """Transforms are used for __exact=None."""
        Season.objects.create(year=1, nulled_text_field="not null")
        self.assertFalse(Season.objects.filter(nulled_text_field__isnull=True))
        self.assertTrue(Season.objects.filter(nulled_text_field__nulled__isnull=True))
        self.assertTrue(Season.objects.filter(nulled_text_field__nulled__exact=None))
        self.assertTrue(Season.objects.filter(nulled_text_field__nulled=None))

    def test_exact_sliced_queryset_limit_one(self):
        self.assertCountEqual(
            Article.objects.filter(author=Author.objects.all()[:1]),
            [self.a1, self.a2, self.a3, self.a4],
        )

    def test_exact_sliced_queryset_limit_one_offset(self):
        self.assertCountEqual(
            Article.objects.filter(author=Author.objects.all()[1:2]),
            [self.a5, self.a6, self.a7],
        )

    def test_exact_sliced_queryset_not_limited_to_one(self):
        msg = (
            "The QuerySet value for an exact lookup must be limited to one "
            "result using slicing."
        )
        with self.assertRaisesMessage(ValueError, msg):
            list(Article.objects.filter(author=Author.objects.all()[:2]))
        with self.assertRaisesMessage(ValueError, msg):
            list(Article.objects.filter(author=Author.objects.all()[1:]))

    @skipUnless(connection.vendor == "mysql", "MySQL-specific workaround.")
    def test_exact_booleanfield(self):
        # MySQL ignores indexes with boolean fields unless they're compared
        # directly to a boolean value.
        """
        Tests the exact querying of a BooleanField in the database, specifically addressing a MySQL-specific workaround.

        This test ensures that when filtering on a BooleanField, the resulting query correctly incorporates the boolean value.
        It verifies that the query returns the expected results and that the query string accurately represents the filter condition.

        The test case covers the creation of database objects, filtering on a boolean field, and validation of the query results and query string.
        It provides assurance that the BooleanField filtering works as expected in the context of the MySQL database backend.
        """
        product = Product.objects.create(name="Paper", qty_target=5000)
        Stock.objects.create(product=product, short=False, qty_available=5100)
        stock_1 = Stock.objects.create(product=product, short=True, qty_available=180)
        qs = Stock.objects.filter(short=True)
        self.assertSequenceEqual(qs, [stock_1])
        self.assertIn(
            "%s = True" % connection.ops.quote_name("short"),
            str(qs.query),
        )

    @skipUnless(connection.vendor == "mysql", "MySQL-specific workaround.")
    def test_exact_booleanfield_annotation(self):
        # MySQL ignores indexes with boolean fields unless they're compared
        # directly to a boolean value.
        """
        Tests the exact boolean field annotation for a MySQL database.

        This test case verifies that the Case and Exists annotations, as well as the ExpressionWrapper, correctly filter objects based on a boolean condition.
        It checks that the generated SQL query is correct and that the results match the expected output.

        The test is divided into three scenarios:

        * Using a Case annotation to filter objects based on a boolean condition
        * Using an ExpressionWrapper to filter objects based on a boolean condition
        * Using an Exists annotation to filter objects based on a boolean condition

        For each scenario, the test checks that the resulting query set matches the expected output and that the generated SQL query contains the expected condition.
        """
        qs = Author.objects.annotate(
            case=Case(
                When(alias="a1", then=True),
                default=False,
                output_field=BooleanField(),
            )
        ).filter(case=True)
        self.assertSequenceEqual(qs, [self.au1])
        self.assertIn(" = True", str(qs.query))

        qs = Author.objects.annotate(
            wrapped=ExpressionWrapper(Q(alias="a1"), output_field=BooleanField()),
        ).filter(wrapped=True)
        self.assertSequenceEqual(qs, [self.au1])
        self.assertIn(" = True", str(qs.query))
        # EXISTS(...) shouldn't be compared to a boolean value.
        qs = Author.objects.annotate(
            exists=Exists(Author.objects.filter(alias="a1", pk=OuterRef("pk"))),
        ).filter(exists=True)
        self.assertSequenceEqual(qs, [self.au1])
        self.assertNotIn(" = True", str(qs.query))

    def test_custom_field_none_rhs(self):
        """
        __exact=value is transformed to __isnull=True if Field.get_prep_value()
        converts value to None.
        """
        season = Season.objects.create(year=2012, nulled_text_field=None)
        self.assertTrue(
            Season.objects.filter(pk=season.pk, nulled_text_field__isnull=True)
        )
        self.assertTrue(Season.objects.filter(pk=season.pk, nulled_text_field=""))

    def test_pattern_lookups_with_substr(self):
        """

        Tests pattern lookups on Author model with Substr function.

        This test case checks the functionality of Django's ORM lookups (startswith, istartswith, contains, icontains, endswith, iendswith)
        when used with the Substr function on the 'alias' field of the Author model.

        It verifies the correct authors are returned for each lookup type, ensuring case sensitivity and substring matching behave as expected.

        """
        a = Author.objects.create(name="John Smith", alias="Johx")
        b = Author.objects.create(name="Rhonda Simpson", alias="sonx")
        tests = (
            ("startswith", [a]),
            ("istartswith", [a]),
            ("contains", [a, b]),
            ("icontains", [a, b]),
            ("endswith", [b]),
            ("iendswith", [b]),
        )
        for lookup, result in tests:
            with self.subTest(lookup=lookup):
                authors = Author.objects.filter(
                    **{"name__%s" % lookup: Substr("alias", 1, 3)}
                )
                self.assertCountEqual(authors, result)

    def test_custom_lookup_none_rhs(self):
        """Lookup.can_use_none_as_rhs=True allows None as a lookup value."""
        season = Season.objects.create(year=2012, nulled_text_field=None)
        query = Season.objects.get_queryset().query
        field = query.model._meta.get_field("nulled_text_field")
        self.assertIsInstance(
            query.build_lookup(["isnull_none_rhs"], field, None), IsNullWithNoneAsRHS
        )
        self.assertTrue(
            Season.objects.filter(pk=season.pk, nulled_text_field__isnull_none_rhs=True)
        )

    def test_exact_exists(self):
        """

        Tests that every Season object has an exact matching Article object.

        Verifies that each Season exists in the Article model by joining the two models
        on their primary keys and asserting that the resulting Season query set is
        equivalent to the complete set of Season objects. This ensures that every Season
        has a corresponding Article, and vice versa.

        """
        qs = Article.objects.filter(pk=OuterRef("pk"))
        seasons = Season.objects.annotate(pk_exists=Exists(qs)).filter(
            pk_exists=Exists(qs),
        )
        self.assertCountEqual(seasons, Season.objects.all())

    def test_nested_outerref_lhs(self):
        """

        Tests the usage of nested OuterRef in the Left-Hand Side of a subquery.

        This test case verifies that the OuterRef expression can be correctly nested
        within another OuterRef expression to reference a table and use it for 
        annotating a queryset. The test specifically checks that the reference to 
        the 'name' field of the Tag model is properly resolved in a subquery, 
        allowing for the correct identification of tags that have a matching author alias.

        """
        tag = Tag.objects.create(name=self.au1.alias)
        tag.articles.add(self.a1)
        qs = Tag.objects.annotate(
            has_author_alias_match=Exists(
                Article.objects.annotate(
                    author_exists=Exists(
                        Author.objects.filter(alias=OuterRef(OuterRef("name")))
                    ),
                ).filter(author_exists=True)
            ),
        )
        self.assertEqual(qs.get(has_author_alias_match=True), tag)

    def test_exact_query_rhs_with_selected_columns(self):
        """

        Tests the retrieval of authors using an exact query with the 'id' column selected.

        Verifies that filtering authors by the maximum 'id' value with a specific 'name' returns the most recently created author with that name.

        The test covers the case where the query is executed with the 'id' column specified, ensuring that the correct author object is retrieved from the database.

        """
        newest_author = Author.objects.create(name="Author 2")
        authors_max_ids = (
            Author.objects.filter(
                name="Author 2",
            )
            .values(
                "name",
            )
            .annotate(
                max_id=Max("id"),
            )
            .values("max_id")
        )
        authors = Author.objects.filter(id=authors_max_ids[:1])
        self.assertEqual(authors.get(), newest_author)

    def test_isnull_non_boolean_value(self):
        """
        Checks if a ValueError is raised when a non-boolean value is used for an 'isnull' lookup in a QuerySet.
        The function tests various QuerySet scenarios, ensuring they fail with a ValueError when 'isnull' is assigned a value other than True or False, providing a clear and specific error message.
        The test covers different model fields and related objects to guarantee consistency in error handling across various use cases.
        """
        msg = "The QuerySet value for an isnull lookup must be True or False."
        tests = [
            Author.objects.filter(alias__isnull=1),
            Article.objects.filter(author__isnull=1),
            Season.objects.filter(games__isnull=1),
            Freebie.objects.filter(stock__isnull=1),
        ]
        for qs in tests:
            with self.subTest(qs=qs):
                with self.assertRaisesMessage(ValueError, msg):
                    qs.exists()

    def test_isnull_textfield(self):
        self.assertSequenceEqual(
            Author.objects.filter(bio__isnull=True),
            [self.au2],
        )
        self.assertSequenceEqual(
            Author.objects.filter(bio__isnull=False),
            [self.au1],
        )

    def test_lookup_rhs(self):
        product = Product.objects.create(name="GME", qty_target=5000)
        stock_1 = Stock.objects.create(product=product, short=True, qty_available=180)
        stock_2 = Stock.objects.create(product=product, short=False, qty_available=5100)
        Stock.objects.create(product=product, short=False, qty_available=4000)
        self.assertCountEqual(
            Stock.objects.filter(short=Q(qty_available__lt=F("product__qty_target"))),
            [stock_1, stock_2],
        )
        self.assertCountEqual(
            Stock.objects.filter(
                short=ExpressionWrapper(
                    Q(qty_available__lt=F("product__qty_target")),
                    output_field=BooleanField(),
                )
            ),
            [stock_1, stock_2],
        )

    def test_lookup_direct_value_rhs_unwrapped(self):
        """
        Tests that a lookup with a direct value on the right-hand side returns the expected results.

        The test verifies that the GreaterThan lookup with the value 2 on the left and the unwrapped value 1 on the right correctly filters the Author objects and generates the expected SQL query.

        It checks that exactly one database query is executed and that the query contains the condition '2 > 1'. The test also verifies that at least one Author object meets the filter condition, i.e., its value is greater than 1.
        """
        with self.assertNumQueries(1) as ctx:
            self.assertIs(Author.objects.filter(GreaterThan(2, 1)).exists(), True)
        # Direct values on RHS are not wrapped.
        self.assertIn("2 > 1", ctx.captured_queries[0]["sql"])


class LookupQueryingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Set up test data for the class.

        This method creates a set of predefined test data, including multiple seasons and games.
        It initializes three seasons with different years and a set of games associated with these seasons.
        The test data is used to support testing of the class functionality.

        The setup includes:

        * Three seasons with distinct years
        * A set of games associated with the seasons, including home and away teams

        This test data provides a foundation for testing various scenarios and edge cases,
        allowing for more comprehensive testing of the class's behavior and functionality.
        """
        cls.s1 = Season.objects.create(year=1942, gt=1942)
        cls.s2 = Season.objects.create(year=1842, gt=1942, nulled_text_field="text")
        cls.s3 = Season.objects.create(year=2042, gt=1942)
        Game.objects.create(season=cls.s1, home="NY", away="Boston")
        Game.objects.create(season=cls.s1, home="NY", away="Tampa")
        Game.objects.create(season=cls.s3, home="Boston", away="Tampa")

    def test_annotate(self):
        """
        Tests the use of Django's built-in database functions for annotation in a query.

        This test case verifies that the annotation correctly identifies and marks
        seasons from a specific year, in this instance 1942, by comparing the actual
        year with the target value using an exact match.

        The expected result is a query set where each season is annotated with a
        boolean indicating whether its year matches the target value, and the test
        asserts that the count and values of the annotated fields match the expected
        output for the given test data. 
        """
        qs = Season.objects.annotate(equal=Exact(F("year"), 1942))
        self.assertCountEqual(
            qs.values_list("year", "equal"),
            ((1942, True), (1842, False), (2042, False)),
        )

    def test_alias(self):
        qs = Season.objects.alias(greater=GreaterThan(F("year"), 1910))
        self.assertCountEqual(qs.filter(greater=True), [self.s1, self.s3])

    def test_annotate_value_greater_than_value(self):
        qs = Season.objects.annotate(greater=GreaterThan(Value(40), Value(30)))
        self.assertCountEqual(
            qs.values_list("year", "greater"),
            ((1942, True), (1842, True), (2042, True)),
        )

    def test_annotate_field_greater_than_field(self):
        """
        Tests the annotation of a model field with a greater than condition between two fields.

        This test case verifies that the GreaterThan function correctly annotates a queryset with a boolean value indicating whether one field's value is greater than another. It checks the result for multiple records, ensuring that the annotation accurately reflects the comparison between the fields. The test passes if the annotated queryset matches the expected output for all records.
        """
        qs = Season.objects.annotate(greater=GreaterThan(F("year"), F("gt")))
        self.assertCountEqual(
            qs.values_list("year", "greater"),
            ((1942, False), (1842, False), (2042, True)),
        )

    def test_annotate_field_greater_than_value(self):
        qs = Season.objects.annotate(greater=GreaterThan(F("year"), Value(1930)))
        self.assertCountEqual(
            qs.values_list("year", "greater"),
            ((1942, True), (1842, False), (2042, True)),
        )

    def test_annotate_field_greater_than_literal(self):
        """

        Tests the GreaterThan annotation for a model field being greater than a literal value.

        Verifies that the GreaterThan annotation correctly identifies whether a model field value 
        exceeds a specified literal value, using the 'year' field of the Season model as an example.

        """
        qs = Season.objects.annotate(greater=GreaterThan(F("year"), 1930))
        self.assertCountEqual(
            qs.values_list("year", "greater"),
            ((1942, True), (1842, False), (2042, True)),
        )

    def test_annotate_literal_greater_than_field(self):
        """
        Tests the annotation of a QuerySet with a 'greater_than' field comparison.

        This test case verifies that the GreaterThan annotation correctly identifies 
        whether a literal value (1930) is greater than the 'year' field in a Season object.
        The test evaluates the annotation for three different years and checks that the 
        results match the expected output, demonstrating the correctness of the comparison.

        """
        qs = Season.objects.annotate(greater=GreaterThan(1930, F("year")))
        self.assertCountEqual(
            qs.values_list("year", "greater"),
            ((1942, False), (1842, True), (2042, False)),
        )

    def test_annotate_less_than_float(self):
        """
        Tests the annotation of a queryset with a LessThan condition for floating point values.

        This test case verifies that the annotation correctly identifies rows where the 'year' field is less than a given floating point value.
        It checks the results against expected values to ensure the annotation is applied accurately.

        Args:
            None

        Returns:
            None

        Notes:
            This test is part of the larger test suite and should be run in conjunction with other tests to ensure comprehensive coverage.

        """
        qs = Season.objects.annotate(lesser=LessThan(F("year"), 1942.1))
        self.assertCountEqual(
            qs.values_list("year", "lesser"),
            ((1942, True), (1842, True), (2042, False)),
        )

    def test_annotate_greater_than_or_equal(self):
        qs = Season.objects.annotate(greater=GreaterThanOrEqual(F("year"), 1942))
        self.assertCountEqual(
            qs.values_list("year", "greater"),
            ((1942, True), (1842, False), (2042, True)),
        )

    def test_annotate_greater_than_or_equal_float(self):
        """
        Tests the annotation of a seasonal dataset to identify records where the year is greater than or equal to a given floating-point value.

        This test case verifies that the GreaterThanOrEqual annotation correctly evaluates floating-point values and returns the expected results, distinguishing between years that meet the condition and those that do not. The test data includes years before, at, and after the specified threshold to ensure comprehensive coverage of the annotation's behavior.
        """
        qs = Season.objects.annotate(greater=GreaterThanOrEqual(F("year"), 1942.1))
        self.assertCountEqual(
            qs.values_list("year", "greater"),
            ((1942, False), (1842, False), (2042, True)),
        )

    def test_combined_lookups(self):
        expression = Exact(F("year"), 1942) | GreaterThan(F("year"), 1942)
        qs = Season.objects.annotate(gte=expression)
        self.assertCountEqual(
            qs.values_list("year", "gte"),
            ((1942, True), (1842, False), (2042, True)),
        )

    def test_lookup_in_filter(self):
        qs = Season.objects.filter(GreaterThan(F("year"), 1910))
        self.assertCountEqual(qs, [self.s1, self.s3])

    def test_isnull_lookup_in_filter(self):
        self.assertSequenceEqual(
            Season.objects.filter(IsNull(F("nulled_text_field"), False)),
            [self.s2],
        )
        self.assertCountEqual(
            Season.objects.filter(IsNull(F("nulled_text_field"), True)),
            [self.s1, self.s3],
        )

    def test_filter_lookup_lhs(self):
        qs = Season.objects.annotate(before_20=LessThan(F("year"), 2000)).filter(
            before_20=LessThan(F("year"), 1900),
        )
        self.assertCountEqual(qs, [self.s2, self.s3])

    def test_filter_wrapped_lookup_lhs(self):
        """

        Tests the filter functionality on a wrapped lookup expression for the left-hand side of a query.

        Verifies that the correct seasons are returned when applying a filter to a boolean-annotated field,
        which is then compared to a value using a less than operator. The expected result is evaluated
        to ensure it matches the queried data.

        """
        qs = (
            Season.objects.annotate(
                before_20=ExpressionWrapper(
                    Q(year__lt=2000),
                    output_field=BooleanField(),
                )
            )
            .filter(before_20=LessThan(F("year"), 1900))
            .values_list("year", flat=True)
        )
        self.assertCountEqual(qs, [1842, 2042])

    def test_filter_exists_lhs(self):
        qs = Season.objects.annotate(
            before_20=Exists(
                Season.objects.filter(pk=OuterRef("pk"), year__lt=2000),
            )
        ).filter(before_20=LessThan(F("year"), 1900))
        self.assertCountEqual(qs, [self.s2, self.s3])

    def test_filter_subquery_lhs(self):
        qs = Season.objects.annotate(
            before_20=Subquery(
                Season.objects.filter(pk=OuterRef("pk")).values(
                    lesser=LessThan(F("year"), 2000),
                ),
            )
        ).filter(before_20=LessThan(F("year"), 1900))
        self.assertCountEqual(qs, [self.s2, self.s3])

    def test_combined_lookups_in_filter(self):
        """
        Tests the functionality of combining lookup expressions in a filter query.

        This test verifies that the filter method correctly applies a logical OR operation
        between two lookup expressions, returning a QuerySet containing objects that match
        either of the conditions.

        The test checks for seasons where the year is exactly 1942 or greater than 1942,
        ensuring that the resulting QuerySet contains the expected seasons.

        :testobjective: Validate the correct application of combined lookup expressions in filters.
        """
        expression = Exact(F("year"), 1942) | GreaterThan(F("year"), 1942)
        qs = Season.objects.filter(expression)
        self.assertCountEqual(qs, [self.s1, self.s3])

    def test_combined_annotated_lookups_in_filter(self):
        expression = Exact(F("year"), 1942) | GreaterThan(F("year"), 1942)
        qs = Season.objects.annotate(gte=expression).filter(gte=True)
        self.assertCountEqual(qs, [self.s1, self.s3])

    def test_combined_annotated_lookups_in_filter_false(self):
        """

        Tests the behavior of combining annotated lookups in a filter query with a False condition.

        This test case verifies that the filter method correctly applies the combined annotation
        to a query, and returns the expected results when the annotated expression evaluates to False.

        The test involves creating an annotation that checks for a condition using an Exact and 
        a GreaterThan comparison on the 'year' field, then using this annotation to filter a 
        queryset and asserting the result matches the expected sequence of objects.

        """
        expression = Exact(F("year"), 1942) | GreaterThan(F("year"), 1942)
        qs = Season.objects.annotate(gte=expression).filter(gte=False)
        self.assertSequenceEqual(qs, [self.s2])

    def test_lookup_in_order_by(self):
        """
        Tests the lookup in an ordered sequence using LessThan and ordering by year.

        This test case verifies that objects are returned in the correct order when 
        LessThan function and field ordering are applied. It checks that the 
        ordering matches the expected sequence, ensuring that the LessThan function 
        correctly filters the results and the objects are ordered as expected by their year value.
        """
        qs = Season.objects.order_by(LessThan(F("year"), 1910), F("year"))
        self.assertSequenceEqual(qs, [self.s1, self.s3, self.s2])

    def test_aggregate_combined_lookup(self):
        """
        Tests the aggregation of a combined lookup expression by casting a greater-than condition to an integer field and summing the results, verifying that the correct count of modern seasons (those after 1900) is returned.
        """
        expression = Cast(GreaterThan(F("year"), 1900), models.IntegerField())
        qs = Season.objects.aggregate(modern=models.Sum(expression))
        self.assertEqual(qs["modern"], 2)

    def test_conditional_expression(self):
        """

        Tests the usage of conditional expressions with Django's ORM.

        This function checks if a given year can be correctly annotated with its corresponding century using a conditional expression.
        The test case covers years within the 20th century (between 1901 and 2000) and years outside of this range.
        It verifies that the resulting query set contains the expected year and century annotations.

        """
        qs = Season.objects.annotate(
            century=Case(
                When(
                    GreaterThan(F("year"), 1900) & LessThanOrEqual(F("year"), 2000),
                    then=Value("20th"),
                ),
                default=Value("other"),
            )
        ).values("year", "century")
        self.assertCountEqual(
            qs,
            [
                {"year": 1942, "century": "20th"},
                {"year": 1842, "century": "other"},
                {"year": 2042, "century": "other"},
            ],
        )

    def test_multivalued_join_reuse(self):
        self.assertEqual(
            Season.objects.get(Exact(F("games__home"), "NY"), games__away="Boston"),
            self.s1,
        )
        self.assertEqual(
            Season.objects.get(Exact(F("games__home"), "NY") & Q(games__away="Boston")),
            self.s1,
        )
        self.assertEqual(
            Season.objects.get(
                Exact(F("games__home"), "NY") & Exact(F("games__away"), "Boston")
            ),
            self.s1,
        )
