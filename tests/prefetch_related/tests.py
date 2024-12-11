from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import NotSupportedError, connection
from django.db.models import Prefetch, QuerySet, prefetch_related_objects
from django.db.models.fields.related import ForwardManyToOneDescriptor
from django.db.models.query import get_prefetcher, prefetch_one_level
from django.db.models.sql import Query
from django.test import (
    TestCase,
    ignore_warnings,
    override_settings,
    skipIfDBFeature,
    skipUnlessDBFeature,
)
from django.test.utils import CaptureQueriesContext
from django.utils.deprecation import RemovedInDjango60Warning

from .models import (
    Article,
    Author,
    Author2,
    AuthorAddress,
    AuthorWithAge,
    Bio,
    Book,
    Bookmark,
    BookReview,
    BookWithYear,
    Comment,
    Department,
    Employee,
    FavoriteAuthors,
    House,
    LessonEntry,
    ModelIterableSubclass,
    Person,
    Qualification,
    Reader,
    Room,
    TaggedItem,
    Teacher,
    WordEntry,
)


class TestDataMixin:
    @classmethod
    def setUpTestData(cls):
        cls.book1 = Book.objects.create(title="Poems")
        cls.book2 = Book.objects.create(title="Jane Eyre")
        cls.book3 = Book.objects.create(title="Wuthering Heights")
        cls.book4 = Book.objects.create(title="Sense and Sensibility")

        cls.author1 = Author.objects.create(name="Charlotte", first_book=cls.book1)
        cls.author2 = Author.objects.create(name="Anne", first_book=cls.book1)
        cls.author3 = Author.objects.create(name="Emily", first_book=cls.book1)
        cls.author4 = Author.objects.create(name="Jane", first_book=cls.book4)

        cls.book1.authors.add(cls.author1, cls.author2, cls.author3)
        cls.book2.authors.add(cls.author1)
        cls.book3.authors.add(cls.author3)
        cls.book4.authors.add(cls.author4)

        cls.reader1 = Reader.objects.create(name="Amy")
        cls.reader2 = Reader.objects.create(name="Belinda")

        cls.reader1.books_read.add(cls.book1, cls.book4)
        cls.reader2.books_read.add(cls.book2, cls.book4)


class PrefetchRelatedTests(TestDataMixin, TestCase):
    def assertWhereContains(self, sql, needle):
        where_idx = sql.index("WHERE")
        self.assertEqual(
            sql.count(str(needle), where_idx),
            1,
            msg="WHERE clause doesn't contain %s, actual SQL: %s"
            % (needle, sql[where_idx:]),
        )

    def test_m2m_forward(self):
        with self.assertNumQueries(2):
            lists = [
                list(b.authors.all()) for b in Book.objects.prefetch_related("authors")
            ]

        normal_lists = [list(b.authors.all()) for b in Book.objects.all()]
        self.assertEqual(lists, normal_lists)

    def test_m2m_reverse(self):
        """
        Tests that using prefetch_related on the many-to-many relationship 'books' of Author objects 
        results in the same output as querying the relationship normally, while also verifying the 
        expected number of database queries.

        This test checks the correctness of the ORM's ability to prefetch related objects in a 
        many-to-many relationship and verifies that it does not introduce any inconsistencies in the 
        results. It also ensures that the optimization of reducing the number of database queries 
        is applied as expected.
        """
        with self.assertNumQueries(2):
            lists = [
                list(a.books.all()) for a in Author.objects.prefetch_related("books")
            ]

        normal_lists = [list(a.books.all()) for a in Author.objects.all()]
        self.assertEqual(lists, normal_lists)

    def test_foreignkey_forward(self):
        with self.assertNumQueries(2):
            books = [
                a.first_book for a in Author.objects.prefetch_related("first_book")
            ]

        normal_books = [a.first_book for a in Author.objects.all()]
        self.assertEqual(books, normal_books)

    def test_foreignkey_reverse(self):
        """
        Tests the reverse relationship of a foreign key, specifically the 'first_time_authors' attribute of the Book model.

        Verify that the relationship is correctly established and that the related objects can be retrieved efficiently using prefetching.

        The test also checks that the authors associated with a specific book are returned in the expected order, confirming the correctness of the relationship and its usage in the application.
        """
        with self.assertNumQueries(2):
            [
                list(b.first_time_authors.all())
                for b in Book.objects.prefetch_related("first_time_authors")
            ]

        self.assertSequenceEqual(self.book2.authors.all(), [self.author1])

    def test_onetoone_reverse_no_match(self):
        # Regression for #17439
        with self.assertNumQueries(2):
            book = Book.objects.prefetch_related("bookwithyear").all()[0]
        with self.assertNumQueries(0):
            with self.assertRaises(BookWithYear.DoesNotExist):
                book.bookwithyear

    def test_onetoone_reverse_with_to_field_pk(self):
        """
        A model (Bio) with a OneToOneField primary key (author) that references
        a non-pk field (name) on the related model (Author) is prefetchable.
        """
        Bio.objects.bulk_create(
            [
                Bio(author=self.author1),
                Bio(author=self.author2),
                Bio(author=self.author3),
            ]
        )
        authors = Author.objects.filter(
            name__in=[self.author1, self.author2, self.author3],
        ).prefetch_related("bio")
        with self.assertNumQueries(2):
            for author in authors:
                self.assertEqual(author.name, author.bio.author.name)

    def test_survives_clone(self):
        """
        Test that the queryset survives cloning when used with prefetch_related.

        This test ensures that the prefetch_related optimization is preserved when 
        the queryset is cloned, such as when it is used within a list comprehension. 
        It verifies that the expected number of database queries are executed.

        """
        with self.assertNumQueries(2):
            [
                list(b.first_time_authors.all())
                for b in Book.objects.prefetch_related("first_time_authors").exclude(
                    id=1000
                )
            ]

    def test_len(self):
        with self.assertNumQueries(2):
            qs = Book.objects.prefetch_related("first_time_authors")
            len(qs)
            [list(b.first_time_authors.all()) for b in qs]

    def test_bool(self):
        """

        Tests that a queryset can be evaluated as a boolean and its results can be iterated over.

        Checks that the queryset is truthy and can be iterated over without raising exceptions.
        Also verifies the number of database queries executed for the given operation.

        The test covers the scenario where a queryset is prefetched with related objects 
        and then iterated over to access those related objects, ensuring that the 
        prefetching is effective and the related objects can be accessed without 
        additional queries beyond the initial prefetch.

        """
        with self.assertNumQueries(2):
            qs = Book.objects.prefetch_related("first_time_authors")
            bool(qs)
            [list(b.first_time_authors.all()) for b in qs]

    def test_count(self):
        with self.assertNumQueries(2):
            qs = Book.objects.prefetch_related("first_time_authors")
            [b.first_time_authors.count() for b in qs]

    def test_exists(self):
        with self.assertNumQueries(2):
            qs = Book.objects.prefetch_related("first_time_authors")
            [b.first_time_authors.exists() for b in qs]

    def test_in_and_prefetch_related(self):
        """
        Regression test for #20242 - QuerySet "in" didn't work the first time
        when using prefetch_related. This was fixed by the removal of chunked
        reads from QuerySet iteration in
        70679243d1786e03557c28929f9762a119e3ac14.
        """
        qs = Book.objects.prefetch_related("first_time_authors")
        self.assertIn(qs[0], qs)

    def test_clear(self):
        """

        Tests the efficiency of clearing a prefetch on a queryset.

        This function verifies that the prefetch is properly cleared when
        prefetch_related(None) is called, resulting in a specific number 
        of database queries being executed. The test checks if the 
        prefetch clearance does not inadvertently cause additional 
        queries to be made when accessing related objects.

        """
        with self.assertNumQueries(5):
            with_prefetch = Author.objects.prefetch_related("books")
            without_prefetch = with_prefetch.prefetch_related(None)
            [list(a.books.all()) for a in without_prefetch]

    def test_m2m_then_m2m(self):
        """A m2m can be followed through another m2m."""
        with self.assertNumQueries(3):
            qs = Author.objects.prefetch_related("books__read_by")
            lists = [
                [[str(r) for r in b.read_by.all()] for b in a.books.all()] for a in qs
            ]
            self.assertEqual(
                lists,
                [
                    [["Amy"], ["Belinda"]],  # Charlotte - Poems, Jane Eyre
                    [["Amy"]],  # Anne - Poems
                    [["Amy"], []],  # Emily - Poems, Wuthering Heights
                    [["Amy", "Belinda"]],  # Jane - Sense and Sense
                ],
            )

    def test_overriding_prefetch(self):
        with self.assertNumQueries(3):
            qs = Author.objects.prefetch_related("books", "books__read_by")
            lists = [
                [[str(r) for r in b.read_by.all()] for b in a.books.all()] for a in qs
            ]
            self.assertEqual(
                lists,
                [
                    [["Amy"], ["Belinda"]],  # Charlotte - Poems, Jane Eyre
                    [["Amy"]],  # Anne - Poems
                    [["Amy"], []],  # Emily - Poems, Wuthering Heights
                    [["Amy", "Belinda"]],  # Jane - Sense and Sense
                ],
            )
        with self.assertNumQueries(3):
            qs = Author.objects.prefetch_related("books__read_by", "books")
            lists = [
                [[str(r) for r in b.read_by.all()] for b in a.books.all()] for a in qs
            ]
            self.assertEqual(
                lists,
                [
                    [["Amy"], ["Belinda"]],  # Charlotte - Poems, Jane Eyre
                    [["Amy"]],  # Anne - Poems
                    [["Amy"], []],  # Emily - Poems, Wuthering Heights
                    [["Amy", "Belinda"]],  # Jane - Sense and Sense
                ],
            )

    def test_get(self):
        """
        Objects retrieved with .get() get the prefetch behavior.
        """
        # Need a double
        with self.assertNumQueries(3):
            author = Author.objects.prefetch_related("books__read_by").get(
                name="Charlotte"
            )
            lists = [[str(r) for r in b.read_by.all()] for b in author.books.all()]
            self.assertEqual(lists, [["Amy"], ["Belinda"]])  # Poems, Jane Eyre

    def test_foreign_key_then_m2m(self):
        """
        A m2m relation can be followed after a relation like ForeignKey that
        doesn't have many objects.
        """
        with self.assertNumQueries(2):
            qs = Author.objects.select_related("first_book").prefetch_related(
                "first_book__read_by"
            )
            lists = [[str(r) for r in a.first_book.read_by.all()] for a in qs]
            self.assertEqual(lists, [["Amy"], ["Amy"], ["Amy"], ["Amy", "Belinda"]])

    def test_reverse_one_to_one_then_m2m(self):
        """
        A m2m relation can be followed after going through the select_related
        reverse of an o2o.
        """
        qs = Author.objects.prefetch_related("bio__books").select_related("bio")

        with self.assertNumQueries(1):
            list(qs.all())

        Bio.objects.create(author=self.author1)
        with self.assertNumQueries(2):
            list(qs.all())

    def test_attribute_error(self):
        """
        Tests that an AttributeError is raised when an invalid attribute is used with prefetch_related.

        Specifically, this test case checks that attempting to prefetch a non-existent attribute 
        ('xyz') on a 'Book' object results in an AttributeError. The error message is verified to 
        contain the expected information, including the name of the invalid parameter and the 
        prefetch_related method.

        This test ensures that the system correctly handles and reports invalid prefetch_related 
        parameters, providing a clear and informative error message to the user.
        """
        qs = Reader.objects.prefetch_related("books_read__xyz")
        msg = (
            "Cannot find 'xyz' on Book object, 'books_read__xyz' "
            "is an invalid parameter to prefetch_related()"
        )
        with self.assertRaisesMessage(AttributeError, msg) as cm:
            list(qs)

        self.assertIn("prefetch_related", str(cm.exception))

    def test_invalid_final_lookup(self):
        """
        Tests that attempting to prefetch a non-relational field raises a ValueError.

        This test case verifies that an error is raised when using the prefetch_related method
        with an invalid parameter, specifically a field that does not support prefetching.
        It checks that the error message includes the name of the prefetch_related method
        and the field that caused the error. This ensures that the error is properly handled
        and reported when trying to prefetch an invalid field. 
        """
        qs = Book.objects.prefetch_related("authors__name")
        msg = (
            "'authors__name' does not resolve to an item that supports "
            "prefetching - this is an invalid parameter to prefetch_related()."
        )
        with self.assertRaisesMessage(ValueError, msg) as cm:
            list(qs)

        self.assertIn("prefetch_related", str(cm.exception))
        self.assertIn("name", str(cm.exception))

    def test_prefetch_eq(self):
        """

        Tests the equality of Prefetch objects.

        This function checks that Prefetch objects are equal when they have the same lookup and queryset,
        and not equal when they have different lookups. It also verifies that a Prefetch object is equal to itself,
        and can be compared with a mock object.

        """
        prefetch_1 = Prefetch("authors", queryset=Author.objects.all())
        prefetch_2 = Prefetch("books", queryset=Book.objects.all())
        self.assertEqual(prefetch_1, prefetch_1)
        self.assertEqual(prefetch_1, mock.ANY)
        self.assertNotEqual(prefetch_1, prefetch_2)

    def test_forward_m2m_to_attr_conflict(self):
        """
        Tests that prefetching a many-to-many relationship with a conflicting attribute name raises a ValueError.

        This test ensures that attempting to prefetch related objects and assign them to an attribute that already exists on the model raises an error. The error message is verified to contain the expected conflict description.

        The test also verifies that the original many-to-many relationship remains unchanged after the attempted prefetch operation, demonstrating that the conflict does not alter the existing data.

        In this case, the test checks the specific scenario where an attempt is made to prefetch authors and assign them to an attribute named 'authors', which conflicts with the existing 'authors' field on the Book model.
        """
        msg = "to_attr=authors conflicts with a field on the Book model."
        authors = Author.objects.all()
        with self.assertRaisesMessage(ValueError, msg):
            list(
                Book.objects.prefetch_related(
                    Prefetch("authors", queryset=authors, to_attr="authors"),
                )
            )
        # Without the ValueError, an author was deleted due to the implicit
        # save of the relation assignment.
        self.assertEqual(self.book1.authors.count(), 3)

    def test_reverse_m2m_to_attr_conflict(self):
        """
        Tests that using 'to_attr' in prefetch_related conflicts with an existing field on the model.

        This test case checks that attempting to prefetch related objects and assign the result to an attribute
        that already exists on the model raises a ValueError. It verifies that the original data remains unchanged
        after the error is raised.

        The test uses the Author model and its relationship with the Book model to simulate the conflict.
        It attempts to prefetch a specific set of books and assign the result to the 'books' attribute, which
        is expected to raise an error due to the attribute already being defined on the Author model.
        """
        msg = "to_attr=books conflicts with a field on the Author model."
        poems = Book.objects.filter(title="Poems")
        with self.assertRaisesMessage(ValueError, msg):
            list(
                Author.objects.prefetch_related(
                    Prefetch("books", queryset=poems, to_attr="books"),
                )
            )
        # Without the ValueError, a book was deleted due to the implicit
        # save of reverse relation assignment.
        self.assertEqual(self.author1.books.count(), 2)

    def test_m2m_then_reverse_fk_object_ids(self):
        """
        Tests that prefetching related objects in a many-to-many relationship, 
        then querying the foreign key of those related objects, results in a SQL query 
        that includes the expected filter condition. The test verifies that the generated 
        SQL query contains the required 'WHERE' clause with the name of the author.
        """
        with CaptureQueriesContext(connection) as queries:
            list(Book.objects.prefetch_related("authors__addresses"))

        sql = queries[-1]["sql"]
        self.assertWhereContains(sql, self.author1.name)

    def test_m2m_then_m2m_object_ids(self):
        with CaptureQueriesContext(connection) as queries:
            list(Book.objects.prefetch_related("authors__favorite_authors"))

        sql = queries[-1]["sql"]
        self.assertWhereContains(sql, self.author1.name)

    def test_m2m_then_reverse_one_to_one_object_ids(self):
        """
        Tests the use of prefetch_related on a many-to-many relationship followed by 
        a reverse one-to-one relationship, verifies that the resulting SQL query contains 
        the expected object ID in the WHERE clause.

        This test ensures that the ORM correctly fetches related objects and constructs 
        the SQL query to filter results based on the specified object ID.
        """
        with CaptureQueriesContext(connection) as queries:
            list(Book.objects.prefetch_related("authors__authorwithage"))

        sql = queries[-1]["sql"]
        self.assertWhereContains(sql, self.author1.id)

    def test_filter_deferred(self):
        """
        Related filtering of prefetched querysets is deferred on m2m and
        reverse m2o relations until necessary.
        """
        add_q = Query.add_q
        for relation in ["authors", "first_time_authors"]:
            with self.subTest(relation=relation):
                with mock.patch.object(
                    Query,
                    "add_q",
                    autospec=True,
                    side_effect=lambda self, q: add_q(self, q),
                ) as add_q_mock:
                    list(Book.objects.prefetch_related(relation))
                    self.assertEqual(add_q_mock.call_count, 1)

    def test_named_values_list(self):
        qs = Author.objects.prefetch_related("books")
        self.assertCountEqual(
            [value.name for value in qs.values_list("name", named=True)],
            ["Anne", "Charlotte", "Emily", "Jane"],
        )

    def test_m2m_prefetching_iterator_with_chunks(self):
        """
        Tests the m2m prefetching iterator with chunking to ensure that the correct authors are retrieved from the database in the expected number of queries. 

        This test case verifies that the iterator() method with prefetch_related() can efficiently fetch related objects from the database in chunks, and that the retrieved authors match the expected results.
        """
        with self.assertNumQueries(3):
            authors = [
                b.authors.first()
                for b in Book.objects.prefetch_related("authors").iterator(chunk_size=2)
            ]
        self.assertEqual(
            authors,
            [self.author1, self.author1, self.author3, self.author4],
        )

    def test_m2m_prefetching_iterator_without_chunks_error(self):
        """
        Tests that using QuerySet.iterator() after prefetch_related() without providing a chunk_size raises a ValueError with a descriptive error message. 

        The test verifies the correct error handling behavior when attempting to iterate over a queryset that has been prefetched with related objects, ensuring that the iterator is properly configured to avoid potential performance issues.
        """
        msg = (
            "chunk_size must be provided when using QuerySet.iterator() after "
            "prefetch_related()."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Book.objects.prefetch_related("authors").iterator()


class RawQuerySetTests(TestDataMixin, TestCase):
    def test_basic(self):
        """

        Tests the basic functionality of prefetching related objects.

        This test case verifies that the `prefetch_related` method is able to correctly 
        fetch related objects in a single database query, and then checks that the 
        subsequent access to the prefetched objects does not incur any additional 
        database queries. Specifically, it checks that the authors of a book are 
        correctly prefetched and can be accessed without triggering additional queries.

        """
        with self.assertNumQueries(2):
            books = Book.objects.raw(
                "SELECT * FROM prefetch_related_book WHERE id = %s", (self.book1.id,)
            ).prefetch_related("authors")
            book1 = list(books)[0]

        with self.assertNumQueries(0):
            self.assertCountEqual(
                book1.authors.all(), [self.author1, self.author2, self.author3]
            )

    def test_prefetch_before_raw(self):
        with self.assertNumQueries(2):
            books = Book.objects.prefetch_related("authors").raw(
                "SELECT * FROM prefetch_related_book WHERE id = %s", (self.book1.id,)
            )
            book1 = list(books)[0]

        with self.assertNumQueries(0):
            self.assertCountEqual(
                book1.authors.all(), [self.author1, self.author2, self.author3]
            )

    def test_clear(self):
        """

         Tests the clear functionality of prefetch_related on a query.

        The purpose of this test is to verify that prefetch_related can be cleared
        properly after it has been applied to a QuerySet. It does this by first creating
        a QuerySet with prefetch_related applied, then clearing it and verifying the
        expected number of database queries are made.

        This test covers the following scenarios:
          - Applying prefetch_related to a QuerySet
          - Clearing prefetch_related from a QuerySet
          - Verifying the correct number of database queries are made after clearing

        """
        with self.assertNumQueries(5):
            with_prefetch = Author.objects.raw(
                "SELECT * FROM prefetch_related_author"
            ).prefetch_related("books")
            without_prefetch = with_prefetch.prefetch_related(None)
            [list(a.books.all()) for a in without_prefetch]


class CustomPrefetchTests(TestCase):
    @classmethod
    def traverse_qs(cls, obj_iter, path):
        """
        Helper method that returns a list containing a list of the objects in the
        obj_iter. Then for each object in the obj_iter, the path will be
        recursively travelled and the found objects are added to the return value.
        """
        ret_val = []

        if hasattr(obj_iter, "all"):
            obj_iter = obj_iter.all()

        try:
            iter(obj_iter)
        except TypeError:
            obj_iter = [obj_iter]

        for obj in obj_iter:
            rel_objs = []
            for part in path:
                if not part:
                    continue
                try:
                    related = getattr(obj, part[0])
                except ObjectDoesNotExist:
                    continue
                if related is not None:
                    rel_objs.extend(cls.traverse_qs(related, [part[1:]]))
            ret_val.append((obj, rel_objs))
        return ret_val

    @classmethod
    def setUpTestData(cls):
        cls.person1 = Person.objects.create(name="Joe")
        cls.person2 = Person.objects.create(name="Mary")

        # Set main_room for each house before creating the next one for
        # databases where supports_nullable_unique_constraints is False.

        cls.house1 = House.objects.create(
            name="House 1", address="123 Main St", owner=cls.person1
        )
        cls.room1_1 = Room.objects.create(name="Dining room", house=cls.house1)
        cls.room1_2 = Room.objects.create(name="Lounge", house=cls.house1)
        cls.room1_3 = Room.objects.create(name="Kitchen", house=cls.house1)
        cls.house1.main_room = cls.room1_1
        cls.house1.save()
        cls.person1.houses.add(cls.house1)

        cls.house2 = House.objects.create(
            name="House 2", address="45 Side St", owner=cls.person1
        )
        cls.room2_1 = Room.objects.create(name="Dining room", house=cls.house2)
        cls.room2_2 = Room.objects.create(name="Lounge", house=cls.house2)
        cls.room2_3 = Room.objects.create(name="Kitchen", house=cls.house2)
        cls.house2.main_room = cls.room2_1
        cls.house2.save()
        cls.person1.houses.add(cls.house2)

        cls.house3 = House.objects.create(
            name="House 3", address="6 Downing St", owner=cls.person2
        )
        cls.room3_1 = Room.objects.create(name="Dining room", house=cls.house3)
        cls.room3_2 = Room.objects.create(name="Lounge", house=cls.house3)
        cls.room3_3 = Room.objects.create(name="Kitchen", house=cls.house3)
        cls.house3.main_room = cls.room3_1
        cls.house3.save()
        cls.person2.houses.add(cls.house3)

        cls.house4 = House.objects.create(
            name="house 4", address="7 Regents St", owner=cls.person2
        )
        cls.room4_1 = Room.objects.create(name="Dining room", house=cls.house4)
        cls.room4_2 = Room.objects.create(name="Lounge", house=cls.house4)
        cls.room4_3 = Room.objects.create(name="Kitchen", house=cls.house4)
        cls.house4.main_room = cls.room4_1
        cls.house4.save()
        cls.person2.houses.add(cls.house4)

    def test_traverse_qs(self):
        """
        Tests the traversal of a queryset to retrieve related objects.

        This function verifies that the :meth:`traverse_qs` method correctly fetches related objects
        from a queryset. It uses a queryset of :class:`Person` objects with prefetched related
        :attr:`houses` to compare the results of normal related object retrieval with the traversal
        approach, ensuring that both methods return the same related objects.

        The test primarily checks the functionality of the :meth:`traverse_qs` method in handling
        prefetched related objects, thereby confirming its correctness in traversing querysets
        and retrieving related objects as expected.
        """
        qs = Person.objects.prefetch_related("houses")
        related_objs_normal = ([list(p.houses.all()) for p in qs],)
        related_objs_from_traverse = [
            [inner[0] for inner in o[1]] for o in self.traverse_qs(qs, [["houses"]])
        ]
        self.assertEqual(related_objs_normal, (related_objs_from_traverse,))

    def test_ambiguous(self):
        # Ambiguous: Lookup was already seen with a different queryset.
        msg = (
            "'houses' lookup was already seen with a different queryset. You "
            "may need to adjust the ordering of your lookups."
        )
        # lookup.queryset shouldn't be evaluated.
        with self.assertNumQueries(3):
            with self.assertRaisesMessage(ValueError, msg):
                self.traverse_qs(
                    Person.objects.prefetch_related(
                        "houses__rooms",
                        Prefetch("houses", queryset=House.objects.all()),
                    ),
                    [["houses", "rooms"]],
                )

        # Ambiguous: Lookup houses_lst doesn't yet exist when performing
        # houses_lst__rooms.
        msg = (
            "Cannot find 'houses_lst' on Person object, 'houses_lst__rooms' is "
            "an invalid parameter to prefetch_related()"
        )
        with self.assertRaisesMessage(AttributeError, msg):
            self.traverse_qs(
                Person.objects.prefetch_related(
                    "houses_lst__rooms",
                    Prefetch(
                        "houses", queryset=House.objects.all(), to_attr="houses_lst"
                    ),
                ),
                [["houses", "rooms"]],
            )

        # Not ambiguous.
        self.traverse_qs(
            Person.objects.prefetch_related("houses__rooms", "houses"),
            [["houses", "rooms"]],
        )

        self.traverse_qs(
            Person.objects.prefetch_related(
                "houses__rooms",
                Prefetch("houses", queryset=House.objects.all(), to_attr="houses_lst"),
            ),
            [["houses", "rooms"]],
        )

    def test_m2m(self):
        # Control lookups.
        """
        Tests the performance and correctness of using Django's prefetch_related method 
        with many-to-many relationships. 

        This test case compares the results of querying a model's related objects 
        using different methods: direct prefetching and Prefetch objects with and without 
        a custom attribute. It ensures that the queries are executed the expected number 
        of times and that the results are consistent across different approaches.

        The goal is to verify that the traverse_qs method can efficiently traverse 
        querysets with prefetched related models, and that using Prefetch objects does 
        not alter the outcome. 

        The expected outcome is that all methods produce the same results and 
        that the number of database queries is optimized as expected.
        """
        with self.assertNumQueries(2):
            lst1 = self.traverse_qs(
                Person.objects.prefetch_related("houses"), [["houses"]]
            )

        # Test lookups.
        with self.assertNumQueries(2):
            lst2 = self.traverse_qs(
                Person.objects.prefetch_related(Prefetch("houses")), [["houses"]]
            )
        self.assertEqual(lst1, lst2)
        with self.assertNumQueries(2):
            lst2 = self.traverse_qs(
                Person.objects.prefetch_related(
                    Prefetch("houses", to_attr="houses_lst")
                ),
                [["houses_lst"]],
            )
        self.assertEqual(lst1, lst2)

    def test_reverse_m2m(self):
        # Control lookups.
        """
        Tests the efficiency of querying related objects in a many-to-many relationship, comparing the usage of `prefetch_related` with and without the `Prefetch` object from Django. 

        It verifies that the number of database queries is optimized when using either method to fetch related objects, specifically the occupants of a House.

        The function checks that the results are consistent across both methods, whether the related objects are accessed directly or via a custom attribute. It ensures that the query optimization works as expected, reducing the number of queries from what would be required without prefetching.
        """
        with self.assertNumQueries(2):
            lst1 = self.traverse_qs(
                House.objects.prefetch_related("occupants"), [["occupants"]]
            )

        # Test lookups.
        with self.assertNumQueries(2):
            lst2 = self.traverse_qs(
                House.objects.prefetch_related(Prefetch("occupants")), [["occupants"]]
            )
        self.assertEqual(lst1, lst2)
        with self.assertNumQueries(2):
            lst2 = self.traverse_qs(
                House.objects.prefetch_related(
                    Prefetch("occupants", to_attr="occupants_lst")
                ),
                [["occupants_lst"]],
            )
        self.assertEqual(lst1, lst2)

    def test_m2m_through_fk(self):
        # Control lookups.
        with self.assertNumQueries(3):
            lst1 = self.traverse_qs(
                Room.objects.prefetch_related("house__occupants"),
                [["house", "occupants"]],
            )

        # Test lookups.
        with self.assertNumQueries(3):
            lst2 = self.traverse_qs(
                Room.objects.prefetch_related(Prefetch("house__occupants")),
                [["house", "occupants"]],
            )
        self.assertEqual(lst1, lst2)
        with self.assertNumQueries(3):
            lst2 = self.traverse_qs(
                Room.objects.prefetch_related(
                    Prefetch("house__occupants", to_attr="occupants_lst")
                ),
                [["house", "occupants_lst"]],
            )
        self.assertEqual(lst1, lst2)

    def test_m2m_through_gfk(self):
        TaggedItem.objects.create(tag="houses", content_object=self.house1)
        TaggedItem.objects.create(tag="houses", content_object=self.house2)

        # Control lookups.
        with self.assertNumQueries(3):
            lst1 = self.traverse_qs(
                TaggedItem.objects.filter(tag="houses").prefetch_related(
                    "content_object__rooms"
                ),
                [["content_object", "rooms"]],
            )

        # Test lookups.
        with self.assertNumQueries(3):
            lst2 = self.traverse_qs(
                TaggedItem.objects.prefetch_related(
                    Prefetch("content_object"),
                    Prefetch("content_object__rooms", to_attr="rooms_lst"),
                ),
                [["content_object", "rooms_lst"]],
            )
        self.assertEqual(lst1, lst2)

    def test_o2m_through_m2m(self):
        # Control lookups.
        with self.assertNumQueries(3):
            lst1 = self.traverse_qs(
                Person.objects.prefetch_related("houses", "houses__rooms"),
                [["houses", "rooms"]],
            )

        # Test lookups.
        with self.assertNumQueries(3):
            lst2 = self.traverse_qs(
                Person.objects.prefetch_related(Prefetch("houses"), "houses__rooms"),
                [["houses", "rooms"]],
            )
        self.assertEqual(lst1, lst2)
        with self.assertNumQueries(3):
            lst2 = self.traverse_qs(
                Person.objects.prefetch_related(
                    Prefetch("houses"), Prefetch("houses__rooms")
                ),
                [["houses", "rooms"]],
            )
        self.assertEqual(lst1, lst2)
        with self.assertNumQueries(3):
            lst2 = self.traverse_qs(
                Person.objects.prefetch_related(
                    Prefetch("houses", to_attr="houses_lst"), "houses_lst__rooms"
                ),
                [["houses_lst", "rooms"]],
            )
        self.assertEqual(lst1, lst2)
        with self.assertNumQueries(3):
            lst2 = self.traverse_qs(
                Person.objects.prefetch_related(
                    Prefetch("houses", to_attr="houses_lst"),
                    Prefetch("houses_lst__rooms", to_attr="rooms_lst"),
                ),
                [["houses_lst", "rooms_lst"]],
            )
        self.assertEqual(lst1, lst2)

    def test_generic_rel(self):
        """

        Tests the functionality of generic relations in conjunction with prefetch_related.

        This test case creates a bookmark object, assigns it tags, and then uses the traverse_qs method to test two different methods of prefetching related objects.
        The first method uses the standard prefetch_related syntax to fetch the 'tags' and 'favorite_tags' relationships, as well as the 'content_object' relationship of the 'tags'.
        The second method uses the Prefetch object to achieve the same result, but with more explicit control over the prefetching process.
        The test then asserts that the results of both methods are equal, ensuring that the generic relations are being correctly prefetched and traversed.

        Parameters: None
        Returns: None

        """
        bookmark = Bookmark.objects.create(url="http://www.djangoproject.com/")
        TaggedItem.objects.create(content_object=bookmark, tag="django")
        TaggedItem.objects.create(
            content_object=bookmark, favorite=bookmark, tag="python"
        )

        # Control lookups.
        with self.assertNumQueries(4):
            lst1 = self.traverse_qs(
                Bookmark.objects.prefetch_related(
                    "tags", "tags__content_object", "favorite_tags"
                ),
                [["tags", "content_object"], ["favorite_tags"]],
            )

        # Test lookups.
        with self.assertNumQueries(4):
            lst2 = self.traverse_qs(
                Bookmark.objects.prefetch_related(
                    Prefetch("tags", to_attr="tags_lst"),
                    Prefetch("tags_lst__content_object"),
                    Prefetch("favorite_tags"),
                ),
                [["tags_lst", "content_object"], ["favorite_tags"]],
            )
        self.assertEqual(lst1, lst2)

    def test_traverse_single_item_property(self):
        # Control lookups.
        with self.assertNumQueries(5):
            lst1 = self.traverse_qs(
                Person.objects.prefetch_related(
                    "houses__rooms",
                    "primary_house__occupants__houses",
                ),
                [["primary_house", "occupants", "houses"]],
            )

        # Test lookups.
        with self.assertNumQueries(5):
            lst2 = self.traverse_qs(
                Person.objects.prefetch_related(
                    "houses__rooms",
                    Prefetch("primary_house__occupants", to_attr="occupants_lst"),
                    "primary_house__occupants_lst__houses",
                ),
                [["primary_house", "occupants_lst", "houses"]],
            )
        self.assertEqual(lst1, lst2)

    def test_traverse_multiple_items_property(self):
        # Control lookups.
        """

        Test that traversing multiple items property works as expected.

        This test checks that the resulting lists are equivalent when traversing 
        nested relationships using the :meth:`traverse_qs` method, either 
        directly or via a prefetched related object stored in a custom attribute.

        The test first creates a list of results by traversing the 'all_houses', 
        'occupants', 'houses' relationships of a :class:`Person` queryset that 
        has prefetched 'houses' and 'all_houses__occupants__houses'. 
        Then it creates another list of results by traversing the same 
        relationships but using a prefetched related object 'occupants_lst' 
        stored in a custom attribute. The test then asserts that the two 
        resulting lists are equal, ensuring that both traversal methods 
        produce the same results.

        """
        with self.assertNumQueries(4):
            lst1 = self.traverse_qs(
                Person.objects.prefetch_related(
                    "houses",
                    "all_houses__occupants__houses",
                ),
                [["all_houses", "occupants", "houses"]],
            )

        # Test lookups.
        with self.assertNumQueries(4):
            lst2 = self.traverse_qs(
                Person.objects.prefetch_related(
                    "houses",
                    Prefetch("all_houses__occupants", to_attr="occupants_lst"),
                    "all_houses__occupants_lst__houses",
                ),
                [["all_houses", "occupants_lst", "houses"]],
            )
        self.assertEqual(lst1, lst2)

    def test_custom_qs(self):
        # Test basic.
        with self.assertNumQueries(2):
            lst1 = list(Person.objects.prefetch_related("houses"))
        with self.assertNumQueries(2):
            lst2 = list(
                Person.objects.prefetch_related(
                    Prefetch(
                        "houses", queryset=House.objects.all(), to_attr="houses_lst"
                    )
                )
            )
        self.assertEqual(
            self.traverse_qs(lst1, [["houses"]]),
            self.traverse_qs(lst2, [["houses_lst"]]),
        )

        # Test queryset filtering.
        with self.assertNumQueries(2):
            lst2 = list(
                Person.objects.prefetch_related(
                    Prefetch(
                        "houses",
                        queryset=House.objects.filter(
                            pk__in=[self.house1.pk, self.house3.pk]
                        ),
                        to_attr="houses_lst",
                    )
                )
            )
        self.assertEqual(len(lst2[0].houses_lst), 1)
        self.assertEqual(lst2[0].houses_lst[0], self.house1)
        self.assertEqual(len(lst2[1].houses_lst), 1)
        self.assertEqual(lst2[1].houses_lst[0], self.house3)

        # Test flattened.
        with self.assertNumQueries(3):
            lst1 = list(Person.objects.prefetch_related("houses__rooms"))
        with self.assertNumQueries(3):
            lst2 = list(
                Person.objects.prefetch_related(
                    Prefetch(
                        "houses__rooms",
                        queryset=Room.objects.all(),
                        to_attr="rooms_lst",
                    )
                )
            )
        self.assertEqual(
            self.traverse_qs(lst1, [["houses", "rooms"]]),
            self.traverse_qs(lst2, [["houses", "rooms_lst"]]),
        )

        # Test inner select_related.
        with self.assertNumQueries(3):
            lst1 = list(Person.objects.prefetch_related("houses__owner"))
        with self.assertNumQueries(2):
            lst2 = list(
                Person.objects.prefetch_related(
                    Prefetch("houses", queryset=House.objects.select_related("owner"))
                )
            )
        self.assertEqual(
            self.traverse_qs(lst1, [["houses", "owner"]]),
            self.traverse_qs(lst2, [["houses", "owner"]]),
        )

        # Test inner prefetch.
        inner_rooms_qs = Room.objects.filter(pk__in=[self.room1_1.pk, self.room1_2.pk])
        houses_qs_prf = House.objects.prefetch_related(
            Prefetch("rooms", queryset=inner_rooms_qs, to_attr="rooms_lst")
        )
        with self.assertNumQueries(4):
            lst2 = list(
                Person.objects.prefetch_related(
                    Prefetch(
                        "houses",
                        queryset=houses_qs_prf.filter(pk=self.house1.pk),
                        to_attr="houses_lst",
                    ),
                    Prefetch("houses_lst__rooms_lst__main_room_of"),
                )
            )

        self.assertEqual(len(lst2[0].houses_lst[0].rooms_lst), 2)
        self.assertEqual(lst2[0].houses_lst[0].rooms_lst[0], self.room1_1)
        self.assertEqual(lst2[0].houses_lst[0].rooms_lst[1], self.room1_2)
        self.assertEqual(lst2[0].houses_lst[0].rooms_lst[0].main_room_of, self.house1)
        self.assertEqual(len(lst2[1].houses_lst), 0)

        # Test ForwardManyToOneDescriptor.
        houses = House.objects.select_related("owner")
        with self.assertNumQueries(6):
            rooms = Room.objects.prefetch_related("house")
            lst1 = self.traverse_qs(rooms, [["house", "owner"]])
        with self.assertNumQueries(2):
            rooms = Room.objects.prefetch_related(Prefetch("house", queryset=houses))
            lst2 = self.traverse_qs(rooms, [["house", "owner"]])
        self.assertEqual(lst1, lst2)
        with self.assertNumQueries(2):
            houses = House.objects.select_related("owner")
            rooms = Room.objects.prefetch_related(
                Prefetch("house", queryset=houses, to_attr="house_attr")
            )
            lst2 = self.traverse_qs(rooms, [["house_attr", "owner"]])
        self.assertEqual(lst1, lst2)
        room = Room.objects.prefetch_related(
            Prefetch("house", queryset=houses.filter(address="DoesNotExist"))
        ).first()
        with self.assertRaises(ObjectDoesNotExist):
            getattr(room, "house")
        room = Room.objects.prefetch_related(
            Prefetch(
                "house",
                queryset=houses.filter(address="DoesNotExist"),
                to_attr="house_attr",
            )
        ).first()
        self.assertIsNone(room.house_attr)
        rooms = Room.objects.prefetch_related(
            Prefetch("house", queryset=House.objects.only("name"))
        )
        with self.assertNumQueries(2):
            getattr(rooms.first().house, "name")
        with self.assertNumQueries(3):
            getattr(rooms.first().house, "address")

        # Test ReverseOneToOneDescriptor.
        houses = House.objects.select_related("owner")
        with self.assertNumQueries(6):
            rooms = Room.objects.prefetch_related("main_room_of")
            lst1 = self.traverse_qs(rooms, [["main_room_of", "owner"]])
        with self.assertNumQueries(2):
            rooms = Room.objects.prefetch_related(
                Prefetch("main_room_of", queryset=houses)
            )
            lst2 = self.traverse_qs(rooms, [["main_room_of", "owner"]])
        self.assertEqual(lst1, lst2)
        with self.assertNumQueries(2):
            rooms = list(
                Room.objects.prefetch_related(
                    Prefetch(
                        "main_room_of",
                        queryset=houses,
                        to_attr="main_room_of_attr",
                    )
                )
            )
            lst2 = self.traverse_qs(rooms, [["main_room_of_attr", "owner"]])
        self.assertEqual(lst1, lst2)
        room = (
            Room.objects.filter(main_room_of__isnull=False)
            .prefetch_related(
                Prefetch("main_room_of", queryset=houses.filter(address="DoesNotExist"))
            )
            .first()
        )
        with self.assertRaises(ObjectDoesNotExist):
            getattr(room, "main_room_of")
        room = (
            Room.objects.filter(main_room_of__isnull=False)
            .prefetch_related(
                Prefetch(
                    "main_room_of",
                    queryset=houses.filter(address="DoesNotExist"),
                    to_attr="main_room_of_attr",
                )
            )
            .first()
        )
        self.assertIsNone(room.main_room_of_attr)

        # The custom queryset filters should be applied to the queryset
        # instance returned by the manager.
        person = Person.objects.prefetch_related(
            Prefetch("houses", queryset=House.objects.filter(name="House 1")),
        ).get(pk=self.person1.pk)
        self.assertEqual(
            list(person.houses.all()),
            list(person.houses.all().all()),
        )

    def test_nested_prefetch_related_are_not_overwritten(self):
        # Regression test for #24873
        houses_2 = House.objects.prefetch_related(Prefetch("rooms"))
        persons = Person.objects.prefetch_related(Prefetch("houses", queryset=houses_2))
        houses = House.objects.prefetch_related(Prefetch("occupants", queryset=persons))
        list(houses)  # queryset must be evaluated once to reproduce the bug.
        self.assertEqual(
            houses.all()[0].occupants.all()[0].houses.all()[1].rooms.all()[0],
            self.room2_1,
        )

    def test_nested_prefetch_related_with_duplicate_prefetcher(self):
        """
        Nested prefetches whose name clashes with descriptor names
        (Person.houses here) are allowed.
        """
        occupants = Person.objects.prefetch_related(
            Prefetch("houses", to_attr="some_attr_name"),
            Prefetch("houses", queryset=House.objects.prefetch_related("main_room")),
        )
        houses = House.objects.prefetch_related(
            Prefetch("occupants", queryset=occupants)
        )
        with self.assertNumQueries(5):
            self.traverse_qs(list(houses), [["occupants", "houses", "main_room"]])

    def test_nested_prefetch_related_with_duplicate_prefetch_and_depth(self):
        people = Person.objects.prefetch_related(
            Prefetch(
                "houses__main_room",
                queryset=Room.objects.filter(name="Dining room"),
                to_attr="dining_room",
            ),
            "houses__main_room",
        )
        with self.assertNumQueries(4):
            main_room = people[0].houses.all()[0]

        people = Person.objects.prefetch_related(
            "houses__main_room",
            Prefetch(
                "houses__main_room",
                queryset=Room.objects.filter(name="Dining room"),
                to_attr="dining_room",
            ),
        )
        with self.assertNumQueries(4):
            main_room = people[0].houses.all()[0]

        self.assertEqual(main_room.main_room, self.room1_1)

    def test_values_queryset(self):
        """

        Tests the behavior of Prefetch when used with querysets that utilize 
        :func:`~django.db.models.query.QuerySet.values` or 
        :func:`~django.db.models.query.QuerySet.values_list`. Verifies that 
        a :class:`~django.core.exceptions.ValidationError` is raised when 
        attempting to prefetch such querysets. Additionally, checks that 
        :func:`~django.db.models.query.QuerySet.prefetch_related` works 
        correctly with custom iterable classes. 

        """
        msg = "Prefetch querysets cannot use raw(), values(), and values_list()."
        with self.assertRaisesMessage(ValueError, msg):
            Prefetch("houses", House.objects.values("pk"))
        with self.assertRaisesMessage(ValueError, msg):
            Prefetch("houses", House.objects.values_list("pk"))
        # That error doesn't affect managers with custom ModelIterable subclasses
        self.assertIs(
            Teacher.objects_custom.all()._iterable_class, ModelIterableSubclass
        )
        Prefetch("teachers", Teacher.objects_custom.all())

    def test_raw_queryset(self):
        msg = "Prefetch querysets cannot use raw(), values(), and values_list()."
        with self.assertRaisesMessage(ValueError, msg):
            Prefetch("houses", House.objects.raw("select pk from house"))

    def test_to_attr_doesnt_cache_through_attr_as_list(self):
        """

        Tests that prefetching through an attribute (in this case 'rooms') to a custom attribute (in this case 'to_rooms') 
        does not prevent the original attribute from returning a QuerySet when accessed as a list.

        This test ensures that the original attribute is not replaced with a cached list when accessing the custom attribute.

        """
        house = House.objects.prefetch_related(
            Prefetch("rooms", queryset=Room.objects.all(), to_attr="to_rooms"),
        ).get(pk=self.house3.pk)
        self.assertIsInstance(house.rooms.all(), QuerySet)

    def test_to_attr_cached_property(self):
        persons = Person.objects.prefetch_related(
            Prefetch("houses", House.objects.all(), to_attr="cached_all_houses"),
        )
        for person in persons:
            # To bypass caching at the related descriptor level, don't use
            # person.houses.all() here.
            all_houses = list(House.objects.filter(occupants=person))
            with self.assertNumQueries(0):
                self.assertEqual(person.cached_all_houses, all_houses)

    def test_filter_deferred(self):
        """
        Related filtering of prefetched querysets is deferred until necessary.
        """
        add_q = Query.add_q
        with mock.patch.object(
            Query,
            "add_q",
            autospec=True,
            side_effect=lambda self, q: add_q(self, q),
        ) as add_q_mock:
            list(
                House.objects.prefetch_related(
                    Prefetch("occupants", queryset=Person.objects.all())
                )
            )
            self.assertEqual(add_q_mock.call_count, 1)


class DefaultManagerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the application.

        This class method creates test instances of Qualification, Teacher, and Department objects,
        and establishes relationships between them. The created data includes four qualifications (BA, BSci, MA, PhD),
        three teachers (Mr Cleese, Mr Idle, Mr Chapman) with various qualifications, and two departments (English, Physics)
        with assigned teachers. The test data is created as class attributes, making it available for use in subsequent tests.

        The purpose of this method is to provide a predefined dataset for testing, ensuring consistency and reliability across different test cases.
        """
        cls.qual1 = Qualification.objects.create(name="BA")
        cls.qual2 = Qualification.objects.create(name="BSci")
        cls.qual3 = Qualification.objects.create(name="MA")
        cls.qual4 = Qualification.objects.create(name="PhD")

        cls.teacher1 = Teacher.objects.create(name="Mr Cleese")
        cls.teacher2 = Teacher.objects.create(name="Mr Idle")
        cls.teacher3 = Teacher.objects.create(name="Mr Chapman")
        cls.teacher1.qualifications.add(cls.qual1, cls.qual2, cls.qual3, cls.qual4)
        cls.teacher2.qualifications.add(cls.qual1)
        cls.teacher3.qualifications.add(cls.qual2)

        cls.dept1 = Department.objects.create(name="English")
        cls.dept2 = Department.objects.create(name="Physics")
        cls.dept1.teachers.add(cls.teacher1, cls.teacher2)
        cls.dept2.teachers.add(cls.teacher1, cls.teacher3)

    def test_m2m_then_m2m(self):
        """

        Tests that Many-to-Many relationships are properly fetched and rendered 
        when using the prefetch_related method for querying Department objects. 

        The test queries departments and their respective teachers, then asserts 
        that the correct teachers are associated with each department, verifying 
        the correct execution of the query and the accuracy of the data retrieved.

        The test also verifies that the query execution performance is optimal 
        by checking that the number of database queries is as expected.

        """
        with self.assertNumQueries(3):
            # When we prefetch the teachers, and force the query, we don't want
            # the default manager on teachers to immediately get all the related
            # qualifications, since this will do one query per teacher.
            qs = Department.objects.prefetch_related("teachers")
            depts = "".join(
                "%s department: %s\n"
                % (dept.name, ", ".join(str(t) for t in dept.teachers.all()))
                for dept in qs
            )

            self.assertEqual(
                depts,
                "English department: Mr Cleese (BA, BSci, MA, PhD), Mr Idle (BA)\n"
                "Physics department: Mr Cleese (BA, BSci, MA, PhD), Mr Chapman "
                "(BSci)\n",
            )


class GenericRelationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        book1 = Book.objects.create(title="Winnie the Pooh")
        book2 = Book.objects.create(title="Do you like green eggs and spam?")
        book3 = Book.objects.create(title="Three Men In A Boat")

        reader1 = Reader.objects.create(name="me")
        reader2 = Reader.objects.create(name="you")
        reader3 = Reader.objects.create(name="someone")

        book1.read_by.add(reader1, reader2)
        book2.read_by.add(reader2)
        book3.read_by.add(reader3)

        cls.book1, cls.book2, cls.book3 = book1, book2, book3
        cls.reader1, cls.reader2, cls.reader3 = reader1, reader2, reader3

    def test_prefetch_GFK(self):
        TaggedItem.objects.create(tag="awesome", content_object=self.book1)
        TaggedItem.objects.create(tag="great", content_object=self.reader1)
        TaggedItem.objects.create(tag="outstanding", content_object=self.book2)
        TaggedItem.objects.create(tag="amazing", content_object=self.reader3)

        # 1 for TaggedItem table, 1 for Book table, 1 for Reader table
        with self.assertNumQueries(3):
            qs = TaggedItem.objects.prefetch_related("content_object")
            list(qs)

    def test_prefetch_GFK_nonint_pk(self):
        """
        Test that prefetching GenericForeignKey relationships for non-integer primary keys works as expected.

        This test checks if the comments can be successfully retrieved along with their related content objects with a minimal number of database queries. 

        It verifies that using prefetch_related on Comment objects results in only the expected number of database queries, demonstrating efficient data retrieval. 

        The test focuses on GenericForeignKey relationships where the primary key is not an integer type, ensuring that the prefetching functionality handles varied primary key types correctly.
        """
        Comment.objects.create(comment="awesome", content_object=self.book1)

        # 1 for Comment table, 1 for Book table
        with self.assertNumQueries(2):
            qs = Comment.objects.prefetch_related("content_object")
            [c.content_object for c in qs]

    def test_prefetch_GFK_uuid_pk(self):
        """

        Tests that prefetching a GenericForeignKey (GFK) field using UUID as the primary key works correctly.

        This test case creates an Article instance and associates a Comment with it using the content_object_uuid field.
        It then prefetches the related objects and verifies that the prefetched objects match the expected result.

        """
        article = Article.objects.create(name="Django")
        Comment.objects.create(comment="awesome", content_object_uuid=article)
        qs = Comment.objects.prefetch_related("content_object_uuid")
        self.assertEqual([c.content_object_uuid for c in qs], [article])

    def test_prefetch_GFK_fk_pk(self):
        book = Book.objects.create(title="Poems")
        book_with_year = BookWithYear.objects.create(book=book, published_year=2019)
        Comment.objects.create(comment="awesome", content_object=book_with_year)
        qs = Comment.objects.prefetch_related("content_object")
        self.assertEqual([c.content_object for c in qs], [book_with_year])

    def test_traverse_GFK(self):
        """
        A 'content_object' can be traversed with prefetch_related() and
        get to related objects on the other side (assuming it is suitably
        filtered)
        """
        TaggedItem.objects.create(tag="awesome", content_object=self.book1)
        TaggedItem.objects.create(tag="awesome", content_object=self.book2)
        TaggedItem.objects.create(tag="awesome", content_object=self.book3)
        TaggedItem.objects.create(tag="awesome", content_object=self.reader1)
        TaggedItem.objects.create(tag="awesome", content_object=self.reader2)

        ct = ContentType.objects.get_for_model(Book)

        # We get 3 queries - 1 for main query, 1 for content_objects since they
        # all use the same table, and 1 for the 'read_by' relation.
        with self.assertNumQueries(3):
            # If we limit to books, we know that they will have 'read_by'
            # attributes, so the following makes sense:
            qs = TaggedItem.objects.filter(
                content_type=ct, tag="awesome"
            ).prefetch_related("content_object__read_by")
            readers_of_awesome_books = {
                r.name for tag in qs for r in tag.content_object.read_by.all()
            }
            self.assertEqual(readers_of_awesome_books, {"me", "you", "someone"})

    def test_nullable_GFK(self):
        """

        Test behavior of Generic Foreign Key (GFK) when dealing with nullable fields.

        Verifies that database queries are optimized when fetching related objects
        using `prefetch_related`, ensuring that the number of database queries remains
        efficient even when dealing with nullable GFK fields. The test also checks
        data consistency by comparing the results of prefetched queries with standard
        queries.

        """
        TaggedItem.objects.create(
            tag="awesome", content_object=self.book1, created_by=self.reader1
        )
        TaggedItem.objects.create(tag="great", content_object=self.book2)
        TaggedItem.objects.create(tag="rubbish", content_object=self.book3)

        with self.assertNumQueries(2):
            result = [
                t.created_by for t in TaggedItem.objects.prefetch_related("created_by")
            ]

        self.assertEqual(result, [t.created_by for t in TaggedItem.objects.all()])

    def test_generic_relation(self):
        """

        Tests the generic relation functionality for retrieving related tags of bookmark objects.

        This function creates a bookmark instance, assigns it two tags ('django' and 'python'), and then 
        retrieves the tags in a single database query using prefetch_related. The result is compared to 
        the expected sorted list of tags to ensure correctness.

        The test also verifies that the database query count remains optimal, at two queries.

        """
        bookmark = Bookmark.objects.create(url="http://www.djangoproject.com/")
        TaggedItem.objects.create(content_object=bookmark, tag="django")
        TaggedItem.objects.create(content_object=bookmark, tag="python")

        with self.assertNumQueries(2):
            tags = [
                t.tag
                for b in Bookmark.objects.prefetch_related("tags")
                for t in b.tags.all()
            ]
            self.assertEqual(sorted(tags), ["django", "python"])

    def test_charfield_GFK(self):
        """
        Tests the charfield within GenericForeignKey (GFK) using the Bookmark model.

        This test case covers the following functionality:
        - Creating a Bookmark instance and associating it with multiple tags.
        - Creating a TaggedItem instance with a favorite bookmark instance and a tag.
        - Verifying that the Bookmark instance can be correctly filtered and retrieved along with its associated tags and favorite tags in a specified number of database queries.
        - Checking that the retrieved bookmark's tags and favorite tags match the expected values.

        Ensures that the GenericForeignKey field within the TaggedItem model functions correctly to associate tags and favorite tags with bookmark instances, and that these associations can be efficiently retrieved using prefetch_related on the BookmarkQuerySet.
        """
        b = Bookmark.objects.create(url="http://www.djangoproject.com/")
        TaggedItem.objects.create(content_object=b, tag="django")
        TaggedItem.objects.create(content_object=b, favorite=b, tag="python")

        with self.assertNumQueries(3):
            bookmark = Bookmark.objects.filter(pk=b.pk).prefetch_related(
                "tags", "favorite_tags"
            )[0]
            self.assertEqual(
                sorted(i.tag for i in bookmark.tags.all()), ["django", "python"]
            )
            self.assertEqual([i.tag for i in bookmark.favorite_tags.all()], ["python"])

    def test_custom_queryset(self):
        """

        Tests the efficiency of a custom queryset when fetching related objects.

        This test case creates a bookmark with multiple tags, then uses Django's
        prefetch_related functionality to fetch the bookmark and its related tags
        in a single database query. It then asserts that subsequent calls to fetch
        the bookmark's tags do not result in additional database queries.

        The test verifies that the prefetch_related method correctly filters the
        related objects, and that the results are consistent across multiple calls.

        """
        bookmark = Bookmark.objects.create(url="http://www.djangoproject.com/")
        django_tag = TaggedItem.objects.create(content_object=bookmark, tag="django")
        TaggedItem.objects.create(content_object=bookmark, tag="python")

        with self.assertNumQueries(2):
            bookmark = Bookmark.objects.prefetch_related(
                Prefetch("tags", TaggedItem.objects.filter(tag="django")),
            ).get()

        with self.assertNumQueries(0):
            self.assertEqual(list(bookmark.tags.all()), [django_tag])

        # The custom queryset filters should be applied to the queryset
        # instance returned by the manager.
        self.assertEqual(list(bookmark.tags.all()), list(bookmark.tags.all().all()))

    def test_deleted_GFK(self):
        TaggedItem.objects.create(tag="awesome", content_object=self.book1)
        TaggedItem.objects.create(tag="awesome", content_object=self.book2)
        ct = ContentType.objects.get_for_model(Book)

        book1_pk = self.book1.pk
        self.book1.delete()

        with self.assertNumQueries(2):
            qs = TaggedItem.objects.filter(tag="awesome").prefetch_related(
                "content_object"
            )
            result = [
                (tag.object_id, tag.content_type_id, tag.content_object) for tag in qs
            ]
            self.assertEqual(
                result,
                [
                    (book1_pk, ct.pk, None),
                    (self.book2.pk, ct.pk, self.book2),
                ],
            )


class MultiTableInheritanceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Class method to set up test data for the class.

        This method creates a set of test objects, including books, authors, and book reviews.
        It establishes relationships between these objects, such as which authors wrote which books,
        and which authors have reviews for which books.

        The test data includes:
            - Two books with different publication years
            - Three authors with different ages and first books
            - An author address for one of the authors
            - Two book reviews, one for each book

        This data can be used as a foundation for testing various scenarios and functionality within the class.

        """
        cls.book1 = BookWithYear.objects.create(title="Poems", published_year=2010)
        cls.book2 = BookWithYear.objects.create(title="More poems", published_year=2011)
        cls.author1 = AuthorWithAge.objects.create(
            name="Jane", first_book=cls.book1, age=50
        )
        cls.author2 = AuthorWithAge.objects.create(
            name="Tom", first_book=cls.book1, age=49
        )
        cls.author3 = AuthorWithAge.objects.create(
            name="Robert", first_book=cls.book2, age=48
        )
        cls.author_address = AuthorAddress.objects.create(
            author=cls.author1, address="SomeStreet 1"
        )
        cls.book2.aged_authors.add(cls.author2, cls.author3)
        cls.br1 = BookReview.objects.create(book=cls.book1, notes="review book1")
        cls.br2 = BookReview.objects.create(book=cls.book2, notes="review book2")

    def test_foreignkey(self):
        with self.assertNumQueries(2):
            qs = AuthorWithAge.objects.prefetch_related("addresses")
            addresses = [
                [str(address) for address in obj.addresses.all()] for obj in qs
            ]
        self.assertEqual(addresses, [[str(self.author_address)], [], []])

    def test_foreignkey_to_inherited(self):
        """
        Test that foreign key to inherited models works correctly when using prefetch_related.

        This test case verifies that the correct number of database queries are executed when fetching related objects, and that the retrieved data is accurate. Specifically, it checks that the titles of books associated with book reviews can be fetched efficiently using prefetch_related.
        """
        with self.assertNumQueries(2):
            qs = BookReview.objects.prefetch_related("book")
            titles = [obj.book.title for obj in qs]
        self.assertCountEqual(titles, ["Poems", "More poems"])

    def test_m2m_to_inheriting_model(self):
        """

        Tests the many-to-many relationship between authors and books, 
        including inheritance of related models. 

        Verifies that prefetching related models reduces database query count, 
        resulting in improved performance. The test checks the relationship 
        in both directions: from authors to books and from books to authors. 

        It ensures that the results are consistent regardless of whether 
        related models are prefetched or not, demonstrating the correctness 
        of the many-to-many relationship implementation.

        """
        qs = AuthorWithAge.objects.prefetch_related("books_with_year")
        with self.assertNumQueries(2):
            lst = [
                [str(book) for book in author.books_with_year.all()] for author in qs
            ]
        qs = AuthorWithAge.objects.all()
        lst2 = [[str(book) for book in author.books_with_year.all()] for author in qs]
        self.assertEqual(lst, lst2)

        qs = BookWithYear.objects.prefetch_related("aged_authors")
        with self.assertNumQueries(2):
            lst = [[str(author) for author in book.aged_authors.all()] for book in qs]
        qs = BookWithYear.objects.all()
        lst2 = [[str(author) for author in book.aged_authors.all()] for book in qs]
        self.assertEqual(lst, lst2)

    def test_parent_link_prefetch(self):
        with self.assertNumQueries(2):
            [a.author for a in AuthorWithAge.objects.prefetch_related("author")]

    @override_settings(DEBUG=True)
    def test_child_link_prefetch(self):
        with self.assertNumQueries(2):
            authors = [
                a.authorwithage
                for a in Author.objects.prefetch_related("authorwithage")
            ]

        # Regression for #18090: the prefetching query must include an IN clause.
        # Note that on Oracle the table name is upper case in the generated SQL,
        # thus the .lower() call.
        self.assertIn("authorwithage", connection.queries[-1]["sql"].lower())
        self.assertIn(" IN ", connection.queries[-1]["sql"])

        self.assertEqual(authors, [a.authorwithage for a in Author.objects.all()])


class ForeignKeyToFieldTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.book = Book.objects.create(title="Poems")
        cls.author1 = Author.objects.create(name="Jane", first_book=cls.book)
        cls.author2 = Author.objects.create(name="Tom", first_book=cls.book)
        cls.author3 = Author.objects.create(name="Robert", first_book=cls.book)
        cls.author_address = AuthorAddress.objects.create(
            author=cls.author1, address="SomeStreet 1"
        )
        FavoriteAuthors.objects.create(author=cls.author1, likes_author=cls.author2)
        FavoriteAuthors.objects.create(author=cls.author2, likes_author=cls.author3)
        FavoriteAuthors.objects.create(author=cls.author3, likes_author=cls.author1)

    def test_foreignkey(self):
        """

        Tests the retrieval of related objects defined by a foreign key relationship.

        Specifically, this test case verifies that the Author model's addresses are properly 
        prefetched and retrieved. It checks that the correct number of database queries are 
        executed and that the resulting addresses are as expected.

        The test case covers three authors: one with an associated address and two without. 
        It ensures that the prefetched addresses are correctly associated with their respective authors.

        """
        with self.assertNumQueries(2):
            qs = Author.objects.prefetch_related("addresses")
            addresses = [
                [str(address) for address in obj.addresses.all()] for obj in qs
            ]
        self.assertEqual(addresses, [[str(self.author_address)], [], []])

    def test_m2m(self):
        """
        Tests many-to-many relationships between authors.

        This test case verifies that the prefetching of favorite authors and authors who favor the current author is performed correctly.
        It checks that the number of database queries is minimized and that the resulting data matches the expected relationships between authors.
        The test covers both the \"favorite_authors\" and \"favors_me\" relationships, ensuring that they are correctly prefetched and contain the expected authors.
        """
        with self.assertNumQueries(3):
            qs = Author.objects.prefetch_related("favorite_authors", "favors_me")
            favorites = [
                (
                    [str(i_like) for i_like in author.favorite_authors.all()],
                    [str(likes_me) for likes_me in author.favors_me.all()],
                )
                for author in qs
            ]
            self.assertEqual(
                favorites,
                [
                    ([str(self.author2)], [str(self.author3)]),
                    ([str(self.author3)], [str(self.author1)]),
                    ([str(self.author1)], [str(self.author2)]),
                ],
            )


class LookupOrderingTest(TestCase):
    """
    Test cases that demonstrate that ordering of lookups is important, and
    ensure it is preserved.
    """

    @classmethod
    def setUpTestData(cls):
        person1 = Person.objects.create(name="Joe")
        person2 = Person.objects.create(name="Mary")

        # Set main_room for each house before creating the next one for
        # databases where supports_nullable_unique_constraints is False.
        house1 = House.objects.create(address="123 Main St")
        room1_1 = Room.objects.create(name="Dining room", house=house1)
        Room.objects.create(name="Lounge", house=house1)
        Room.objects.create(name="Kitchen", house=house1)
        house1.main_room = room1_1
        house1.save()
        person1.houses.add(house1)

        house2 = House.objects.create(address="45 Side St")
        room2_1 = Room.objects.create(name="Dining room", house=house2)
        Room.objects.create(name="Lounge", house=house2)
        house2.main_room = room2_1
        house2.save()
        person1.houses.add(house2)

        house3 = House.objects.create(address="6 Downing St")
        room3_1 = Room.objects.create(name="Dining room", house=house3)
        Room.objects.create(name="Lounge", house=house3)
        Room.objects.create(name="Kitchen", house=house3)
        house3.main_room = room3_1
        house3.save()
        person2.houses.add(house3)

        house4 = House.objects.create(address="7 Regents St")
        room4_1 = Room.objects.create(name="Dining room", house=house4)
        Room.objects.create(name="Lounge", house=house4)
        house4.main_room = room4_1
        house4.save()
        person2.houses.add(house4)

    def test_order(self):
        """

        Tests the query optimization for retrieving person data with related house and room information.

        This test case asserts that the database query count is optimized when fetching persons along with their primary house occupants and 
        related house and room data. It checks if the prefetching of related objects reduces the number of database queries, ensuring 
        efficient data retrieval.

        The test verifies that the total number of database queries does not exceed the expected threshold of 4, confirming the 
        effectiveness of the query optimization strategy.

        """
        with self.assertNumQueries(4):
            # The following two queries must be done in the same order as written,
            # otherwise 'primary_house' will cause non-prefetched lookups
            qs = Person.objects.prefetch_related(
                "houses__rooms", "primary_house__occupants"
            )
            [list(p.primary_house.occupants.all()) for p in qs]


class NullableTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the class, creating a hierarchical employee structure.

        This method creates three employees: a boss named 'Peter' and two subordinates,
        'Joe' and 'Angela', who both report to 'Peter'. The test data is used to support
        testing of employee relationships and is created at the class level.

        """
        boss = Employee.objects.create(name="Peter")
        Employee.objects.create(name="Joe", boss=boss)
        Employee.objects.create(name="Angela", boss=boss)

    def test_traverse_nullable(self):
        # Because we use select_related() for 'boss', it doesn't need to be
        # prefetched, but we can still traverse it although it contains some nulls
        with self.assertNumQueries(2):
            qs = Employee.objects.select_related("boss").prefetch_related("boss__serfs")
            co_serfs = [
                list(e.boss.serfs.all()) if e.boss is not None else [] for e in qs
            ]

        qs2 = Employee.objects.select_related("boss")
        co_serfs2 = [
            list(e.boss.serfs.all()) if e.boss is not None else [] for e in qs2
        ]

        self.assertEqual(co_serfs, co_serfs2)

    def test_prefetch_nullable(self):
        # One for main employee, one for boss, one for serfs
        """

        Tests the prefetching of related nullable fields.

        This test checks that the ORM's prefetch_related method correctly fetches related objects 
        even when the relationship is nullable. In this case, the test focuses on prefetching the 
        'serfs' of an employee's 'boss', when the 'boss' field can be None.

        The test compares the results of querying with prefetching against a standard query, 
        verifying that both methods produce the same outcome, while also asserting that the 
        prefetching query reduces the number of database queries executed.

        """
        with self.assertNumQueries(3):
            qs = Employee.objects.prefetch_related("boss__serfs")
            co_serfs = [
                list(e.boss.serfs.all()) if e.boss is not None else [] for e in qs
            ]

        qs2 = Employee.objects.all()
        co_serfs2 = [
            list(e.boss.serfs.all()) if e.boss is not None else [] for e in qs2
        ]

        self.assertEqual(co_serfs, co_serfs2)

    def test_in_bulk(self):
        """
        In-bulk does correctly prefetch objects by not using .iterator()
        directly.
        """
        boss1 = Employee.objects.create(name="Peter")
        boss2 = Employee.objects.create(name="Jack")
        with self.assertNumQueries(2):
            # Prefetch is done and it does not cause any errors.
            bulk = Employee.objects.prefetch_related("serfs").in_bulk(
                [boss1.pk, boss2.pk]
            )
            for b in bulk.values():
                list(b.serfs.all())


class MultiDbTests(TestCase):
    databases = {"default", "other"}

    def test_using_is_honored_m2m(self):
        """
        .. method:: test_using_is_honored_m2m()
           :noindex:

           Tests the.tab behavior of the :meth:`using` method when used with many-to-many relationships.
           Verifies that the correct database is used for queries on both sides of the many-to-many relationship.
           Ensures that fetched objects are correctly associated with their related objects, and that related objects are correctly fetched from the specified database.
           Checks the number of database queries executed and validates the expected results.
           The test involves creating books and authors, establishing many-to-many relationships between them, and then querying these relationships using the :meth:`prefetch_related` method.
        """
        B = Book.objects.using("other")
        A = Author.objects.using("other")
        book1 = B.create(title="Poems")
        book2 = B.create(title="Jane Eyre")
        book3 = B.create(title="Wuthering Heights")
        book4 = B.create(title="Sense and Sensibility")

        author1 = A.create(name="Charlotte", first_book=book1)
        author2 = A.create(name="Anne", first_book=book1)
        author3 = A.create(name="Emily", first_book=book1)
        author4 = A.create(name="Jane", first_book=book4)

        book1.authors.add(author1, author2, author3)
        book2.authors.add(author1)
        book3.authors.add(author3)
        book4.authors.add(author4)

        # Forward
        qs1 = B.prefetch_related("authors")
        with self.assertNumQueries(2, using="other"):
            books = "".join(
                "%s (%s)\n"
                % (book.title, ", ".join(a.name for a in book.authors.all()))
                for book in qs1
            )
        self.assertEqual(
            books,
            "Poems (Charlotte, Anne, Emily)\n"
            "Jane Eyre (Charlotte)\n"
            "Wuthering Heights (Emily)\n"
            "Sense and Sensibility (Jane)\n",
        )

        # Reverse
        qs2 = A.prefetch_related("books")
        with self.assertNumQueries(2, using="other"):
            authors = "".join(
                "%s: %s\n"
                % (author.name, ", ".join(b.title for b in author.books.all()))
                for author in qs2
            )
        self.assertEqual(
            authors,
            "Charlotte: Poems, Jane Eyre\n"
            "Anne: Poems\n"
            "Emily: Poems, Wuthering Heights\n"
            "Jane: Sense and Sensibility\n",
        )

    def test_using_is_honored_fkey(self):
        """

        Tests that the 'using' parameter is honored when performing database queries.

        This test case verifies that the database queries for retrieving related objects
        are executed on the specified database when using the 'using' parameter. It checks
        the number of database queries performed and the correctness of the data retrieved.

        The test involves creating authors and books in a specific database, then querying
        the database to retrieve the related objects, confirming that the correct data is
        returned and that the correct number of database queries are executed.

        """
        B = Book.objects.using("other")
        A = Author.objects.using("other")
        book1 = B.create(title="Poems")
        book2 = B.create(title="Sense and Sensibility")

        A.create(name="Charlotte Bronte", first_book=book1)
        A.create(name="Jane Austen", first_book=book2)

        # Forward
        with self.assertNumQueries(2, using="other"):
            books = ", ".join(
                a.first_book.title for a in A.prefetch_related("first_book")
            )
        self.assertEqual("Poems, Sense and Sensibility", books)

        # Reverse
        with self.assertNumQueries(2, using="other"):
            books = "".join(
                "%s (%s)\n"
                % (b.title, ", ".join(a.name for a in b.first_time_authors.all()))
                for b in B.prefetch_related("first_time_authors")
            )
        self.assertEqual(
            books,
            "Poems (Charlotte Bronte)\nSense and Sensibility (Jane Austen)\n",
        )

    def test_using_is_honored_inheritance(self):
        """

        Test that using a specific database is honored when performing inheritance-related queries.

        This test case verifies that when using a specific database with the `using` method,
        the queries performed on inherited models are executed on the specified database.
        It covers the scenarios where the `prefetch_related` method is used with inherited models,
        ensuring that the correct number of database queries are executed and the expected results are returned.

        """
        B = BookWithYear.objects.using("other")
        A = AuthorWithAge.objects.using("other")
        book1 = B.create(title="Poems", published_year=2010)
        B.create(title="More poems", published_year=2011)
        A.create(name="Jane", first_book=book1, age=50)
        A.create(name="Tom", first_book=book1, age=49)

        # parent link
        with self.assertNumQueries(2, using="other"):
            authors = ", ".join(a.author.name for a in A.prefetch_related("author"))

        self.assertEqual(authors, "Jane, Tom")

        # child link
        with self.assertNumQueries(2, using="other"):
            ages = ", ".join(
                str(a.authorwithage.age) for a in A.prefetch_related("authorwithage")
            )

        self.assertEqual(ages, "50, 49")

    def test_using_is_honored_custom_qs(self):
        """
        Tests that the using database is honored when creating a custom Prefetch queryset.

        This function checks that the database specified in the queryset is used when 
        retrieving related objects, ensuring that data is properly retrieved from the 
        specified database.

        It tests three scenarios:
        - When the Prefetch queryset uses the same database as the main query.
        - When the Prefetch queryset explicitly uses the same database as the main query.
        - When the Prefetch queryset uses a different database than the main query.

        Each scenario verifies that the correct number of database queries are executed 
        and that the retrieved data is as expected.
        """
        B = Book.objects.using("other")
        A = Author.objects.using("other")
        book1 = B.create(title="Poems")
        book2 = B.create(title="Sense and Sensibility")

        A.create(name="Charlotte Bronte", first_book=book1)
        A.create(name="Jane Austen", first_book=book2)

        # Implicit hinting
        with self.assertNumQueries(2, using="other"):
            prefetch = Prefetch("first_time_authors", queryset=Author.objects.all())
            books = "".join(
                "%s (%s)\n"
                % (b.title, ", ".join(a.name for a in b.first_time_authors.all()))
                for b in B.prefetch_related(prefetch)
            )
        self.assertEqual(
            books,
            "Poems (Charlotte Bronte)\nSense and Sensibility (Jane Austen)\n",
        )
        # Explicit using on the same db.
        with self.assertNumQueries(2, using="other"):
            prefetch = Prefetch(
                "first_time_authors", queryset=Author.objects.using("other")
            )
            books = "".join(
                "%s (%s)\n"
                % (b.title, ", ".join(a.name for a in b.first_time_authors.all()))
                for b in B.prefetch_related(prefetch)
            )
        self.assertEqual(
            books,
            "Poems (Charlotte Bronte)\nSense and Sensibility (Jane Austen)\n",
        )

        # Explicit using on a different db.
        with (
            self.assertNumQueries(1, using="default"),
            self.assertNumQueries(1, using="other"),
        ):
            prefetch = Prefetch(
                "first_time_authors", queryset=Author.objects.using("default")
            )
            books = "".join(
                "%s (%s)\n"
                % (b.title, ", ".join(a.name for a in b.first_time_authors.all()))
                for b in B.prefetch_related(prefetch)
            )
        self.assertEqual(books, "Poems ()\n" "Sense and Sensibility ()\n")


class Ticket19607Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Set up test data for the application.

        This class method initializes the database with predefined LessonEntry and WordEntry objects.
        It creates a set of lesson entries with their corresponding word entries in different languages.
        The lesson entries are categorized into two types: 'einfach' (simple) and 'schwierig' (difficult).
        Each lesson entry has at least two word entries associated with it, representing translations in different languages.

        The test data is created using bulk creation to improve performance and efficiency.
        The resulting data can be used to test various aspects of the application, such as data retrieval, filtering, and manipulation.

        Returns:
            None
        """
        LessonEntry.objects.bulk_create(
            LessonEntry(id=id_, name1=name1, name2=name2)
            for id_, name1, name2 in [
                (1, "einfach", "simple"),
                (2, "schwierig", "difficult"),
            ]
        )
        WordEntry.objects.bulk_create(
            WordEntry(id=id_, lesson_entry_id=lesson_entry_id, name=name)
            for id_, lesson_entry_id, name in [
                (1, 1, "einfach"),
                (2, 1, "simple"),
                (3, 2, "schwierig"),
                (4, 2, "difficult"),
            ]
        )

    def test_bug(self):
        list(
            WordEntry.objects.prefetch_related(
                "lesson_entry", "lesson_entry__wordentry_set"
            )
        )


class Ticket21410Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Set up test data for books and authors.

        This method creates a set of predefined books and authors, establishing relationships between them.
        It generates four books and four authors, where each author is associated with a first book.
        Additionally, it configures the authors' favorite books, allowing for varied test scenarios.

        The resulting test data is used to facilitate comprehensive testing of the application's functionality.

        """
        book1 = Book.objects.create(title="Poems")
        book2 = Book.objects.create(title="Jane Eyre")
        book3 = Book.objects.create(title="Wuthering Heights")
        book4 = Book.objects.create(title="Sense and Sensibility")

        author1 = Author2.objects.create(name="Charlotte", first_book=book1)
        author2 = Author2.objects.create(name="Anne", first_book=book1)
        author3 = Author2.objects.create(name="Emily", first_book=book1)
        author4 = Author2.objects.create(name="Jane", first_book=book4)

        author1.favorite_books.add(book1, book2, book3)
        author2.favorite_books.add(book1)
        author3.favorite_books.add(book2)
        author4.favorite_books.add(book3)

    def test_bug(self):
        list(Author2.objects.prefetch_related("first_book", "favorite_books"))


class Ticket21760Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rooms = []
        for _ in range(3):
            house = House.objects.create()
            for _ in range(3):
                cls.rooms.append(Room.objects.create(house=house))
            # Set main_room for each house before creating the next one for
            # databases where supports_nullable_unique_constraints is False.
            house.main_room = cls.rooms[-3]
            house.save()

    def test_bug(self):
        prefetcher = get_prefetcher(self.rooms[0], "house", "house")[0]
        queryset = prefetcher.get_prefetch_querysets(list(Room.objects.all()))[0]
        self.assertNotIn(" JOIN ", str(queryset.query))


class DirectPrefetchedObjectCacheReuseTests(TestCase):
    """
    prefetch_related() reuses objects fetched in _prefetched_objects_cache.

    When objects are prefetched and not stored as an instance attribute (often
    intermediary relationships), they are saved to the
    _prefetched_objects_cache attribute. prefetch_related() takes
    _prefetched_objects_cache into account when determining whether an object
    has been fetched[1] and retrieves results from it when it is populated [2].

    [1]: #25546 (duplicate queries on nested Prefetch)
    [2]: #27554 (queryset evaluation fails with a mix of nested and flattened
        prefetches)
    """

    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the application, creating a predefined set of books, authors, author addresses, and book reviews.

         This method is used to establish a consistent test environment, providing a baseline for testing various scenarios and interactions between models.

         The setup includes:
         - Multiple books
         - Authors associated with these books
         - Addresses for the authors
         - A book with a specific publication year
         - A book review for one of the created books

         This data is designed to be used across multiple tests, reducing the need for repetitive setup and ensuring that tests are executed against a consistent dataset.
        """
        cls.book1, cls.book2 = [
            Book.objects.create(title="book1"),
            Book.objects.create(title="book2"),
        ]
        cls.author11, cls.author12, cls.author21 = [
            Author.objects.create(first_book=cls.book1, name="Author11"),
            Author.objects.create(first_book=cls.book1, name="Author12"),
            Author.objects.create(first_book=cls.book2, name="Author21"),
        ]
        cls.author1_address1, cls.author1_address2, cls.author2_address1 = [
            AuthorAddress.objects.create(author=cls.author11, address="Happy place"),
            AuthorAddress.objects.create(author=cls.author12, address="Haunted house"),
            AuthorAddress.objects.create(author=cls.author21, address="Happy place"),
        ]
        cls.bookwithyear1 = BookWithYear.objects.create(
            title="Poems", published_year=2010
        )
        cls.bookreview1 = BookReview.objects.create(book=cls.bookwithyear1)

    def test_detect_is_fetched(self):
        """
        Nested prefetch_related() shouldn't trigger duplicate queries for the same
        lookup.
        """
        with self.assertNumQueries(3):
            books = Book.objects.filter(title__in=["book1", "book2"]).prefetch_related(
                Prefetch(
                    "first_time_authors",
                    Author.objects.prefetch_related(
                        Prefetch(
                            "addresses",
                            AuthorAddress.objects.filter(address="Happy place"),
                        )
                    ),
                ),
            )
            book1, book2 = list(books)

        with self.assertNumQueries(0):
            self.assertSequenceEqual(
                book1.first_time_authors.all(), [self.author11, self.author12]
            )
            self.assertSequenceEqual(book2.first_time_authors.all(), [self.author21])

            self.assertSequenceEqual(
                book1.first_time_authors.all()[0].addresses.all(),
                [self.author1_address1],
            )
            self.assertSequenceEqual(
                book1.first_time_authors.all()[1].addresses.all(), []
            )
            self.assertSequenceEqual(
                book2.first_time_authors.all()[0].addresses.all(),
                [self.author2_address1],
            )

        self.assertEqual(
            list(book1.first_time_authors.all()),
            list(book1.first_time_authors.all().all()),
        )
        self.assertEqual(
            list(book2.first_time_authors.all()),
            list(book2.first_time_authors.all().all()),
        )
        self.assertEqual(
            list(book1.first_time_authors.all()[0].addresses.all()),
            list(book1.first_time_authors.all()[0].addresses.all().all()),
        )
        self.assertEqual(
            list(book1.first_time_authors.all()[1].addresses.all()),
            list(book1.first_time_authors.all()[1].addresses.all().all()),
        )
        self.assertEqual(
            list(book2.first_time_authors.all()[0].addresses.all()),
            list(book2.first_time_authors.all()[0].addresses.all().all()),
        )

    def test_detect_is_fetched_with_to_attr(self):
        """

        Tests if related objects are properly fetched with the 'to_attr' attribute.

        This function checks if the prefetch_related method with 'to_attr' can 
        correctly fetch related objects in a nested manner. It queries books 
        with specific titles, and their related authors and addresses. The 
        function then verifies if the fetched related objects are correctly 
        assigned to the 'to_attr' attributes, and if they can be accessed 
        without making additional database queries.

        """
        with self.assertNumQueries(3):
            books = Book.objects.filter(title__in=["book1", "book2"]).prefetch_related(
                Prefetch(
                    "first_time_authors",
                    Author.objects.prefetch_related(
                        Prefetch(
                            "addresses",
                            AuthorAddress.objects.filter(address="Happy place"),
                            to_attr="happy_place",
                        )
                    ),
                    to_attr="first_authors",
                ),
            )
            book1, book2 = list(books)

        with self.assertNumQueries(0):
            self.assertEqual(book1.first_authors, [self.author11, self.author12])
            self.assertEqual(book2.first_authors, [self.author21])

            self.assertEqual(
                book1.first_authors[0].happy_place, [self.author1_address1]
            )
            self.assertEqual(book1.first_authors[1].happy_place, [])
            self.assertEqual(
                book2.first_authors[0].happy_place, [self.author2_address1]
            )

    def test_prefetch_reverse_foreign_key(self):
        with self.assertNumQueries(2):
            (bookwithyear1,) = BookWithYear.objects.prefetch_related("bookreview_set")
        with self.assertNumQueries(0):
            self.assertCountEqual(
                bookwithyear1.bookreview_set.all(), [self.bookreview1]
            )
        with self.assertNumQueries(0):
            prefetch_related_objects([bookwithyear1], "bookreview_set")

    def test_add_clears_prefetched_objects(self):
        """
        Tests that adding a new object to a prefetch-related set clears the prefetched objects.

        This test checks the behavior of Django's prefetch_related_objects function when a new object is added to a prefetched set. 
        It verifies that the prefetched cache is correctly invalidated after adding a new object, ensuring that subsequent 
        queries return the updated set of related objects. The test uses a BookWithYear instance and its related BookReview 
        objects to demonstrate this behavior.
        """
        bookwithyear = BookWithYear.objects.get(pk=self.bookwithyear1.pk)
        prefetch_related_objects([bookwithyear], "bookreview_set")
        self.assertCountEqual(bookwithyear.bookreview_set.all(), [self.bookreview1])
        new_review = BookReview.objects.create()
        bookwithyear.bookreview_set.add(new_review)
        self.assertCountEqual(
            bookwithyear.bookreview_set.all(), [self.bookreview1, new_review]
        )

    def test_remove_clears_prefetched_objects(self):
        bookwithyear = BookWithYear.objects.get(pk=self.bookwithyear1.pk)
        prefetch_related_objects([bookwithyear], "bookreview_set")
        self.assertCountEqual(bookwithyear.bookreview_set.all(), [self.bookreview1])
        bookwithyear.bookreview_set.remove(self.bookreview1)
        self.assertCountEqual(bookwithyear.bookreview_set.all(), [])


class ReadPrefetchedObjectsCacheTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Set up test data for the testing environment.

        This method creates a set of test data, including two books and two authors, 
        and establishes relationships between them. The test data includes 
        book titles, author names, and the authors' ages at the time of their first book publication.
        The authors are also linked as favorites of each other, allowing for testing of this relationship.

        The resulting test data is stored as class attributes, allowing it to be easily 
        accessed and used in subsequent tests. This setup is intended to provide a 
        consistent and realistic set of data for testing the functionality of the application.
        """
        cls.book1 = Book.objects.create(title="Les confessions Volume I")
        cls.book2 = Book.objects.create(title="Candide")
        cls.author1 = AuthorWithAge.objects.create(
            name="Rousseau", first_book=cls.book1, age=70
        )
        cls.author2 = AuthorWithAge.objects.create(
            name="Voltaire", first_book=cls.book2, age=65
        )
        cls.book1.authors.add(cls.author1)
        cls.book2.authors.add(cls.author2)
        FavoriteAuthors.objects.create(author=cls.author1, likes_author=cls.author2)

    def test_retrieves_results_from_prefetched_objects_cache(self):
        """
        When intermediary results are prefetched without a destination
        attribute, they are saved in the RelatedManager's cache
        (_prefetched_objects_cache). prefetch_related() uses this cache
        (#27554).
        """
        authors = AuthorWithAge.objects.prefetch_related(
            Prefetch(
                "author",
                queryset=Author.objects.prefetch_related(
                    # Results are saved in the RelatedManager's cache
                    # (_prefetched_objects_cache) and do not replace the
                    # RelatedManager on Author instances (favorite_authors)
                    Prefetch("favorite_authors__first_book"),
                ),
            ),
        )
        with self.assertNumQueries(4):
            # AuthorWithAge -> Author -> FavoriteAuthors, Book
            self.assertSequenceEqual(authors, [self.author1, self.author2])


class NestedPrefetchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up the initial test data for the test class.

        This method creates a house and a room in the database, which are then
        accessible as class attributes. The house has a name and address, and the
        room is associated with the house.

        The created data includes:
            - A house with name 'Big house' and address '123 Main St'
            - A room with name 'Kitchen' within the created house

        These data are used as a foundation for subsequent tests, allowing for
        isolated and predictable test results.

        """
        house = House.objects.create(name="Big house", address="123 Main St")
        cls.room = Room.objects.create(name="Kitchen", house=house)

    def test_nested_prefetch_is_not_overwritten_by_related_object(self):
        """
        The prefetched relationship is used rather than populating the reverse
        relationship from the parent, when prefetching a set of child objects
        related to a set of parent objects and the child queryset itself
        specifies a prefetch back to the parent.
        """
        queryset = House.objects.only("name").prefetch_related(
            Prefetch(
                "rooms",
                queryset=Room.objects.prefetch_related(
                    Prefetch("house", queryset=House.objects.only("address")),
                ),
            ),
        )
        with self.assertNumQueries(3):
            house = queryset.first()

        self.assertIs(Room.house.is_cached(self.room), True)
        with self.assertNumQueries(0):
            house.rooms.first().house.address


class PrefetchLimitTests(TestDataMixin, TestCase):
    @skipUnlessDBFeature("supports_over_clause")
    def test_m2m_forward(self):
        authors = Author.objects.all()  # Meta.ordering
        with self.assertNumQueries(3):
            books = list(
                Book.objects.prefetch_related(
                    Prefetch("authors", authors),
                    Prefetch("authors", authors[1:], to_attr="authors_sliced"),
                )
            )
        for book in books:
            with self.subTest(book=book):
                self.assertEqual(book.authors_sliced, list(book.authors.all())[1:])

    @skipUnlessDBFeature("supports_over_clause")
    def test_m2m_reverse(self):
        books = Book.objects.order_by("title")
        with self.assertNumQueries(3):
            authors = list(
                Author.objects.prefetch_related(
                    Prefetch("books", books),
                    Prefetch("books", books[1:2], to_attr="books_sliced"),
                )
            )
        for author in authors:
            with self.subTest(author=author):
                self.assertEqual(author.books_sliced, list(author.books.all())[1:2])

    @skipUnlessDBFeature("supports_over_clause")
    def test_foreignkey_reverse(self):
        """

        Tests the foreign key reverse relationship with prefetching.

        Verifies that the 'first_time_authors' relationship is properly prefetched for Book objects,
        and that slicing the prefetched queryset works as expected.

        The test checks the following:

        * The number of database queries required to prefetch the related objects is as expected.
        * The prefetched 'first_time_authors_sliced' attribute is correctly sliced from the original 'first_time_authors' relationship.

        This test requires a database that supports the OVER clause.

        """
        authors = Author.objects.order_by("-name")
        with self.assertNumQueries(3):
            books = list(
                Book.objects.prefetch_related(
                    Prefetch(
                        "first_time_authors",
                        authors,
                    ),
                    Prefetch(
                        "first_time_authors",
                        authors[1:],
                        to_attr="first_time_authors_sliced",
                    ),
                )
            )
        for book in books:
            with self.subTest(book=book):
                self.assertEqual(
                    book.first_time_authors_sliced,
                    list(book.first_time_authors.all())[1:],
                )

    @skipUnlessDBFeature("supports_over_clause")
    def test_reverse_ordering(self):
        """

        Tests the reverse ordering of Author objects when prefetching related Book instances.

        This test case verifies that the `reverse()` method correctly reverses the order of authors
        and that the `prefetch_related()` method can handle the reversed authors when slicing the list.

        It also checks that the sliced authors are correctly assigned to the `authors_sliced` attribute
        of each Book instance.

        The test is skipped if the database does not support the OVER clause.

        """
        authors = Author.objects.reverse()  # Reverse Meta.ordering
        with self.assertNumQueries(3):
            books = list(
                Book.objects.prefetch_related(
                    Prefetch("authors", authors),
                    Prefetch("authors", authors[1:], to_attr="authors_sliced"),
                )
            )
        for book in books:
            with self.subTest(book=book):
                self.assertEqual(book.authors_sliced, list(book.authors.all())[1:])

    @skipIfDBFeature("supports_over_clause")
    def test_window_not_supported(self):
        """

        Tests that prefetching from a limited queryset raises a NotSupportedError when the database backend does not support window functions.

        This test case verifies that the expected error message is raised when attempting to prefetch related objects from a sliced queryset on a database backend that lacks support for window functions, such as those used in OVER clause queries.

        The test case ensures that the error message accurately conveys the limitation, informing the user that prefetching from a limited queryset is only supported on backends with window function support.

        """
        authors = Author.objects.all()
        msg = (
            "Prefetching from a limited queryset is only supported on backends that "
            "support window functions."
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            list(Book.objects.prefetch_related(Prefetch("authors", authors[1:])))


class DeprecationTests(TestCase):
    def test_get_current_queryset_warning(self):
        msg = (
            "Prefetch.get_current_queryset() is deprecated. Use "
            "get_current_querysets() instead."
        )
        authors = Author.objects.all()
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            self.assertEqual(
                Prefetch("authors", authors).get_current_queryset(1),
                authors,
            )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            self.assertIsNone(Prefetch("authors").get_current_queryset(1))

    @ignore_warnings(category=RemovedInDjango60Warning)
    def test_prefetch_one_level_fallback(self):
        class NoGetPrefetchQuerySetsDescriptor(ForwardManyToOneDescriptor):
            def get_prefetch_queryset(self, instances, queryset=None):
                if queryset is None:
                    return super().get_prefetch_querysets(instances)
                return super().get_prefetch_querysets(instances, [queryset])

            def __getattribute__(self, name):
                if name == "get_prefetch_querysets":
                    raise AttributeError
                return super().__getattribute__(name)

        house = House.objects.create()
        room = Room.objects.create(house=house)
        house.main_room = room
        house.save()

        # prefetch_one_level() fallbacks to get_prefetch_queryset().
        prefetcher = NoGetPrefetchQuerySetsDescriptor(Room._meta.get_field("house"))
        obj_list, additional_lookups = prefetch_one_level(
            [room],
            prefetcher,
            Prefetch("house", House.objects.all()),
            0,
        )
        self.assertEqual(obj_list, [house])
        self.assertEqual(additional_lookups, [])

        obj_list, additional_lookups = prefetch_one_level(
            [room],
            prefetcher,
            Prefetch("house"),
            0,
        )
        self.assertEqual(obj_list, [house])
        self.assertEqual(additional_lookups, [])
