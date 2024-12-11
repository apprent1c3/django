import datetime
from decimal import Decimal

from django.db.models import (
    Avg,
    Case,
    Count,
    Exists,
    F,
    Max,
    OuterRef,
    Q,
    StdDev,
    Subquery,
    Sum,
    Variance,
    When,
)
from django.test import TestCase
from django.test.utils import Approximate

from .models import Author, Book, Publisher


class FilteredAggregateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a1 = Author.objects.create(name="test", age=40)
        cls.a2 = Author.objects.create(name="test2", age=60)
        cls.a3 = Author.objects.create(name="test3", age=100)
        cls.p1 = Publisher.objects.create(
            name="Apress", num_awards=3, duration=datetime.timedelta(days=1)
        )
        cls.b1 = Book.objects.create(
            isbn="159059725",
            name="The Definitive Guide to Django: Web Development Done Right",
            pages=447,
            rating=4.5,
            price=Decimal("30.00"),
            contact=cls.a1,
            publisher=cls.p1,
            pubdate=datetime.date(2007, 12, 6),
        )
        cls.b2 = Book.objects.create(
            isbn="067232959",
            name="Sams Teach Yourself Django in 24 Hours",
            pages=528,
            rating=3.0,
            price=Decimal("23.09"),
            contact=cls.a2,
            publisher=cls.p1,
            pubdate=datetime.date(2008, 3, 3),
        )
        cls.b3 = Book.objects.create(
            isbn="159059996",
            name="Practical Django Projects",
            pages=600,
            rating=4.5,
            price=Decimal("29.69"),
            contact=cls.a3,
            publisher=cls.p1,
            pubdate=datetime.date(2008, 6, 23),
        )
        cls.a1.friends.add(cls.a2)
        cls.a1.friends.add(cls.a3)
        cls.b1.authors.add(cls.a1)
        cls.b1.authors.add(cls.a3)
        cls.b2.authors.add(cls.a2)
        cls.b3.authors.add(cls.a3)

    def test_filtered_aggregates(self):
        agg = Sum("age", filter=Q(name__startswith="test"))
        self.assertEqual(Author.objects.aggregate(age=agg)["age"], 200)

    def test_filtered_numerical_aggregates(self):
        """

        Tests the calculation of numerical aggregates with filtering.

        Verifies that various numerical aggregate functions (average, standard deviation, and variance)
        are correctly applied to a filtered dataset. The test checks if the results match the expected
        values when the data is filtered based on a specific condition.

        The test uses the Author model and filters the data to include only records where the 'name' field
        starts with 'test'. It then calculates the numerical aggregates for the 'age' field and compares
        the results with the predefined expected values.

        The test ensures that the aggregate functions work correctly with filtered data and provides
        confidence in the accuracy of the results. 

        Parameters
        ----------
        None

        Returns
        -------
        None

        Raises
        ------
        AssertionError: If the calculated aggregate value does not match the expected result.

        """
        for aggregate, expected_result in (
            (Avg, Approximate(66.7, 1)),
            (StdDev, Approximate(24.9, 1)),
            (Variance, Approximate(622.2, 1)),
        ):
            with self.subTest(aggregate=aggregate.__name__):
                agg = aggregate("age", filter=Q(name__startswith="test"))
                self.assertEqual(
                    Author.objects.aggregate(age=agg)["age"], expected_result
                )

    def test_double_filtered_aggregates(self):
        """

        Tests the functionality of filtered aggregates within Django QuerySets.

        Specifically, this test case verifies that a Sum aggregate operation on the 'age' field
        can be successfully applied with a complex filter, which includes both an inclusion and
        exclusion criterion. The test validates the correctness of the aggregated result by asserting
        its expected value.

        It demonstrates the use of the Q object to construct compound filters and ensure that only
        relevant data is included in the aggregation calculation.

        """
        agg = Sum("age", filter=Q(Q(name="test2") & ~Q(name="test")))
        self.assertEqual(Author.objects.aggregate(age=agg)["age"], 60)

    def test_excluded_aggregates(self):
        agg = Sum("age", filter=~Q(name="test2"))
        self.assertEqual(Author.objects.aggregate(age=agg)["age"], 140)

    def test_related_aggregates_m2m(self):
        """

        Tests the calculation of aggregates on related models with many-to-many relationships.

        Specifically, this test case verifies that the Sum aggregation function correctly 
        calculates the total age of friends of an author, excluding friends with a specific name.

        The test uses a queryset to filter authors with a certain name, and then applies the 
        aggregate function to the filtered queryset, ensuring the expected result is returned.

        """
        agg = Sum("friends__age", filter=~Q(friends__name="test"))
        self.assertEqual(
            Author.objects.filter(name="test").aggregate(age=agg)["age"], 160
        )

    def test_related_aggregates_m2m_and_fk(self):
        """

        Tests that the aggregate function correctly sums related fields over a many-to-many relationship,
        applying a filter to exclude certain records.

        The test verifies that the total pages of books from a specific publisher, associated with a particular author's friends,
        excluding friends with a certain name, matches the expected value.

        """
        q = Q(friends__book__publisher__name="Apress") & ~Q(friends__name="test3")
        agg = Sum("friends__book__pages", filter=q)
        self.assertEqual(
            Author.objects.filter(name="test").aggregate(pages=agg)["pages"], 528
        )

    def test_plain_annotate(self):
        """

        Tests the annotation of Author objects with a Sum aggregation over related Book instances,
        filtered by a specific rating condition, and verifies the resulting annotated values.

        The test covers the following:
            - Annotation with a Sum aggregation over related objects.
            - Filtering of related objects based on a specific condition.
            - Ordering of the annotated queryset by primary key.

        The expected outcome is a queryset of Author objects with annotated 'pages' values, 
        where the values match the specified sequence, indicating correct annotation and filtering.

        """
        agg = Sum("book__pages", filter=Q(book__rating__gt=3))
        qs = Author.objects.annotate(pages=agg).order_by("pk")
        self.assertSequenceEqual([a.pages for a in qs], [447, None, 1047])

    def test_filtered_aggregate_on_annotate(self):
        """
        Tests the application of filtered aggregate on annotated fields.

        This test case verifies the correctness of annotating an aggregate value 
        ('total_pages') based on a related field ('book__pages'), and then 
        applying another aggregate ('summed_age') on the annotated field with 
        a filter condition ('total_pages__gte=400'). The test asserts that the 
        resulting aggregated value matches the expected output.

        Args:
            None

        Returns:
            None

        Notes:
            This test case relies on the presence of Author objects with related 
            Book instances and their respective ratings and pages.

        """
        pages_annotate = Sum("book__pages", filter=Q(book__rating__gt=3))
        age_agg = Sum("age", filter=Q(total_pages__gte=400))
        aggregated = Author.objects.annotate(total_pages=pages_annotate).aggregate(
            summed_age=age_agg
        )
        self.assertEqual(aggregated, {"summed_age": 140})

    def test_case_aggregate(self):
        agg = Sum(
            Case(When(friends__age=40, then=F("friends__age"))),
            filter=Q(friends__name__startswith="test"),
        )
        self.assertEqual(Author.objects.aggregate(age=agg)["age"], 80)

    def test_sum_star_exception(self):
        msg = "Star cannot be used with filter. Please specify a field."
        with self.assertRaisesMessage(ValueError, msg):
            Count("*", filter=Q(age=40))

    def test_filtered_reused_subquery(self):
        """
        Tests that a filtered reused subquery correctly identifies Authors with at least two older friends.

        This test ensures that the subquery to count the number of friends older than the Author is applied correctly to the QuerySet of Authors, 
        and that the resulting QuerySet contains only Authors meeting the specified condition.

        It verifies the result by checking if the Author instance with the most older friends is correctly retrieved from the filtered QuerySet.
        """
        qs = Author.objects.annotate(
            older_friends_count=Count("friends", filter=Q(friends__age__gt=F("age"))),
        ).filter(
            older_friends_count__gte=2,
        )
        self.assertEqual(qs.get(pk__in=qs.values("pk")), self.a1)

    def test_filtered_aggregate_ref_annotation(self):
        """
        Tests the filtered aggregate ref annotation functionality.

        This test case checks if an aggregate reference can be filtered correctly based on an annotated value.
        It verifies that the aggregate count is calculated accurately when filtered by a condition applied to the annotated field.

        The test uses a query to annotate authors with their double age and then aggregates the count of authors
        where the double age is greater than 100, ensuring that the result matches the expected count of 2.

        Returns:
            None

        Raises:
            AssertionError: If the aggregate count does not match the expected value.

        """
        aggs = Author.objects.annotate(double_age=F("age") * 2).aggregate(
            cnt=Count("pk", filter=Q(double_age__gt=100)),
        )
        self.assertEqual(aggs["cnt"], 2)

    def test_filtered_aggregate_ref_subquery_annotation(self):
        """
        Tests the functionality of annotating a queryset with a subquery and then applying a filter to an aggregate operation.

        The test checks if the proper count of authors is returned when their earliest book was published in a specific year, leveraging Django's ORM to perform the query. 
        It verifies that the result correctly reflects the number of authors matching the specified condition.
        """
        aggs = Author.objects.annotate(
            earliest_book_year=Subquery(
                Book.objects.filter(
                    contact__pk=OuterRef("pk"),
                )
                .order_by("pubdate")
                .values("pubdate__year")[:1]
            ),
        ).aggregate(
            cnt=Count("pk", filter=Q(earliest_book_year=2008)),
        )
        self.assertEqual(aggs["cnt"], 2)

    def test_filtered_aggregate_ref_multiple_subquery_annotation(self):
        """

        Tests the filtered aggregate reference for multiple subquery annotations.

        This function verifies that the aggregate function correctly filters and aggregates 
        the maximum rating of books that have authors and where these authors do not have 
        other books. It checks the result against an expected value.

        The test covers the scenario where a book's rating is considered only if it has 
        at least one author, and none of these authors are associated with any other books. 
        The maximum rating from such books is then compared to the expected value.

        """
        aggregate = (
            Book.objects.values("publisher")
            .annotate(
                has_authors=Exists(
                    Book.authors.through.objects.filter(book=OuterRef("pk")),
                ),
                authors_have_other_books=Exists(
                    Book.objects.filter(
                        authors__in=Author.objects.filter(
                            book_contact_set=OuterRef(OuterRef("pk")),
                        )
                    ).exclude(pk=OuterRef("pk")),
                ),
            )
            .aggregate(
                max_rating=Max(
                    "rating",
                    filter=Q(has_authors=True, authors_have_other_books=False),
                )
            )
        )
        self.assertEqual(aggregate, {"max_rating": 4.5})

    def test_filtered_aggregate_on_exists(self):
        """

        Tests the filtered aggregate functionality on a model field when a related object exists.

        This function verifies that the maximum rating of a book can be correctly aggregated
        when filtering for books that have at least one author. It checks if the calculated
        maximum rating matches the expected value.

        The test uses the Exists lookup to filter books based on the existence of a related
        author, and then applies the Max aggregation function to calculate the maximum rating
        of the filtered books.

        :param none:
        :raises AssertionError: if the calculated maximum rating does not match the expected value
        :return: none

        """
        aggregate = Book.objects.values("publisher").aggregate(
            max_rating=Max(
                "rating",
                filter=Exists(
                    Book.authors.through.objects.filter(book=OuterRef("pk")),
                ),
            ),
        )
        self.assertEqual(aggregate, {"max_rating": 4.5})

    def test_filtered_aggregate_empty_condition(self):
        book = Book.objects.annotate(
            authors_count=Count(
                "authors",
                filter=Q(authors__in=[]),
            ),
        ).get(pk=self.b1.pk)
        self.assertEqual(book.authors_count, 0)
        aggregate = Book.objects.aggregate(
            max_rating=Max("rating", filter=Q(rating__in=[]))
        )
        self.assertEqual(aggregate, {"max_rating": None})

    def test_filtered_aggregate_full_condition(self):
        book = Book.objects.annotate(
            authors_count=Count(
                "authors",
                filter=~Q(authors__in=[]),
            ),
        ).get(pk=self.b1.pk)
        self.assertEqual(book.authors_count, 2)
        aggregate = Book.objects.aggregate(
            max_rating=Max("rating", filter=~Q(rating__in=[]))
        )
        self.assertEqual(aggregate, {"max_rating": 4.5})
