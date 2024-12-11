import datetime
from decimal import Decimal

from django.core.exceptions import FieldDoesNotExist, FieldError
from django.db.models import (
    BooleanField,
    Case,
    CharField,
    Count,
    DateTimeField,
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    FloatField,
    Func,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.expressions import RawSQL
from django.db.models.functions import (
    Cast,
    Coalesce,
    ExtractYear,
    Floor,
    Length,
    Lower,
    Trim,
)
from django.db.models.sql.query import get_field_names_from_opts
from django.test import TestCase, skipUnlessDBFeature
from django.test.utils import register_lookup

from .models import (
    Author,
    Book,
    Company,
    DepartmentStore,
    Employee,
    Publisher,
    Store,
    Ticket,
)


class NonAggregateAnnotationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Class method to set up test data for the application.

        This method creates a set of authors, publishers, books, and stores, and establishes relationships between them.
        The created data includes:
            - 9 authors with varying ages and friendships
            - 5 publishers with different numbers of awards
            - 6 books with unique ISBNs, names, ratings, prices, and publication dates
            - 3 stores with different opening times and book collections

        These test data are used to populate the database for testing purposes, providing a comprehensive dataset for evaluating the application's functionality.
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

        cls.p1 = Publisher.objects.create(name="Apress", num_awards=3)
        cls.p2 = Publisher.objects.create(name="Sams", num_awards=1)
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

        cls.s1 = Store.objects.create(
            name="Amazon.com",
            original_opening=datetime.datetime(1994, 4, 23, 9, 17, 42),
            friday_night_closing=datetime.time(23, 59, 59),
        )
        cls.s2 = Store.objects.create(
            name="Books.com",
            original_opening=datetime.datetime(2001, 3, 15, 11, 23, 37),
            friday_night_closing=datetime.time(23, 59, 59),
        )
        cls.s3 = Store.objects.create(
            name="Mamma and Pappa's Books",
            original_opening=datetime.datetime(1945, 4, 25, 16, 24, 14),
            friday_night_closing=datetime.time(21, 30),
        )
        cls.s1.books.add(cls.b1, cls.b2, cls.b3, cls.b4, cls.b5, cls.b6)
        cls.s2.books.add(cls.b1, cls.b3, cls.b5, cls.b6)
        cls.s3.books.add(cls.b3, cls.b4, cls.b6)

    def test_basic_annotation(self):
        books = Book.objects.annotate(is_book=Value(1))
        for book in books:
            self.assertEqual(book.is_book, 1)

    def test_basic_f_annotation(self):
        books = Book.objects.annotate(another_rating=F("rating"))
        for book in books:
            self.assertEqual(book.another_rating, book.rating)

    def test_joined_annotation(self):
        books = Book.objects.select_related("publisher").annotate(
            num_awards=F("publisher__num_awards")
        )
        for book in books:
            self.assertEqual(book.num_awards, book.publisher.num_awards)

    def test_joined_transformed_annotation(self):
        """

        Tests the annotation of employee objects with the year their store was originally opened.

        This test case creates a set of employee objects and then annotates them with the year their associated store was opened. It then verifies that the annotated year matches the actual year stored in the store's original opening date.

        The test ensures that the joined and transformed annotation is correctly applied to the employee objects, and that the resulting annotated value is accurate.

        """
        Employee.objects.bulk_create(
            [
                Employee(
                    first_name="John",
                    last_name="Doe",
                    age=18,
                    store=self.s1,
                    salary=15000,
                ),
                Employee(
                    first_name="Jane",
                    last_name="Jones",
                    age=30,
                    store=self.s2,
                    salary=30000,
                ),
                Employee(
                    first_name="Jo",
                    last_name="Smith",
                    age=55,
                    store=self.s3,
                    salary=50000,
                ),
            ]
        )
        employees = Employee.objects.annotate(
            store_opened_year=F("store__original_opening__year"),
        )
        for employee in employees:
            self.assertEqual(
                employee.store_opened_year,
                employee.store.original_opening.year,
            )

    def test_custom_transform_annotation(self):
        with register_lookup(DecimalField, Floor):
            books = Book.objects.annotate(floor_price=F("price__floor"))

        self.assertCountEqual(
            books.values_list("pk", "floor_price"),
            [
                (self.b1.pk, 30),
                (self.b2.pk, 23),
                (self.b3.pk, 29),
                (self.b4.pk, 29),
                (self.b5.pk, 82),
                (self.b6.pk, 75),
            ],
        )

    def test_chaining_transforms(self):
        """
        Checks the correct application of chained lookups and transformations on model fields.

        This test verifies that multiple database functions can be applied in sequence to a model field, ensuring that the output of one function is correctly passed as input to the next. Specifically, it tests the combination of trimming whitespace from a string field and then calculating its length. The test confirms that the resulting lengths are correctly annotated and retrieved from the database for a set of test companies.
        """
        Company.objects.create(name=" Django Software Foundation  ")
        Company.objects.create(name="Yahoo")
        with register_lookup(CharField, Trim), register_lookup(CharField, Length):
            for expr in [Length("name__trim"), F("name__trim__length")]:
                with self.subTest(expr=expr):
                    self.assertCountEqual(
                        Company.objects.annotate(length=expr).values("name", "length"),
                        [
                            {"name": " Django Software Foundation  ", "length": 26},
                            {"name": "Yahoo", "length": 5},
                        ],
                    )

    def test_mixed_type_annotation_date_interval(self):
        active = datetime.datetime(2015, 3, 20, 14, 0, 0)
        duration = datetime.timedelta(hours=1)
        expires = datetime.datetime(2015, 3, 20, 14, 0, 0) + duration
        Ticket.objects.create(active_at=active, duration=duration)
        t = Ticket.objects.annotate(
            expires=ExpressionWrapper(
                F("active_at") + F("duration"), output_field=DateTimeField()
            )
        ).first()
        self.assertEqual(t.expires, expires)

    def test_mixed_type_annotation_numbers(self):
        """

        Tests the mixed type annotation of numbers by combining integer fields 'pages' and 'rating' 
        in a Book object and comparing the result with the expected combined value.

        The function verifies that the annotation correctly adds the 'pages' and 'rating' fields 
        and returns the result as an integer, ensuring that the database query produces the 
        expected outcome.

        """
        test = self.b1
        b = Book.objects.annotate(
            combined=ExpressionWrapper(
                F("pages") + F("rating"), output_field=IntegerField()
            )
        ).get(isbn=test.isbn)
        combined = int(test.pages + test.rating)
        self.assertEqual(b.combined, combined)

    def test_empty_expression_annotation(self):
        """
        Tests the annotation of a Django model with an empty expression.

        This function checks that annotating a model with an expression that always evaluates to False
        does not affect the number of results returned, and that the annotated field is correctly set
        to False for all instances. It tests this behavior with two different ways of specifying an empty
        expression: using an empty list and using a QuerySet with no results. The test ensures that the
        results are consistent with the expected behavior, validating the correctness of the annotation
        logic.
        """
        books = Book.objects.annotate(
            selected=ExpressionWrapper(Q(pk__in=[]), output_field=BooleanField())
        )
        self.assertEqual(len(books), Book.objects.count())
        self.assertTrue(all(not book.selected for book in books))

        books = Book.objects.annotate(
            selected=ExpressionWrapper(
                Q(pk__in=Book.objects.none()), output_field=BooleanField()
            )
        )
        self.assertEqual(len(books), Book.objects.count())
        self.assertTrue(all(not book.selected for book in books))

    def test_full_expression_annotation(self):
        books = Book.objects.annotate(
            selected=ExpressionWrapper(~Q(pk__in=[]), output_field=BooleanField()),
        )
        self.assertEqual(len(books), Book.objects.count())
        self.assertTrue(all(book.selected for book in books))

    def test_full_expression_wrapped_annotation(self):
        books = Book.objects.annotate(
            selected=Coalesce(~Q(pk__in=[]), True),
        )
        self.assertEqual(len(books), Book.objects.count())
        self.assertTrue(all(book.selected for book in books))

    def test_full_expression_annotation_with_aggregation(self):
        qs = Book.objects.filter(isbn="159059725").annotate(
            selected=ExpressionWrapper(~Q(pk__in=[]), output_field=BooleanField()),
            rating_count=Count("rating"),
        )
        self.assertEqual([book.rating_count for book in qs], [1])

    def test_aggregate_over_full_expression_annotation(self):
        qs = Book.objects.annotate(
            selected=ExpressionWrapper(~Q(pk__in=[]), output_field=BooleanField()),
        ).aggregate(selected__sum=Sum(Cast("selected", IntegerField())))
        self.assertEqual(qs["selected__sum"], Book.objects.count())

    def test_empty_queryset_annotation(self):
        """
        Tests the behavior of Django queryset annotations when using an empty subquery. 

        This test case verifies that annotating a queryset with a subquery that returns no results (i.e., an empty queryset) does not raise any errors and correctly assigns a value of None to the annotated field. The test ensures that the annotated field 'empty' is None for the first object in the queryset.
        """
        qs = Author.objects.annotate(empty=Subquery(Author.objects.values("id").none()))
        self.assertIsNone(qs.first().empty)

    def test_annotate_with_aggregation(self):
        books = Book.objects.annotate(is_book=Value(1), rating_count=Count("rating"))
        for book in books:
            self.assertEqual(book.is_book, 1)
            self.assertEqual(book.rating_count, 1)

    def test_combined_expression_annotation_with_aggregation(self):
        book = Book.objects.annotate(
            combined=ExpressionWrapper(
                Value(3) * Value(4), output_field=IntegerField()
            ),
            rating_count=Count("rating"),
        ).first()
        self.assertEqual(book.combined, 12)
        self.assertEqual(book.rating_count, 1)

    def test_combined_f_expression_annotation_with_aggregation(self):
        """

        Tests the functionality of combining F expressions with aggregation in a single database query.

        This test case verifies that the combination of F expressions and aggregation functions, such as Count, can be successfully applied to a Django model.
        The test checks if the annotated 'combined' field, calculated by multiplying 'price' and 'pages', and the 'rating_count' field, which counts the number of ratings, are correctly computed.

        The expected values are then asserted to ensure the correctness of the query result.

        """
        book = (
            Book.objects.filter(isbn="159059725")
            .annotate(
                combined=ExpressionWrapper(
                    F("price") * F("pages"), output_field=FloatField()
                ),
                rating_count=Count("rating"),
            )
            .first()
        )
        self.assertEqual(book.combined, 13410.0)
        self.assertEqual(book.rating_count, 1)

    @skipUnlessDBFeature("supports_boolean_expr_in_select_clause")
    def test_q_expression_annotation_with_aggregation(self):
        """

        Tests the annotation of QuerySets with boolean expressions in the SELECT clause,
        using Q expressions with ExpressionWrapper and Count aggregation.

        This test case verifies the correct annotation of a QuerySet with a boolean field
        indicating whether a book's publication date is null, and the count of ratings for
        each book. It checks that the expected boolean value is returned for a book with
        a non-null publication date and that the rating count is correctly calculated.

        """
        book = (
            Book.objects.filter(isbn="159059725")
            .annotate(
                isnull_pubdate=ExpressionWrapper(
                    Q(pubdate__isnull=True),
                    output_field=BooleanField(),
                ),
                rating_count=Count("rating"),
            )
            .first()
        )
        self.assertIs(book.isnull_pubdate, False)
        self.assertEqual(book.rating_count, 1)

    @skipUnlessDBFeature("supports_boolean_expr_in_select_clause")
    def test_grouping_by_q_expression_annotation(self):
        authors = (
            Author.objects.annotate(
                under_40=ExpressionWrapper(Q(age__lt=40), output_field=BooleanField()),
            )
            .values("under_40")
            .annotate(
                count_id=Count("id"),
            )
            .values("under_40", "count_id")
        )
        self.assertCountEqual(
            authors,
            [
                {"under_40": False, "count_id": 3},
                {"under_40": True, "count_id": 6},
            ],
        )

    def test_aggregate_over_annotation(self):
        agg = Author.objects.annotate(other_age=F("age")).aggregate(
            otherage_sum=Sum("other_age")
        )
        other_agg = Author.objects.aggregate(age_sum=Sum("age"))
        self.assertEqual(agg["otherage_sum"], other_agg["age_sum"])

    @skipUnlessDBFeature("can_distinct_on_fields")
    def test_distinct_on_with_annotation(self):
        store = Store.objects.create(
            name="test store",
            original_opening=datetime.datetime.now(),
            friday_night_closing=datetime.time(21, 00, 00),
        )
        names = [
            "Theodore Roosevelt",
            "Eleanor Roosevelt",
            "Franklin Roosevelt",
            "Ned Stark",
            "Catelyn Stark",
        ]
        for name in names:
            Employee.objects.create(
                store=store,
                first_name=name.split()[0],
                last_name=name.split()[1],
                age=30,
                salary=2000,
            )

        people = Employee.objects.annotate(
            name_lower=Lower("last_name"),
        ).distinct("name_lower")

        self.assertEqual({p.last_name for p in people}, {"Stark", "Roosevelt"})
        self.assertEqual(len(people), 2)

        people2 = Employee.objects.annotate(
            test_alias=F("store__name"),
        ).distinct("test_alias")
        self.assertEqual(len(people2), 1)

        lengths = (
            Employee.objects.annotate(
                name_len=Length("first_name"),
            )
            .distinct("name_len")
            .values_list("name_len", flat=True)
        )
        self.assertCountEqual(lengths, [3, 7, 8])

    def test_filter_annotation(self):
        books = Book.objects.annotate(is_book=Value(1)).filter(is_book=1)
        for book in books:
            self.assertEqual(book.is_book, 1)

    def test_filter_annotation_with_f(self):
        books = Book.objects.annotate(other_rating=F("rating")).filter(other_rating=3.5)
        for book in books:
            self.assertEqual(book.other_rating, 3.5)

    def test_filter_annotation_with_double_f(self):
        books = Book.objects.annotate(other_rating=F("rating")).filter(
            other_rating=F("rating")
        )
        for book in books:
            self.assertEqual(book.other_rating, book.rating)

    def test_filter_agg_with_double_f(self):
        books = Book.objects.annotate(sum_rating=Sum("rating")).filter(
            sum_rating=F("sum_rating")
        )
        for book in books:
            self.assertEqual(book.sum_rating, book.rating)

    def test_filter_wrong_annotation(self):
        with self.assertRaisesMessage(
            FieldError, "Cannot resolve keyword 'nope' into field."
        ):
            list(
                Book.objects.annotate(sum_rating=Sum("rating")).filter(
                    sum_rating=F("nope")
                )
            )

    def test_values_wrong_annotation(self):
        expected_message = (
            "Cannot resolve keyword 'annotation_typo' into field. Choices are: %s"
        )
        article_fields = ", ".join(
            ["annotation"] + sorted(get_field_names_from_opts(Book._meta))
        )
        with self.assertRaisesMessage(FieldError, expected_message % article_fields):
            Book.objects.annotate(annotation=Value(1)).values_list("annotation_typo")

    def test_decimal_annotation(self):
        salary = Decimal(10) ** -Employee._meta.get_field("salary").decimal_places
        Employee.objects.create(
            first_name="Max",
            last_name="Paine",
            store=Store.objects.first(),
            age=23,
            salary=salary,
        )
        self.assertEqual(
            Employee.objects.annotate(new_salary=F("salary") / 10).get().new_salary,
            salary / 10,
        )

    def test_filter_decimal_annotation(self):
        qs = (
            Book.objects.annotate(new_price=F("price") + 1)
            .filter(new_price=Decimal(31))
            .values_list("new_price")
        )
        self.assertEqual(qs.get(), (Decimal(31),))

    def test_combined_annotation_commutative(self):
        book1 = Book.objects.annotate(adjusted_rating=F("rating") + 2).get(
            pk=self.b1.pk
        )
        book2 = Book.objects.annotate(adjusted_rating=2 + F("rating")).get(
            pk=self.b1.pk
        )
        self.assertEqual(book1.adjusted_rating, book2.adjusted_rating)
        book1 = Book.objects.annotate(adjusted_rating=F("rating") + None).get(
            pk=self.b1.pk
        )
        book2 = Book.objects.annotate(adjusted_rating=None + F("rating")).get(
            pk=self.b1.pk
        )
        self.assertIs(book1.adjusted_rating, None)
        self.assertEqual(book1.adjusted_rating, book2.adjusted_rating)

    def test_update_with_annotation(self):
        book_preupdate = Book.objects.get(pk=self.b2.pk)
        Book.objects.annotate(other_rating=F("rating") - 1).update(
            rating=F("other_rating")
        )
        book_postupdate = Book.objects.get(pk=self.b2.pk)
        self.assertEqual(book_preupdate.rating - 1, book_postupdate.rating)

    def test_annotation_with_m2m(self):
        """

        Tests the annotation of a Book model instance with the age of its authors,
        where the author-book relationship is defined as a many-to-many field.

        Verifies that the annotation is correctly applied by checking the age of authors
        for a specific book, sorted in ascending order by the author's age.

        """
        books = (
            Book.objects.annotate(author_age=F("authors__age"))
            .filter(pk=self.b1.pk)
            .order_by("author_age")
        )
        self.assertEqual(books[0].author_age, 34)
        self.assertEqual(books[1].author_age, 35)

    def test_annotation_reverse_m2m(self):
        """

        Tests the correct annotation and reversal of a many-to-many relationship.

        This test case verifies that the store names associated with a specific book 
        ('Practical Django Projects') are correctly annotated and ordered.

        The test checks that the resulting queryset contains the expected store names, 
        in the correct order.

        """
        books = (
            Book.objects.annotate(
                store_name=F("store__name"),
            )
            .filter(
                name="Practical Django Projects",
            )
            .order_by("store_name")
        )

        self.assertQuerySetEqual(
            books,
            ["Amazon.com", "Books.com", "Mamma and Pappa's Books"],
            lambda b: b.store_name,
        )

    def test_values_annotation(self):
        """
        Annotations can reference fields in a values clause,
        and contribute to an existing values clause.
        """
        # annotate references a field in values()
        qs = Book.objects.values("rating").annotate(other_rating=F("rating") - 1)
        book = qs.get(pk=self.b1.pk)
        self.assertEqual(book["rating"] - 1, book["other_rating"])

        # filter refs the annotated value
        book = qs.get(other_rating=4)
        self.assertEqual(book["other_rating"], 4)

        # can annotate an existing values with a new field
        book = qs.annotate(other_isbn=F("isbn")).get(other_rating=4)
        self.assertEqual(book["other_rating"], 4)
        self.assertEqual(book["other_isbn"], "155860191")

    def test_values_fields_annotations_order(self):
        """
        Tests the order of annotated fields and values in a QuerySet.

        Verifies that annotated fields are correctly added to the result dictionary
        and that their values are calculated as expected. The test checks the
        ordering of the fields in the output dictionary, ensuring that they match
        the order specified in the values() method.

        The test case covers a scenario where an annotation is used to create a
        new field based on an existing field, and then both the annotated and
        original fields are included in the values() method. The result is then
        compared to the expected output, which includes the correct values for
        both fields in the correct order.
        """
        qs = Book.objects.annotate(other_rating=F("rating") - 1).values(
            "other_rating", "rating"
        )
        book = qs.get(pk=self.b1.pk)
        self.assertEqual(
            list(book.items()),
            [("other_rating", self.b1.rating - 1), ("rating", self.b1.rating)],
        )

    def test_values_with_pk_annotation(self):
        # annotate references a field in values() with pk
        publishers = Publisher.objects.values("id", "book__rating").annotate(
            total=Sum("book__rating")
        )
        for publisher in publishers.filter(pk=self.p1.pk):
            self.assertEqual(publisher["book__rating"], publisher["total"])

    def test_defer_annotation(self):
        """
        Deferred attributes can be referenced by an annotation,
        but they are not themselves deferred, and cannot be deferred.
        """
        qs = Book.objects.defer("rating").annotate(other_rating=F("rating") - 1)

        with self.assertNumQueries(2):
            book = qs.get(other_rating=4)
            self.assertEqual(book.rating, 5)
            self.assertEqual(book.other_rating, 4)

        with self.assertRaisesMessage(
            FieldDoesNotExist, "Book has no field named 'other_rating'"
        ):
            book = qs.defer("other_rating").get(other_rating=4)

    def test_mti_annotations(self):
        """
        Fields on an inherited model can be referenced by an
        annotated field.
        """
        d = DepartmentStore.objects.create(
            name="Angus & Robinson",
            original_opening=datetime.date(2014, 3, 8),
            friday_night_closing=datetime.time(21, 00, 00),
            chain="Westfield",
        )

        books = Book.objects.filter(rating__gt=4)
        for b in books:
            d.books.add(b)

        qs = (
            DepartmentStore.objects.annotate(
                other_name=F("name"),
                other_chain=F("chain"),
                is_open=Value(True, BooleanField()),
                book_isbn=F("books__isbn"),
            )
            .order_by("book_isbn")
            .filter(chain="Westfield")
        )

        self.assertQuerySetEqual(
            qs,
            [
                ("Angus & Robinson", "Westfield", True, "155860191"),
                ("Angus & Robinson", "Westfield", True, "159059725"),
            ],
            lambda d: (d.other_name, d.other_chain, d.is_open, d.book_isbn),
        )

    def test_null_annotation(self):
        """
        Annotating None onto a model round-trips
        """
        book = Book.objects.annotate(
            no_value=Value(None, output_field=IntegerField())
        ).first()
        self.assertIsNone(book.no_value)

    def test_order_by_annotation(self):
        """
        Tests if the function can correctly order authors by their annotated age.

        This test case utilizes the Django ORM's annotate and order_by functions to
        assign an alias 'other_age' to the 'age' field of each author and then orders
        the authors based on this annotated field. The test asserts that the ordered
        queryset matches the expected order of ages.

        The test result is evaluated as a sequence of ages in ascending order, which
        should match the predefined sequence of ages for a successful test.

         Note: The actual implementation relies on Django's ORM functionality and 
               its ability to support F expressions for dynamic calculations within 
               the database query.

        """
        authors = Author.objects.annotate(other_age=F("age")).order_by("other_age")
        self.assertQuerySetEqual(
            authors,
            [
                25,
                29,
                29,
                34,
                35,
                37,
                45,
                46,
                57,
            ],
            lambda a: a.other_age,
        )

    def test_order_by_aggregate(self):
        """

        Tests the ordering of authors by aggregate age count.

        This test case verifies that authors are correctly ordered by the age count in descending order, 
        and then by age in ascending order. The result set is compared with the expected output to 
        ensure that the query produces the correct ordering.

        The expected output includes a list of tuples, where each tuple contains the age of an author 
        and the count of authors with that age.

        """
        authors = (
            Author.objects.values("age")
            .annotate(age_count=Count("age"))
            .order_by("age_count", "age")
        )
        self.assertQuerySetEqual(
            authors,
            [
                (25, 1),
                (34, 1),
                (35, 1),
                (37, 1),
                (45, 1),
                (46, 1),
                (57, 1),
                (29, 2),
            ],
            lambda a: (a["age"], a["age_count"]),
        )

    def test_raw_sql_with_inherited_field(self):
        DepartmentStore.objects.create(
            name="Angus & Robinson",
            original_opening=datetime.date(2014, 3, 8),
            friday_night_closing=datetime.time(21),
            chain="Westfield",
            area=123,
        )
        tests = (
            ("name", "Angus & Robinson"),
            ("surface", 123),
            ("case when name='Angus & Robinson' then chain else name end", "Westfield"),
        )
        for sql, expected_result in tests:
            with self.subTest(sql=sql):
                self.assertSequenceEqual(
                    DepartmentStore.objects.annotate(
                        annotation=RawSQL(sql, ()),
                    ).values_list("annotation", flat=True),
                    [expected_result],
                )

    def test_annotate_exists(self):
        authors = Author.objects.annotate(c=Count("id")).filter(c__gt=1)
        self.assertFalse(authors.exists())

    def test_column_field_ordering(self):
        """
        Columns are aligned in the correct order for resolve_columns. This test
        will fail on MySQL if column ordering is out. Column fields should be
        aligned as:
        1. extra_select
        2. model_fields
        3. annotation_fields
        4. model_related_fields
        """
        store = Store.objects.first()
        Employee.objects.create(
            id=1,
            first_name="Max",
            manager=True,
            last_name="Paine",
            store=store,
            age=23,
            salary=Decimal(50000.00),
        )
        Employee.objects.create(
            id=2,
            first_name="Buffy",
            manager=False,
            last_name="Summers",
            store=store,
            age=18,
            salary=Decimal(40000.00),
        )

        qs = (
            Employee.objects.extra(select={"random_value": "42"})
            .select_related("store")
            .annotate(
                annotated_value=Value(17),
            )
        )

        rows = [
            (1, "Max", True, 42, "Paine", 23, Decimal(50000.00), store.name, 17),
            (2, "Buffy", False, 42, "Summers", 18, Decimal(40000.00), store.name, 17),
        ]

        self.assertQuerySetEqual(
            qs.order_by("id"),
            rows,
            lambda e: (
                e.id,
                e.first_name,
                e.manager,
                e.random_value,
                e.last_name,
                e.age,
                e.salary,
                e.store.name,
                e.annotated_value,
            ),
        )

    def test_column_field_ordering_with_deferred(self):
        store = Store.objects.first()
        Employee.objects.create(
            id=1,
            first_name="Max",
            manager=True,
            last_name="Paine",
            store=store,
            age=23,
            salary=Decimal(50000.00),
        )
        Employee.objects.create(
            id=2,
            first_name="Buffy",
            manager=False,
            last_name="Summers",
            store=store,
            age=18,
            salary=Decimal(40000.00),
        )

        qs = (
            Employee.objects.extra(select={"random_value": "42"})
            .select_related("store")
            .annotate(
                annotated_value=Value(17),
            )
        )

        rows = [
            (1, "Max", True, 42, "Paine", 23, Decimal(50000.00), store.name, 17),
            (2, "Buffy", False, 42, "Summers", 18, Decimal(40000.00), store.name, 17),
        ]

        # and we respect deferred columns!
        self.assertQuerySetEqual(
            qs.defer("age").order_by("id"),
            rows,
            lambda e: (
                e.id,
                e.first_name,
                e.manager,
                e.random_value,
                e.last_name,
                e.age,
                e.salary,
                e.store.name,
                e.annotated_value,
            ),
        )

    def test_custom_functions(self):
        Company(
            name="Apple",
            motto=None,
            ticker_name="APPL",
            description="Beautiful Devices",
        ).save()
        Company(
            name="Django Software Foundation",
            motto=None,
            ticker_name=None,
            description=None,
        ).save()
        Company(
            name="Google",
            motto="Do No Evil",
            ticker_name="GOOG",
            description="Internet Company",
        ).save()
        Company(
            name="Yahoo", motto=None, ticker_name=None, description="Internet Company"
        ).save()

        qs = Company.objects.annotate(
            tagline=Func(
                F("motto"),
                F("ticker_name"),
                F("description"),
                Value("No Tag"),
                function="COALESCE",
            )
        ).order_by("name")

        self.assertQuerySetEqual(
            qs,
            [
                ("Apple", "APPL"),
                ("Django Software Foundation", "No Tag"),
                ("Google", "Do No Evil"),
                ("Yahoo", "Internet Company"),
            ],
            lambda c: (c.name, c.tagline),
        )

    def test_custom_functions_can_ref_other_functions(self):
        Company(
            name="Apple",
            motto=None,
            ticker_name="APPL",
            description="Beautiful Devices",
        ).save()
        Company(
            name="Django Software Foundation",
            motto=None,
            ticker_name=None,
            description=None,
        ).save()
        Company(
            name="Google",
            motto="Do No Evil",
            ticker_name="GOOG",
            description="Internet Company",
        ).save()
        Company(
            name="Yahoo", motto=None, ticker_name=None, description="Internet Company"
        ).save()

        class Lower(Func):
            function = "LOWER"

        qs = (
            Company.objects.annotate(
                tagline=Func(
                    F("motto"),
                    F("ticker_name"),
                    F("description"),
                    Value("No Tag"),
                    function="COALESCE",
                )
            )
            .annotate(
                tagline_lower=Lower(F("tagline")),
            )
            .order_by("name")
        )

        # LOWER function supported by:
        # oracle, postgres, mysql, sqlite, sqlserver

        self.assertQuerySetEqual(
            qs,
            [
                ("Apple", "APPL".lower()),
                ("Django Software Foundation", "No Tag".lower()),
                ("Google", "Do No Evil".lower()),
                ("Yahoo", "Internet Company".lower()),
            ],
            lambda c: (c.name, c.tagline_lower),
        )

    def test_boolean_value_annotation(self):
        """
        Tests whether boolean value annotations are correctly applied to query results.

        This test case verifies that the `annotate` method can add boolean fields with predefined values to a query set. It checks that all query results have these boolean fields set to their expected values: True, False, and None.

        The test ensures that the resulting query set is not empty and that each item in the set has the correct boolean values. The test covers both non-nullable and nullable boolean fields.
        """
        books = Book.objects.annotate(
            is_book=Value(True, output_field=BooleanField()),
            is_pony=Value(False, output_field=BooleanField()),
            is_none=Value(None, output_field=BooleanField(null=True)),
        )
        self.assertGreater(len(books), 0)
        for book in books:
            self.assertIs(book.is_book, True)
            self.assertIs(book.is_pony, False)
            self.assertIsNone(book.is_none)

    def test_annotation_in_f_grouped_by_annotation(self):
        """

        Tests the annotation functionality in a queryset grouped by publisher name.

        This test case validates the ability to annotate a queryset with a calculated field,
        specifically by multiplying a constant value with an existing field, and then summing
        the result grouped by publisher name.

        The test expects the output to be a list of dictionaries, each containing the publisher
        name and the calculated sum of multiplied values.

        """
        qs = (
            Publisher.objects.annotate(multiplier=Value(3))
            # group by option => sum of value * multiplier
            .values("name")
            .annotate(multiplied_value_sum=Sum(F("multiplier") * F("num_awards")))
            .order_by()
        )
        self.assertCountEqual(
            qs,
            [
                {"multiplied_value_sum": 9, "name": "Apress"},
                {"multiplied_value_sum": 0, "name": "Jonno's House of Books"},
                {"multiplied_value_sum": 27, "name": "Morgan Kaufmann"},
                {"multiplied_value_sum": 21, "name": "Prentice Hall"},
                {"multiplied_value_sum": 3, "name": "Sams"},
            ],
        )

    def test_arguments_must_be_expressions(self):
        """

        Verifies that the arguments passed to QuerySet.annotate() are valid Django expressions.

        Ensures that only proper expressions are used when annotating a QuerySet, 
        preventing the incorrect usage of non-expression arguments such as fields 
        or boolean values. The function checks that attempting to annotate with 
        invalid arguments raises a TypeError with an appropriate error message, 
        indicating the specific invalid argument(s) passed to the annotate method.

        """
        msg = "QuerySet.annotate() received non-expression(s): %s."
        with self.assertRaisesMessage(TypeError, msg % BooleanField()):
            Book.objects.annotate(BooleanField())
        with self.assertRaisesMessage(TypeError, msg % True):
            Book.objects.annotate(is_book=True)
        with self.assertRaisesMessage(
            TypeError, msg % ", ".join([str(BooleanField()), "True"])
        ):
            Book.objects.annotate(BooleanField(), Value(False), is_book=True)

    def test_chaining_annotation_filter_with_m2m(self):
        """

        Tests the chaining of annotation filters with many-to-many relationships.

        Verifies that it is possible to filter a queryset based on multiple conditions
        and then annotate the results with values from related objects. The test
        specifically checks the correctness of the output when filtering by different
        conditions in a sequence, demonstrating that the annotations are correctly
        applied at each step.

        The expected outcome is a queryset containing the names of specific friends
        ('Jacob Kaplan-Moss' and 'James Bennett') for an author ('Adrian Holovaty'),
        reflecting the correct application of filters and annotations.

        """
        qs = (
            Author.objects.filter(
                name="Adrian Holovaty",
                friends__age=35,
            )
            .annotate(
                jacob_name=F("friends__name"),
            )
            .filter(
                friends__age=29,
            )
            .annotate(
                james_name=F("friends__name"),
            )
            .values("jacob_name", "james_name")
        )
        self.assertCountEqual(
            qs,
            [{"jacob_name": "Jacob Kaplan-Moss", "james_name": "James Bennett"}],
        )

    def test_annotation_filter_with_subquery(self):
        long_books_qs = (
            Book.objects.filter(
                publisher=OuterRef("pk"),
                pages__gt=400,
            )
            .values("publisher")
            .annotate(count=Count("pk"))
            .values("count")
        )
        publisher_books_qs = (
            Publisher.objects.annotate(
                total_books=Count("book"),
            )
            .filter(
                total_books=Subquery(long_books_qs, output_field=IntegerField()),
            )
            .values("name")
        )
        self.assertCountEqual(
            publisher_books_qs, [{"name": "Sams"}, {"name": "Morgan Kaufmann"}]
        )

    def test_annotation_and_alias_filter_in_subquery(self):
        """
        Tests that annotation and aliasing in a subquery works as expected.

        This test verifies that a Publisher queryset can be filtered based on a subquery 
        that utilizes annotation and aliasing. The subquery filters publishers who have 
        won more than 4 awards, annotates and aliases them, and the main query then 
        filters publishers based on the subquery. The test checks that the resulting 
        queryset contains the expected publishers.

        Ensures correct usage of the `annotate` and `alias` methods in combination 
        with subqueries to filter objects based on aggregated values and aliases.
        """
        awarded_publishers_qs = (
            Publisher.objects.filter(num_awards__gt=4)
            .annotate(publisher_annotate=Value(1))
            .alias(publisher_alias=Value(1))
        )
        qs = Publisher.objects.filter(pk__in=awarded_publishers_qs)
        self.assertCountEqual(qs, [self.p3, self.p4])

    def test_annotation_and_alias_filter_related_in_subquery(self):
        long_books_qs = (
            Book.objects.filter(pages__gt=400)
            .annotate(book_annotate=Value(1))
            .alias(book_alias=Value(1))
        )
        publisher_books_qs = Publisher.objects.filter(
            book__in=long_books_qs,
        ).values("name")
        self.assertCountEqual(
            publisher_books_qs,
            [
                {"name": "Apress"},
                {"name": "Sams"},
                {"name": "Prentice Hall"},
                {"name": "Morgan Kaufmann"},
            ],
        )

    def test_annotation_exists_none_query(self):
        self.assertIs(
            Author.objects.annotate(exists=Exists(Company.objects.none()))
            .get(pk=self.a1.pk)
            .exists,
            False,
        )

    def test_annotation_exists_aggregate_values_chaining(self):
        qs = (
            Book.objects.values("publisher")
            .annotate(
                has_authors=Exists(
                    Book.authors.through.objects.filter(book=OuterRef("pk"))
                ),
                max_pubdate=Max("pubdate"),
            )
            .values_list("max_pubdate", flat=True)
            .order_by("max_pubdate")
        )
        self.assertCountEqual(
            qs,
            [
                datetime.date(1991, 10, 15),
                datetime.date(2008, 3, 3),
                datetime.date(2008, 6, 23),
                datetime.date(2008, 11, 3),
            ],
        )

    @skipUnlessDBFeature("supports_subqueries_in_group_by")
    def test_annotation_subquery_and_aggregate_values_chaining(self):
        qs = (
            Book.objects.annotate(pub_year=ExtractYear("pubdate"))
            .values("pub_year")
            .annotate(
                top_rating=Subquery(
                    Book.objects.filter(pubdate__year=OuterRef("pub_year"))
                    .order_by("-rating")
                    .values("rating")[:1]
                ),
                total_pages=Sum("pages"),
            )
            .values("pub_year", "total_pages", "top_rating")
        )
        self.assertCountEqual(
            qs,
            [
                {"pub_year": 1991, "top_rating": 5.0, "total_pages": 946},
                {"pub_year": 1995, "top_rating": 4.0, "total_pages": 1132},
                {"pub_year": 2007, "top_rating": 4.5, "total_pages": 447},
                {"pub_year": 2008, "top_rating": 4.0, "total_pages": 1178},
            ],
        )

    def test_annotation_subquery_outerref_transform(self):
        """

        Tests the transformation of an annotation subquery that uses an OuterRef to reference the outer query.

        The test ensures that for each distinct publication year in a set of books, the highest rated book is correctly identified.
        It validates the functionality of annotating a queryset with a subquery that filters results based on the outer query's publication year,
        orders them by rating in descending order, and selects the top rating for each year.

        The expected outcome is a queryset containing the publication year and the corresponding highest rating for that year.

        """
        qs = Book.objects.annotate(
            top_rating_year=Subquery(
                Book.objects.filter(pubdate__year=OuterRef("pubdate__year"))
                .order_by("-rating")
                .values("rating")[:1]
            ),
        ).values("pubdate__year", "top_rating_year")
        self.assertCountEqual(
            qs,
            [
                {"pubdate__year": 1991, "top_rating_year": 5.0},
                {"pubdate__year": 1995, "top_rating_year": 4.0},
                {"pubdate__year": 2007, "top_rating_year": 4.5},
                {"pubdate__year": 2008, "top_rating_year": 4.0},
                {"pubdate__year": 2008, "top_rating_year": 4.0},
                {"pubdate__year": 2008, "top_rating_year": 4.0},
            ],
        )

    def test_annotation_aggregate_with_m2o(self):
        """

        Tests the aggregation of annotations on a model instance with a many-to-one relationship.

        This test case verifies that the annotation of aggregate values, in this case the maximum number of pages, 
        is correctly calculated for authors with and without associated books. The test checks that the 
        'max_pages' annotation is set to 0 for authors without books and to the maximum pages of their books 
        for authors with books.

        The test also ensures that the results are correctly returned when filtering authors by age.

        """
        qs = (
            Author.objects.filter(age__lt=30)
            .annotate(
                max_pages=Case(
                    When(book_contact_set__isnull=True, then=Value(0)),
                    default=Max(F("book__pages")),
                ),
            )
            .values("name", "max_pages")
        )
        self.assertCountEqual(
            qs,
            [
                {"name": "James Bennett", "max_pages": 300},
                {"name": "Paul Bissex", "max_pages": 0},
                {"name": "Wesley J. Chun", "max_pages": 0},
            ],
        )

    def test_alias_sql_injection(self):
        """

        Tests the handling of potential SQL injection attacks in Django ORM query 
        annotations through column aliases. Specifically, it checks that attempting 
        to use a crafted alias containing invalid characters (such as whitespace, 
        quotation marks, semicolons, or SQL comments) raises a ValueError with an 
        informative message. This ensures that the function protects against 
        maliciously constructed input that could lead to SQL injection vulnerabilities.

        """
        crafted_alias = """injected_name" from "annotations_book"; --"""
        msg = (
            "Column aliases cannot contain whitespace characters, quotation marks, "
            "semicolons, or SQL comments."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Book.objects.annotate(**{crafted_alias: Value(1)})

    def test_alias_forbidden_chars(self):
        tests = [
            'al"ias',
            "a'lias",
            "ali`as",
            "alia s",
            "alias\t",
            "ali\nas",
            "alias--",
            "ali/*as",
            "alias*/",
            "alias;",
            # [] are used by MSSQL.
            "alias[",
            "alias]",
        ]
        msg = (
            "Column aliases cannot contain whitespace characters, quotation marks, "
            "semicolons, or SQL comments."
        )
        for crafted_alias in tests:
            with self.subTest(crafted_alias):
                with self.assertRaisesMessage(ValueError, msg):
                    Book.objects.annotate(**{crafted_alias: Value(1)})


class AliasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a1 = Author.objects.create(name="Adrian Holovaty", age=34)
        cls.a2 = Author.objects.create(name="Jacob Kaplan-Moss", age=35)
        cls.a3 = Author.objects.create(name="James Bennett", age=34)
        cls.a4 = Author.objects.create(name="Peter Norvig", age=57)
        cls.a5 = Author.objects.create(name="Stuart Russell", age=46)
        p1 = Publisher.objects.create(name="Apress", num_awards=3)

        cls.b1 = Book.objects.create(
            isbn="159059725",
            pages=447,
            rating=4.5,
            price=Decimal("30.00"),
            contact=cls.a1,
            publisher=p1,
            pubdate=datetime.date(2007, 12, 6),
            name="The Definitive Guide to Django: Web Development Done Right",
        )
        cls.b2 = Book.objects.create(
            isbn="159059996",
            pages=300,
            rating=4.0,
            price=Decimal("29.69"),
            contact=cls.a3,
            publisher=p1,
            pubdate=datetime.date(2008, 6, 23),
            name="Practical Django Projects",
        )
        cls.b3 = Book.objects.create(
            isbn="013790395",
            pages=1132,
            rating=4.0,
            price=Decimal("82.80"),
            contact=cls.a4,
            publisher=p1,
            pubdate=datetime.date(1995, 1, 15),
            name="Artificial Intelligence: A Modern Approach",
        )
        cls.b4 = Book.objects.create(
            isbn="155860191",
            pages=946,
            rating=5.0,
            price=Decimal("75.00"),
            contact=cls.a4,
            publisher=p1,
            pubdate=datetime.date(1991, 10, 15),
            name=(
                "Paradigms of Artificial Intelligence Programming: Case Studies in "
                "Common Lisp"
            ),
        )
        cls.b1.authors.add(cls.a1, cls.a2)
        cls.b2.authors.add(cls.a3)
        cls.b3.authors.add(cls.a4, cls.a5)
        cls.b4.authors.add(cls.a4)

        Store.objects.create(
            name="Amazon.com",
            original_opening=datetime.datetime(1994, 4, 23, 9, 17, 42),
            friday_night_closing=datetime.time(23, 59, 59),
        )
        Store.objects.create(
            name="Books.com",
            original_opening=datetime.datetime(2001, 3, 15, 11, 23, 37),
            friday_night_closing=datetime.time(23, 59, 59),
        )

    def test_basic_alias(self):
        qs = Book.objects.alias(is_book=Value(1))
        self.assertIs(hasattr(qs.first(), "is_book"), False)

    def test_basic_alias_annotation(self):
        qs = Book.objects.alias(
            is_book_alias=Value(1),
        ).annotate(is_book=F("is_book_alias"))
        self.assertIs(hasattr(qs.first(), "is_book_alias"), False)
        for book in qs:
            with self.subTest(book=book):
                self.assertEqual(book.is_book, 1)

    def test_basic_alias_f_annotation(self):
        qs = Book.objects.alias(another_rating_alias=F("rating")).annotate(
            another_rating=F("another_rating_alias")
        )
        self.assertIs(hasattr(qs.first(), "another_rating_alias"), False)
        for book in qs:
            with self.subTest(book=book):
                self.assertEqual(book.another_rating, book.rating)

    def test_basic_alias_f_transform_annotation(self):
        """

        Tests the basic functionality of aliases in querysets with F-transform annotations.
        Verifies that the aliased field is not directly accessible as an attribute on the model instance.
        Checks that the annotated field, which references the aliased field, correctly computes the year of the publication date.

        """
        qs = Book.objects.alias(
            pubdate_alias=F("pubdate"),
        ).annotate(pubdate_year=F("pubdate_alias__year"))
        self.assertIs(hasattr(qs.first(), "pubdate_alias"), False)
        for book in qs:
            with self.subTest(book=book):
                self.assertEqual(book.pubdate_year, book.pubdate.year)

    def test_alias_after_annotation(self):
        """
        Tests the behavior of aliasing an annotated field in a Django QuerySet.

        Verifies that when an annotated field is aliased, the original annotation attribute is present on the resulting model instance,
        while the aliased attribute is not.

        Ensures that the annotation is correctly applied and can be accessed via its original name, despite the alias not being directly accessible.
        """
        qs = Book.objects.annotate(
            is_book=Value(1),
        ).alias(is_book_alias=F("is_book"))
        book = qs.first()
        self.assertIs(hasattr(book, "is_book"), True)
        self.assertIs(hasattr(book, "is_book_alias"), False)

    def test_overwrite_annotation_with_alias(self):
        """
        Tests overwriting an annotation with an alias.

        This test checks that when an annotation is overwritten with an alias of the same name, 
        the original annotation is no longer accessible as an attribute on the resulting objects.

        The test verifies that the 'is_book' attribute is not present on the first object retrieved 
        from the QuerySet after overwriting the annotation.
        """
        qs = Book.objects.annotate(is_book=Value(1)).alias(is_book=F("is_book"))
        self.assertIs(hasattr(qs.first(), "is_book"), False)

    def test_overwrite_alias_with_annotation(self):
        qs = Book.objects.alias(is_book=Value(1)).annotate(is_book=F("is_book"))
        for book in qs:
            with self.subTest(book=book):
                self.assertEqual(book.is_book, 1)

    def test_alias_annotation_expression(self):
        qs = Book.objects.alias(
            is_book_alias=Value(1),
        ).annotate(is_book=Coalesce("is_book_alias", 0))
        self.assertIs(hasattr(qs.first(), "is_book_alias"), False)
        for book in qs:
            with self.subTest(book=book):
                self.assertEqual(book.is_book, 1)

    def test_alias_default_alias_expression(self):
        qs = Author.objects.alias(
            Sum("book__pages"),
        ).filter(book__pages__sum__gt=2000)
        self.assertIs(hasattr(qs.first(), "book__pages__sum"), False)
        self.assertSequenceEqual(qs, [self.a4])

    def test_joined_alias_annotation(self):
        qs = (
            Book.objects.select_related("publisher")
            .alias(
                num_awards_alias=F("publisher__num_awards"),
            )
            .annotate(num_awards=F("num_awards_alias"))
        )
        self.assertIs(hasattr(qs.first(), "num_awards_alias"), False)
        for book in qs:
            with self.subTest(book=book):
                self.assertEqual(book.num_awards, book.publisher.num_awards)

    def test_alias_annotate_with_aggregation(self):
        qs = Book.objects.alias(
            is_book_alias=Value(1),
            rating_count_alias=Count("rating"),
        ).annotate(
            is_book=F("is_book_alias"),
            rating_count=F("rating_count_alias"),
        )
        book = qs.first()
        self.assertIs(hasattr(book, "is_book_alias"), False)
        self.assertIs(hasattr(book, "rating_count_alias"), False)
        for book in qs:
            with self.subTest(book=book):
                self.assertEqual(book.is_book, 1)
                self.assertEqual(book.rating_count, 1)

    def test_filter_alias_with_f(self):
        qs = Book.objects.alias(
            other_rating=F("rating"),
        ).filter(other_rating=4.5)
        self.assertIs(hasattr(qs.first(), "other_rating"), False)
        self.assertSequenceEqual(qs, [self.b1])

    def test_filter_alias_with_double_f(self):
        qs = Book.objects.alias(
            other_rating=F("rating"),
        ).filter(other_rating=F("rating"))
        self.assertIs(hasattr(qs.first(), "other_rating"), False)
        self.assertEqual(qs.count(), Book.objects.count())

    def test_filter_alias_agg_with_double_f(self):
        """
        Tests that filtering with an aggregate alias that references itself does not 
        create an attribute on the queryset instances. 

        It verifies that although the queryset is filtered by the alias value, the 
        calculated aggregate is not accessible as an attribute on the individual model 
        instances returned by the queryset. The test also ensures that the filter 
        operation does not affect the overall count of objects returned by the queryset.
        """
        qs = Book.objects.alias(
            sum_rating=Sum("rating"),
        ).filter(sum_rating=F("sum_rating"))
        self.assertIs(hasattr(qs.first(), "sum_rating"), False)
        self.assertEqual(qs.count(), Book.objects.count())

    def test_update_with_alias(self):
        Book.objects.alias(
            other_rating=F("rating") - 1,
        ).update(rating=F("other_rating"))
        self.b1.refresh_from_db()
        self.assertEqual(self.b1.rating, 3.5)

    def test_order_by_alias(self):
        qs = Author.objects.alias(other_age=F("age")).order_by("other_age")
        self.assertIs(hasattr(qs.first(), "other_age"), False)
        self.assertQuerySetEqual(qs, [34, 34, 35, 46, 57], lambda a: a.age)

    def test_order_by_alias_aggregate(self):
        qs = (
            Author.objects.values("age")
            .alias(age_count=Count("age"))
            .order_by("age_count", "age")
        )
        self.assertIs(hasattr(qs.first(), "age_count"), False)
        self.assertQuerySetEqual(qs, [35, 46, 57, 34], lambda a: a["age"])

    def test_dates_alias(self):
        """

        Tests the retrieval of distinct dates from a model's field using an alias.

        This function ensures that the dates method, applied to the pubdate field of the Book model via an alias,
        correctly returns the distinct months from the data. The expected result is a list of dates representing
        the first day of each month in which at least one book was published.

        The function verifies that the output matches the anticipated list of dates, confirming the proper
        functionality of the dates method with aliasing.

        """
        qs = Book.objects.alias(
            pubdate_alias=F("pubdate"),
        ).dates("pubdate_alias", "month")
        self.assertCountEqual(
            qs,
            [
                datetime.date(1991, 10, 1),
                datetime.date(1995, 1, 1),
                datetime.date(2007, 12, 1),
                datetime.date(2008, 6, 1),
            ],
        )

    def test_datetimes_alias(self):
        """

        Tests that datetime aliasing works correctly in Store objects queries.

        This test checks if using an alias for a datetime field in a query results in the expected datetimes.
        It verifies that the datetimes extracted from the 'original_opening' field using an alias match the expected years.
        The test case ensures that the count and order of the extracted datetimes are equal to the expected datetimes.

        """
        qs = Store.objects.alias(
            original_opening_alias=F("original_opening"),
        ).datetimes("original_opening_alias", "year")
        self.assertCountEqual(
            qs,
            [
                datetime.datetime(1994, 1, 1),
                datetime.datetime(2001, 1, 1),
            ],
        )

    def test_aggregate_alias(self):
        msg = (
            "Cannot aggregate over the 'other_age' alias. Use annotate() to promote it."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.alias(
                other_age=F("age"),
            ).aggregate(otherage_sum=Sum("other_age"))

    def test_defer_only_alias(self):
        """
        Tests that attempting to use the defer or only method with an alias 
            raises a FieldDoesNotExist exception.

            This test case verifies the correct behavior of the ORM when 
            attempting to defer or include an alias field in a query, ensuring 
            that the alias is not treated as a real field in the model.

            The test checks both the defer and only methods for this behavior, 
            confirming that the exception is raised with the expected message 
            when trying to access a query result with an alias field that is 
            not a valid model field.
        """
        qs = Book.objects.alias(rating_alias=F("rating") - 1)
        msg = "Book has no field named 'rating_alias'"
        for operation in ["defer", "only"]:
            with self.subTest(operation=operation):
                with self.assertRaisesMessage(FieldDoesNotExist, msg):
                    getattr(qs, operation)("rating_alias").first()

    @skipUnlessDBFeature("can_distinct_on_fields")
    def test_distinct_on_alias(self):
        qs = Book.objects.alias(rating_alias=F("rating") - 1)
        msg = "Cannot resolve keyword 'rating_alias' into field."
        with self.assertRaisesMessage(FieldError, msg):
            qs.distinct("rating_alias").first()

    def test_values_alias(self):
        qs = Book.objects.alias(rating_alias=F("rating") - 1)
        msg = "Cannot select the 'rating_alias' alias. Use annotate() to promote it."
        for operation in ["values", "values_list"]:
            with self.subTest(operation=operation):
                with self.assertRaisesMessage(FieldError, msg):
                    getattr(qs, operation)("rating_alias")

    def test_alias_sql_injection(self):
        crafted_alias = """injected_name" from "annotations_book"; --"""
        msg = (
            "Column aliases cannot contain whitespace characters, quotation marks, "
            "semicolons, or SQL comments."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Book.objects.alias(**{crafted_alias: Value(1)})
