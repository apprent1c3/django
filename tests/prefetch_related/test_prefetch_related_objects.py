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
        Tests that prefetching related objects with an unknown attribute raises an AttributeError.

        This test case ensures that attempting to prefetch related objects using an attribute
        that does not exist on the model results in an appropriate error being raised.

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
        Tests the functionality of prefetching related objects through a foreign key reverse relationship.

        This test ensures that related objects can be prefetched in a single database query,
        and that the prefetched objects can be accessed without triggering additional queries.
        It also verifies that the prefetched objects are ordered according to the specified queryset.

        The test covers two scenarios: 
        1. Prefetching related objects using a string lookup, 
        2. Prefetching related objects using a Prefetch object with a custom queryset.

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

        Test that one-to-one relationships are correctly prefetched.

        This test verifies the functionality of prefetching one-to-one relationships using 
        :func:`~django.db.models.prefetch_related_objects`. It checks that the relationship 
        is fetched in a single database query and that subsequent accesses to the 
        relationship do not result in additional queries. The test also confirms that any 
        order specified on the related model's queryset does not affect the prefetch 
        query.

        The test uses the :class:`~House` model and its one-to-one relationship with 
        :class:`~Room`, defined as :attr:`~House.main_room`.

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
        Tests the one-to-one reverse prefetching functionality.

        This test case verifies that Django's prefetch_related_objects function 
        correctly prefetches one-to-one reverse relationships in a single database query.
        It checks that no ORDER BY statement is included in the query when prefetching 
        without a specified queryset, and also when prefetching with a queryset 
        that includes an order_by statement. Additionally, it ensures that accessing 
        the prefetched objects does not trigger any additional database queries.
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
        book1 = Book.objects.get(id=self.book1.id)
        with self.assertNumQueries(1):
            prefetch_related_objects([book1], Prefetch("authors"))

        with self.assertNumQueries(0):
            self.assertCountEqual(
                book1.authors.all(), [self.author1, self.author2, self.author3]
            )

    def test_prefetch_object_twice(self):
        """

        Tests the prefetching of related objects to ensure it is only executed when necessary.

        Verifies that the database query count remains optimal when fetching related objects
        multiple times, including during prefetching of objects individually or in batches.

        In particular, this test case confirms that:

        - Prefetching a single object does not trigger unnecessary database queries.
        - Prefetching multiple objects at once also maintains optimal query count.
        - Repeatedly accessing the prefetched related objects does not result in additional queries.

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
