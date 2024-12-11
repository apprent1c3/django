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
        Set up initial test data for the application.

        This class method creates a set of authors, publishers, books, and stores, and establishes relationships between them. 
        It includes multiple authors with varying ages and friendships, several publishers with different numbers of awards, 
        and various books with distinct ISBNs, titles, pages, ratings, prices, and publication dates. 
        Each book is associated with one or more authors and a single publisher. 
        Additionally, the method sets up several stores, each with its own opening date and closing time, and assigns books to these stores.
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
        """

        Tests the basic functionality of using the F expression for annotation.

        This test case verifies that the annotation of a field with itself using the F expression
        produces the expected result. It checks that the annotated field 'another_rating' has the same
        value as the original 'rating' field for each Book object.

        The purpose of this test is to ensure that the annotation is correctly applied and that the
        results can be accessed and asserted as expected.

        """
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

        Test the joined and transformed annotation functionality on the Employee model.

        This test ensures that the annotation of the store's opening year is accurately 
        joined and transformed from the Employee's store relation. It verifies that 
        the annotated store opening year matches the actual store opening year for each employee.

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
        """
        Tests the custom transform annotation by applying the Floor function to a DecimalField.

        This test demonstrates how to register a custom lookup and use it to annotate a queryset.
        The Floor function is applied to the 'price' field of Book objects, and the resulting 'floor_price' is compared to expected values.

        The test verifies that the correct floor prices are calculated for each book in the queryset, ensuring that the custom transform annotation is working as expected.
        """
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
        Tests the chaining of lookup transforms.

        This test case ensures that the lookup transforms can be combined to create more complex transformations.
        It creates sample company objects, registers the 'trim' and 'length' lookups, and then annotates these objects
        with the length of their trimmed names. The test checks that the resulting lengths are correct and that 
        both the `Length` and `F` expressions produce the same results.

        The test covers the following scenarios:
        - Trimming the company names and calculating their length.
        - Using both the `Length` and `F` expressions to create the length annotation.

        The expected output is a list of dictionaries containing the company names and their corresponding lengths.
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
        """
        Tests the annotation of mixed-type date intervals for ticket expiration dates.

        This test case verifies that the expires annotation, calculated by adding the active_at date and duration, correctly determines the expiration date of a ticket. The expiration date is calculated using the active_at date and the duration of the ticket, ensuring accurate tracking of ticket lifetimes. The test validates the annotated expires date against an expected expiration date, confirming the correctness of the annotation operation.
        """
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

        Tests the mixed type annotation functionality by combining numeric fields.

        This test case verifies that the database can correctly combine numeric fields of different types, 
        in this instance, 'pages' and 'rating', into a single annotated field 'combined'. 
        It checks that the result of this annotation matches the expected result obtained by combining the fields in Python.

        The test ensures that the database annotation is correctly calculating the combined value of the 'pages' and 'rating' fields,
        and that this value is an integer, as specified by the output field.

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
        Tests the annotation of a QuerySet with an empty expression.

        This method checks that annotating a QuerySet of Book objects with an empty
        expression (i.e., an IN operator with an empty list or a QuerySet with no results)
        behaves as expected. It verifies that the annotated QuerySet has the same length
        as the original QuerySet and that all annotated objects have a 'selected' attribute
        set to False. The test covers two cases: annotating with an empty list and annotating
        with a QuerySet that returns no results.
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
        """

        Tests the full expression wrapped annotation functionality.

        This test case verifies that a queryset of Book objects can be annotated with a 
        boolean expression that evaluates to True for all objects when the Q object 
        passed to Coalesce is empty. It checks that the length of the annotated queryset 
        is equal to the total count of Book objects and that all objects in the 
        annotated queryset have the 'selected' attribute set to True.

        """
        books = Book.objects.annotate(
            selected=Coalesce(~Q(pk__in=[]), True),
        )
        self.assertEqual(len(books), Book.objects.count())
        self.assertTrue(all(book.selected for book in books))

    def test_full_expression_annotation_with_aggregation(self):
        """

        Tests the annotation of a full expression with aggregation on a QuerySet of Book objects.

        Verifies that the annotation correctly applies a boolean expression and counts related ratings, 
        resulting in the expected rating count for each book in the QuerySet.

        The test case uses a Book QuerySet filtered by a specific ISBN and annotated with a boolean 
        expression and a rating count aggregation. It then asserts that the resulting rating counts 
        match the expected values.

        """
        qs = Book.objects.filter(isbn="159059725").annotate(
            selected=ExpressionWrapper(~Q(pk__in=[]), output_field=BooleanField()),
            rating_count=Count("rating"),
        )
        self.assertEqual([book.rating_count for book in qs], [1])

    def test_aggregate_over_full_expression_annotation(self):
        """
        Tests the aggregation of an annotated queryset over a full expression.

        The test verifies that when an annotation is applied to a queryset using an `ExpressionWrapper` and `Q` object, 
        and then aggregated using `Sum` with a `Cast` to an integer field, 
        the result is correct and matches the total count of objects in the queryset.
        """
        qs = Book.objects.annotate(
            selected=ExpressionWrapper(~Q(pk__in=[]), output_field=BooleanField()),
        ).aggregate(selected__sum=Sum(Cast("selected", IntegerField())))
        self.assertEqual(qs["selected__sum"], Book.objects.count())

    def test_empty_queryset_annotation(self):
        qs = Author.objects.annotate(empty=Subquery(Author.objects.values("id").none()))
        self.assertIsNone(qs.first().empty)

    def test_annotate_with_aggregation(self):
        """

        Tests annotating Book objects with aggregated values.

        This test case verifies that Book objects can be successfully annotated with 
        additional attributes, including a constant value and an aggregated count of 
        related ratings. It checks that each annotated Book object has the expected 
        attributes and values.

        The test validates the correct application of database aggregation functions 
        to related model instances, ensuring that the annotation process correctly 
        retrieves and assigns the required information to the Book objects.

        """
        books = Book.objects.annotate(is_book=Value(1), rating_count=Count("rating"))
        for book in books:
            self.assertEqual(book.is_book, 1)
            self.assertEqual(book.rating_count, 1)

    def test_combined_expression_annotation_with_aggregation(self):
        """

        Tests the combined usage of expression annotations with aggregation in a database query.

        This test case verifies that a database query can correctly annotate a model instance with both a combined expression and an aggregated value.
        It ensures that the combined expression, which involves arithmetic operations on values, is evaluated correctly and assigned to the instance.
        Additionally, it checks that the aggregated value, which is a count of related objects, is accurately calculated and assigned to the instance.
        The test validates the results of the query by asserting that the annotated instance attributes match the expected values.

        """
        book = Book.objects.annotate(
            combined=ExpressionWrapper(
                Value(3) * Value(4), output_field=IntegerField()
            ),
            rating_count=Count("rating"),
        ).first()
        self.assertEqual(book.combined, 12)
        self.assertEqual(book.rating_count, 1)

    def test_combined_f_expression_annotation_with_aggregation(self):
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
        """
        Tests the aggregate function's behavior on an annotation, verifying that the sum of ages is calculated correctly regardless of whether the 'age' field is directly aggregated or first annotated as 'other_age' and then aggregated.
        """
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
        """
        Tests the filtering of annotated fields on the Book model.

        This test case verifies that the annotation 'is_book' is correctly applied to
        the Book model and that the filtered results match the expected criteria.

        It checks that each book object in the filtered queryset has the 'is_book' 
        attribute set to 1, confirming the successful application of the annotation 
        and filter operations.
        """
        books = Book.objects.annotate(is_book=Value(1)).filter(is_book=1)
        for book in books:
            self.assertEqual(book.is_book, 1)

    def test_filter_annotation_with_f(self):
        """

        Tests the filtering of annotated fields in a queryset.

        This test ensures that the annotate method can be used in conjunction with the filter method
        to retrieve objects based on calculated values. In this case, it checks that a book object's
        rating can be annotated and then filtered to only include books with a specific rating.

        The test validates that the annotated field 'other_rating' is correctly calculated and
        that the filtered queryset only contains books with the specified rating of 3.5.

        """
        books = Book.objects.annotate(other_rating=F("rating")).filter(other_rating=3.5)
        for book in books:
            self.assertEqual(book.other_rating, 3.5)

    def test_filter_annotation_with_double_f(self):
        """
        Tests the functionality of filtering objects using annotations with duplicate values.

        This test case verifies that when an annotation is created with a duplicate value,
        the filter function correctly identifies and returns the objects where the annotated
        value matches the original value. The test uses the Book model as an example, 
        annotating the rating field and then filtering the results to ensure that the 
        annotated rating matches the original rating for each book in the query set.
        """
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
        """
        Tests that using a field alias with an incorrect annotation name in a filter raises a FieldError.

        The function evaluates the case where an attempt is made to filter a QuerySet based on an annotated field that doesn't exist. It verifies that this operation correctly raises an exception with an informative error message, indicating that the specified keyword cannot be resolved into a valid field.
        """
        with self.assertRaisesMessage(
            FieldError, "Cannot resolve keyword 'nope' into field."
        ):
            list(
                Book.objects.annotate(sum_rating=Sum("rating")).filter(
                    sum_rating=F("nope")
                )
            )

    def test_values_wrong_annotation(self):
        """

        Tests that a FieldError is raised when trying to retrieve values from a non-existent annotation.

        The function checks that a meaningful error message is returned when an incorrect annotation name is used in the `values_list` method.
        The expected error message includes the available field names, helping to identify the typo in the annotation name.

        """
        expected_message = (
            "Cannot resolve keyword 'annotation_typo' into field. Choices are: %s"
        )
        article_fields = ", ".join(
            ["annotation"] + sorted(get_field_names_from_opts(Book._meta))
        )
        with self.assertRaisesMessage(FieldError, expected_message % article_fields):
            Book.objects.annotate(annotation=Value(1)).values_list("annotation_typo")

    def test_decimal_annotation(self):
        """

        Tests the annotation of decimal fields in the Employee model.

        Verifies that the new_salary annotation, calculated by dividing the salary field by 10,
        produces the expected result for a newly created Employee instance.

        """
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
        """

        Tests the commutativity of combined annotations in Django queries.

        This test case verifies that the order of operations in combined annotations does not affect the result.
        It checks two scenarios:

        1. Addition of a constant to a field: The test ensures that `F('rating') + 2` and `2 + F('rating')` produce the same result.
        2. Addition of `None` to a field: The test verifies that both `F('rating') + None` and `None + F('rating')` result in `None`.

        The test uses the `Book` model and its `rating` field to demonstrate the commutativity of combined annotations.

        """
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
        """

        Tests if an update operation with annotation correctly updates a model instance's field.

        This test verifies that the rating of a Book instance is correctly updated after annotating it with a calculated field and using the annotated field to update the original field. The test checks that the post-update rating is as expected, specifically one less than the pre-update rating.

        """
        book_preupdate = Book.objects.get(pk=self.b2.pk)
        Book.objects.annotate(other_rating=F("rating") - 1).update(
            rating=F("other_rating")
        )
        book_postupdate = Book.objects.get(pk=self.b2.pk)
        self.assertEqual(book_preupdate.rating - 1, book_postupdate.rating)

    def test_annotation_with_m2m(self):
        """

        Tests the annotation of Book instances with the age of their authors, 
        utilizing a many-to-many relationship. This function specifically 
        verifies that the Book instances are correctly ordered by author age 
        after annotation, and that the annotated age values match the 
        expected ages of 34 and 35 for the first two Book instances.

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

        Tests that a many-to-many relationship can be reversed and annotated correctly.

        This test case verifies that a queryset of books can be annotated with the store name
        and sorted by the store name, and that the resulting queryset contains the expected
        store names. It checks that the annotation is correctly applied in reverse, from the
        book to its related store, ensuring that the books are ordered as expected by store name.

        Returns:
            None

        Raises:
            AssertionError: If the annotated and sorted queryset does not match the expected store names.

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
        """
        Tests if authors with duplicate IDs exist in the database.

        Checks for the existence of authors that have been annotated with a count 
        of their IDs and filtered to only include those with a count greater than 1. 
        The test passes if no such authors are found, indicating no duplicates.

        """
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
        """

        Tests if custom database functions can reference other database functions.

        This test demonstrates the ability to create custom database functions that 
        utilize existing database functions, such as ``LOWER``. The test creates a 
        number of ``Company`` instances with varying amounts of information and then 
        defines a custom database function ``Lower`` that applies the ``LOWER`` 
        function to a given field.

        The test then uses the Django ORM to annotate the ``Company`` instances with 
        a ``tagline`` field, which is generated using the ``COALESCE`` function to 
        return the first non-null value from a list of fields. This ``tagline`` field 
        is then annotated with a ``tagline_lower`` field, which applies the custom 
        ``Lower`` function to the ``tagline`` field.

        Finally, the test checks that the resulting query set is correctly ordered by 
        the ``name`` field and that the ``tagline_lower`` field contains the expected 
        values.

        """
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

        Tests annotation in a queryset, specifically using the annotate function to 
        group publishers by their names and calculate the sum of a multiplied value.

        The function creates a queryset of publishers, annotates it with a multiplier value, 
        and then calculates the sum of the product of the multiplier and the number of awards 
        for each publisher. The results are ordered and compared to an expected output to 
        ensure the annotation is performed correctly.

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
        Tests the chaining of annotation filters on a many-to-many relationship.
        This test case verifies that the annotation is correctly applied when using a sequence of filter and annotate operations on a many-to-many field.
        It checks if the filtered and annotated results match the expected values, ensuring the correct application of the filters and annotations in the query chain.
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
        Tests the functionality of annotation and alias filters within subqueries in the Publisher QuerySet.

        Checks if publishers with more than 4 awards are correctly filtered and if the annotated and aliased values are properly applied.

        The test verifies that the resulting QuerySet matches the expected publishers, ensuring correct data retrieval and filtering.
        """
        awarded_publishers_qs = (
            Publisher.objects.filter(num_awards__gt=4)
            .annotate(publisher_annotate=Value(1))
            .alias(publisher_alias=Value(1))
        )
        qs = Publisher.objects.filter(pk__in=awarded_publishers_qs)
        self.assertCountEqual(qs, [self.p3, self.p4])

    def test_annotation_and_alias_filter_related_in_subquery(self):
        """

        Tests the filtering of related objects in a subquery using annotations and aliases.

        This test case verifies that the Django ORM correctly filters related objects based on
        a subquery that includes annotations and aliases. It checks that the publishers of books
        with more than 400 pages are correctly retrieved.

        The test query first creates a subquery that selects books with more than 400 pages,
        annotates and aliases these books, and then uses this subquery to filter the publishers
        of these books. The test asserts that the resulting publishers match the expected list.

        """
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
        """

        Tests that annotations with aggregate values can be chained together correctly.

        This test case checks that the :func:`Exists` and :func:`Max` aggregate functions
        can be used in conjunction to annotate a queryset with complex conditions.
        It verifies that the resulting queryset contains the expected values, ordered
        by the maximum publication date.

        The test focuses on the validity of the generated query, ensuring that
        the combination of annotations and aggregate functions produces the correct
        output, specifically the list of maximum publication dates for books with authors.

        """
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
        """

        Tests the chaining of annotation and aggregate values in a queryset
        using subqueries and aggregation functions.

        This test case verifies that the queryset can correctly extract the year
        of publication from the 'pubdate' field, group the results by this year,
        and then annotate each group with the top rating and total number of pages
        for that year.

        The test covers the use of the ExtractYear, Subquery, and Sum aggregation
        functions, as well as the chaining of multiple annotate and values calls.
        It checks that the resulting queryset contains the expected data, including
        the publication year, top rating, and total number of pages for each group.

        """
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

        Tests the annotation of a queryset with a subquery that uses an OuterRef to reference the outer query.
        This test ensures that the top rating year for each publication year is correctly retrieved.

        The test case verifies that the resulting queryset contains the expected publication years along with their corresponding top rating years.

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

        Tests the aggregation of data triggered by a many-to-one relationship.

        This test case verifies that when authors are filtered by age, the maximum number of pages
        is correctly annotated and retrieved. The maximum number of pages is calculated based on
        the author's associated books, if any. If an author has no associated books, the maximum
        number of pages is set to 0. The test then asserts that the results match the expected
        output, ensuring that the annotation and aggregation are working as expected.

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

        Test that using a crafted alias with SQL injection characters raises an error.

        This test ensures that attempting to create an annotation with an alias that
        contains characters that could be used for SQL injection, such as semicolons or
        quotation marks, results in a ValueError. This helps to prevent potential
        security vulnerabilities by rejecting such aliases and providing a clear error
        message.

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
        """

        Set up test data for the application.

        This class method creates and populates a set of test data for use in testing the application.
        The data includes a selection of authors, books, and stores. The authors are assigned to books,
        and the books are assigned to a publisher. The test data is created to provide a consistent
        and representative set of data for testing purposes.

        The test data includes:

        * 5 authors with varying ages
        * 4 books with different ISBNs, page counts, ratings, prices, and publication dates
        * 2 stores with different opening dates and Friday night closing times

        The method is designed to be used in a testing context to provide a known and consistent
        dataset for testing the application's functionality.

        """
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
        """
        Tests the basic alias annotation functionality for created querysets.

        This test checks that a queryset with an alias annotation does not have the 
        alias attribute directly, but the annotated field is correctly populated 
        with the aliased value. It verifies the correctness of the annotation for 
        each object in the queryset. The test function ensures that the annotated 
        field 'is_book' has the expected value, demonstrating the proper usage of 
        alias and annotate methods in querysets.
        """
        qs = Book.objects.alias(
            is_book_alias=Value(1),
        ).annotate(is_book=F("is_book_alias"))
        self.assertIs(hasattr(qs.first(), "is_book_alias"), False)
        for book in qs:
            with self.subTest(book=book):
                self.assertEqual(book.is_book, 1)

    def test_basic_alias_f_annotation(self):
        """

        Test the basic functionality of using alias and annotate in queries.

        This test verifies that when using an alias to reference a field in an annotation,
        the original alias is not added as an attribute to the model instance.

        It checks that the annotated field 'another_rating' is equal to the original field 'rating'
        for each book in the query set.

        """
        qs = Book.objects.alias(another_rating_alias=F("rating")).annotate(
            another_rating=F("another_rating_alias")
        )
        self.assertIs(hasattr(qs.first(), "another_rating_alias"), False)
        for book in qs:
            with self.subTest(book=book):
                self.assertEqual(book.another_rating, book.rating)

    def test_basic_alias_f_transform_annotation(self):
        qs = Book.objects.alias(
            pubdate_alias=F("pubdate"),
        ).annotate(pubdate_year=F("pubdate_alias__year"))
        self.assertIs(hasattr(qs.first(), "pubdate_alias"), False)
        for book in qs:
            with self.subTest(book=book):
                self.assertEqual(book.pubdate_year, book.pubdate.year)

    def test_alias_after_annotation(self):
        qs = Book.objects.annotate(
            is_book=Value(1),
        ).alias(is_book_alias=F("is_book"))
        book = qs.first()
        self.assertIs(hasattr(book, "is_book"), True)
        self.assertIs(hasattr(book, "is_book_alias"), False)

    def test_overwrite_annotation_with_alias(self):
        """

        Tests that annotating a model field with an alias and then overwriting that annotation renders the original alias inaccessible.

        This test ensures that when an annotation is overwritten with an alias, the original annotation is no longer present in the resulting queryset. 

        """
        qs = Book.objects.annotate(is_book=Value(1)).alias(is_book=F("is_book"))
        self.assertIs(hasattr(qs.first(), "is_book"), False)

    def test_overwrite_alias_with_annotation(self):
        """
        Tests that an alias can be overwritten with an annotation.

        This test case verifies that when an alias is defined and then annotation 
        with the same name is applied to a query, the annotation value takes 
        precedence over the alias value.

        The test uses a query on the Book model, applying an alias 'is_book' with 
        a value of 1 and then annotating 'is_book' with a reference to itself. 
        It checks that for each book in the query result, the 'is_book' attribute 
        has the expected value of 1, demonstrating that the annotation correctly 
        overrides the alias.


        """
        qs = Book.objects.alias(is_book=Value(1)).annotate(is_book=F("is_book"))
        for book in qs:
            with self.subTest(book=book):
                self.assertEqual(book.is_book, 1)

    def test_alias_annotation_expression(self):
        """
        Tests the behavior of aliasing and annotating in database queries.

        Verifies that when aliasing an expression, the original alias is not available
        as an attribute on the resulting model instances, while the annotated value
        is available and correctly set.

        This test case ensures that the Coalesce function is applied correctly,
        returning the expected value when the aliased expression is present,
        and the default value when it is not.
        """
        qs = Book.objects.alias(
            is_book_alias=Value(1),
        ).annotate(is_book=Coalesce("is_book_alias", 0))
        self.assertIs(hasattr(qs.first(), "is_book_alias"), False)
        for book in qs:
            with self.subTest(book=book):
                self.assertEqual(book.is_book, 1)

    def test_alias_default_alias_expression(self):
        """

        Tests the default alias expression for annotated querysets.

        Verifies that when an alias is applied to a queryset using the :meth:`alias` method,
        the resulting queryset does not have the annotated field as an attribute.
        Instead, it can be accessed using the lookup syntax in filters and other queryset methods.
        In this specific case, it checks that only authors with books having more than 2000 pages are returned.

        """
        qs = Author.objects.alias(
            Sum("book__pages"),
        ).filter(book__pages__sum__gt=2000)
        self.assertIs(hasattr(qs.first(), "book__pages__sum"), False)
        self.assertSequenceEqual(qs, [self.a4])

    def test_joined_alias_annotation(self):
        """

        Tests the correct behavior of joined alias annotations.

        This test case verifies that when an alias is created for a joined field, it is not
        exposed as an attribute on the model instance. Instead, the annotated field should
        return the expected value.

        The test performs the following checks:

        *   Verifies that the alias is not accessible as an attribute on the model instance.
        *   Confirms that the annotated field returns the correct value by comparing it to
            the value obtained directly from the related model.

        """
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
        """
        Tests the usage of aliases in annotations with aggregation operations.

        This test ensures that alias fields are properly replaced by their corresponding annotated fields,
        and that the annotated fields are correctly populated with the expected values.

        Verifies that:
        - The alias fields are not present as attributes on the resulting query objects.
        - The annotated fields are correctly set with the expected values for each object in the query.

        """
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
        """
        Tests that aliasing a database field does not add the aliased field to the resulting model instance.

        This test case verifies that an aliased field is used only for filtering purposes and does not become a visible attribute of the retrieved objects.

        It checks that a query that filters on an aliased field returns the correct objects, but the aliased field itself is not accessible as an attribute of the retrieved objects.
        """
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
        Tests that the dates method can handle aliased fields for month-level date retrieval.

        This test case verifies that by applying an alias to a field (in this case, 'pubdate'), the
        dates method can successfully retrieve unique month-level dates from the aliased field.

        The expected output is a list of datetime.date objects representing the unique months 
        present in the data, indicating that the aliasing and date retrieval are correctly performed.
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

        Tests that date/time values can be extracted from a query using an alias.

        This test confirms that the datetimes method can correctly extract distinct year values 
        from a queryset that has been filtered using an alias. It verifies that the extracted 
        years match the expected results.

        The test case covers the use of an alias to access a model field, and then applying 
        the datetimes method to extract the desired date components.

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
        """
        Tests that attempting to aggregate over an aliased field without promoting it raises a FieldError.

        Checks that an exception with a specific error message is raised when trying to calculate an aggregate value 
        ('otherage_sum') using the 'other_age' alias directly on the Author queryset.

        The error message indicates that the alias must be promoted using the annotate() method before it can be used 
        for aggregation operations, such as calculating the sum of the aliased field.
        """
        msg = (
            "Cannot aggregate over the 'other_age' alias. Use annotate() to promote it."
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.alias(
                other_age=F("age"),
            ).aggregate(otherage_sum=Sum("other_age"))

    def test_defer_only_alias(self):
        """

        Tests that attempting to use the 'defer' or 'only' query methods on a queryset 
        with an aliased field results in a FieldDoesNotExist error.

        The test specifically checks that the 'defer' and 'only' operations do not 
        recognize the aliased field name, treating it as a non-existent field, and 
        raises an exception accordingly.

        """
        qs = Book.objects.alias(rating_alias=F("rating") - 1)
        msg = "Book has no field named 'rating_alias'"
        for operation in ["defer", "only"]:
            with self.subTest(operation=operation):
                with self.assertRaisesMessage(FieldDoesNotExist, msg):
                    getattr(qs, operation)("rating_alias").first()

    @skipUnlessDBFeature("can_distinct_on_fields")
    def test_distinct_on_alias(self):
        """

        Tests the usage of distinct on an alias in a database query.

        Checks if attempting to use the distinct method on a query that includes an alias
        field, instead of an actual field, correctly raises a FieldError. This ensures 
        that Django's ORM correctly handles invalid distinct field names.

        Args:
            self: The test instance.

        Raises:
            FieldError: When attempting to use the distinct method on an alias field.

        """
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
