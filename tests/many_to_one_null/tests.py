from django.test import TestCase

from .models import Article, Car, Driver, Reporter


class ManyToOneNullTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a Reporter.
        """

        Sets up test data for the application.

        This method creates a set of predefined Reporter and Article instances, 
        which can be used as a basis for testing various scenarios. 
        It establishes relationships between reporters and their respective articles, 
        including cases where an article has a reporter and where it does not.

        The following test data is created:
        - Two reporters: John Smith and Paul Jones
        - Four articles with varying relationships to the reporters, 
          including articles with and without assigned reporters.

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
        """

        Tests the retrieval of a related object.

        Verifies that the reporter associated with an instance can be correctly accessed and identified.
        The function checks that the reporter's ID matches the expected ID, ensuring a valid relationship.

        """
        self.assertEqual(self.a.reporter.id, self.r.id)
        # Article objects have access to their related Reporter objects.
        r = self.a.reporter
        self.assertEqual(r.id, self.r.id)

    def test_created_via_related_set(self):
        self.assertEqual(self.a2.reporter.id, self.r.id)

    def test_related_set(self):
        # Reporter objects have access to their related Article objects.
        """

        Tests the functionality of the related set, specifically the article set associated with an instance.

        This test case verifies that the article set is correctly retrieved and filtered, ensuring the following conditions are met:
        - All articles in the set are correctly identified.
        - Articles can be filtered by specific criteria, such as headline.
        - The total count of articles in the set is accurate.

        """
        self.assertSequenceEqual(self.r.article_set.all(), [self.a, self.a2])
        self.assertSequenceEqual(
            self.r.article_set.filter(headline__startswith="Fir"), [self.a]
        )
        self.assertEqual(self.r.article_set.count(), 2)

    def test_created_without_related(self):
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
        Tests the removal of an article from a reporter's article set when the article does not belong to that reporter.

        Verifies that attempting to remove an article from the wrong reporter results in a Reporter.DoesNotExist exception and does not modify the article set of the reporter that actually owns the article.
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
        Tests the functionality of setting articles in a reporter's article set.

        This test covers the basic operations of setting, replacing, and clearing the article set.
        It verifies that the articles are correctly added, replaced, and removed, and that the original
        articles are updated correctly to reflect changes in their reporter association.

        The test checks the following scenarios:

        * Setting a new list of articles
        * Replacing the existing list with a new one
        * Clearing the article set
        * Verifying the correct handling of article reporter associations after changes

        It ensures that the article set is correctly updated and that the underlying data is consistent
        with the changes made to the set.
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

        Tests the behavior of setting a relation with a clear and non-bulk operation.

        This test case verifies that the relation is correctly cleared and set when
        using a non-bulk operation. It also checks that the expected number of database
        queries are executed during this process.

        The test case exercises the set method of the article_set relation, passing a
        single item to be set, with the bulk parameter set to False and the clear
        parameter set to True. The expected outcome is that the relation is cleared of
        any existing items and then set to contain only the specified item.

        """
        with self.assertNumQueries(4):
            self.r.article_set.set([self.a], bulk=False, clear=True)

    def test_assign_clear_related_set(self):
        # Use descriptor assignment to allocate ForeignKey. Null is legal, so
        # existing members of the set that are not in the assignment set are
        # set to null.
        """
        Tests the assignment and clearing of related sets in the Reporter model.

        This test case checks if a set of articles can be successfully assigned to a reporter and if the assignment is correctly reflected in the database.
        It then tests the clearing of the related set, verifying that the articles are properly removed from the reporter's set and that the articles are updated to have a null reporter, indicating they are no longer associated with any reporter.
        """
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
        r = Reporter.objects.create()
        articles = []
        for _ in range(3):
            articles.append(Article.objects.create())
        with self.assertNumQueries(1):
            r.article_set.add(*articles)
        self.assertEqual(r.article_set.count(), 3)

    def test_clear_efficiency(self):
        """
        Tests the efficiency of clearing all articles associated with a reporter.

        This test case verifies that clearing all articles for a reporter can be done 
        in a single database query, ensuring efficient removal of related objects.

        It creates a reporter, adds multiple articles to it, and then checks that 
        clearing the articles can be achieved with a minimal number of database queries.
        The test also confirms that after clearing, the article count for the reporter returns to zero.
        """
        r = Reporter.objects.create()
        for _ in range(3):
            r.article_set.create()
        with self.assertNumQueries(1):
            r.article_set.clear()
        self.assertEqual(r.article_set.count(), 0)

    def test_related_null_to_field(self):
        c1 = Car.objects.create()
        d1 = Driver.objects.create()
        self.assertIs(d1.car, None)
        with self.assertNumQueries(0):
            self.assertEqual(list(c1.drivers.all()), [])

    def test_unsaved(self):
        msg = (
            "'Car' instance needs to have a primary key value before this relationship "
            "can be used."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Car(make="Ford").drivers.all()

    def test_related_null_to_field_related_managers(self):
        """

        Tests that attempting to use a related manager on an instance with a null related field raises a ValueError.

        This test case covers scenarios where the related field is null and an operation is attempted on the related manager,
        including adding, creating, getting or creating, updating or creating, removing, clearing, and setting related instances.

        The test verifies that a ValueError with a descriptive message is raised in each scenario, ensuring that the related manager
        cannot be used until the null related field is populated with a valid value.

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
