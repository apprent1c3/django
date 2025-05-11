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
        Sets up test data for the application, creating instances of books, authors, readers, houses, and rooms, and establishing relationships between them, to facilitate testing of the application's functionality.
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

        Tests the forward many-to-many relationship between a Book and its Authors, 
        verifying that the authors are correctly prefetched in a single database query.

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
        Tests the many-to-many reverse relationship between an Author and their associated Books, 
        ensuring that the related objects are properly prefetched in a single database query.
        """
        author1 = Author.objects.get(id=self.author1.id)
        with self.assertNumQueries(1):
            prefetch_related_objects([author1], "books")

        with self.assertNumQueries(0):
            self.assertCountEqual(author1.books.all(), [self.book1, self.book2])

    def test_foreignkey_forward(self):
        """
        Checks that prefetching foreign key fields using `prefetch_related_objects` works correctly and efficiently, 
        especially when dealing with related objects ordered by a specific attribute. 
        Verifies that the related objects are fetched in a single database query and that subsequent accesses do not trigger additional queries.
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
        Tests the prefetching of related objects using foreign key reverse relationships, 
        verifying that it reduces database queries and allows custom ordering of the prefetched objects.
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
        Tests that the one-to-one relationship between House and Room is properly prefetched, 
        without introducing unnecessary ORDER BY clauses in the resulting SQL query, 
        and that prefetched objects can be accessed without additional database queries.
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
        Verifies the correctness of one-to-one reverse relationship prefetching.

        This test checks that prefetching a one-to-one reverse relationship does not result
        in an additional 'ORDER BY' query and that subsequent access to the prefetched
        objects does not trigger any additional queries.

        It also ensures that specifying an ordered queryset for the prefetch does not
        include the 'ORDER BY' clause in the initial prefetch query.
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
        """
        Tests the ability to prefetch objects through a many-to-many relationship followed by another many-to-many relationship, verifying that the data is retrieved efficiently and the expected results are returned.
        """
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
        Tests the prefetching of related objects for a Book instance, verifying that it reduces the number of database queries needed to access the related authors.
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
        Tests that prefetching related objects twice does not result in unnecessary database queries, ensuring efficient data retrieval.
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
        Tests that prefetching an object to a custom attribute works correctly, ensuring that the related objects are loaded in a single query and can be accessed without triggering additional database queries.
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
        Tests that prefetching the same related object to an attribute twice results in efficient database queries and correctly populates the attribute on multiple objects.
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
        Tests the performance optimization of prefetching related objects, specifically authors for a given book, to ensure that it reduces the number of database queries.
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
