from django.db.models import Prefetch, prefetch_related_objects
from django.test import TestCase

from .models import Author, Book, House, Reader, Room


class PrefetchRelatedObjectsTests(TestCase):
    """
    Since prefetch_related_objects() is just the inner part of
    prefetch_related(), only do basic tests to ensure its API hasn't changed.
    """

    @classmethod
    def setUpTestData(cls):
        """

        Set up test data for the application.

        This class method creates a set of pre-defined books, authors, readers, houses, and rooms,
        and establishes relationships between them. It sets up a basic data structure for testing,
        including multiple books with various authors, readers who have read certain books, and
        houses with rooms. The test data is stored as class attributes for easy access in tests.

        """
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

        cls.house1 = House.objects.create(name="b1", address="1")
        cls.house2 = House.objects.create(name="b2", address="2")

        cls.room1 = Room.objects.create(name="a1", house=cls.house1)
        cls.room2 = Room.objects.create(name="a2", house=cls.house2)

        cls.house1.main_room = cls.room1
        cls.house1.save()
        cls.house2.main_room = cls.room2
        cls.house2.save()

    def test_unknown(self):
        """
        Tests that an AttributeError is raised when attempting to prefetch a related object 
        with an unknown attribute.

        This test case verifies the behavior of the prefetch_related_objects function when 
        given an invalid attribute name, ensuring that it correctly raises an exception 
        instead of causing unexpected behavior or errors. It helps maintain the robustness 
        and reliability of the related object prefetching mechanism by checking its error 
        handling capabilities.
        """
        book1 = Book.objects.get(id=self.book1.id)
        with self.assertRaises(AttributeError):
            prefetch_related_objects([book1], "unknown_attribute")

    def test_m2m_forward(self):
        book1 = Book.objects.get(id=self.book1.id)
        with self.assertNumQueries(1):
            prefetch_related_objects([book1], "authors")

        with self.assertNumQueries(0):
            self.assertCountEqual(
                book1.authors.all(), [self.author1, self.author2, self.author3]
            )

    def test_m2m_reverse(self):
        author1 = Author.objects.get(id=self.author1.id)
        with self.assertNumQueries(1):
            prefetch_related_objects([author1], "books")

        with self.assertNumQueries(0):
            self.assertCountEqual(author1.books.all(), [self.book1, self.book2])

    def test_foreignkey_forward(self):
        """

        Tests the behavior of the prefetch_related_objects function when used with a ForeignKey field.

        This function verifies that the prefetch_related_objects function correctly fetches 
        related objects in a single query, without introducing an ORDER BY clause in the 
        underlying SQL query. It also checks that accessing the prefetched related objects 
        does not result in additional database queries.

        """
        authors = list(Author.objects.all())
        with self.assertNumQueries(1) as ctx:
            prefetch_related_objects(authors, "first_book")
        self.assertNotIn("ORDER BY", ctx.captured_queries[0]["sql"])

        with self.assertNumQueries(0):
            [author.first_book for author in authors]

        authors = list(Author.objects.all())
        with self.assertNumQueries(1) as ctx:
            prefetch_related_objects(
                authors,
                Prefetch("first_book", queryset=Book.objects.order_by("-title")),
            )
        self.assertNotIn("ORDER BY", ctx.captured_queries[0]["sql"])

    def test_foreignkey_reverse(self):
        books = list(Book.objects.all())
        with self.assertNumQueries(1) as ctx:
            prefetch_related_objects(books, "first_time_authors")
        self.assertIn("ORDER BY", ctx.captured_queries[0]["sql"])

        with self.assertNumQueries(0):
            [list(book.first_time_authors.all()) for book in books]

        books = list(Book.objects.all())
        with self.assertNumQueries(1) as ctx:
            prefetch_related_objects(
                books,
                Prefetch(
                    "first_time_authors",
                    queryset=Author.objects.order_by("-name"),
                ),
            )
        self.assertIn("ORDER BY", ctx.captured_queries[0]["sql"])

    def test_one_to_one_forward(self):
        """

        Tests that one-to-one relationships are correctly prefetched.

        This test case verifies the behavior of the prefetch_related_objects function
        when dealing with one-to-one relationships. It checks that the prefetching is
        done efficiently, with the correct number of database queries, and that the
        prefetched objects can be accessed without additional queries.

        Specifically, it tests two scenarios:

        * Prefetching a one-to-one relationship without any ordering
        * Prefetching a one-to-one relationship with a custom ordering, ensuring that
          the ordering does not affect the prefetching query.

        """
        houses = list(House.objects.all())
        with self.assertNumQueries(1) as ctx:
            prefetch_related_objects(houses, "main_room")
        self.assertNotIn("ORDER BY", ctx.captured_queries[0]["sql"])

        with self.assertNumQueries(0):
            [house.main_room for house in houses]

        houses = list(House.objects.all())
        with self.assertNumQueries(1) as ctx:
            prefetch_related_objects(
                houses,
                Prefetch("main_room", queryset=Room.objects.order_by("-name")),
            )
        self.assertNotIn("ORDER BY", ctx.captured_queries[0]["sql"])

    def test_one_to_one_reverse(self):
        rooms = list(Room.objects.all())
        with self.assertNumQueries(1) as ctx:
            prefetch_related_objects(rooms, "main_room_of")
        self.assertNotIn("ORDER BY", ctx.captured_queries[0]["sql"])

        with self.assertNumQueries(0):
            [room.main_room_of for room in rooms]

        rooms = list(Room.objects.all())
        with self.assertNumQueries(1) as ctx:
            prefetch_related_objects(
                rooms,
                Prefetch("main_room_of", queryset=House.objects.order_by("-name")),
            )
        self.assertNotIn("ORDER BY", ctx.captured_queries[0]["sql"])

    def test_m2m_then_m2m(self):
        """A m2m can be followed through another m2m."""
        authors = list(Author.objects.all())
        with self.assertNumQueries(2):
            prefetch_related_objects(authors, "books__read_by")

        with self.assertNumQueries(0):
            self.assertEqual(
                [
                    [[str(r) for r in b.read_by.all()] for b in a.books.all()]
                    for a in authors
                ],
                [
                    [["Amy"], ["Belinda"]],  # Charlotte - Poems, Jane Eyre
                    [["Amy"]],  # Anne - Poems
                    [["Amy"], []],  # Emily - Poems, Wuthering Heights
                    [["Amy", "Belinda"]],  # Jane - Sense and Sense
                ],
            )

    def test_prefetch_object(self):
        """
        Tests the efficiency of prefetching related objects.

        This test verifies that using the prefetch_related_objects function with a Prefetch
        object reduces the number of database queries required to access related objects.
        In this case, it checks that the 'authors' of a Book object can be prefetched with a single query,
        and subsequently accessed without triggering any additional queries.

        The test ensures that the prefetched related objects are correctly assigned to the
        Book instance, and that their count matches the expected number of authors.

        """
        book1 = Book.objects.get(id=self.book1.id)
        with self.assertNumQueries(1):
            prefetch_related_objects([book1], Prefetch("authors"))

        with self.assertNumQueries(0):
            self.assertCountEqual(
                book1.authors.all(), [self.author1, self.author2, self.author3]
            )

    def test_prefetch_object_twice(self):
        """

        Test that prefetching the same related object multiple times does not result in additional database queries.

        This test case verifies the optimization of the prefetch_related_objects function when 
        it encounters the same related object more than once. Specifically, it checks that 
        prefetching the 'authors' relation for two Book objects does not result in more than 
        two database queries and that the prefetched objects are correctly associated with 
        their respective Book instances.

        """
        book1 = Book.objects.get(id=self.book1.id)
        book2 = Book.objects.get(id=self.book2.id)
        with self.assertNumQueries(1):
            prefetch_related_objects([book1], Prefetch("authors"))
        with self.assertNumQueries(1):
            prefetch_related_objects([book1, book2], Prefetch("authors"))
        with self.assertNumQueries(0):
            self.assertCountEqual(book2.authors.all(), [self.author1])

    def test_prefetch_object_to_attr(self):
        """
        Tests that prefetching objects to a custom attribute works as expected.

        This test case verifies that the prefetch_related_objects function can efficiently
        fetch related objects and store them in a custom attribute. It checks that the
        database query count is minimized by using the prefetch functionality.

        The test focuses on the 'authors' relationship of a 'Book' object, ensuring that
        the related authors are correctly fetched and stored in the 'the_authors' attribute.
        It then asserts that the prefetched authors match the expected set of authors.

        By using this test, developers can ensure that their code is using the prefetch
        functionality correctly, which can lead to improved performance by reducing the
        number of database queries needed to fetch related objects.
        """
        book1 = Book.objects.get(id=self.book1.id)
        with self.assertNumQueries(1):
            prefetch_related_objects(
                [book1], Prefetch("authors", to_attr="the_authors")
            )

        with self.assertNumQueries(0):
            self.assertCountEqual(
                book1.the_authors, [self.author1, self.author2, self.author3]
            )

    def test_prefetch_object_to_attr_twice(self):
        """
        Tests the behavior of prefetching related objects to a custom attribute twice.

        Verifies that when prefetching related objects to a custom attribute for the first time, 
        it results in a single database query. Subsequent prefetching of the same relation to 
        the same attribute for a single or multiple objects does not fetch the data again from 
        the database, instead reusing the already prefetched data, thus resulting in no additional 
        queries. The test also checks that the prefetched data is correctly assigned to the 
        custom attribute and has the expected contents.
        """
        book1 = Book.objects.get(id=self.book1.id)
        book2 = Book.objects.get(id=self.book2.id)
        with self.assertNumQueries(1):
            prefetch_related_objects(
                [book1],
                Prefetch("authors", to_attr="the_authors"),
            )
        with self.assertNumQueries(1):
            prefetch_related_objects(
                [book1, book2],
                Prefetch("authors", to_attr="the_authors"),
            )
        with self.assertNumQueries(0):
            self.assertCountEqual(book2.the_authors, [self.author1])

    def test_prefetch_queryset(self):
        book1 = Book.objects.get(id=self.book1.id)
        with self.assertNumQueries(1):
            prefetch_related_objects(
                [book1],
                Prefetch(
                    "authors",
                    queryset=Author.objects.filter(
                        id__in=[self.author1.id, self.author2.id]
                    ),
                ),
            )

        with self.assertNumQueries(0):
            self.assertCountEqual(book1.authors.all(), [self.author1, self.author2])
