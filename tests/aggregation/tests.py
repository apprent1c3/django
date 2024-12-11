import datetime
import math
import re
from decimal import Decimal

from django.core.exceptions import FieldError
from django.db import connection
from django.db.models import (
    Avg,
    Case,
    Count,
    DateField,
    DateTimeField,
    DecimalField,
    DurationField,
    Exists,
    F,
    FloatField,
    IntegerField,
    Max,
    Min,
    OuterRef,
    Q,
    StdDev,
    Subquery,
    Sum,
    TimeField,
    Transform,
    Value,
    Variance,
    When,
    Window,
)
from django.db.models.expressions import Func, RawSQL
from django.db.models.functions import (
    Cast,
    Coalesce,
    Greatest,
    Least,
    Lower,
    Mod,
    Now,
    Pi,
    TruncDate,
    TruncHour,
)
from django.test import TestCase
from django.test.testcases import skipUnlessDBFeature
from django.test.utils import Approximate, CaptureQueriesContext
from django.utils import timezone

from .models import Author, Book, Publisher, Store


class NowUTC(Now):
    template = "CURRENT_TIMESTAMP"
    output_field = DateTimeField()

    def as_sql(self, compiler, connection, **extra_context):
        if connection.features.test_now_utc_template:
            extra_context["template"] = connection.features.test_now_utc_template
        return super().as_sql(compiler, connection, **extra_context)


class AggregateTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Set up test data for the database.

        This method creates a set of authors, publishers, books, and stores with relationships between them.
        It populates the database with a predefined set of data to support testing of the application.

        The test data includes:
            - 9 authors with varying ages and friendships
            - 5 publishers with names and awards
            - 6 books with details such as ISBN, name, pages, rating, price, and publication dates
            - 3 stores with names, opening dates, and closing times
            - Many-to-many relationships between authors and books, and between books and stores

        This method is used to establish a consistent test environment, ensuring that tests run against a predictable set of data.

        """
        cls.a1 = Author.objects.create(name="Adrian Holovaty", age=34)
        cls.a2 = Author.objects.create(name="Jacob Kaplan-Moss", age=35)
        cls.a3 = Author.objects.create(name="Brad Dayley", age=45)
        cls.a4 = Author.objects.create(name="James Bennett", age=29)
        cls.a5 = Author.objects.create(name="Jeffrey Forcier", age=37)
        cls.a6 = Author.objects.create(name="Paul Bissex", age=29)
        cls.a7 = Author.objects.create(name="Wesley J. Chun", age=25)
        cls.a8 = Author.objects.create(name="Peter Norvig", age=57)
        cls.a9 = Author.objects.create(name="Stuart Russell", age=46)
        cls.a1.friends.add(cls.a2, cls.a4)
        cls.a2.friends.add(cls.a1, cls.a7)
        cls.a4.friends.add(cls.a1)
        cls.a5.friends.add(cls.a6, cls.a7)
        cls.a6.friends.add(cls.a5, cls.a7)
        cls.a7.friends.add(cls.a2, cls.a5, cls.a6)
        cls.a8.friends.add(cls.a9)
        cls.a9.friends.add(cls.a8)

        cls.p1 = Publisher.objects.create(
            name="Apress", num_awards=3, duration=datetime.timedelta(days=1)
        )
        cls.p2 = Publisher.objects.create(
            name="Sams", num_awards=1, duration=datetime.timedelta(days=2)
        )
        cls.p3 = Publisher.objects.create(name="Prentice Hall", num_awards=7)
        cls.p4 = Publisher.objects.create(name="Morgan Kaufmann", num_awards=9)
        cls.p5 = Publisher.objects.create(name="Jonno's House of Books", num_awards=0)

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
            contact=cls.a3,
            publisher=cls.p2,
            pubdate=datetime.date(2008, 3, 3),
        )
        cls.b3 = Book.objects.create(
            isbn="159059996",
            name="Practical Django Projects",
            pages=300,
            rating=4.0,
            price=Decimal("29.69"),
            contact=cls.a4,
            publisher=cls.p1,
            pubdate=datetime.date(2008, 6, 23),
        )
        cls.b4 = Book.objects.create(
            isbn="013235613",
            name="Python Web Development with Django",
            pages=350,
            rating=4.0,
            price=Decimal("29.69"),
            contact=cls.a5,
            publisher=cls.p3,
            pubdate=datetime.date(2008, 11, 3),
        )
        cls.b5 = Book.objects.create(
            isbn="013790395",
            name="Artificial Intelligence: A Modern Approach",
            pages=1132,
            rating=4.0,
            price=Decimal("82.80"),
            contact=cls.a8,
            publisher=cls.p3,
            pubdate=datetime.date(1995, 1, 15),
        )
        cls.b6 = Book.objects.create(
            isbn="155860191",
            name=(
                "Paradigms of Artificial Intelligence Programming: Case Studies in "
                "Common Lisp"
            ),
            pages=946,
            rating=5.0,
            price=Decimal("75.00"),
            contact=cls.a8,
            publisher=cls.p4,
            pubdate=datetime.date(1991, 10, 15),
        )
        cls.b1.authors.add(cls.a1, cls.a2)
        cls.b2.authors.add(cls.a3)
        cls.b3.authors.add(cls.a4)
        cls.b4.authors.add(cls.a5, cls.a6, cls.a7)
        cls.b5.authors.add(cls.a8, cls.a9)
        cls.b6.authors.add(cls.a8)

        s1 = Store.objects.create(
            name="Amazon.com",
            original_opening=datetime.datetime(1994, 4, 23, 9, 17, 42),
            friday_night_closing=datetime.time(23, 59, 59),
        )
        s2 = Store.objects.create(
            name="Books.com",
            original_opening=datetime.datetime(2001, 3, 15, 11, 23, 37),
            friday_night_closing=datetime.time(23, 59, 59),
        )
        s3 = Store.objects.create(
            name="Mamma and Pappa's Books",
            original_opening=datetime.datetime(1945, 4, 25, 16, 24, 14),
            friday_night_closing=datetime.time(21, 30),
        )
        s1.books.add(cls.b1, cls.b2, cls.b3, cls.b4, cls.b5, cls.b6)
        s2.books.add(cls.b1, cls.b3, cls.b5, cls.b6)
        s3.books.add(cls.b3, cls.b4, cls.b6)

    def test_empty_aggregate(self):
        self.assertEqual(Author.objects.aggregate(), {})

    def test_aggregate_in_order_by(self):
        msg = (
            "Using an aggregate in order_by() without also including it in "
            "annotate() is not allowed: Avg(F(book__rating)"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.values("age").order_by(Avg("book__rating"))

    def test_single_aggregate(self):
        vals = Author.objects.aggregate(Avg("age"))
        self.assertEqual(vals, {"age__avg": Approximate(37.4, places=1)})

    def test_multiple_aggregates(self):
        """

        Tests the calculation of multiple aggregate values on a query set of Authors.
        Verifies that the function correctly computes the sum and average of the 'age' attribute.

        """
        vals = Author.objects.aggregate(Sum("age"), Avg("age"))
        self.assertEqual(
            vals, {"age__sum": 337, "age__avg": Approximate(37.4, places=1)}
        )

    def test_filter_aggregate(self):
        """

        Tests the filtering and aggregation of Author objects based on age.

        This test case filters authors who are older than 29 years and calculates the sum of their ages.
        It then asserts that the total sum of ages matches the expected value.

        """
        vals = Author.objects.filter(age__gt=29).aggregate(Sum("age"))
        self.assertEqual(vals, {"age__sum": 254})

    def test_related_aggregate(self):
        vals = Author.objects.aggregate(Avg("friends__age"))
        self.assertEqual(vals, {"friends__age__avg": Approximate(34.07, places=2)})

        vals = Book.objects.filter(rating__lt=4.5).aggregate(Avg("authors__age"))
        self.assertEqual(vals, {"authors__age__avg": Approximate(38.2857, places=2)})

        vals = Author.objects.filter(name__contains="a").aggregate(Avg("book__rating"))
        self.assertEqual(vals, {"book__rating__avg": 4.0})

        vals = Book.objects.aggregate(Sum("publisher__num_awards"))
        self.assertEqual(vals, {"publisher__num_awards__sum": 30})

        vals = Publisher.objects.aggregate(Sum("book__price"))
        self.assertEqual(vals, {"book__price__sum": Decimal("270.27")})

    def test_aggregate_multi_join(self):
        vals = Store.objects.aggregate(Max("books__authors__age"))
        self.assertEqual(vals, {"books__authors__age__max": 57})

        vals = Author.objects.aggregate(Min("book__publisher__num_awards"))
        self.assertEqual(vals, {"book__publisher__num_awards__min": 1})

    def test_aggregate_alias(self):
        vals = Store.objects.filter(name="Amazon.com").aggregate(
            amazon_mean=Avg("books__rating")
        )
        self.assertEqual(vals, {"amazon_mean": Approximate(4.08, places=2)})

    def test_aggregate_transform(self):
        """

        Tests the aggregation transformation functionality by verifying the minimum month value.
        It checks if the aggregate function correctly retrieves the minimum month from a dataset of store objects.
        The test asserts that the result matches the expected minimum month, which is March (3).

        """
        vals = Store.objects.aggregate(min_month=Min("original_opening__month"))
        self.assertEqual(vals, {"min_month": 3})

    def test_aggregate_join_transform(self):
        vals = Publisher.objects.aggregate(min_year=Min("book__pubdate__year"))
        self.assertEqual(vals, {"min_year": 1991})

    def test_annotate_basic(self):
        self.assertQuerySetEqual(
            Book.objects.annotate().order_by("pk"),
            [
                "The Definitive Guide to Django: Web Development Done Right",
                "Sams Teach Yourself Django in 24 Hours",
                "Practical Django Projects",
                "Python Web Development with Django",
                "Artificial Intelligence: A Modern Approach",
                "Paradigms of Artificial Intelligence Programming: Case Studies in "
                "Common Lisp",
            ],
            lambda b: b.name,
        )

        books = Book.objects.annotate(mean_age=Avg("authors__age"))
        b = books.get(pk=self.b1.pk)
        self.assertEqual(
            b.name, "The Definitive Guide to Django: Web Development Done Right"
        )
        self.assertEqual(b.mean_age, 34.5)

    def test_annotate_defer(self):
        """

        Tests the functionality of annotating and deferring model fields in database queries.

        This test case checks that the annotation of a calculated field ('page_sum') and deferring 
        of another field ('name') works correctly when filtering and ordering a query set.

        It verifies that the resulting query set contains the expected data and that the deferred 
        field ('name') is still accessible even though it was not included in the initial query.

        """
        qs = (
            Book.objects.annotate(page_sum=Sum("pages"))
            .defer("name")
            .filter(pk=self.b1.pk)
        )

        rows = [
            (
                self.b1.id,
                "159059725",
                447,
                "The Definitive Guide to Django: Web Development Done Right",
            )
        ]
        self.assertQuerySetEqual(
            qs.order_by("pk"), rows, lambda r: (r.id, r.isbn, r.page_sum, r.name)
        )

    def test_annotate_defer_select_related(self):
        """

        Tests the annotation and defer functionality on a Django queryset.

        Ensures that the select_related and defer methods are correctly applied 
        to a queryset, allowing for efficient retrieval of related objects and 
        exclusion of unnecessary fields, while also properly annotating a field 
        using an aggregate function. This test case verifies that the resulting 
        queryset is correctly ordered and contains the expected fields and values.

        """
        qs = (
            Book.objects.select_related("contact")
            .annotate(page_sum=Sum("pages"))
            .defer("name")
            .filter(pk=self.b1.pk)
        )

        rows = [
            (
                self.b1.id,
                "159059725",
                447,
                "Adrian Holovaty",
                "The Definitive Guide to Django: Web Development Done Right",
            )
        ]
        self.assertQuerySetEqual(
            qs.order_by("pk"),
            rows,
            lambda r: (r.id, r.isbn, r.page_sum, r.contact.name, r.name),
        )

    def test_annotate_m2m(self):
        books = (
            Book.objects.filter(rating__lt=4.5)
            .annotate(Avg("authors__age"))
            .order_by("name")
        )
        self.assertQuerySetEqual(
            books,
            [
                ("Artificial Intelligence: A Modern Approach", 51.5),
                ("Practical Django Projects", 29.0),
                ("Python Web Development with Django", Approximate(30.3, places=1)),
                ("Sams Teach Yourself Django in 24 Hours", 45.0),
            ],
            lambda b: (b.name, b.authors__age__avg),
        )

        books = Book.objects.annotate(num_authors=Count("authors")).order_by("name")
        self.assertQuerySetEqual(
            books,
            [
                ("Artificial Intelligence: A Modern Approach", 2),
                (
                    "Paradigms of Artificial Intelligence Programming: Case Studies in "
                    "Common Lisp",
                    1,
                ),
                ("Practical Django Projects", 1),
                ("Python Web Development with Django", 3),
                ("Sams Teach Yourself Django in 24 Hours", 1),
                ("The Definitive Guide to Django: Web Development Done Right", 2),
            ],
            lambda b: (b.name, b.num_authors),
        )

    def test_backwards_m2m_annotate(self):
        """
        Tests annotation of authors using Many-to-Many (m2m) relationships.

        This test case verifies that authors can be annotated with aggregated values
        from related books, such as average rating, and counted values, such as the
        number of books written. The test checks that the annotated values are
        correctly calculated and ordered by author name.

        The test covers two annotation scenarios:

        * Annotating authors with the average rating of their books
        * Annotating authors with the number of books they have written

        The test compares the annotated query sets with expected results to ensure
        that the annotations are accurate and correctly ordered.
        """
        authors = (
            Author.objects.filter(name__contains="a")
            .annotate(Avg("book__rating"))
            .order_by("name")
        )
        self.assertQuerySetEqual(
            authors,
            [
                ("Adrian Holovaty", 4.5),
                ("Brad Dayley", 3.0),
                ("Jacob Kaplan-Moss", 4.5),
                ("James Bennett", 4.0),
                ("Paul Bissex", 4.0),
                ("Stuart Russell", 4.0),
            ],
            lambda a: (a.name, a.book__rating__avg),
        )

        authors = Author.objects.annotate(num_books=Count("book")).order_by("name")
        self.assertQuerySetEqual(
            authors,
            [
                ("Adrian Holovaty", 1),
                ("Brad Dayley", 1),
                ("Jacob Kaplan-Moss", 1),
                ("James Bennett", 1),
                ("Jeffrey Forcier", 1),
                ("Paul Bissex", 1),
                ("Peter Norvig", 2),
                ("Stuart Russell", 1),
                ("Wesley J. Chun", 1),
            ],
            lambda a: (a.name, a.num_books),
        )

    def test_reverse_fkey_annotate(self):
        """

        Tests that Django model instances are correctly annotated with aggregate values 
        from related models when using a reverse foreign key.

        Verifies that the `annotate` method correctly calculates aggregate values, 
        such as sums, from related models and that the results are ordered as expected.

        """
        books = Book.objects.annotate(Sum("publisher__num_awards")).order_by("name")
        self.assertQuerySetEqual(
            books,
            [
                ("Artificial Intelligence: A Modern Approach", 7),
                (
                    "Paradigms of Artificial Intelligence Programming: Case Studies in "
                    "Common Lisp",
                    9,
                ),
                ("Practical Django Projects", 3),
                ("Python Web Development with Django", 7),
                ("Sams Teach Yourself Django in 24 Hours", 1),
                ("The Definitive Guide to Django: Web Development Done Right", 3),
            ],
            lambda b: (b.name, b.publisher__num_awards__sum),
        )

        publishers = Publisher.objects.annotate(Sum("book__price")).order_by("name")
        self.assertQuerySetEqual(
            publishers,
            [
                ("Apress", Decimal("59.69")),
                ("Jonno's House of Books", None),
                ("Morgan Kaufmann", Decimal("75.00")),
                ("Prentice Hall", Decimal("112.49")),
                ("Sams", Decimal("23.09")),
            ],
            lambda p: (p.name, p.book__price__sum),
        )

    def test_annotate_values(self):
        """
        Tests the functionality of annotating values in database queries.

        This test case covers various scenarios, including annotating with aggregate functions 
        such as average age of authors and counting the number of authors for a book. 
        It also verifies that the annotated values can be filtered, ordered, and retrieved 
        in different combinations. The test cases check that the results match the expected 
        output in different query scenarios.

        The test methods check for the correct annotation of values, 
        filtering, ordering, and retrieval of annotated values in the database queries. 

        Args:
            None

        Returns:
            None
        """
        books = list(
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values()
        )
        self.assertEqual(
            books,
            [
                {
                    "contact_id": self.a1.id,
                    "id": self.b1.id,
                    "isbn": "159059725",
                    "mean_age": 34.5,
                    "name": (
                        "The Definitive Guide to Django: Web Development Done Right"
                    ),
                    "pages": 447,
                    "price": Approximate(Decimal("30")),
                    "pubdate": datetime.date(2007, 12, 6),
                    "publisher_id": self.p1.id,
                    "rating": 4.5,
                }
            ],
        )

        books = (
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values("pk", "isbn", "mean_age")
        )
        self.assertEqual(
            list(books),
            [
                {
                    "pk": self.b1.pk,
                    "isbn": "159059725",
                    "mean_age": 34.5,
                }
            ],
        )

        books = (
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values("name")
        )
        self.assertEqual(
            list(books),
            [{"name": "The Definitive Guide to Django: Web Development Done Right"}],
        )

        books = (
            Book.objects.filter(pk=self.b1.pk)
            .values()
            .annotate(mean_age=Avg("authors__age"))
        )
        self.assertEqual(
            list(books),
            [
                {
                    "contact_id": self.a1.id,
                    "id": self.b1.id,
                    "isbn": "159059725",
                    "mean_age": 34.5,
                    "name": (
                        "The Definitive Guide to Django: Web Development Done Right"
                    ),
                    "pages": 447,
                    "price": Approximate(Decimal("30")),
                    "pubdate": datetime.date(2007, 12, 6),
                    "publisher_id": self.p1.id,
                    "rating": 4.5,
                }
            ],
        )

        books = (
            Book.objects.values("rating")
            .annotate(n_authors=Count("authors__id"), mean_age=Avg("authors__age"))
            .order_by("rating")
        )
        self.assertEqual(
            list(books),
            [
                {
                    "rating": 3.0,
                    "n_authors": 1,
                    "mean_age": 45.0,
                },
                {
                    "rating": 4.0,
                    "n_authors": 6,
                    "mean_age": Approximate(37.16, places=1),
                },
                {
                    "rating": 4.5,
                    "n_authors": 2,
                    "mean_age": 34.5,
                },
                {
                    "rating": 5.0,
                    "n_authors": 1,
                    "mean_age": 57.0,
                },
            ],
        )

        authors = Author.objects.annotate(Avg("friends__age")).order_by("name")
        self.assertQuerySetEqual(
            authors,
            [
                ("Adrian Holovaty", 32.0),
                ("Brad Dayley", None),
                ("Jacob Kaplan-Moss", 29.5),
                ("James Bennett", 34.0),
                ("Jeffrey Forcier", 27.0),
                ("Paul Bissex", 31.0),
                ("Peter Norvig", 46.0),
                ("Stuart Russell", 57.0),
                ("Wesley J. Chun", Approximate(33.66, places=1)),
            ],
            lambda a: (a.name, a.friends__age__avg),
        )

    def test_count(self):
        vals = Book.objects.aggregate(Count("rating"))
        self.assertEqual(vals, {"rating__count": 6})

    def test_count_star(self):
        with self.assertNumQueries(1) as ctx:
            Book.objects.aggregate(n=Count("*"))
        sql = ctx.captured_queries[0]["sql"]
        self.assertIn("SELECT COUNT(*) ", sql)

    def test_count_distinct_expression(self):
        """
        Tests the ability to count distinct ratings for books with more than 300 pages. 
        The function utilizes database aggregation to determine the number of unique ratings 
        for such books, where a book is only counted once towards the total, 
        regardless of whether it has multiple ratings.
        """
        aggs = Book.objects.aggregate(
            distinct_ratings=Count(
                Case(When(pages__gt=300, then="rating")), distinct=True
            ),
        )
        self.assertEqual(aggs["distinct_ratings"], 4)

    def test_distinct_on_aggregate(self):
        """

        Tests the calculation of aggregate values on distinct ratings.

        This method verifies that the average, count, and sum of distinct ratings are calculated correctly.
        It checks the result of each aggregate function against an expected value, ensuring the
        correct application of the distinct flag. The following aggregate functions are tested:
        - Average (Avg)
        - Count of distinct values
        - Sum of distinct values

        The test covers various aggregate functions to ensure the distinct flag is applied correctly
        in different scenarios.

        """
        for aggregate, expected_result in (
            (Avg, 4.125),
            (Count, 4),
            (Sum, 16.5),
        ):
            with self.subTest(aggregate=aggregate.__name__):
                books = Book.objects.aggregate(
                    ratings=aggregate("rating", distinct=True)
                )
                self.assertEqual(books["ratings"], expected_result)

    def test_non_grouped_annotation_not_in_group_by(self):
        """
        An annotation not included in values() before an aggregate should be
        excluded from the group by clause.
        """
        qs = (
            Book.objects.annotate(xprice=F("price"))
            .filter(rating=4.0)
            .values("rating")
            .annotate(count=Count("publisher_id", distinct=True))
            .values("count", "rating")
            .order_by("count")
        )
        self.assertEqual(list(qs), [{"rating": 4.0, "count": 2}])

    def test_grouped_annotation_in_group_by(self):
        """
        An annotation included in values() before an aggregate should be
        included in the group by clause.
        """
        qs = (
            Book.objects.annotate(xprice=F("price"))
            .filter(rating=4.0)
            .values("rating", "xprice")
            .annotate(count=Count("publisher_id", distinct=True))
            .values("count", "rating")
            .order_by("count")
        )
        self.assertEqual(
            list(qs),
            [
                {"rating": 4.0, "count": 1},
                {"rating": 4.0, "count": 2},
            ],
        )

    def test_fkey_aggregate(self):
        explicit = list(Author.objects.annotate(Count("book__id")))
        implicit = list(Author.objects.annotate(Count("book")))
        self.assertCountEqual(explicit, implicit)

    def test_annotate_ordering(self):
        """

        Tests the annotation and ordering of books based on the age of their authors and rating.

        This test case verifies that books can be correctly ordered in ascending and descending
        order based on the oldest author's age and their rating. The test checks that the books
        are annotated with the maximum age of their authors and then ordered accordingly.

        The test cases cover two scenarios: ordering in ascending order (oldest author's age and
        then rating) and ordering in descending order (youngest author's age and then rating in
        reverse).

        """
        books = (
            Book.objects.values("rating")
            .annotate(oldest=Max("authors__age"))
            .order_by("oldest", "rating")
        )
        self.assertEqual(
            list(books),
            [
                {"rating": 4.5, "oldest": 35},
                {"rating": 3.0, "oldest": 45},
                {"rating": 4.0, "oldest": 57},
                {"rating": 5.0, "oldest": 57},
            ],
        )

        books = (
            Book.objects.values("rating")
            .annotate(oldest=Max("authors__age"))
            .order_by("-oldest", "-rating")
        )
        self.assertEqual(
            list(books),
            [
                {"rating": 5.0, "oldest": 57},
                {"rating": 4.0, "oldest": 57},
                {"rating": 3.0, "oldest": 45},
                {"rating": 4.5, "oldest": 35},
            ],
        )

    def test_aggregate_annotation(self):
        """
        Test the aggregation of annotations on the Book model. 
        This test case checks if the average number of authors per book is correctly calculated.
        It uses Django's ORM to annotate each book with the number of authors and then aggregates these values to find the average. 
        The result is then compared to the expected average value of approximately 1.66 authors per book.
        """
        vals = Book.objects.annotate(num_authors=Count("authors__id")).aggregate(
            Avg("num_authors")
        )
        self.assertEqual(vals, {"num_authors__avg": Approximate(1.66, places=1)})

    def test_avg_duration_field(self):
        # Explicit `output_field`.
        self.assertEqual(
            Publisher.objects.aggregate(Avg("duration", output_field=DurationField())),
            {"duration__avg": datetime.timedelta(days=1, hours=12)},
        )
        # Implicit `output_field`.
        self.assertEqual(
            Publisher.objects.aggregate(Avg("duration")),
            {"duration__avg": datetime.timedelta(days=1, hours=12)},
        )

    def test_sum_duration_field(self):
        self.assertEqual(
            Publisher.objects.aggregate(Sum("duration", output_field=DurationField())),
            {"duration__sum": datetime.timedelta(days=3)},
        )

    def test_sum_distinct_aggregate(self):
        """
        Sum on a distinct() QuerySet should aggregate only the distinct items.
        """
        authors = Author.objects.filter(book__in=[self.b5, self.b6])
        self.assertEqual(authors.count(), 3)

        distinct_authors = authors.distinct()
        self.assertEqual(distinct_authors.count(), 2)

        # Selected author ages are 57 and 46
        age_sum = distinct_authors.aggregate(Sum("age"))
        self.assertEqual(age_sum["age__sum"], 103)

    def test_filtering(self):
        p = Publisher.objects.create(name="Expensive Publisher", num_awards=0)
        Book.objects.create(
            name="ExpensiveBook1",
            pages=1,
            isbn="111",
            rating=3.5,
            price=Decimal("1000"),
            publisher=p,
            contact_id=self.a1.id,
            pubdate=datetime.date(2008, 12, 1),
        )
        Book.objects.create(
            name="ExpensiveBook2",
            pages=1,
            isbn="222",
            rating=4.0,
            price=Decimal("1000"),
            publisher=p,
            contact_id=self.a1.id,
            pubdate=datetime.date(2008, 12, 2),
        )
        Book.objects.create(
            name="ExpensiveBook3",
            pages=1,
            isbn="333",
            rating=4.5,
            price=Decimal("35"),
            publisher=p,
            contact_id=self.a1.id,
            pubdate=datetime.date(2008, 12, 3),
        )

        publishers = (
            Publisher.objects.annotate(num_books=Count("book__id"))
            .filter(num_books__gt=1)
            .order_by("pk")
        )
        self.assertQuerySetEqual(
            publishers,
            ["Apress", "Prentice Hall", "Expensive Publisher"],
            lambda p: p.name,
        )

        publishers = Publisher.objects.filter(book__price__lt=Decimal("40.0")).order_by(
            "pk"
        )
        self.assertQuerySetEqual(
            publishers,
            [
                "Apress",
                "Apress",
                "Sams",
                "Prentice Hall",
                "Expensive Publisher",
            ],
            lambda p: p.name,
        )

        publishers = (
            Publisher.objects.annotate(num_books=Count("book__id"))
            .filter(num_books__gt=1, book__price__lt=Decimal("40.0"))
            .order_by("pk")
        )
        self.assertQuerySetEqual(
            publishers,
            ["Apress", "Prentice Hall", "Expensive Publisher"],
            lambda p: p.name,
        )

        publishers = (
            Publisher.objects.filter(book__price__lt=Decimal("40.0"))
            .annotate(num_books=Count("book__id"))
            .filter(num_books__gt=1)
            .order_by("pk")
        )
        self.assertQuerySetEqual(publishers, ["Apress"], lambda p: p.name)

        publishers = (
            Publisher.objects.annotate(num_books=Count("book"))
            .filter(num_books__range=[1, 3])
            .order_by("pk")
        )
        self.assertQuerySetEqual(
            publishers,
            [
                "Apress",
                "Sams",
                "Prentice Hall",
                "Morgan Kaufmann",
                "Expensive Publisher",
            ],
            lambda p: p.name,
        )

        publishers = (
            Publisher.objects.annotate(num_books=Count("book"))
            .filter(num_books__range=[1, 2])
            .order_by("pk")
        )
        self.assertQuerySetEqual(
            publishers,
            ["Apress", "Sams", "Prentice Hall", "Morgan Kaufmann"],
            lambda p: p.name,
        )

        publishers = (
            Publisher.objects.annotate(num_books=Count("book"))
            .filter(num_books__in=[1, 3])
            .order_by("pk")
        )
        self.assertQuerySetEqual(
            publishers,
            ["Sams", "Morgan Kaufmann", "Expensive Publisher"],
            lambda p: p.name,
        )

        publishers = Publisher.objects.annotate(num_books=Count("book")).filter(
            num_books__isnull=True
        )
        self.assertEqual(len(publishers), 0)

    def test_annotation(self):
        """
        Tests annotation functionality on various querysets.

        Verifies that the Count aggregation function works correctly when applied 
        to different relationships (e.g., friends of authors, authors of books, books of publishers). 
        Checks that the annotate method allows filtering on the annotated field and 
        ensures the results are ordered as expected.

        Also tests more complex queries that involve combining filters and annotations, 
        such as finding publishers with multiple books below a certain price, and books 
        with multiple authors that match a specific name pattern.

        The tests cover various aspects of annotation, including distinct counts and 
        filtering on annotated fields, to ensure the functionality works as expected 
        in different scenarios.
        """
        vals = Author.objects.filter(pk=self.a1.pk).aggregate(Count("friends__id"))
        self.assertEqual(vals, {"friends__id__count": 2})

        books = (
            Book.objects.annotate(num_authors=Count("authors__name"))
            .filter(num_authors__exact=2)
            .order_by("pk")
        )
        self.assertQuerySetEqual(
            books,
            [
                "The Definitive Guide to Django: Web Development Done Right",
                "Artificial Intelligence: A Modern Approach",
            ],
            lambda b: b.name,
        )

        authors = (
            Author.objects.annotate(num_friends=Count("friends__id", distinct=True))
            .filter(num_friends=0)
            .order_by("pk")
        )
        self.assertQuerySetEqual(authors, ["Brad Dayley"], lambda a: a.name)

        publishers = (
            Publisher.objects.annotate(num_books=Count("book__id"))
            .filter(num_books__gt=1)
            .order_by("pk")
        )
        self.assertQuerySetEqual(
            publishers, ["Apress", "Prentice Hall"], lambda p: p.name
        )

        publishers = (
            Publisher.objects.filter(book__price__lt=Decimal("40.0"))
            .annotate(num_books=Count("book__id"))
            .filter(num_books__gt=1)
        )
        self.assertQuerySetEqual(publishers, ["Apress"], lambda p: p.name)

        books = Book.objects.annotate(num_authors=Count("authors__id")).filter(
            authors__name__contains="Norvig", num_authors__gt=1
        )
        self.assertQuerySetEqual(
            books, ["Artificial Intelligence: A Modern Approach"], lambda b: b.name
        )

    def test_more_aggregation(self):
        """

        Tests the aggregation of books with multiple authors.

        This test case verifies that books with more than one author can be correctly
        aggregated and their average rating calculated. It specifically checks for books
        that have at least one author with 'Norvig' in their name and ensures the average
        rating of such books with multiple authors is correctly computed.

        """
        a = Author.objects.get(name__contains="Norvig")
        b = Book.objects.get(name__contains="Done Right")
        b.authors.add(a)
        b.save()

        vals = (
            Book.objects.annotate(num_authors=Count("authors__id"))
            .filter(authors__name__contains="Norvig", num_authors__gt=1)
            .aggregate(Avg("rating"))
        )
        self.assertEqual(vals, {"rating__avg": 4.25})

    def test_even_more_aggregate(self):
        publishers = (
            Publisher.objects.annotate(
                earliest_book=Min("book__pubdate"),
            )
            .exclude(earliest_book=None)
            .order_by("earliest_book")
            .values(
                "earliest_book",
                "num_awards",
                "id",
                "name",
            )
        )
        self.assertEqual(
            list(publishers),
            [
                {
                    "earliest_book": datetime.date(1991, 10, 15),
                    "num_awards": 9,
                    "id": self.p4.id,
                    "name": "Morgan Kaufmann",
                },
                {
                    "earliest_book": datetime.date(1995, 1, 15),
                    "num_awards": 7,
                    "id": self.p3.id,
                    "name": "Prentice Hall",
                },
                {
                    "earliest_book": datetime.date(2007, 12, 6),
                    "num_awards": 3,
                    "id": self.p1.id,
                    "name": "Apress",
                },
                {
                    "earliest_book": datetime.date(2008, 3, 3),
                    "num_awards": 1,
                    "id": self.p2.id,
                    "name": "Sams",
                },
            ],
        )

        vals = Store.objects.aggregate(
            Max("friday_night_closing"), Min("original_opening")
        )
        self.assertEqual(
            vals,
            {
                "friday_night_closing__max": datetime.time(23, 59, 59),
                "original_opening__min": datetime.datetime(1945, 4, 25, 16, 24, 14),
            },
        )

    def test_annotate_values_list(self):
        """

        Tests the annotation and values_list functionality of the model query API.

        This test suite verifies the correct results when annotating models with aggregated values
        and retrieving specific fields as lists of values. It checks various scenarios, including:

        * Annotating a field with the average value of a related model field and retrieving multiple fields.
        * Annotating a field with the average value of a related model field and retrieving a single field.
        * Annotating a field with the average value of a related model field and retrieving a single field with flat output.
        * Annotating a field with the count of a model field and retrieving ordered results.

        The test cases cover different combinations of annotation and values_list usage, ensuring the query API behaves as expected.

        """
        books = (
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values_list("pk", "isbn", "mean_age")
        )
        self.assertEqual(list(books), [(self.b1.id, "159059725", 34.5)])

        books = (
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values_list("isbn")
        )
        self.assertEqual(list(books), [("159059725",)])

        books = (
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values_list("mean_age")
        )
        self.assertEqual(list(books), [(34.5,)])

        books = (
            Book.objects.filter(pk=self.b1.pk)
            .annotate(mean_age=Avg("authors__age"))
            .values_list("mean_age", flat=True)
        )
        self.assertEqual(list(books), [34.5])

        books = (
            Book.objects.values_list("price")
            .annotate(count=Count("price"))
            .order_by("-count", "price")
        )
        self.assertEqual(
            list(books),
            [
                (Decimal("29.69"), 2),
                (Decimal("23.09"), 1),
                (Decimal("30"), 1),
                (Decimal("75"), 1),
                (Decimal("82.8"), 1),
            ],
        )

    def test_dates_with_aggregation(self):
        """
        .dates() returns a distinct set of dates when applied to a
        QuerySet with aggregation.

        Refs #18056. Previously, .dates() would return distinct (date_kind,
        aggregation) sets, in this case (year, num_authors), so 2008 would be
        returned twice because there are books from 2008 with a different
        number of authors.
        """
        dates = Book.objects.annotate(num_authors=Count("authors")).dates(
            "pubdate", "year"
        )
        self.assertSequenceEqual(
            dates,
            [
                datetime.date(1991, 1, 1),
                datetime.date(1995, 1, 1),
                datetime.date(2007, 1, 1),
                datetime.date(2008, 1, 1),
            ],
        )

    def test_values_aggregation(self):
        # Refs #20782
        max_rating = Book.objects.values("rating").aggregate(max_rating=Max("rating"))
        self.assertEqual(max_rating["max_rating"], 5)
        max_books_per_rating = (
            Book.objects.values("rating")
            .annotate(books_per_rating=Count("id"))
            .aggregate(Max("books_per_rating"))
        )
        self.assertEqual(max_books_per_rating, {"books_per_rating__max": 3})

    def test_ticket17424(self):
        """
        Doing exclude() on a foreign model after annotate() doesn't crash.
        """
        all_books = list(Book.objects.values_list("pk", flat=True).order_by("pk"))
        annotated_books = Book.objects.order_by("pk").annotate(one=Count("id"))

        # The value doesn't matter, we just need any negative
        # constraint on a related model that's a noop.
        excluded_books = annotated_books.exclude(publisher__name="__UNLIKELY_VALUE__")

        # Try to generate query tree
        str(excluded_books.query)

        self.assertQuerySetEqual(excluded_books, all_books, lambda x: x.pk)

        # Check internal state
        self.assertIsNone(annotated_books.query.alias_map["aggregation_book"].join_type)
        self.assertIsNone(excluded_books.query.alias_map["aggregation_book"].join_type)

    def test_ticket12886(self):
        """
        Aggregation over sliced queryset works correctly.
        """
        qs = Book.objects.order_by("-rating")[0:3]
        vals = qs.aggregate(average_top3_rating=Avg("rating"))["average_top3_rating"]
        self.assertAlmostEqual(vals, 4.5, places=2)

    def test_ticket11881(self):
        """
        Subqueries do not needlessly contain ORDER BY, SELECT FOR UPDATE or
        select_related() stuff.
        """
        qs = (
            Book.objects.select_for_update()
            .order_by("pk")
            .select_related("publisher")
            .annotate(max_pk=Max("pk"))
        )
        with CaptureQueriesContext(connection) as captured_queries:
            qs.aggregate(avg_pk=Avg("max_pk"))
            self.assertEqual(len(captured_queries), 1)
            qstr = captured_queries[0]["sql"].lower()
            self.assertNotIn("for update", qstr)
            forced_ordering = connection.ops.force_no_ordering()
            if forced_ordering:
                # If the backend needs to force an ordering we make sure it's
                # the only "ORDER BY" clause present in the query.
                self.assertEqual(
                    re.findall(r"order by (\w+)", qstr),
                    [", ".join(f[1][0] for f in forced_ordering).lower()],
                )
            else:
                self.assertNotIn("order by", qstr)
            self.assertEqual(qstr.count(" join "), 0)

    def test_decimal_max_digits_has_no_effect(self):
        """

        Tests that the max_digits constraint on decimal fields has no effect on aggregation operations.

        This test creates a set of Book objects with a fixed price, then uses the aggregate function to calculate the total price.
        The result is compared to the expected total price to ensure that the aggregation operation is correct and unaffected by the max_digits constraint.

        """
        Book.objects.all().delete()
        a1 = Author.objects.first()
        p1 = Publisher.objects.first()
        thedate = timezone.now()
        for i in range(10):
            Book.objects.create(
                isbn="abcde{}".format(i),
                name="none",
                pages=10,
                rating=4.0,
                price=9999.98,
                contact=a1,
                publisher=p1,
                pubdate=thedate,
            )

        book = Book.objects.aggregate(price_sum=Sum("price"))
        self.assertEqual(book["price_sum"], Decimal("99999.80"))

    def test_nonaggregate_aggregation_throws(self):
        """

        Tests that attempting to aggregate a non-aggregate expression throws a TypeError.

        This test case verifies that the aggregate method raises an error when a non-aggregate function is used.
        It checks that the error message correctly identifies the issue and mentions that the provided expression is not an aggregate expression.

        """
        with self.assertRaisesMessage(TypeError, "fail is not an aggregate expression"):
            Book.objects.aggregate(fail=F("price"))

    def test_nonfield_annotation(self):
        """

        Tests the annotation of non-field values in database queries.

        This test case verifies that annotating a query with a non-field value, 
        such as an integer, returns the correct result. It checks the annotation 
        with and without specifying an output field, ensuring consistency in the 
        result. The test covers different scenarios to ensure the functionality 
        works as expected, providing a solid foundation for reliable query results.

        """
        book = Book.objects.annotate(val=Max(Value(2))).first()
        self.assertEqual(book.val, 2)
        book = Book.objects.annotate(
            val=Max(Value(2), output_field=IntegerField())
        ).first()
        self.assertEqual(book.val, 2)
        book = Book.objects.annotate(val=Max(2, output_field=IntegerField())).first()
        self.assertEqual(book.val, 2)

    def test_annotation_expressions(self):
        """
        Tests the annotation of combined age expressions in Author querysets.

        This test case ensures that the `combined_ages` annotation is calculated correctly
        and that it is possible to combine age fields in a single column using both 
        inlined `Sum(F('age') + F('friends__age'))` and separate `Sum` functions. 

        The test verifies the equality of two querysets, `authors` and `authors2`, 
        each containing the combined age of an author and their friends, ordered by author name. 

        The expected result is a list of tuples containing the author's name and their combined age,
        with `None` indicating missing friend age data for a particular author.
        """
        authors = Author.objects.annotate(
            combined_ages=Sum(F("age") + F("friends__age"))
        ).order_by("name")
        authors2 = Author.objects.annotate(
            combined_ages=Sum("age") + Sum("friends__age")
        ).order_by("name")
        for qs in (authors, authors2):
            self.assertQuerySetEqual(
                qs,
                [
                    ("Adrian Holovaty", 132),
                    ("Brad Dayley", None),
                    ("Jacob Kaplan-Moss", 129),
                    ("James Bennett", 63),
                    ("Jeffrey Forcier", 128),
                    ("Paul Bissex", 120),
                    ("Peter Norvig", 103),
                    ("Stuart Russell", 103),
                    ("Wesley J. Chun", 176),
                ],
                lambda a: (a.name, a.combined_ages),
            )

    def test_aggregation_expressions(self):
        a1 = Author.objects.aggregate(av_age=Sum("age") / Count("*"))
        a2 = Author.objects.aggregate(av_age=Sum("age") / Count("age"))
        a3 = Author.objects.aggregate(av_age=Avg("age"))
        self.assertEqual(a1, {"av_age": 37})
        self.assertEqual(a2, {"av_age": 37})
        self.assertEqual(a3, {"av_age": Approximate(37.4, places=1)})

    def test_avg_decimal_field(self):
        """
        Verifies that the average price of books with a rating of 4 is calculated correctly.

        Tests that the average price is returned as a Decimal object and checks if its value is approximately 47.39, allowing for a small margin of error due to potential floating point precision issues.
        """
        v = Book.objects.filter(rating=4).aggregate(avg_price=(Avg("price")))[
            "avg_price"
        ]
        self.assertIsInstance(v, Decimal)
        self.assertEqual(v, Approximate(Decimal("47.39"), places=2))

    def test_order_of_precedence(self):
        """

        Tests the order of precedence in aggregate database queries.

        This function verifies that the correct order of operations is followed when combining
        aggregation functions and arithmetic operations in queries. It checks two different
        queries with varying orders of operations and asserts that the results match the
        expected values, demonstrating a correct application of the order of precedence.

        The function specifically tests the difference in results when operations are grouped
        differently, ensuring that the database query interpreter correctly handles expressions
        involving averages, additions, and multiplications.

        """
        p1 = Book.objects.filter(rating=4).aggregate(avg_price=(Avg("price") + 2) * 3)
        self.assertEqual(p1, {"avg_price": Approximate(Decimal("148.18"), places=2)})

        p2 = Book.objects.filter(rating=4).aggregate(avg_price=Avg("price") + 2 * 3)
        self.assertEqual(p2, {"avg_price": Approximate(Decimal("53.39"), places=2)})

    def test_combine_different_types(self):
        """

        Tests the combination of different field types in a Django ORM annotation.

        Verifies that when adding fields of different types in an annotation, a FieldError is raised if the output field type is not explicitly specified.
        It then tests the outcome of specifying the output field type as IntegerField, FloatField, and DecimalField, and ensures the results are correct.

        """
        msg = (
            "Cannot infer type of '+' expression involving these types: FloatField, "
            "DecimalField. You must set output_field."
        )
        qs = Book.objects.annotate(sums=Sum("rating") + Sum("pages") + Sum("price"))
        with self.assertRaisesMessage(FieldError, msg):
            qs.first()
        with self.assertRaisesMessage(FieldError, msg):
            qs.first()

        b1 = Book.objects.annotate(
            sums=Sum(F("rating") + F("pages") + F("price"), output_field=IntegerField())
        ).get(pk=self.b4.pk)
        self.assertEqual(b1.sums, 383)

        b2 = Book.objects.annotate(
            sums=Sum(F("rating") + F("pages") + F("price"), output_field=FloatField())
        ).get(pk=self.b4.pk)
        self.assertEqual(b2.sums, 383.69)

        b3 = Book.objects.annotate(
            sums=Sum(F("rating") + F("pages") + F("price"), output_field=DecimalField())
        ).get(pk=self.b4.pk)
        self.assertEqual(b3.sums, Approximate(Decimal("383.69"), places=2))

    def test_complex_aggregations_require_kwarg(self):
        with self.assertRaisesMessage(
            TypeError, "Complex annotations require an alias"
        ):
            Author.objects.annotate(Sum(F("age") + F("friends__age")))
        with self.assertRaisesMessage(TypeError, "Complex aggregates require an alias"):
            Author.objects.aggregate(Sum("age") / Count("age"))
        with self.assertRaisesMessage(TypeError, "Complex aggregates require an alias"):
            Author.objects.aggregate(Sum(1))

    def test_aggregate_over_complex_annotation(self):
        """

        Tests aggregation over complex annotations on Author objects.

        This test case checks the correctness of calculating aggregated values 
        (such as sum and max) over annotated fields that are the result of 
        combining multiple fields using an expression. The annotation used 
        combines the age of an author with the ages of their friends. The test 
        verifies that various aggregation operations (e.g., sum, max) on this 
        combined field produce the expected results, including when these 
        operations are composed together (e.g., doubling the result).

        """
        qs = Author.objects.annotate(combined_ages=Sum(F("age") + F("friends__age")))

        age = qs.aggregate(max_combined_age=Max("combined_ages"))
        self.assertEqual(age["max_combined_age"], 176)

        age = qs.aggregate(max_combined_age_doubled=Max("combined_ages") * 2)
        self.assertEqual(age["max_combined_age_doubled"], 176 * 2)

        age = qs.aggregate(
            max_combined_age_doubled=Max("combined_ages") + Max("combined_ages")
        )
        self.assertEqual(age["max_combined_age_doubled"], 176 * 2)

        age = qs.aggregate(
            max_combined_age_doubled=Max("combined_ages") + Max("combined_ages"),
            sum_combined_age=Sum("combined_ages"),
        )
        self.assertEqual(age["max_combined_age_doubled"], 176 * 2)
        self.assertEqual(age["sum_combined_age"], 954)

        age = qs.aggregate(
            max_combined_age_doubled=Max("combined_ages") + Max("combined_ages"),
            sum_combined_age_doubled=Sum("combined_ages") + Sum("combined_ages"),
        )
        self.assertEqual(age["max_combined_age_doubled"], 176 * 2)
        self.assertEqual(age["sum_combined_age_doubled"], 954 * 2)

    def test_values_annotation_with_expression(self):
        # ensure the F() is promoted to the group by clause
        """

        Tests the usage of values and annotate with expressions on a QuerySet.

        Verifies that the results returned from the database match the expected values when using
        annotate with Sum and F expressions, as well as Count aggregation. Additionally, checks
        that filtering and ordering on annotated fields work as expected. The test covers various
        scenarios, including combining multiple annotations and using them in conjunction with
        values and ordering.

        """
        qs = Author.objects.values("name").annotate(another_age=Sum("age") + F("age"))
        a = qs.get(name="Adrian Holovaty")
        self.assertEqual(a["another_age"], 68)

        qs = qs.annotate(friend_count=Count("friends"))
        a = qs.get(name="Adrian Holovaty")
        self.assertEqual(a["friend_count"], 2)

        qs = (
            qs.annotate(combined_age=Sum("age") + F("friends__age"))
            .filter(name="Adrian Holovaty")
            .order_by("-combined_age")
        )
        self.assertEqual(
            list(qs),
            [
                {
                    "name": "Adrian Holovaty",
                    "another_age": 68,
                    "friend_count": 1,
                    "combined_age": 69,
                },
                {
                    "name": "Adrian Holovaty",
                    "another_age": 68,
                    "friend_count": 1,
                    "combined_age": 63,
                },
            ],
        )

        vals = qs.values("name", "combined_age")
        self.assertEqual(
            list(vals),
            [
                {"name": "Adrian Holovaty", "combined_age": 69},
                {"name": "Adrian Holovaty", "combined_age": 63},
            ],
        )

    def test_annotate_values_aggregate(self):
        """

        Tests the annotation and aggregation of values in the Author model.

        This test case verifies that annotating a field with an alias and then aggregating the annotated values produces the same result as directly aggregating the original field values.

        The test checks for consistency in the calculated sum of ages when using an alias for the age field, ensuring that the annotation and aggregation operations are performed correctly.

        """
        alias_age = (
            Author.objects.annotate(age_alias=F("age"))
            .values(
                "age_alias",
            )
            .aggregate(sum_age=Sum("age_alias"))
        )

        age = Author.objects.values("age").aggregate(sum_age=Sum("age"))

        self.assertEqual(alias_age["sum_age"], age["sum_age"])

    def test_annotate_over_annotate(self):
        author = (
            Author.objects.annotate(age_alias=F("age"))
            .annotate(sum_age=Sum("age_alias"))
            .get(name="Adrian Holovaty")
        )

        other_author = Author.objects.annotate(sum_age=Sum("age")).get(
            name="Adrian Holovaty"
        )

        self.assertEqual(author.sum_age, other_author.sum_age)

    def test_aggregate_over_aggregate(self):
        """
        Tests that computing an aggregate function over another aggregate function raises a FieldError.

        The function verifies that attempting to calculate the average of a previously computed aggregate (in this case, the sum of ages) is not allowed, as aggregate functions cannot be nested in this manner. It checks that the expected error message is raised when such an operation is attempted through the Author.objects.aggregate function.
        """
        msg = "Cannot compute Avg('age_agg'): 'age_agg' is an aggregate"
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.aggregate(
                age_agg=Sum(F("age")),
                avg_age=Avg(F("age_agg")),
            )

    def test_annotated_aggregate_over_annotated_aggregate(self):
        """

        Tests the scenario where an annotated aggregate is attempted to be used 
        within another aggregate function.

        This function contains two separate test cases:

        1. It first checks that attempting to compute a Sum of a Max annotated 
        field raises a FieldError, as aggregates cannot be used as arguments 
        to another aggregate function.

        2. It then defines a custom aggregate function MyMax and checks that 
        attempting to compute the Max of a previously computed Max annotated 
        field also raises a FieldError, further enforcing the rule that 
        aggregates cannot be nested in this way.

        These test cases ensure that Django's ORM correctly handles and rejects 
        such invalid operations, preventing potential data inconsistencies or 
        errors.

        """
        with self.assertRaisesMessage(
            FieldError, "Cannot compute Sum('id__max'): 'id__max' is an aggregate"
        ):
            Book.objects.annotate(Max("id")).annotate(Sum("id__max"))

        class MyMax(Max):
            def as_sql(self, compiler, connection):
                self.set_source_expressions(self.get_source_expressions()[0:1])
                return super().as_sql(compiler, connection)

        with self.assertRaisesMessage(
            FieldError, "Cannot compute Max('id__max'): 'id__max' is an aggregate"
        ):
            Book.objects.annotate(Max("id")).annotate(my_max=MyMax("id__max", "price"))

    def test_multi_arg_aggregate(self):
        class MyMax(Max):
            output_field = DecimalField()

            def as_sql(self, compiler, connection):
                """

                Overrides the default as_sql method to generate SQL for a custom MAX aggregation function.

                This method modifies the source expressions of the current object to include a single 
                original expression and a None placeholder, then delegates the actual SQL generation 
                to the superclass method.

                The resulting SQL will apply the MAX aggregation function to the specified column or 
                expression, handling the custom requirements of the current object.

                :param compiler: The compiler object used to generate the SQL.
                :param connection: The database connection used to generate the SQL.
                :return: The generated SQL as a string.

                """
                copy = self.copy()
                copy.set_source_expressions(copy.get_source_expressions()[0:1] + [None])
                return super(MyMax, copy).as_sql(compiler, connection)

        with self.assertRaisesMessage(TypeError, "Complex aggregates require an alias"):
            Book.objects.aggregate(MyMax("pages", "price"))

        with self.assertRaisesMessage(
            TypeError, "Complex annotations require an alias"
        ):
            Book.objects.annotate(MyMax("pages", "price"))

        Book.objects.aggregate(max_field=MyMax("pages", "price"))

    def test_add_implementation(self):
        class MySum(Sum):
            pass

        # test completely changing how the output is rendered
        def lower_case_function_override(self, compiler, connection):
            """

            Overrides a function to render it as lower case in the generated SQL.

            This function takes in a compiler and a database connection, and returns 
            a tuple containing the compiled SQL string and the parameters to be used 
            with that SQL. It compiles the source expressions, generates substitutions 
            for the function name, expressions, and distinct keyword, and then applies 
            these substitutions to a template string to generate the final SQL.

            The substitutions include the function name converted to lower case, the 
            compiled source expressions, and any additional extra parameters provided.

            """
            sql, params = compiler.compile(self.source_expressions[0])
            substitutions = {
                "function": self.function.lower(),
                "expressions": sql,
                "distinct": "",
            }
            substitutions.update(self.extra)
            return self.template % substitutions, params

        setattr(MySum, "as_" + connection.vendor, lower_case_function_override)

        qs = Book.objects.annotate(
            sums=MySum(
                F("rating") + F("pages") + F("price"), output_field=IntegerField()
            )
        )
        self.assertEqual(str(qs.query).count("sum("), 1)
        b1 = qs.get(pk=self.b4.pk)
        self.assertEqual(b1.sums, 383)

        # test changing the dict and delegating
        def lower_case_function_super(self, compiler, connection):
            """
            Generates SQL for a sum operation while ensuring the function name is in lower case.

            This method extends the base functionality by explicitly converting the function
            name to lower case, addressing potential case sensitivity issues. It then delegates
            to the parent class to construct the SQL string.

            :param compiler: The compiler object used to generate the SQL.
            :param connection: The database connection to be used.
            :return: The generated SQL string for the operation.

            """
            self.extra["function"] = self.function.lower()
            return super(MySum, self).as_sql(compiler, connection)

        setattr(MySum, "as_" + connection.vendor, lower_case_function_super)

        qs = Book.objects.annotate(
            sums=MySum(
                F("rating") + F("pages") + F("price"), output_field=IntegerField()
            )
        )
        self.assertEqual(str(qs.query).count("sum("), 1)
        b1 = qs.get(pk=self.b4.pk)
        self.assertEqual(b1.sums, 383)

        # test overriding all parts of the template
        def be_evil(self, compiler, connection):
            """

            Generates an SQL query string using a predefined template.

            The query is constructed by replacing placeholders in the template with specified values.
            The values include the function to apply (currently set to 'MAX'), the number of expressions,
            and whether to apply the 'distinct' keyword.

            Additional substitutions can be provided through the :attr:`extra` attribute.

            :param compiler: The SQL compiler to use.
            :param connection: The database connection.

            :return: A tuple containing the generated SQL query string and an empty parameter list.

            """
            substitutions = {"function": "MAX", "expressions": "2", "distinct": ""}
            substitutions.update(self.extra)
            return self.template % substitutions, ()

        setattr(MySum, "as_" + connection.vendor, be_evil)

        qs = Book.objects.annotate(
            sums=MySum(
                F("rating") + F("pages") + F("price"), output_field=IntegerField()
            )
        )
        self.assertEqual(str(qs.query).count("MAX("), 1)
        b1 = qs.get(pk=self.b4.pk)
        self.assertEqual(b1.sums, 2)

    def test_complex_values_aggregation(self):
        """

        Tests the aggregation of complex values in the Book model.

        Verifies that the maximum rating can be doubled and correctly calculated using the 
        Max aggregation function. Additionally, checks that the count of books per rating 
        can be offset by a constant value and then the maximum value can be correctly 
        aggregated.

        Validates the functionality of combining aggregation functions with arithmetic 
        operations, ensuring accurate results are returned.

        """
        max_rating = Book.objects.values("rating").aggregate(
            double_max_rating=Max("rating") + Max("rating")
        )
        self.assertEqual(max_rating["double_max_rating"], 5 * 2)

        max_books_per_rating = (
            Book.objects.values("rating")
            .annotate(books_per_rating=Count("id") + 5)
            .aggregate(Max("books_per_rating"))
        )
        self.assertEqual(max_books_per_rating, {"books_per_rating__max": 3 + 5})

    def test_expression_on_aggregation(self):
        """
        Tests the correct execution of database queries that involve annotations with greatest aggregation and filtering.

        This function verifies that the database queries correctly calculate the greatest value between the average rating or price of books published by a publisher, 
        or the greatest value between the average book rating and the number of awards received by a publisher. 
        The results are then filtered to include only publishers where this calculated value meets certain conditions and are ordered by the number of awards received.

        Two specific test cases are executed:
        1. The first test case checks if the publishers with the greatest value of either the average book rating or average book price 
           are correctly identified and filtered when this value is greater than or equal to the number of awards received.
        2. The second test case checks if the publishers with the greatest value of either the average book rating or the number of awards received 
           are correctly identified and filtered when this value is greater than the number of awards received.

        Both test cases verify the expected results by comparing the querysets to predefined expected values, ensuring the correct functionality of 
        the database queries and annotations used.
        """
        qs = (
            Publisher.objects.annotate(
                price_or_median=Greatest(
                    Avg("book__rating", output_field=DecimalField()), Avg("book__price")
                )
            )
            .filter(price_or_median__gte=F("num_awards"))
            .order_by("num_awards")
        )
        self.assertQuerySetEqual(qs, [1, 3, 7, 9], lambda v: v.num_awards)

        qs2 = (
            Publisher.objects.annotate(
                rating_or_num_awards=Greatest(
                    Avg("book__rating"), F("num_awards"), output_field=FloatField()
                )
            )
            .filter(rating_or_num_awards__gt=F("num_awards"))
            .order_by("num_awards")
        )
        self.assertQuerySetEqual(qs2, [1, 3], lambda v: v.num_awards)

    def test_arguments_must_be_expressions(self):
        """
        Tests that the aggregate method of a QuerySet requires all arguments to be valid expressions.

        Verifies that passing non-expression arguments, such as a Field instance or a boolean value,
        raises a TypeError with a descriptive message indicating which arguments are invalid.

        Checks both individual invalid arguments and a combination of valid and invalid arguments.
        """
        msg = "QuerySet.aggregate() received non-expression(s): %s."
        with self.assertRaisesMessage(TypeError, msg % FloatField()):
            Book.objects.aggregate(FloatField())
        with self.assertRaisesMessage(TypeError, msg % True):
            Book.objects.aggregate(is_book=True)
        with self.assertRaisesMessage(
            TypeError, msg % ", ".join([str(FloatField()), "True"])
        ):
            Book.objects.aggregate(FloatField(), Avg("price"), is_book=True)

    def test_aggregation_subquery_annotation(self):
        """Subquery annotations are excluded from the GROUP BY if they are
        not explicitly grouped against."""
        latest_book_pubdate_qs = (
            Book.objects.filter(publisher=OuterRef("pk"))
            .order_by("-pubdate")
            .values("pubdate")[:1]
        )
        publisher_qs = Publisher.objects.annotate(
            latest_book_pubdate=Subquery(latest_book_pubdate_qs),
        ).annotate(count=Count("book"))
        with self.assertNumQueries(1) as ctx:
            list(publisher_qs)
        self.assertEqual(ctx[0]["sql"].count("SELECT"), 2)
        # The GROUP BY should not be by alias either.
        self.assertEqual(ctx[0]["sql"].lower().count("latest_book_pubdate"), 1)

    def test_aggregation_subquery_annotation_exists(self):
        latest_book_pubdate_qs = (
            Book.objects.filter(publisher=OuterRef("pk"))
            .order_by("-pubdate")
            .values("pubdate")[:1]
        )
        publisher_qs = Publisher.objects.annotate(
            latest_book_pubdate=Subquery(latest_book_pubdate_qs),
            count=Count("book"),
        )
        self.assertTrue(publisher_qs.exists())

    def test_aggregation_filter_exists(self):
        """

        Tests that an aggregation filter exists.

        This test case verifies the existence of an aggregation filter that checks if a publisher has more than one book.
        It checks the query generated by the Django ORM to ensure that a single grouping clause is applied, 
        indicating the correct application of the aggregation filter.

        """
        publishers_having_more_than_one_book_qs = (
            Book.objects.values("publisher")
            .annotate(cnt=Count("isbn"))
            .filter(cnt__gt=1)
        )
        query = publishers_having_more_than_one_book_qs.query.exists()
        _, _, group_by = query.get_compiler(connection=connection).pre_sql_setup()
        self.assertEqual(len(group_by), 1)

    def test_aggregation_exists_annotation(self):
        published_books = Book.objects.filter(publisher=OuterRef("pk"))
        publisher_qs = Publisher.objects.annotate(
            published_book=Exists(published_books),
            count=Count("book"),
        ).values_list("name", flat=True)
        self.assertCountEqual(
            list(publisher_qs),
            [
                "Apress",
                "Morgan Kaufmann",
                "Jonno's House of Books",
                "Prentice Hall",
                "Sams",
            ],
        )

    def test_aggregation_subquery_annotation_values(self):
        """
        Subquery annotations and external aliases are excluded from the GROUP
        BY if they are not selected.
        """
        books_qs = (
            Book.objects.annotate(
                first_author_the_same_age=Subquery(
                    Author.objects.filter(
                        age=OuterRef("contact__friends__age"),
                    )
                    .order_by("age")
                    .values("id")[:1],
                )
            )
            .filter(
                publisher=self.p1,
                first_author_the_same_age__isnull=False,
            )
            .annotate(
                min_age=Min("contact__friends__age"),
            )
            .values("name", "min_age")
            .order_by("name")
        )
        self.assertEqual(
            list(books_qs),
            [
                {"name": "Practical Django Projects", "min_age": 34},
                {
                    "name": (
                        "The Definitive Guide to Django: Web Development Done Right"
                    ),
                    "min_age": 29,
                },
            ],
        )

    @skipUnlessDBFeature("supports_subqueries_in_group_by")
    def test_aggregation_subquery_annotation_values_collision(self):
        books_rating_qs = Book.objects.filter(
            pk=OuterRef("book"),
        ).values("rating")
        publisher_qs = (
            Publisher.objects.filter(
                book__contact__age__gt=20,
            )
            .annotate(
                rating=Subquery(books_rating_qs),
            )
            .values("rating")
            .annotate(total_count=Count("*"))
            .order_by("rating")
        )
        self.assertEqual(
            list(publisher_qs),
            [
                {"rating": 3.0, "total_count": 1},
                {"rating": 4.0, "total_count": 3},
                {"rating": 4.5, "total_count": 1},
                {"rating": 5.0, "total_count": 1},
            ],
        )

    @skipUnlessDBFeature("supports_subqueries_in_group_by")
    def test_aggregation_subquery_annotation_multivalued(self):
        """
        Subquery annotations must be included in the GROUP BY if they use
        potentially multivalued relations (contain the LOOKUP_SEP).
        """
        subquery_qs = Author.objects.filter(
            pk=OuterRef("pk"),
            book__name=OuterRef("book__name"),
        ).values("pk")
        author_qs = Author.objects.annotate(
            subquery_id=Subquery(subquery_qs),
        ).annotate(count=Count("book"))
        self.assertEqual(author_qs.count(), Author.objects.count())

    def test_aggregation_order_by_not_selected_annotation_values(self):
        result_asc = [
            self.b4.pk,
            self.b3.pk,
            self.b1.pk,
            self.b2.pk,
            self.b5.pk,
            self.b6.pk,
        ]
        result_desc = result_asc[::-1]
        tests = [
            ("min_related_age", result_asc),
            ("-min_related_age", result_desc),
            (F("min_related_age"), result_asc),
            (F("min_related_age").asc(), result_asc),
            (F("min_related_age").desc(), result_desc),
        ]
        for ordering, expected_result in tests:
            with self.subTest(ordering=ordering):
                books_qs = (
                    Book.objects.annotate(
                        min_age=Min("authors__age"),
                    )
                    .annotate(
                        min_related_age=Coalesce("min_age", "contact__age"),
                    )
                    .order_by(ordering)
                    .values_list("pk", flat=True)
                )
                self.assertEqual(list(books_qs), expected_result)

    @skipUnlessDBFeature("supports_subqueries_in_group_by")
    def test_group_by_subquery_annotation(self):
        """
        Subquery annotations are included in the GROUP BY if they are
        grouped against.
        """
        long_books_count_qs = (
            Book.objects.filter(
                publisher=OuterRef("pk"),
                pages__gt=400,
            )
            .values("publisher")
            .annotate(count=Count("pk"))
            .values("count")
        )
        groups = [
            Subquery(long_books_count_qs),
            long_books_count_qs,
            long_books_count_qs.query,
        ]
        for group in groups:
            with self.subTest(group=group.__class__.__name__):
                long_books_count_breakdown = Publisher.objects.values_list(
                    group,
                ).annotate(total=Count("*"))
                self.assertEqual(dict(long_books_count_breakdown), {None: 1, 1: 4})

    @skipUnlessDBFeature("supports_subqueries_in_group_by")
    def test_group_by_exists_annotation(self):
        """
        Exists annotations are included in the GROUP BY if they are
        grouped against.
        """
        long_books_qs = Book.objects.filter(
            publisher=OuterRef("pk"),
            pages__gt=800,
        )
        has_long_books_breakdown = Publisher.objects.values_list(
            Exists(long_books_qs),
        ).annotate(total=Count("*"))
        self.assertEqual(dict(has_long_books_breakdown), {True: 2, False: 3})

    def test_group_by_nested_expression_with_params(self):
        """

        Tests the usage of the group by functionality with nested expressions that take parameters.

        This test case verifies that the database query correctly annotates and aggregates data based on multiple expressions, 
        including the Greatest and Least functions, and returns the expected results. The query filters Book objects, 
        annotating each with the greatest value between the 'pages' field and a specified threshold, 
        and then calculates the minimum 'pages' value and the least value between the minimum 'pages' and the previously calculated greatest value.
        The test asserts that the output matches the expected list of least values.

        """
        books_qs = (
            Book.objects.annotate(greatest_pages=Greatest("pages", Value(600)))
            .values(
                "greatest_pages",
            )
            .annotate(
                min_pages=Min("pages"),
                least=Least("min_pages", "greatest_pages"),
            )
            .values_list("least", flat=True)
        )
        self.assertCountEqual(books_qs, [300, 946, 1132])

    @skipUnlessDBFeature("supports_subqueries_in_group_by")
    def test_aggregation_subquery_annotation_related_field(self):
        """

        Tests that aggregation subqueries can be used as annotations on related fields.

        This test case verifies that a subquery annotation can be applied to a related field,
        in this case, the publisher of a book, and that the resulting queryset can be filtered
        and aggregated accordingly. The test also checks the number of database queries
        executed and the structure of the generated SQL query.

        The test creates a book instance with a publisher and authors, and then uses a subquery
        to annotate the book queryset with the name of the publisher that matches the contact
        name of the book. The test then filters the queryset to include only books with a
        non-null contact publisher annotation and annotates the result with the count of authors.

        """
        publisher = Publisher.objects.create(name=self.a9.name, num_awards=2)
        book = Book.objects.create(
            isbn="159059999",
            name="Test book.",
            pages=819,
            rating=2.5,
            price=Decimal("14.44"),
            contact=self.a9,
            publisher=publisher,
            pubdate=datetime.date(2019, 12, 6),
        )
        book.authors.add(self.a5, self.a6, self.a7)
        books_qs = (
            Book.objects.annotate(
                contact_publisher=Subquery(
                    Publisher.objects.filter(
                        pk=OuterRef("publisher"),
                        name=OuterRef("contact__name"),
                    ).values("name")[:1],
                )
            )
            .filter(
                contact_publisher__isnull=False,
            )
            .annotate(count=Count("authors"))
        )
        with self.assertNumQueries(1) as ctx:
            self.assertSequenceEqual(books_qs, [book])
        if connection.features.allows_group_by_select_index:
            self.assertEqual(ctx[0]["sql"].count("SELECT"), 3)

    @skipUnlessDBFeature("supports_subqueries_in_group_by")
    def test_aggregation_nested_subquery_outerref(self):
        """

        Tests the aggregation of nested subqueries with outer references in the GROUP BY clause.

        This test case verifies that the database backend correctly handles subqueries within the GROUP BY clause.
        It checks the count of books for each publisher, using a subquery to filter publishers with the same name.
        The output is a list of publisher counts, which should match the expected sequence.

        The test ensures that the database supports subqueries in the GROUP BY clause, and that the ORM correctly translates the query.

        """
        publisher_with_same_name = Publisher.objects.filter(
            id__in=Subquery(
                Publisher.objects.filter(
                    name=OuterRef(OuterRef("publisher__name")),
                ).values("id"),
            ),
        ).values(publisher_count=Count("id"))[:1]
        books_breakdown = Book.objects.annotate(
            publisher_count=Subquery(publisher_with_same_name),
            authors_count=Count("authors"),
        ).values_list("publisher_count", flat=True)
        self.assertSequenceEqual(books_breakdown, [1] * 6)

    def test_aggregation_exists_multivalued_outeref(self):
        self.assertCountEqual(
            Publisher.objects.annotate(
                books_exists=Exists(
                    Book.objects.filter(publisher=OuterRef("book__publisher"))
                ),
                books_count=Count("book"),
            ),
            Publisher.objects.all(),
        )

    def test_filter_in_subquery_or_aggregation(self):
        """
        Filtering against an aggregate requires the usage of the HAVING clause.

        If such a filter is unionized to a non-aggregate one the latter will
        also need to be moved to the HAVING clause and have its grouping
        columns used in the GROUP BY.

        When this is done with a subquery the specialized logic in charge of
        using outer reference columns to group should be used instead of the
        subquery itself as the latter might return multiple rows.
        """
        authors = Author.objects.annotate(
            Count("book"),
        ).filter(Q(book__count__gt=0) | Q(pk__in=Book.objects.values("authors")))
        self.assertCountEqual(authors, Author.objects.all())

    def test_aggregation_random_ordering(self):
        """Random() is not included in the GROUP BY when used for ordering."""
        authors = Author.objects.annotate(contact_count=Count("book")).order_by("?")
        self.assertQuerySetEqual(
            authors,
            [
                ("Adrian Holovaty", 1),
                ("Jacob Kaplan-Moss", 1),
                ("Brad Dayley", 1),
                ("James Bennett", 1),
                ("Jeffrey Forcier", 1),
                ("Paul Bissex", 1),
                ("Wesley J. Chun", 1),
                ("Stuart Russell", 1),
                ("Peter Norvig", 2),
            ],
            lambda a: (a.name, a.contact_count),
            ordered=False,
        )

    def test_order_by_aggregate_transform(self):
        class Mod100(Mod, Transform):
            def __init__(self, expr):
                super().__init__(expr, 100)

        sum_field = IntegerField()
        sum_field.register_lookup(Mod100, "mod100")
        publisher_pages = (
            Book.objects.values("publisher")
            .annotate(sum_pages=Sum("pages", output_field=sum_field))
            .order_by("sum_pages__mod100")
        )
        self.assertQuerySetEqual(
            publisher_pages,
            [
                {"publisher": self.p2.id, "sum_pages": 528},
                {"publisher": self.p4.id, "sum_pages": 946},
                {"publisher": self.p1.id, "sum_pages": 747},
                {"publisher": self.p3.id, "sum_pages": 1482},
            ],
        )

    def test_empty_result_optimization(self):
        with self.assertNumQueries(0):
            self.assertEqual(
                Publisher.objects.none().aggregate(
                    sum_awards=Sum("num_awards"),
                    books_count=Count("book"),
                ),
                {
                    "sum_awards": None,
                    "books_count": 0,
                },
            )
        # Expression without empty_result_set_value forces queries to be
        # executed even if they would return an empty result set.
        raw_books_count = Func("book", function="COUNT")
        raw_books_count.contains_aggregate = True
        with self.assertNumQueries(1):
            self.assertEqual(
                Publisher.objects.none().aggregate(
                    sum_awards=Sum("num_awards"),
                    books_count=raw_books_count,
                ),
                {
                    "sum_awards": None,
                    "books_count": 0,
                },
            )

    def test_coalesced_empty_result_set(self):
        with self.assertNumQueries(0):
            self.assertEqual(
                Publisher.objects.none().aggregate(
                    sum_awards=Coalesce(Sum("num_awards"), 0),
                )["sum_awards"],
                0,
            )
        # Multiple expressions.
        with self.assertNumQueries(0):
            self.assertEqual(
                Publisher.objects.none().aggregate(
                    sum_awards=Coalesce(Sum("num_awards"), None, 0),
                )["sum_awards"],
                0,
            )
        # Nested coalesce.
        with self.assertNumQueries(0):
            self.assertEqual(
                Publisher.objects.none().aggregate(
                    sum_awards=Coalesce(Coalesce(Sum("num_awards"), None), 0),
                )["sum_awards"],
                0,
            )
        # Expression coalesce.
        with self.assertNumQueries(1):
            self.assertIsInstance(
                Store.objects.none().aggregate(
                    latest_opening=Coalesce(
                        Max("original_opening"),
                        RawSQL("CURRENT_TIMESTAMP", []),
                    ),
                )["latest_opening"],
                datetime.datetime,
            )

    def test_aggregation_default_unsupported_by_count(self):
        """
        Tests that creating a Count aggregation with a default value raises a TypeError.

        This test verifies that the Count aggregation does not support a default value, 
        as it is not applicable to counting operations. If a default value is provided, 
        a TypeError is expected to be raised with a message indicating that default is 
        not allowed for Count.

        """
        msg = "Count does not allow default."
        with self.assertRaisesMessage(TypeError, msg):
            Count("age", default=0)

    def test_aggregation_default_unset(self):
        """

        Tests the default behavior of aggregation functions when no values are aggregated.

        Verifies that aggregating on an empty set of values returns None for various
        aggregation functions, including average, maximum, minimum, standard deviation,
        sum, and variance. The test applies these functions to a queryset of authors
        older than 100 years, which is expected to be empty.

        """
        for Aggregate in [Avg, Max, Min, StdDev, Sum, Variance]:
            with self.subTest(Aggregate):
                result = Author.objects.filter(age__gt=100).aggregate(
                    value=Aggregate("age"),
                )
                self.assertIsNone(result["value"])

    def test_aggregation_default_zero(self):
        """
        Checks the default behavior of various aggregation functions when there are no items to aggregate, verifying that they return zero as expected.

        The function tests the Aggregate functions (Avg, Max, Min, StdDev, Sum, Variance) 
        on an empty dataset to confirm that they return 0 when no items meet the filter criteria.
        """
        for Aggregate in [Avg, Max, Min, StdDev, Sum, Variance]:
            with self.subTest(Aggregate):
                result = Author.objects.filter(age__gt=100).aggregate(
                    value=Aggregate("age", default=0),
                )
                self.assertEqual(result["value"], 0)

    def test_aggregation_default_integer(self):
        for Aggregate in [Avg, Max, Min, StdDev, Sum, Variance]:
            with self.subTest(Aggregate):
                result = Author.objects.filter(age__gt=100).aggregate(
                    value=Aggregate("age", default=21),
                )
                self.assertEqual(result["value"], 21)

    def test_aggregation_default_expression(self):
        """

        Tests the behavior of aggregation functions when a default expression is provided.

        This test case checks that the default expression is correctly evaluated when the 
        query set used in the aggregation is empty. It tests multiple aggregation functions 
        including average, maximum, minimum, standard deviation, sum, and variance, to 
        ensure consistent behavior across all of them.

        The test verifies that the result of the aggregation is equal to the expected value 
        calculated from the default expression, which demonstrates the correct handling of 
        the default value in the aggregation.

        """
        for Aggregate in [Avg, Max, Min, StdDev, Sum, Variance]:
            with self.subTest(Aggregate):
                result = Author.objects.filter(age__gt=100).aggregate(
                    value=Aggregate("age", default=Value(5) * Value(7)),
                )
                self.assertEqual(result["value"], 35)

    def test_aggregation_default_group_by(self):
        """

        Tests the default group_by behavior in aggregation queries.

        Verifies that when aggregating a queryset of publishers and filtering for those with no books,
        the resulting queryset contains the expected publisher name and correctly calculates the number of books and total pages.
        The test case ensures that publishers without any books are correctly identified and that the total pages is set to 0 by default.

        """
        qs = (
            Publisher.objects.values("name")
            .annotate(
                books=Count("book"),
                pages=Sum("book__pages", default=0),
            )
            .filter(books=0)
        )
        self.assertSequenceEqual(
            qs,
            [{"name": "Jonno's House of Books", "books": 0, "pages": 0}],
        )

    def test_aggregation_default_compound_expression(self):
        # Scale rating to a percentage; default to 50% if no books published.
        formula = Avg("book__rating", default=2.5) * 20.0
        queryset = Publisher.objects.annotate(rating=formula).order_by("name")
        self.assertSequenceEqual(
            queryset.values("name", "rating"),
            [
                {"name": "Apress", "rating": 85.0},
                {"name": "Jonno's House of Books", "rating": 50.0},
                {"name": "Morgan Kaufmann", "rating": 100.0},
                {"name": "Prentice Hall", "rating": 80.0},
                {"name": "Sams", "rating": 60.0},
            ],
        )

    def test_aggregation_default_using_time_from_python(self):
        expr = Min(
            "store__friday_night_closing",
            filter=~Q(store__name="Amazon.com"),
            default=datetime.time(17),
        )
        if connection.vendor == "mysql":
            # Workaround for #30224 for MySQL & MariaDB.
            expr.default = Cast(expr.default, TimeField())
        queryset = Book.objects.annotate(oldest_store_opening=expr).order_by("isbn")
        self.assertSequenceEqual(
            queryset.values("isbn", "oldest_store_opening"),
            [
                {"isbn": "013235613", "oldest_store_opening": datetime.time(21, 30)},
                {
                    "isbn": "013790395",
                    "oldest_store_opening": datetime.time(23, 59, 59),
                },
                {"isbn": "067232959", "oldest_store_opening": datetime.time(17)},
                {"isbn": "155860191", "oldest_store_opening": datetime.time(21, 30)},
                {
                    "isbn": "159059725",
                    "oldest_store_opening": datetime.time(23, 59, 59),
                },
                {"isbn": "159059996", "oldest_store_opening": datetime.time(21, 30)},
            ],
        )

    def test_aggregation_default_using_time_from_database(self):
        now = timezone.now().astimezone(datetime.timezone.utc)
        expr = Min(
            "store__friday_night_closing",
            filter=~Q(store__name="Amazon.com"),
            default=TruncHour(NowUTC(), output_field=TimeField()),
        )
        queryset = Book.objects.annotate(oldest_store_opening=expr).order_by("isbn")
        self.assertSequenceEqual(
            queryset.values("isbn", "oldest_store_opening"),
            [
                {"isbn": "013235613", "oldest_store_opening": datetime.time(21, 30)},
                {
                    "isbn": "013790395",
                    "oldest_store_opening": datetime.time(23, 59, 59),
                },
                {"isbn": "067232959", "oldest_store_opening": datetime.time(now.hour)},
                {"isbn": "155860191", "oldest_store_opening": datetime.time(21, 30)},
                {
                    "isbn": "159059725",
                    "oldest_store_opening": datetime.time(23, 59, 59),
                },
                {"isbn": "159059996", "oldest_store_opening": datetime.time(21, 30)},
            ],
        )

    def test_aggregation_default_using_date_from_python(self):
        """

        Tests the aggregation of a date field with a default value using a Min expression.

        This test case verifies that the Min aggregation function returns the earliest date
        for a publisher's book publication dates. If no publication date is found for a
        publisher, a default date of January 1, 1970 is used. The test checks the results
        against a predefined set of expected values.

        The test also accounts for differences in database vendor implementations by
        casting the default date to a DateField for MySQL databases.

        """
        expr = Min("book__pubdate", default=datetime.date(1970, 1, 1))
        if connection.vendor == "mysql":
            # Workaround for #30224 for MySQL & MariaDB.
            expr.default = Cast(expr.default, DateField())
        queryset = Publisher.objects.annotate(earliest_pubdate=expr).order_by("name")
        self.assertSequenceEqual(
            queryset.values("name", "earliest_pubdate"),
            [
                {"name": "Apress", "earliest_pubdate": datetime.date(2007, 12, 6)},
                {
                    "name": "Jonno's House of Books",
                    "earliest_pubdate": datetime.date(1970, 1, 1),
                },
                {
                    "name": "Morgan Kaufmann",
                    "earliest_pubdate": datetime.date(1991, 10, 15),
                },
                {
                    "name": "Prentice Hall",
                    "earliest_pubdate": datetime.date(1995, 1, 15),
                },
                {"name": "Sams", "earliest_pubdate": datetime.date(2008, 3, 3)},
            ],
        )

    def test_aggregation_default_using_date_from_database(self):
        now = timezone.now().astimezone(datetime.timezone.utc)
        expr = Min("book__pubdate", default=TruncDate(NowUTC()))
        queryset = Publisher.objects.annotate(earliest_pubdate=expr).order_by("name")
        self.assertSequenceEqual(
            queryset.values("name", "earliest_pubdate"),
            [
                {"name": "Apress", "earliest_pubdate": datetime.date(2007, 12, 6)},
                {"name": "Jonno's House of Books", "earliest_pubdate": now.date()},
                {
                    "name": "Morgan Kaufmann",
                    "earliest_pubdate": datetime.date(1991, 10, 15),
                },
                {
                    "name": "Prentice Hall",
                    "earliest_pubdate": datetime.date(1995, 1, 15),
                },
                {"name": "Sams", "earliest_pubdate": datetime.date(2008, 3, 3)},
            ],
        )

    def test_aggregation_default_using_datetime_from_python(self):
        """

        Tests the default behavior of aggregation using datetime objects when
        annotating a QuerySet. Specifically, it verifies that the minimum
        'store__original_opening' date is correctly calculated for each book,
        excluding stores named 'Amazon.com' and using a default value of January 1, 1970,
        if no valid date is found. The results are then ordered by ISBN.

        """
        expr = Min(
            "store__original_opening",
            filter=~Q(store__name="Amazon.com"),
            default=datetime.datetime(1970, 1, 1),
        )
        if connection.vendor == "mysql":
            # Workaround for #30224 for MySQL & MariaDB.
            expr.default = Cast(expr.default, DateTimeField())
        queryset = Book.objects.annotate(oldest_store_opening=expr).order_by("isbn")
        self.assertSequenceEqual(
            queryset.values("isbn", "oldest_store_opening"),
            [
                {
                    "isbn": "013235613",
                    "oldest_store_opening": datetime.datetime(1945, 4, 25, 16, 24, 14),
                },
                {
                    "isbn": "013790395",
                    "oldest_store_opening": datetime.datetime(2001, 3, 15, 11, 23, 37),
                },
                {
                    "isbn": "067232959",
                    "oldest_store_opening": datetime.datetime(1970, 1, 1),
                },
                {
                    "isbn": "155860191",
                    "oldest_store_opening": datetime.datetime(1945, 4, 25, 16, 24, 14),
                },
                {
                    "isbn": "159059725",
                    "oldest_store_opening": datetime.datetime(2001, 3, 15, 11, 23, 37),
                },
                {
                    "isbn": "159059996",
                    "oldest_store_opening": datetime.datetime(1945, 4, 25, 16, 24, 14),
                },
            ],
        )

    def test_aggregation_default_using_datetime_from_database(self):
        """
        =\\"\"\"
        Tests the aggregation of store opening dates using the datetime field from the database, 
        with default value set to the current hour when no opening date is available for a store, 
        excluding 'Amazon.com' stores from the aggregation.

        The test annotates a Book queryset with the oldest store opening date for each book, 
        using a TruncHour function to truncate the current datetime to the hour, 
        and then orders the queryset by ISBN.

        Asserts that the resulting queryset matches the expected sequence of ISBN and oldest store opening dates.
        \\"\"\\"
        """
        now = timezone.now().astimezone(datetime.timezone.utc)
        expr = Min(
            "store__original_opening",
            filter=~Q(store__name="Amazon.com"),
            default=TruncHour(NowUTC(), output_field=DateTimeField()),
        )
        queryset = Book.objects.annotate(oldest_store_opening=expr).order_by("isbn")
        self.assertSequenceEqual(
            queryset.values("isbn", "oldest_store_opening"),
            [
                {
                    "isbn": "013235613",
                    "oldest_store_opening": datetime.datetime(1945, 4, 25, 16, 24, 14),
                },
                {
                    "isbn": "013790395",
                    "oldest_store_opening": datetime.datetime(2001, 3, 15, 11, 23, 37),
                },
                {
                    "isbn": "067232959",
                    "oldest_store_opening": now.replace(
                        minute=0, second=0, microsecond=0, tzinfo=None
                    ),
                },
                {
                    "isbn": "155860191",
                    "oldest_store_opening": datetime.datetime(1945, 4, 25, 16, 24, 14),
                },
                {
                    "isbn": "159059725",
                    "oldest_store_opening": datetime.datetime(2001, 3, 15, 11, 23, 37),
                },
                {
                    "isbn": "159059996",
                    "oldest_store_opening": datetime.datetime(1945, 4, 25, 16, 24, 14),
                },
            ],
        )

    def test_aggregation_default_using_duration_from_python(self):
        result = Publisher.objects.filter(num_awards__gt=3).aggregate(
            value=Sum("duration", default=datetime.timedelta(0)),
        )
        self.assertEqual(result["value"], datetime.timedelta(0))

    def test_aggregation_default_using_duration_from_database(self):
        result = Publisher.objects.filter(num_awards__gt=3).aggregate(
            value=Sum("duration", default=Now() - Now()),
        )
        self.assertEqual(result["value"], datetime.timedelta(0))

    def test_aggregation_default_using_decimal_from_python(self):
        """

        Tests the aggregation function using a default Decimal value.

        This function verifies that when aggregating objects with a condition that 
        yields no results, the default value is correctly returned. In this case, 
        it checks that the sum of book prices with a rating less than 3.0 returns 
        a default value of 0.00 when no such books exist.

        Returns:
            None

        Raises:
            AssertionError: If the aggregation result does not match the expected default value.

        """
        result = Book.objects.filter(rating__lt=3.0).aggregate(
            value=Sum("price", default=Decimal("0.00")),
        )
        self.assertEqual(result["value"], Decimal("0.00"))

    def test_aggregation_default_using_decimal_from_database(self):
        """
        Tests the default value of a database aggregation operation using decimal values.

        This function checks that when aggregating a numeric field with a default value,
        the result is accurate to a high degree of precision.

        The test case uses a query that filters books with a rating less than 3.0 and
        applies the Sum aggregation function with a default value of Pi. The result is
        then compared to the expected value using a high degree of precision (6 decimal places).
        """
        result = Book.objects.filter(rating__lt=3.0).aggregate(
            value=Sum("price", default=Pi()),
        )
        self.assertAlmostEqual(result["value"], Decimal.from_float(math.pi), places=6)

    def test_aggregation_default_passed_another_aggregate(self):
        """
        Tests that an aggregation function with a default value can be used to calculate a summary metric.

        The function aggregates a collection of objects, applying a filter to only consider objects with a rating less than 3.0.
        If no objects match the filter, the function returns a default value calculated from the average number of pages in all objects, divided by 10.0.

        The result is then compared to an expected value to verify the correctness of the aggregation calculation.

        :raises AssertionError: if the calculated value does not match the expected value within a tolerance of 2 decimal places.
        """
        result = Book.objects.aggregate(
            value=Sum("price", filter=Q(rating__lt=3.0), default=Avg("pages") / 10.0),
        )
        self.assertAlmostEqual(result["value"], Decimal("61.72"), places=2)

    def test_aggregation_default_after_annotation(self):
        """
        Tester for aggregation on annotated database query results with a default value.

         This test case checks if the aggregation function correctly calculates the sum of a double value of a specific field, 
         using a default value when no results are found. The expected result is then compared to a predefined value for validation.
        """
        result = Publisher.objects.annotate(
            double_num_awards=F("num_awards") * 2,
        ).aggregate(value=Sum("double_num_awards", default=0))
        self.assertEqual(result["value"], 40)

    def test_aggregation_default_not_in_aggregate(self):
        """
        Tests the aggregation of publisher objects with a default value for average book rating.

        This test case verifies that the average rating of books is correctly annotated with a default value when it's not in the aggregate, and the total number of awards for publishers is aggregated correctly. The test expects the sum of the number of awards to be 20.

        :raises AssertionError: If the sum of the number of awards does not match the expected value
        """
        result = Publisher.objects.annotate(
            avg_rating=Avg("book__rating", default=2.5),
        ).aggregate(Sum("num_awards"))
        self.assertEqual(result["num_awards__sum"], 20)

    def test_exists_none_with_aggregate(self):
        """
        Tests that annotated queries with Exists and empty subqueries return all objects.

         This test case verifies the behavior of the Exists annotation in conjunction with an 
         aggregate function when the subquery is empty, ensuring that the main query returns 
         all objects as expected. The test asserts the length of the resulting queryset is 
         equal to the total number of books, implying that the annotation does not filter out 
         any objects when the subquery does not produce any results.
        """
        qs = Book.objects.annotate(
            count=Count("id"),
            exists=Exists(Author.objects.none()),
        )
        self.assertEqual(len(qs), 6)

    def test_alias_sql_injection(self):
        """
        Tests that using a malicious alias that attempts to inject SQL fails with a ValueError.

        The function checks that an AggregateQuery with a crafted alias containing SQL injection characters raises an error.
        This ensures that the system prevents malicious users from injecting arbitrary SQL code through crafted aliases.

        Args: None

        Returns: None

        Raises:
            ValueError: If the alias contains invalid characters such as whitespace, quotation marks, semicolons, or SQL comments.

        """
        crafted_alias = """injected_name" from "aggregation_author"; --"""
        msg = (
            "Column aliases cannot contain whitespace characters, quotation marks, "
            "semicolons, or SQL comments."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Author.objects.aggregate(**{crafted_alias: Avg("age")})

    def test_exists_extra_where_with_aggregate(self):
        """

        Tests the existence of an extra where clause with aggregate functions in a query.

        Verifies that a query correctly applies an extra where clause when used in conjunction 
        with aggregate functions such as Count and Exists, ensuring the expected results are returned.

        """
        qs = Book.objects.annotate(
            count=Count("id"),
            exists=Exists(Author.objects.extra(where=["1=0"])),
        )
        self.assertEqual(len(qs), 6)

    def test_multiple_aggregate_references(self):
        """

        Tests the functionality of referencing multiple aggregate values within a queryset.

        Verifies that Django's ORM correctly calculates and returns aggregate values when 
        multiple aggregate references are used. This test case specifically checks the 
        usage of Count and Coalesce aggregate functions to ensure they are correctly 
        applied to a model's related objects. 

        The test validates the expected output by comparing the actual aggregate values 
        returned from the database with the expected results.

        """
        aggregates = Author.objects.aggregate(
            total_books=Count("book"),
            coalesced_total_books=Coalesce("total_books", 0),
        )
        self.assertEqual(
            aggregates,
            {
                "total_books": 10,
                "coalesced_total_books": 10,
            },
        )

    def test_group_by_reference_subquery(self):
        """

        Tests the ability to filter publishers based on a subquery that groups authors by their book's publisher.

        This test case verifies that the publishers retrieved using a subquery are correct.
        It ensures that the subset of publishers, whose authors have written books, matches the expected set of publishers.

        """
        author_qs = (
            Author.objects.annotate(publisher_id=F("book__publisher"))
            .values("publisher_id")
            .annotate(cnt=Count("*"))
            .values("publisher_id")
        )
        qs = Publisher.objects.filter(pk__in=author_qs)
        self.assertCountEqual(qs, [self.p1, self.p2, self.p3, self.p4])

    def test_having_with_no_group_by(self):
        author_qs = (
            Author.objects.values(static_value=Value("static-value"))
            .annotate(sum=Sum("age"))
            .filter(sum__gte=0)
            .values_list("sum", flat=True)
        )
        self.assertEqual(list(author_qs), [337])


class AggregateAnnotationPruningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a1 = Author.objects.create(age=1)
        cls.a2 = Author.objects.create(age=2)
        cls.p1 = Publisher.objects.create(num_awards=1)
        cls.p2 = Publisher.objects.create(num_awards=0)
        cls.b1 = Book.objects.create(
            name="b1",
            publisher=cls.p1,
            pages=100,
            rating=4.5,
            price=10,
            contact=cls.a1,
            pubdate=datetime.date.today(),
        )
        cls.b1.authors.add(cls.a1)
        cls.b2 = Book.objects.create(
            name="b2",
            publisher=cls.p2,
            pages=1000,
            rating=3.2,
            price=50,
            contact=cls.a2,
            pubdate=datetime.date.today(),
        )
        cls.b2.authors.add(cls.a1, cls.a2)

    def test_unused_aliased_aggregate_pruned(self):
        """

        Tests that unused aliased aggregate fields are pruned from the SQL query.

        This test case verifies that when an aliased aggregate field (in this case, 'authors_count')
        is not used in the query, it is removed from the generated SQL. It also checks that the
        query is wrapped in a subquery as required.

        The test asserts that the number of books is correctly counted, and that the generated
        SQL query does not include the unused aliased field 'authors_count'. It also checks
        that the query is executed as a subquery by verifying that the 'SELECT' statement
        appears twice in the SQL query.

        """
        with CaptureQueriesContext(connection) as ctx:
            cnt = Book.objects.alias(
                authors_count=Count("authors"),
            ).count()
        self.assertEqual(cnt, 2)
        sql = ctx.captured_queries[0]["sql"].lower()
        self.assertEqual(sql.count("select"), 2, "Subquery wrapping required")
        self.assertNotIn("authors_count", sql)

    def test_unused_aliased_aggregate_and_annotation_reverse_fk(self):
        """
        Tests the annotation and aggregation of aliased fields in a reverse foreign key relationship.

        This test verifies that the total number of pages and the presence of highly rated books 
        can be correctly calculated for each publisher. It checks if the annotation correctly 
        identifies books with a rating greater than 4.0 and if the total number of pages is 
        accurately aggregated. The result is then compared to the expected number of publishers 
        to ensure the query produces the correct output.
        """
        Book.objects.create(
            name="b3",
            publisher=self.p2,
            pages=1000,
            rating=4.2,
            price=50,
            contact=self.a2,
            pubdate=datetime.date.today(),
        )
        qs = Publisher.objects.annotate(
            total_pages=Sum("book__pages"),
            good_book=Case(
                When(book__rating__gt=4.0, then=Value(True)),
                default=Value(False),
            ),
        )
        self.assertEqual(qs.count(), 3)

    def test_unused_aliased_aggregate_and_annotation_reverse_fk_grouped(self):
        Book.objects.create(
            name="b3",
            publisher=self.p2,
            pages=1000,
            rating=4.2,
            price=50,
            contact=self.a2,
            pubdate=datetime.date.today(),
        )
        qs = (
            Publisher.objects.values("id", "name")
            .annotate(total_pages=Sum("book__pages"))
            .annotate(
                good_book=Case(
                    When(book__rating__gt=4.0, then=Value(True)),
                    default=Value(False),
                )
            )
        )
        self.assertEqual(qs.count(), 3)

    def test_non_aggregate_annotation_pruned(self):
        """
        Tests that non-aggregate annotations are pruned from the SQL query.

        This test ensures that when an annotation is not used in an aggregate function, 
        it is removed from the generated SQL query to prevent unnecessary subqueries. 

        It verifies that the SQL query generated by the ORM does not contain the 
        annotation column and that only a single SELECT statement is used.
        """
        with CaptureQueriesContext(connection) as ctx:
            Book.objects.annotate(
                name_lower=Lower("name"),
            ).count()
        sql = ctx.captured_queries[0]["sql"].lower()
        self.assertEqual(sql.count("select"), 1, "No subquery wrapping required")
        self.assertNotIn("name_lower", sql)

    def test_unreferenced_aggregate_annotation_pruned(self):
        """
        Test that unreferenced aggregate annotations are pruned from the SQL query.

        This test case verifies that when an aggregate annotation, such as the count of authors, is added to a query but not actually used, it does not appear in the generated SQL. The test checks that the query count is correct and that the SQL query contains the expected subqueries, but does not include the unreferenced annotation.
        """
        with CaptureQueriesContext(connection) as ctx:
            cnt = Book.objects.annotate(
                authors_count=Count("authors"),
            ).count()
        self.assertEqual(cnt, 2)
        sql = ctx.captured_queries[0]["sql"].lower()
        self.assertEqual(sql.count("select"), 2, "Subquery wrapping required")
        self.assertNotIn("authors_count", sql)

    def test_referenced_aggregate_annotation_kept(self):
        with CaptureQueriesContext(connection) as ctx:
            Book.objects.annotate(
                authors_count=Count("authors"),
            ).aggregate(Avg("authors_count"))
        sql = ctx.captured_queries[0]["sql"].lower()
        self.assertEqual(sql.count("select"), 2, "Subquery wrapping required")
        self.assertEqual(sql.count("authors_count"), 2)

    def test_referenced_group_by_annotation_kept(self):
        queryset = Book.objects.values(pages_mod=Mod("pages", 10)).annotate(
            mod_count=Count("*")
        )
        self.assertEqual(queryset.count(), 1)

    def test_referenced_subquery_requires_wrapping(self):
        total_books_qs = (
            Author.book_set.through.objects.values("author")
            .filter(author=OuterRef("pk"))
            .annotate(total=Count("book"))
        )
        with self.assertNumQueries(1) as ctx:
            aggregate = (
                Author.objects.annotate(
                    total_books=Subquery(total_books_qs.values("total"))
                )
                .values("pk", "total_books")
                .aggregate(
                    sum_total_books=Sum("total_books"),
                )
            )
        sql = ctx.captured_queries[0]["sql"].lower()
        self.assertEqual(sql.count("select"), 3, "Subquery wrapping required")
        self.assertEqual(aggregate, {"sum_total_books": 3})

    def test_referenced_composed_subquery_requires_wrapping(self):
        """

        Tests that a referenced composed subquery requires wrapping.

        This test verifies that when a subquery is used within an aggregate function 
        and referenced in the outer query, it is correctly wrapped in a subquery.
        The test checks the generated SQL query to ensure that wrapping occurs 
        and that the query produces the expected results.

        It validates the behavior of the database query when using a subquery 
        within an aggregate function and referencing the result in the outer query.
        The test case ensures that the database query is optimized by using 
        appropriate subquery wrapping.

        """
        total_books_qs = (
            Author.book_set.through.objects.values("author")
            .filter(author=OuterRef("pk"))
            .annotate(total=Count("book"))
        )
        with self.assertNumQueries(1) as ctx:
            aggregate = (
                Author.objects.annotate(
                    total_books=Subquery(total_books_qs.values("total")),
                    total_books_ref=F("total_books") / 1,
                )
                .values("pk", "total_books_ref")
                .aggregate(
                    sum_total_books=Sum("total_books_ref"),
                )
            )
        sql = ctx.captured_queries[0]["sql"].lower()
        self.assertEqual(sql.count("select"), 3, "Subquery wrapping required")
        self.assertEqual(aggregate, {"sum_total_books": 3})

    @skipUnlessDBFeature("supports_over_clause")
    def test_referenced_window_requires_wrapping(self):
        """

        Tests the requirement of wrapping window functions in a subquery when referenced.

        This test case verifies that when a window function is used in a query and then
        referenced in an aggregation, Django correctly wraps the window function in a
        subquery to ensure valid SQL. The test checks the generated SQL and the
        resulting aggregation values to confirm this behavior.

        """
        total_books_qs = Book.objects.annotate(
            avg_publisher_pages=Coalesce(
                Window(Avg("pages"), partition_by=F("publisher")),
                0.0,
            )
        )
        with self.assertNumQueries(1) as ctx:
            aggregate = total_books_qs.aggregate(
                sum_avg_publisher_pages=Sum("avg_publisher_pages"),
                books_count=Count("id"),
            )
        sql = ctx.captured_queries[0]["sql"].lower()
        self.assertEqual(sql.count("select"), 2, "Subquery wrapping required")
        self.assertEqual(
            aggregate,
            {"sum_avg_publisher_pages": 1100.0, "books_count": 2},
        )

    def test_aggregate_reference_lookup_rhs(self):
        """

        Tests the aggregate reference lookup on the right-hand side of a query.

        This function verifies that the annotation of a model with an aggregate value,
        and the subsequent aggregation of the model using a filter referencing the annotation,
        produces the expected result. The test case checks that the count of objects
        where the id matches the annotated maximum book author, is equal to 1.

        :raises AssertionError: If the count of matching objects is not equal to 1.

        """
        aggregates = Author.objects.annotate(
            max_book_author=Max("book__authors"),
        ).aggregate(count=Count("id", filter=Q(id=F("max_book_author"))))
        self.assertEqual(aggregates, {"count": 1})

    def test_aggregate_reference_lookup_rhs_iter(self):
        """

        Tests the functionality of aggregate reference lookup on the right-hand side of an expression.

        This test case verifies that Django's ORM correctly handles annotations and aggregates 
        when used in conjunction with filters and F expressions. It checks if the annotation 
        'max_book_author' is properly applied to the 'Author' objects and if the resulting 
        aggregate count matches the expected value.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the aggregate count does not match the expected value.

        """
        aggregates = Author.objects.annotate(
            max_book_author=Max("book__authors"),
        ).aggregate(count=Count("id", filter=Q(id__in=[F("max_book_author"), 0])))
        self.assertEqual(aggregates, {"count": 1})

    def test_aggregate_combined_queries(self):
        # Combined queries could have members in their values select mask while
        # others have them in their annotation mask which makes annotation
        # pruning complex to implement hence why it's not implemented.
        """
        Tests the aggregation of combined queries using the union operation.

        Verifies that the union of two separate queries, one retrieving authors and the other retrieving books, 
        returns the expected number of rows when both queries have their fields restricted to 'age' and a constant 'other' value.

        The test confirms that the resulting queryset contains the combined results of both queries, 
        with each row containing the specified fields. The expected result count is 3, 
        indicating that the queries have been successfully combined and the resulting rows are as expected.
        """
        qs = Author.objects.values(
            "age",
            other=Value(0),
        ).union(
            Book.objects.values(
                age=Value(0),
                other=Value(0),
            )
        )
        self.assertEqual(qs.count(), 3)
