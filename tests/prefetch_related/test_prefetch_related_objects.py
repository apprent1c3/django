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
        Sets up test data for the application, creating instances of Book, Author, Reader, House, and Room models, 
        and establishing relationships between them to serve as a foundation for testing scenarios.
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
        book1 = Book.objects.get(id=self.book1.id)
        with self.assertRaises(AttributeError):
            prefetch_related_objects([book1], "unknown_attribute")

    def test_m2m_forward(self):
        """
        Tests the efficiency of the many-to-many relationship prefetching for a Book's authors, ensuring it only requires one database query.
        """
        book1 = Book.objects.get(id=self.book1.id)
        with self.assertNumQueries(1):
            prefetch_related_objects([book1], "authors")

        with self.assertNumQueries(0):
            self.assertCountEqual(
                book1.authors.all(), [self.author1, self.author2, self.author3]
            )

    def test_m2m_reverse(self):
        """
        Tests the performance of Django's select_related and prefetch_related on many-to-many relationships by checking if the related objects are correctly prefetched in a single database query.\"\"\"


        Alternatively, a shorter version: 
        \"\"\"Tests prefetching of many-to-many relationships in a single database query.
        """
        author1 = Author.objects.get(id=self.author1.id)
        with self.assertNumQueries(1):
            prefetch_related_objects([author1], "books")

        with self.assertNumQueries(0):
            self.assertCountEqual(author1.books.all(), [self.book1, self.book2])

    def test_foreignkey_forward(self):
        """
        Tests the behavior of prefetching foreign key-related objects, verifying that the related objects are fetched in a single query without applying any ordering.
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
        """
        Tests the behavior of prefetching related objects through foreign keys, 
        ensuring that the correct number of database queries are made and 
        that the prefetching respects the specified ordering of related objects.
        """
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
        Tests one-to-one prefetching behavior, verifying that the related objects are fetched in a single query without additional ordering, and that accessing the prefetched relationships does not trigger additional queries.
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
        """
        Tests the efficiency of prefetching related objects in a one-to-one relationship, verifying that a single database query is executed and that the prefetched objects do not include an ORDER BY clause in their SQL query, even when an ordered queryset is provided.
        """
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
        Tests that a related object is correctly prefetched, reducing database queries.
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
        Tests that prefetching the same related object multiple times only queries the database once.
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
        Tests that prefetching an object to an attribute works as expected by verifying that the object's attribute is populated with the expected related objects after a single database query.
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
        Test that prefetching an object to an attribute twice still only results in a single query.

        Verifies that the second prefetch operation for the same attribute does not issue an additional database query.
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
        """
        Tests that prefetching a queryset reduces the number of database queries when accessing related objects.
        """
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
