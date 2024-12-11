from django.test import TestCase

from .models import Article, Car, Driver, Reporter


class ManyToOneNullTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a Reporter.
        """
        Sets up test data for the application, creating a set of reporters and associated articles.

        This method initializes the database with a predefined set of objects, including reporters and their corresponding articles.
        It creates multiple reporters with varying numbers of articles, as well as articles with and without assigned reporters.
        The resulting test data provides a foundation for testing the relationships and functionality of the Reporter and Article models.

        """
        cls.r = Reporter(name="John Smith")
        cls.r.save()
        # Create an Article.
        cls.a = Article(headline="First", reporter=cls.r)
        cls.a.save()
        # Create an Article via the Reporter object.
        cls.a2 = cls.r.article_set.create(headline="Second")
        # Create an Article with no Reporter by passing "reporter=None".
        cls.a3 = Article(headline="Third", reporter=None)
        cls.a3.save()
        # Create another article and reporter
        cls.r2 = Reporter(name="Paul Jones")
        cls.r2.save()
        cls.a4 = cls.r2.article_set.create(headline="Fourth")

    def test_get_related(self):
        self.assertEqual(self.a.reporter.id, self.r.id)
        # Article objects have access to their related Reporter objects.
        r = self.a.reporter
        self.assertEqual(r.id, self.r.id)

    def test_created_via_related_set(self):
        self.assertEqual(self.a2.reporter.id, self.r.id)

    def test_related_set(self):
        # Reporter objects have access to their related Article objects.
        self.assertSequenceEqual(self.r.article_set.all(), [self.a, self.a2])
        self.assertSequenceEqual(
            self.r.article_set.filter(headline__startswith="Fir"), [self.a]
        )
        self.assertEqual(self.r.article_set.count(), 2)

    def test_created_without_related(self):
        """

        Verify the behavior of an Article instance created without a related Reporter.

        This test case checks that an Article object created without a Reporter has its
        'reporter' attribute set to None and that attempting to access the 'id' attribute
        of this None object raises an AttributeError. It also verifies that the Article
        can be successfully added to and removed from a Reporter's article set, and that
        the Article's 'reporter' attribute is updated accordingly.

        Additionally, it ensures that the Article is correctly filtered in database
        queries when searching for articles with a null or None reporter.

        """
        self.assertIsNone(self.a3.reporter)
        # Need to reget a3 to refresh the cache
        a3 = Article.objects.get(pk=self.a3.pk)
        with self.assertRaises(AttributeError):
            getattr(a3.reporter, "id")
        # Accessing an article's 'reporter' attribute returns None
        # if the reporter is set to None.
        self.assertIsNone(a3.reporter)
        # To retrieve the articles with no reporters set, use "reporter__isnull=True".
        self.assertSequenceEqual(
            Article.objects.filter(reporter__isnull=True), [self.a3]
        )
        # We can achieve the same thing by filtering for the case where the
        # reporter is None.
        self.assertSequenceEqual(Article.objects.filter(reporter=None), [self.a3])
        # Set the reporter for the Third article
        self.assertSequenceEqual(self.r.article_set.all(), [self.a, self.a2])
        self.r.article_set.add(a3)
        self.assertSequenceEqual(
            self.r.article_set.all(),
            [self.a, self.a2, self.a3],
        )
        # Remove an article from the set, and check that it was removed.
        self.r.article_set.remove(a3)
        self.assertSequenceEqual(self.r.article_set.all(), [self.a, self.a2])
        self.assertSequenceEqual(
            Article.objects.filter(reporter__isnull=True), [self.a3]
        )

    def test_remove_from_wrong_set(self):
        """
        Tests that attempting to remove an article from a reporter's set when the article is actually associated with a different reporter raises a Reporter.DoesNotExist exception.

        The test verifies that:
        - The initial state of the reporter and article associations is correct.
        - Removing the article from the wrong reporter's set results in the expected exception.
        - The article's association with the correct reporter remains unchanged after the exception is raised.
        """
        self.assertSequenceEqual(self.r2.article_set.all(), [self.a4])
        # Try to remove a4 from a set it does not belong to
        with self.assertRaises(Reporter.DoesNotExist):
            self.r.article_set.remove(self.a4)
        self.assertSequenceEqual(self.r2.article_set.all(), [self.a4])

    def test_set(self):
        # Use manager.set() to allocate ForeignKey. Null is legal, so existing
        # members of the set that are not in the assignment set are set to null.
        """

        Tests the functionality of the article set on a reporter object.

        This test ensures that the article set can be successfully updated and cleared,
        and that the changes are reflected in the object's state. It also verifies that
        the articles that are removed from the set are properly reset to have no reporter.

        Specifically, this test covers the following scenarios:
        - Setting a new list of articles for the reporter
        - Clearing the existing set of articles and setting a new list
        - Clearing the entire set of articles
        - Verifying that articles removed from the set have their reporter field reset

        """
        self.r2.article_set.set([self.a2, self.a3])
        self.assertSequenceEqual(self.r2.article_set.all(), [self.a2, self.a3])
        # Use manager.set(clear=True)
        self.r2.article_set.set([self.a3, self.a4], clear=True)
        self.assertSequenceEqual(self.r2.article_set.all(), [self.a4, self.a3])
        # Clear the rest of the set
        self.r2.article_set.set([])
        self.assertSequenceEqual(self.r2.article_set.all(), [])
        self.assertSequenceEqual(
            Article.objects.filter(reporter__isnull=True),
            [self.a4, self.a2, self.a3],
        )

    def test_set_clear_non_bulk(self):
        # 2 queries for clear(), 1 for add(), and 1 to select objects.
        """
        Tests the set method of the article set with non-bulk operations and clearing of existing data.

        This test ensures that the set method correctly clears the existing data and then adds the specified article to the set, 
        while also verifying that the correct number of database queries are executed.

        """
        with self.assertNumQueries(4):
            self.r.article_set.set([self.a], bulk=False, clear=True)

    def test_assign_clear_related_set(self):
        # Use descriptor assignment to allocate ForeignKey. Null is legal, so
        # existing members of the set that are not in the assignment set are
        # set to null.
        self.r2.article_set.set([self.a2, self.a3])
        self.assertSequenceEqual(self.r2.article_set.all(), [self.a2, self.a3])
        # Clear the rest of the set
        self.r.article_set.clear()
        self.assertSequenceEqual(self.r.article_set.all(), [])
        self.assertSequenceEqual(
            Article.objects.filter(reporter__isnull=True),
            [self.a, self.a4],
        )

    def test_assign_with_queryset(self):
        # Querysets used in reverse FK assignments are pre-evaluated
        # so their value isn't affected by the clearing operation in
        # RelatedManager.set() (#19816).
        self.r2.article_set.set([self.a2, self.a3])

        qs = self.r2.article_set.filter(headline="Second")
        self.r2.article_set.set(qs)

        self.assertEqual(1, self.r2.article_set.count())
        self.assertEqual(1, qs.count())

    def test_add_efficiency(self):
        """
        Tests the efficiency of adding multiple articles to a reporter's article set.

        This test checks that adding multiple articles to a reporter's article set can be done in a single database query, 
        thus ensuring efficient database usage. It verifies that the operation does not result in excessive queries 
        and that the correct number of articles are added to the reporter's set.
        """
        r = Reporter.objects.create()
        articles = []
        for _ in range(3):
            articles.append(Article.objects.create())
        with self.assertNumQueries(1):
            r.article_set.add(*articles)
        self.assertEqual(r.article_set.count(), 3)

    def test_clear_efficiency(self):
        """
        Tests the efficiency of clearing a set of associated articles for a reporter.

        Verifies that the clear operation is performed in a single database query, 
        regardless of the number of articles in the set. This ensures that the 
        clear operation does not incur additional database overhead as the size of 
        the article set grows. The test also confirms that after clearing, the 
        article set is empty and has a count of 0. 
        """
        r = Reporter.objects.create()
        for _ in range(3):
            r.article_set.create()
        with self.assertNumQueries(1):
            r.article_set.clear()
        self.assertEqual(r.article_set.count(), 0)

    def test_related_null_to_field(self):
        """
        Tests that a newly created Driver instance has no associated Car, and that a newly created Car instance has no associated Drivers, with no additional database queries when accessing the relationship
        """
        c1 = Car.objects.create()
        d1 = Driver.objects.create()
        self.assertIs(d1.car, None)
        with self.assertNumQueries(0):
            self.assertEqual(list(c1.drivers.all()), [])

    def test_unsaved(self):
        """
        Tests that a ValueError is raised when trying to access related objects on an unsaved 'Car' instance.

         Raises a ValueError with a message indicating that the 'Car' instance needs a primary key value before the relationship can be used.

         This test ensures that the relationship between 'Car' and its related objects (in this case, 'drivers') cannot be accessed until the 'Car' instance has been saved and has a primary key value.
        """
        msg = (
            "'Car' instance needs to have a primary key value before this relationship "
            "can be used."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Car(make="Ford").drivers.all()

    def test_related_null_to_field_related_managers(self):
        """

        Test that attempting to use a related manager on an instance with a null related field raises a ValueError.

        This test case ensures that the related manager for an instance with a null related field cannot be used to add, create, get or create, update or create, remove, clear, or set related objects. It verifies that a ValueError is raised with a descriptive message when such operations are attempted, and that no queries are executed when attempting to count the number of related objects.

        """
        car = Car.objects.create(make=None)
        driver = Driver.objects.create()
        msg = (
            f'"{car!r}" needs to have a value for field "make" before this '
            f"relationship can be used."
        )
        with self.assertRaisesMessage(ValueError, msg):
            car.drivers.add(driver)
        with self.assertRaisesMessage(ValueError, msg):
            car.drivers.create()
        with self.assertRaisesMessage(ValueError, msg):
            car.drivers.get_or_create()
        with self.assertRaisesMessage(ValueError, msg):
            car.drivers.update_or_create()
        with self.assertRaisesMessage(ValueError, msg):
            car.drivers.remove(driver)
        with self.assertRaisesMessage(ValueError, msg):
            car.drivers.clear()
        with self.assertRaisesMessage(ValueError, msg):
            car.drivers.set([driver])

        with self.assertNumQueries(0):
            self.assertEqual(car.drivers.count(), 0)
