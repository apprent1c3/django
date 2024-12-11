import datetime
from copy import deepcopy

from django.core.exceptions import FieldError, MultipleObjectsReturned
from django.db import IntegrityError, models, transaction
from django.test import TestCase
from django.utils.deprecation import RemovedInDjango60Warning
from django.utils.translation import gettext_lazy

from .models import (
    Article,
    Category,
    Child,
    ChildNullableParent,
    ChildStringPrimaryKeyParent,
    City,
    Country,
    District,
    First,
    Parent,
    ParentStringPrimaryKey,
    Record,
    Relation,
    Reporter,
    School,
    Student,
    Third,
    ToFieldChild,
)


class ManyToOneTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a few Reporters.
        """
        Sets up test data for the class, creating and saving instances of Reporter and Article to be used in subsequent tests. 
        The reporters 'John Smith' and 'Paul Jones' are created with example email addresses, and an Article is created with a test headline and publication date, assigned to 'John Smith' as the reporter. 
        This data is stored as class attributes, making it accessible throughout the test suite.
        """
        cls.r = Reporter(first_name="John", last_name="Smith", email="john@example.com")
        cls.r.save()
        cls.r2 = Reporter(
            first_name="Paul", last_name="Jones", email="paul@example.com"
        )
        cls.r2.save()
        # Create an Article.
        cls.a = Article(
            headline="This is a test",
            pub_date=datetime.date(2005, 7, 27),
            reporter=cls.r,
        )
        cls.a.save()

    def test_get(self):
        # Article objects have access to their related Reporter objects.
        """

        Tests the retrieval of a reporter's information.

        Verifies that the retrieved reporter's ID matches the expected ID and 
        that their name matches the predefined first and last names ('John' and 'Smith' respectively).

        """
        r = self.a.reporter
        self.assertEqual(r.id, self.r.id)
        self.assertEqual((r.first_name, self.r.last_name), ("John", "Smith"))

    def test_create(self):
        # You can also instantiate an Article by passing the Reporter's ID
        # instead of a Reporter object.
        """

        Test the creation of Article instances, ensuring that the reporter assignment works correctly
        when the reporter ID is passed both as an integer and as a string. Verifies that the reporter
        object associated with the article is correctly set and that the article can be saved successfully.

        Validates the following scenarios:
        - Creation of an article with a reporter ID passed as an integer.
        - Creation of an article with a reporter ID passed as a string.
        - Successful assignment of the reporter object to the article in both cases.

        The test asserts that the article's reporter ID matches the expected reporter ID after saving,
        and that the string representation of the reporter object is as expected.

        """
        a3 = Article(
            headline="Third article",
            pub_date=datetime.date(2005, 7, 27),
            reporter_id=self.r.id,
        )
        a3.save()
        self.assertEqual(a3.reporter.id, self.r.id)

        # Similarly, the reporter ID can be a string.
        a4 = Article(
            headline="Fourth article",
            pub_date=datetime.date(2005, 7, 27),
            reporter_id=str(self.r.id),
        )
        a4.save()
        self.assertEqual(repr(a4.reporter), "<Reporter: John Smith>")

    def test_add(self):
        # Create an Article via the Reporter object.
        """

        Tests the addition of articles to a reporter's article set.

        The function creates a new article and verifies that it is correctly associated with
        the expected reporter. It also tests the error handling when attempting to add an
        unsaved article or an article that is not an instance of the Article class.

        Specifically, it checks that:

        * A new article is correctly added to the reporter's article set
        * An unsaved article raises a ValueError when added with the default bulk=True
        * An article can be added with bulk=False, even if it is not saved
        * Adding an article to a reporter's article set updates the article's reporter
        * Attempting to add a non-Article instance raises a TypeError

        """
        new_article = self.r.article_set.create(
            headline="John's second story", pub_date=datetime.date(2005, 7, 29)
        )
        self.assertEqual(repr(new_article), "<Article: John's second story>")
        self.assertEqual(new_article.reporter.id, self.r.id)

        # Create a new article, and add it to the article set.
        new_article2 = Article(
            headline="Paul's story", pub_date=datetime.date(2006, 1, 17)
        )
        msg = (
            "<Article: Paul's story> instance isn't saved. Use bulk=False or save the "
            "object first."
        )
        with self.assertRaisesMessage(ValueError, msg):
            self.r.article_set.add(new_article2)

        self.r.article_set.add(new_article2, bulk=False)
        self.assertEqual(new_article2.reporter.id, self.r.id)
        self.assertSequenceEqual(
            self.r.article_set.all(),
            [new_article, new_article2, self.a],
        )

        # Add the same article to a different article set - check that it moves.
        self.r2.article_set.add(new_article2)
        self.assertEqual(new_article2.reporter.id, self.r2.id)
        self.assertSequenceEqual(self.r2.article_set.all(), [new_article2])

        # Adding an object of the wrong type raises TypeError.
        with transaction.atomic():
            with self.assertRaisesMessage(
                TypeError, "'Article' instance expected, got <Reporter:"
            ):
                self.r.article_set.add(self.r2)
        self.assertSequenceEqual(
            self.r.article_set.all(),
            [new_article, self.a],
        )

    def test_set(self):
        """
        Tests the behavior of setting articles for a reporter, including creating new articles, assigning them to different reporters, and ensuring that the article sets are correctly updated. 

        Verifies that setting an article set for a reporter replaces any existing articles, and that articles can be freely assigned to different reporters without affecting the original article instances. 

        Checks the resulting article sets for both reporters to ensure they match the expected state after each modification.
        """
        new_article = self.r.article_set.create(
            headline="John's second story", pub_date=datetime.date(2005, 7, 29)
        )
        new_article2 = self.r2.article_set.create(
            headline="Paul's story", pub_date=datetime.date(2006, 1, 17)
        )

        # Assign the article to the reporter.
        new_article2.reporter = self.r
        new_article2.save()
        self.assertEqual(repr(new_article2.reporter), "<Reporter: John Smith>")
        self.assertEqual(new_article2.reporter.id, self.r.id)
        self.assertSequenceEqual(
            self.r.article_set.all(),
            [new_article, new_article2, self.a],
        )
        self.assertSequenceEqual(self.r2.article_set.all(), [])

        # Set the article back again.
        self.r2.article_set.set([new_article, new_article2])
        self.assertSequenceEqual(self.r.article_set.all(), [self.a])
        self.assertSequenceEqual(
            self.r2.article_set.all(),
            [new_article, new_article2],
        )

        # Funny case - because the ForeignKey cannot be null,
        # existing members of the set must remain.
        self.r.article_set.set([new_article])
        self.assertSequenceEqual(
            self.r.article_set.all(),
            [new_article, self.a],
        )
        self.assertSequenceEqual(self.r2.article_set.all(), [new_article2])

    def test_reverse_assignment_deprecation(self):
        """
        ..: Test that attempting to directly assign to the reverse side of a related set raises a TypeError with a meaningful error message.

            This test verifies that the prohibition on direct assignment to the reverse side of a related set is enforced, 
            and instead suggests using the set() method to modify the related set. The test passes if a TypeError is raised 
            with the expected error message when attempting to directly assign to the reverse side.
        """
        msg = (
            "Direct assignment to the reverse side of a related set is "
            "prohibited. Use article_set.set() instead."
        )
        with self.assertRaisesMessage(TypeError, msg):
            self.r2.article_set = []

    def test_assign(self):
        new_article = self.r.article_set.create(
            headline="John's second story", pub_date=datetime.date(2005, 7, 29)
        )
        new_article2 = self.r2.article_set.create(
            headline="Paul's story", pub_date=datetime.date(2006, 1, 17)
        )

        # Assign the article to the reporter directly using the descriptor.
        new_article2.reporter = self.r
        new_article2.save()
        self.assertEqual(repr(new_article2.reporter), "<Reporter: John Smith>")
        self.assertEqual(new_article2.reporter.id, self.r.id)
        self.assertSequenceEqual(
            self.r.article_set.all(),
            [new_article, new_article2, self.a],
        )
        self.assertSequenceEqual(self.r2.article_set.all(), [])

        # Set the article back again using set() method.
        self.r2.article_set.set([new_article, new_article2])
        self.assertSequenceEqual(self.r.article_set.all(), [self.a])
        self.assertSequenceEqual(
            self.r2.article_set.all(),
            [new_article, new_article2],
        )

        # Because the ForeignKey cannot be null, existing members of the set
        # must remain.
        self.r.article_set.set([new_article])
        self.assertSequenceEqual(
            self.r.article_set.all(),
            [new_article, self.a],
        )
        self.assertSequenceEqual(self.r2.article_set.all(), [new_article2])
        # Reporter cannot be null - there should not be a clear or remove method
        self.assertFalse(hasattr(self.r2.article_set, "remove"))
        self.assertFalse(hasattr(self.r2.article_set, "clear"))

    def test_assign_fk_id_value(self):
        """

        Test assigning a foreign key ID value to a parent object and verifying the behavior of the related object cache.

        This test case checks the following scenarios:
            - Creating a parent object and assigning it a child object as its best child.
            - Updating the best child ID of the parent object and verifying that the related object cache is invalidated.
            - Retrieving the best child object after updating the ID and verifying that the cache is populated.
            - Verifying that subsequent assignments of the same ID do not invalidate the cache.

        The test ensures that the foreign key ID assignment and the related object cache behave as expected, providing a correct and efficient way to manage relationships between objects.

        """
        parent = Parent.objects.create(name="jeff")
        child1 = Child.objects.create(name="frank", parent=parent)
        child2 = Child.objects.create(name="randy", parent=parent)
        parent.bestchild = child1
        parent.save()
        parent.bestchild_id = child2.pk
        parent.save()
        self.assertEqual(parent.bestchild_id, child2.pk)
        self.assertFalse(Parent.bestchild.is_cached(parent))
        self.assertEqual(parent.bestchild, child2)
        self.assertTrue(Parent.bestchild.is_cached(parent))
        # Reassigning the same value doesn't clear cached instance.
        parent.bestchild_id = child2.pk
        self.assertTrue(Parent.bestchild.is_cached(parent))

    def test_assign_fk_id_none(self):
        """
        Tests assigning a foreign key ID to None and checks the subsequent behavior.

        This test case covers the scenario where a foreign key reference is set to None and 
        then saved. It verifies that the foreign key ID is correctly updated to None, the 
        related object is cleared from the cache, and the related object itself becomes None.

        The test ensures that the foreign key relationship is properly handled when the 
        reference is removed, and that the cache is updated accordingly to reflect the 
        changes made to the object's state.
        """
        parent = Parent.objects.create(name="jeff")
        child = Child.objects.create(name="frank", parent=parent)
        parent.bestchild = child
        parent.save()
        parent.bestchild_id = None
        parent.save()
        self.assertIsNone(parent.bestchild_id)
        self.assertFalse(Parent.bestchild.is_cached(parent))
        self.assertIsNone(parent.bestchild)
        self.assertTrue(Parent.bestchild.is_cached(parent))

    def test_selects(self):
        """
        Tests the functionality of Django's ORM select queries.

        This test case ensures that various methods of selecting data from the database 
        are working correctly, including filtering by field values, using exact and 
        non-exact matches, and querying by related object fields. It also checks that 
        the resulting querysets contain the expected data and that the queries are 
        executed efficiently.

        The test covers a range of scenarios, including:

        * Filtering by simple field values
        * Filtering by related object fields
        * Using exact and non-exact matches
        * Querying by primary key and object instance
        * Using the 'in' operator to filter by multiple values
        * Using the 'distinct' method to remove duplicate results

        By testing these different scenarios, this test case provides a comprehensive 
        check of the select query functionality in Django's ORM.
        """
        new_article1 = self.r.article_set.create(
            headline="John's second story",
            pub_date=datetime.date(2005, 7, 29),
        )
        new_article2 = self.r2.article_set.create(
            headline="Paul's story",
            pub_date=datetime.date(2006, 1, 17),
        )
        # Reporter objects have access to their related Article objects.
        self.assertSequenceEqual(
            self.r.article_set.all(),
            [new_article1, self.a],
        )
        self.assertSequenceEqual(
            self.r.article_set.filter(headline__startswith="This"), [self.a]
        )
        self.assertEqual(self.r.article_set.count(), 2)
        self.assertEqual(self.r2.article_set.count(), 1)
        # Get articles by id
        self.assertSequenceEqual(Article.objects.filter(id__exact=self.a.id), [self.a])
        self.assertSequenceEqual(Article.objects.filter(pk=self.a.id), [self.a])
        # Query on an article property
        self.assertSequenceEqual(
            Article.objects.filter(headline__startswith="This"), [self.a]
        )
        # The API automatically follows relationships as far as you need.
        # Use double underscores to separate relationships.
        # This works as many levels deep as you want. There's no limit.
        # Find all Articles for any Reporter whose first name is "John".
        self.assertSequenceEqual(
            Article.objects.filter(reporter__first_name__exact="John"),
            [new_article1, self.a],
        )
        # Implied __exact also works
        self.assertSequenceEqual(
            Article.objects.filter(reporter__first_name="John"),
            [new_article1, self.a],
        )
        # Query twice over the related field.
        self.assertSequenceEqual(
            Article.objects.filter(
                reporter__first_name__exact="John", reporter__last_name__exact="Smith"
            ),
            [new_article1, self.a],
        )
        # The underlying query only makes one join when a related table is
        # referenced twice.
        queryset = Article.objects.filter(
            reporter__first_name__exact="John", reporter__last_name__exact="Smith"
        )
        self.assertNumQueries(1, list, queryset)
        self.assertEqual(
            queryset.query.get_compiler(queryset.db).as_sql()[0].count("INNER JOIN"), 1
        )

        # The automatically joined table has a predictable name.
        self.assertSequenceEqual(
            Article.objects.filter(reporter__first_name__exact="John").extra(
                where=["many_to_one_reporter.last_name='Smith'"]
            ),
            [new_article1, self.a],
        )
        # ... and should work fine with the string that comes out of
        # forms.Form.cleaned_data.
        self.assertQuerySetEqual(
            (
                Article.objects.filter(reporter__first_name__exact="John").extra(
                    where=["many_to_one_reporter.last_name='%s'" % "Smith"]
                )
            ),
            [new_article1, self.a],
        )
        # Find all Articles for a Reporter.
        # Use direct ID check, pk check, and object comparison
        self.assertSequenceEqual(
            Article.objects.filter(reporter__id__exact=self.r.id),
            [new_article1, self.a],
        )
        self.assertSequenceEqual(
            Article.objects.filter(reporter__pk=self.r.id),
            [new_article1, self.a],
        )
        self.assertSequenceEqual(
            Article.objects.filter(reporter=self.r.id),
            [new_article1, self.a],
        )
        self.assertSequenceEqual(
            Article.objects.filter(reporter=self.r),
            [new_article1, self.a],
        )
        self.assertSequenceEqual(
            Article.objects.filter(reporter__in=[self.r.id, self.r2.id]).distinct(),
            [new_article1, new_article2, self.a],
        )
        self.assertSequenceEqual(
            Article.objects.filter(reporter__in=[self.r, self.r2]).distinct(),
            [new_article1, new_article2, self.a],
        )
        # You can also use a queryset instead of a literal list of instances.
        # The queryset must be reduced to a list of values using values(),
        # then converted into a query
        self.assertSequenceEqual(
            Article.objects.filter(
                reporter__in=Reporter.objects.filter(first_name="John")
                .values("pk")
                .query
            ).distinct(),
            [new_article1, self.a],
        )

    def test_reverse_selects(self):
        """

        Tests the select related functionality of the ORM, ensuring that Reporter 
        objects can be filtered in various ways based on their associated Articles.

        Verifies correct retrieval of Reporter objects using exact and primary key 
        matches, as well as lookups based on attributes of related Article objects. 
        This includes filtering on exact article matches, article attributes, and 
        attributes of the reporter associated with an article.

        Additionally, tests the use of distinct() method to eliminate duplicate 
        Reporter objects from query results, and the use of in operator to filter 
        Reporters based on multiple related Articles.

        The function also checks the count of Reporter objects returned in the query 
        results and verifies the correct ordering and values of query sets when using 
        the values() method. 

        """
        a3 = Article.objects.create(
            headline="Third article",
            pub_date=datetime.date(2005, 7, 27),
            reporter_id=self.r.id,
        )
        Article.objects.create(
            headline="Fourth article",
            pub_date=datetime.date(2005, 7, 27),
            reporter_id=self.r.id,
        )
        john_smith = [self.r]
        # Reporters can be queried
        self.assertSequenceEqual(
            Reporter.objects.filter(id__exact=self.r.id), john_smith
        )
        self.assertSequenceEqual(Reporter.objects.filter(pk=self.r.id), john_smith)
        self.assertSequenceEqual(
            Reporter.objects.filter(first_name__startswith="John"), john_smith
        )
        # Reporters can query in opposite direction of ForeignKey definition
        self.assertSequenceEqual(
            Reporter.objects.filter(article__id__exact=self.a.id), john_smith
        )
        self.assertSequenceEqual(
            Reporter.objects.filter(article__pk=self.a.id), john_smith
        )
        self.assertSequenceEqual(Reporter.objects.filter(article=self.a.id), john_smith)
        self.assertSequenceEqual(Reporter.objects.filter(article=self.a), john_smith)
        self.assertSequenceEqual(
            Reporter.objects.filter(article__in=[self.a.id, a3.id]).distinct(),
            john_smith,
        )
        self.assertSequenceEqual(
            Reporter.objects.filter(article__in=[self.a.id, a3]).distinct(), john_smith
        )
        self.assertSequenceEqual(
            Reporter.objects.filter(article__in=[self.a, a3]).distinct(), john_smith
        )
        self.assertCountEqual(
            Reporter.objects.filter(article__headline__startswith="T"),
            [self.r, self.r],
        )
        self.assertSequenceEqual(
            Reporter.objects.filter(article__headline__startswith="T").distinct(),
            john_smith,
        )

        # Counting in the opposite direction works in conjunction with distinct()
        self.assertEqual(
            Reporter.objects.filter(article__headline__startswith="T").count(), 2
        )
        self.assertEqual(
            Reporter.objects.filter(article__headline__startswith="T")
            .distinct()
            .count(),
            1,
        )

        # Queries can go round in circles.
        self.assertCountEqual(
            Reporter.objects.filter(article__reporter__first_name__startswith="John"),
            [self.r, self.r, self.r],
        )
        self.assertSequenceEqual(
            Reporter.objects.filter(
                article__reporter__first_name__startswith="John"
            ).distinct(),
            john_smith,
        )
        self.assertSequenceEqual(
            Reporter.objects.filter(article__reporter__exact=self.r).distinct(),
            john_smith,
        )

        # Implied __exact also works.
        self.assertSequenceEqual(
            Reporter.objects.filter(article__reporter=self.r).distinct(), john_smith
        )

        # It's possible to use values() calls across many-to-one relations.
        # (Note, too, that we clear the ordering here so as not to drag the
        # 'headline' field into the columns being used to determine uniqueness)
        d = {"reporter__first_name": "John", "reporter__last_name": "Smith"}
        qs = (
            Article.objects.filter(
                reporter=self.r,
            )
            .distinct()
            .order_by()
            .values("reporter__first_name", "reporter__last_name")
        )
        self.assertEqual([d], list(qs))

    def test_select_related(self):
        # Article.objects.select_related().dates() works properly when there
        # are multiple Articles with the same date but different foreign-key
        # objects (Reporters).
        """
        Test the select_related functionality on Article objects.

        This test verifies that the select_related method can efficiently retrieve 
        Article objects with their associated reporters, while also testing the dates 
        method to retrieve a list of dates for a specific field, grouped by day, month, 
        or year.

        The test ensures that the select_related method correctly reduces the number 
        of database queries, and that the dates method returns the expected list of dates 
        for each grouping period.
        """
        r1 = Reporter.objects.create(
            first_name="Mike", last_name="Royko", email="royko@suntimes.com"
        )
        r2 = Reporter.objects.create(
            first_name="John", last_name="Kass", email="jkass@tribune.com"
        )
        Article.objects.create(
            headline="First", pub_date=datetime.date(1980, 4, 23), reporter=r1
        )
        Article.objects.create(
            headline="Second", pub_date=datetime.date(1980, 4, 23), reporter=r2
        )
        self.assertEqual(
            list(Article.objects.select_related().dates("pub_date", "day")),
            [datetime.date(1980, 4, 23), datetime.date(2005, 7, 27)],
        )
        self.assertEqual(
            list(Article.objects.select_related().dates("pub_date", "month")),
            [datetime.date(1980, 4, 1), datetime.date(2005, 7, 1)],
        )
        self.assertEqual(
            list(Article.objects.select_related().dates("pub_date", "year")),
            [datetime.date(1980, 1, 1), datetime.date(2005, 1, 1)],
        )

    def test_delete(self):
        """
        Tests the deletion of Reporters and Articles.

        This function tests the behavior of deleting Reporter objects and its effect on
        associated Article objects. It creates multiple Reporters and Articles, then
        verifies the order and integrity of the data before and after deletion.

        The test checks for the following scenarios:

        - Deletion of a Reporter and the subsequent removal of its associated Article
        - Deletion of Reporters based on specific conditions, such as articles with
          headlines starting with a particular string
        - The final state of the database after all deletions, ensuring that both
          Reporters and Articles are correctly removed

        The goal of this test is to ensure that the deletion mechanism works as expected,
        maintaining data consistency across related models.
        """
        new_article1 = self.r.article_set.create(
            headline="John's second story",
            pub_date=datetime.date(2005, 7, 29),
        )
        new_article2 = self.r2.article_set.create(
            headline="Paul's story",
            pub_date=datetime.date(2006, 1, 17),
        )
        new_article3 = Article.objects.create(
            headline="Third article",
            pub_date=datetime.date(2005, 7, 27),
            reporter_id=self.r.id,
        )
        new_article4 = Article.objects.create(
            headline="Fourth article",
            pub_date=datetime.date(2005, 7, 27),
            reporter_id=str(self.r.id),
        )
        # If you delete a reporter, their articles will be deleted.
        self.assertSequenceEqual(
            Article.objects.all(),
            [new_article4, new_article1, new_article2, new_article3, self.a],
        )
        self.assertSequenceEqual(
            Reporter.objects.order_by("first_name"),
            [self.r, self.r2],
        )
        self.r2.delete()
        self.assertSequenceEqual(
            Article.objects.all(),
            [new_article4, new_article1, new_article3, self.a],
        )
        self.assertSequenceEqual(Reporter.objects.order_by("first_name"), [self.r])
        # You can delete using a JOIN in the query.
        Reporter.objects.filter(article__headline__startswith="This").delete()
        self.assertSequenceEqual(Reporter.objects.all(), [])
        self.assertSequenceEqual(Article.objects.all(), [])

    def test_explicit_fk(self):
        # Create a new Article with get_or_create using an explicit value
        # for a ForeignKey.
        """

        Test the explicit assignment of foreign keys in the Article model.

        This test case verifies that foreign keys can be explicitly set when creating or
        retrieving Article objects. It checks that the 'reporter' field is correctly
        assigned and that the corresponding Article objects are returned when filtered by
        'reporter_id'.

        The test also covers the scenario where multiple Article objects are associated
        with the same reporter, ensuring that the correct error is raised when attempting
        to retrieve a single object with a non-unique 'reporter_id'.

        Finally, it validates that the string representation of an Article object is
        consistent with the object retrieved from the database using its 'reporter_id' and
        'pub_date' fields.

        """
        a2, created = Article.objects.get_or_create(
            headline="John's second test",
            pub_date=datetime.date(2011, 5, 7),
            reporter_id=self.r.id,
        )
        self.assertTrue(created)
        self.assertEqual(a2.reporter.id, self.r.id)

        # You can specify filters containing the explicit FK value.
        self.assertSequenceEqual(
            Article.objects.filter(reporter_id__exact=self.r.id),
            [a2, self.a],
        )

        # Create an Article by Paul for the same date.
        a3 = Article.objects.create(
            headline="Paul's commentary",
            pub_date=datetime.date(2011, 5, 7),
            reporter_id=self.r2.id,
        )
        self.assertEqual(a3.reporter.id, self.r2.id)

        # Get should respect explicit foreign keys as well.
        msg = "get() returned more than one Article -- it returned 2!"
        with self.assertRaisesMessage(MultipleObjectsReturned, msg):
            Article.objects.get(reporter_id=self.r.id)
        self.assertEqual(
            repr(a3),
            repr(
                Article.objects.get(
                    reporter_id=self.r2.id, pub_date=datetime.date(2011, 5, 7)
                )
            ),
        )

    def test_deepcopy_and_circular_references(self):
        # Regression for #12876 -- Model methods that include queries that
        # recursive don't cause recursion depth problems under deepcopy.
        """
        Tests the deepcopy functionality on a model instance with circular references.

        Verifies that creating a deep copy of a model instance does not result in an infinite recursion
        when the instance has a circular relationship, such as a cached query referencing the instance itself.
        The test checks that the deep copy operation produces an identical representation of the original instance,
        confirming that the circular reference is properly handled during the copying process.
        """
        self.r.cached_query = Article.objects.filter(reporter=self.r)
        self.assertEqual(repr(deepcopy(self.r)), "<Reporter: John Smith>")

    def test_manager_class_caching(self):
        """

        Tests the class caching mechanism of the Manager class in the Reporter model.

        Verifies that the class of the article_set manager remains consistent across 
        different Reporter instances, ensuring efficient caching and retrieval of related 
        objects.

        """
        r1 = Reporter.objects.create(first_name="Mike")
        r2 = Reporter.objects.create(first_name="John")

        # Same twice
        self.assertIs(r1.article_set.__class__, r1.article_set.__class__)

        # Same as each other
        self.assertIs(r1.article_set.__class__, r2.article_set.__class__)

    def test_create_relation_with_gettext_lazy(self):
        reporter = Reporter.objects.create(
            first_name="John", last_name="Smith", email="john.smith@example.com"
        )
        lazy = gettext_lazy("test")
        reporter.article_set.create(headline=lazy, pub_date=datetime.date(2011, 6, 10))
        notlazy = str(lazy)
        article = reporter.article_set.get()
        self.assertEqual(article.headline, notlazy)

    def test_values_list_exception(self):
        """
        Tests the exception handling of :meth:`values_list` when an invalid field name is provided.

        The test checks two scenarios:

        * When an invalid field name is used in a related field lookup (e.g., 'reporter__notafield').
        * When an invalid field name is used in a query that includes an 'extra' select statement.

        In both cases, the test expects a :class:`FieldError` to be raised with a message indicating the valid field choices.
        """
        expected_message = (
            "Cannot resolve keyword 'notafield' into field. Choices are: %s"
        )
        reporter_fields = ", ".join(sorted(f.name for f in Reporter._meta.get_fields()))
        with self.assertRaisesMessage(FieldError, expected_message % reporter_fields):
            Article.objects.values_list("reporter__notafield")
        article_fields = ", ".join(
            ["EXTRA"] + sorted(f.name for f in Article._meta.get_fields())
        )
        with self.assertRaisesMessage(FieldError, expected_message % article_fields):
            Article.objects.extra(select={"EXTRA": "EXTRA_SELECT"}).values_list(
                "notafield"
            )

    def test_fk_assignment_and_related_object_cache(self):
        # Tests of ForeignKey assignment and the related-object cache (see #6886).

        """
        Tests the assignment of foreign key fields and the behavior of related object caching.

        This test case covers various scenarios including:

        *   Creating and retrieving related objects
        *   Assigning and reassigning foreign key fields
        *   Verifying that related objects are correctly cached
        *   Ensuring that foreign key fields can only be assigned instances of the correct model
        *   Handling cases where a related object is not saved
        *   Testing the creation of objects with unsaved related objects

        The test also checks for expected errors and exceptions, such as ValueError and IntegrityError, when attempting to assign or save invalid or inconsistent data.

        The test covers the following models and relationships:

        *   Parent and Child models with a foreign key relationship
        *   ToFieldChild model with a foreign key relationship to Parent

        By verifying the behavior of foreign key assignments and related object caching, this test ensures the correctness and consistency of the data in the database.
        """
        p = Parent.objects.create(name="Parent")
        c = Child.objects.create(name="Child", parent=p)

        # Look up the object again so that we get a "fresh" object.
        c = Child.objects.get(name="Child")
        p = c.parent

        # Accessing the related object again returns the exactly same object.
        self.assertIs(c.parent, p)

        # But if we kill the cache, we get a new object.
        del c._state.fields_cache["parent"]
        self.assertIsNot(c.parent, p)

        # Assigning a new object results in that object getting cached immediately.
        p2 = Parent.objects.create(name="Parent 2")
        c.parent = p2
        self.assertIs(c.parent, p2)

        # Assigning None succeeds if field is null=True.
        p.bestchild = None
        self.assertIsNone(p.bestchild)

        # bestchild should still be None after saving.
        p.save()
        self.assertIsNone(p.bestchild)

        # bestchild should still be None after fetching the object again.
        p = Parent.objects.get(name="Parent")
        self.assertIsNone(p.bestchild)

        # Assigning None will not fail: Child.parent is null=False.
        setattr(c, "parent", None)

        # You also can't assign an object of the wrong type here
        msg = (
            'Cannot assign "<First: First object (1)>": "Child.parent" must '
            'be a "Parent" instance.'
        )
        with self.assertRaisesMessage(ValueError, msg):
            setattr(c, "parent", First(id=1, second=1))

        # You can assign None to Child.parent during object creation.
        Child(name="xyzzy", parent=None)

        # But when trying to save a Child with parent=None, the database will
        # raise IntegrityError.
        with self.assertRaises(IntegrityError), transaction.atomic():
            Child.objects.create(name="xyzzy", parent=None)

        # Creation using keyword argument should cache the related object.
        p = Parent.objects.get(name="Parent")
        c = Child(parent=p)
        self.assertIs(c.parent, p)

        # Creation using keyword argument and unsaved related instance (#8070).
        p = Parent()
        msg = (
            "save() prohibited to prevent data loss due to unsaved related object "
            "'parent'."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Child.objects.create(parent=p)

        with self.assertRaisesMessage(ValueError, msg):
            ToFieldChild.objects.create(parent=p)

        # Creation using attname keyword argument and an id will cause the
        # related object to be fetched.
        p = Parent.objects.get(name="Parent")
        c = Child(parent_id=p.id)
        self.assertIsNot(c.parent, p)
        self.assertEqual(c.parent, p)

    def test_save_parent_after_assign(self):
        """
        Tests the behavior of a Record's category after reassigning the parent Category.

        Checks that when a Category is updated after being assigned to a Record and saved,
        the Record's category reference remains consistent, without triggering additional database queries.

        Verifies that both the Category id and name are correctly reflected in the assigned Record's category.
        """
        category = Category(name="cats")
        record = Record(category=category)
        category.save()
        record.save()
        category.name = "dogs"
        with self.assertNumQueries(0):
            self.assertEqual(category.id, record.category_id)
            self.assertEqual(category.name, record.category.name)

    def test_save_nullable_fk_after_parent(self):
        parent = Parent()
        child = ChildNullableParent(parent=parent)
        parent.save()
        child.save()
        child.refresh_from_db()
        self.assertEqual(child.parent, parent)

    def test_save_nullable_fk_after_parent_with_to_field(self):
        """

        Tests the saving of a nullable foreign key after its parent object, 
        where the foreign key is specified with the 'to_field' argument.

        Verifies that the child object's foreign key field is correctly set 
        to the parent object's field specified by 'to_field' and that the 
        relationship is correctly established after saving and refreshing 
        the child object from the database.

        """
        parent = Parent(name="jeff")
        child = ToFieldChild(parent=parent)
        parent.save()
        child.save()
        child.refresh_from_db()
        self.assertEqual(child.parent, parent)
        self.assertEqual(child.parent_id, parent.name)

    def test_save_fk_after_parent_with_non_numeric_pk_set_on_child(self):
        """
        Tests the saving of a child object with a foreign key reference to a parent object, 
        where the parent object has a non-numeric primary key. The test ensures that after 
        setting the foreign key on the child object, saving both the parent and child objects, 
        and then refreshing the child object from the database, the foreign key reference 
        is correctly established and the parent object's primary key is correctly stored 
        in the child object's foreign key field.
        """
        parent = ParentStringPrimaryKey()
        child = ChildStringPrimaryKeyParent(parent=parent)
        child.parent.name = "jeff"
        parent.save()
        child.save()
        child.refresh_from_db()
        self.assertEqual(child.parent, parent)
        self.assertEqual(child.parent_id, parent.name)

    def test_fk_to_bigautofield(self):
        """
        Tests foreign key relationships with a BigAutoField primary key.

        This test case creates cities and their respective districts to verify the functionality
        of foreign key references to a BigAutoField primary key. It covers scenario with both
        auto-assigned and manually specified large primary key values, ensuring proper creation
        and relationship establishment between the City and District models.

        The test covers the following scenarios:
            * Creation of a city with an auto-assigned primary key and its districts
            * Creation of a city with a large manually specified primary key and its districts
        """
        ch = City.objects.create(name="Chicago")
        District.objects.create(city=ch, name="Far South")
        District.objects.create(city=ch, name="North")

        ny = City.objects.create(name="New York", id=2**33)
        District.objects.create(city=ny, name="Brooklyn")
        District.objects.create(city=ny, name="Manhattan")

    def test_fk_to_smallautofield(self):
        us = Country.objects.create(name="United States")
        City.objects.create(country=us, name="Chicago")
        City.objects.create(country=us, name="New York")

        uk = Country.objects.create(name="United Kingdom", id=2**11)
        City.objects.create(country=uk, name="London")
        City.objects.create(country=uk, name="Edinburgh")

    def test_multiple_foreignkeys(self):
        # Test of multiple ForeignKeys to the same model (bug #7125).
        """
        Tests the handling of multiple foreign keys in various model relationships.

        This test case covers the following scenarios:
        - Creating categories and records, and establishing relationships between them.
        - Filtering relations based on category names.
        - Retrieving categories based on record relationships.
        - Validating the assignment of parent-child relationships to ensure correct instance types.

        The test verifies that the relationships are correctly established and queried, and that invalid assignments raise the expected error messages.
        """
        c1 = Category.objects.create(name="First")
        c2 = Category.objects.create(name="Second")
        c3 = Category.objects.create(name="Third")
        r1 = Record.objects.create(category=c1)
        r2 = Record.objects.create(category=c1)
        r3 = Record.objects.create(category=c2)
        r4 = Record.objects.create(category=c2)
        r5 = Record.objects.create(category=c3)
        Relation.objects.create(left=r1, right=r2)
        Relation.objects.create(left=r3, right=r4)
        rel = Relation.objects.create(left=r1, right=r3)
        Relation.objects.create(left=r5, right=r2)
        Relation.objects.create(left=r3, right=r2)

        q1 = Relation.objects.filter(
            left__category__name__in=["First"], right__category__name__in=["Second"]
        )
        self.assertSequenceEqual(q1, [rel])

        q2 = Category.objects.filter(
            record__left_set__right__category__name="Second"
        ).order_by("name")
        self.assertSequenceEqual(q2, [c1, c2])

        p = Parent.objects.create(name="Parent")
        c = Child.objects.create(name="Child", parent=p)
        msg = 'Cannot assign "%r": "Child.parent" must be a "Parent" instance.' % c
        with self.assertRaisesMessage(ValueError, msg):
            Child.objects.create(name="Grandchild", parent=c)

    def test_fk_instantiation_outside_model(self):
        # Regression for #12190 -- Should be able to instantiate a FK outside
        # of a model, and interrogate its related field.
        """

        Tests the instantiation of a ForeignKey field outside of a model.

        This test case verifies that a ForeignKey object can be created independently of a model
        and that its remote field properties are correctly set. Specifically, it checks that the
        related field name of the ForeignKey is correctly identified as 'id'.

        """
        cat = models.ForeignKey(Category, models.CASCADE)
        self.assertEqual("id", cat.remote_field.get_related_field().name)

    def test_relation_unsaved(self):
        """

        Test the behavior of the relation when the instance is not saved.

        This test checks that attempting to access the related objects of an unsaved instance
        raises a ValueError, as the instance needs to have a primary key value for the relation
        to work correctly. It also verifies that the relation's model is correctly set.

        After saving the instance, the test ensures that the related objects are correctly
        retrieved with a single database query, and that the count of related objects is initially 0.

        """
        Third.objects.create(name="Third 1")
        Third.objects.create(name="Third 2")
        th = Third(name="testing")
        # The object isn't saved and the relation cannot be used.
        msg = (
            "'Third' instance needs to have a primary key value before this "
            "relationship can be used."
        )
        with self.assertRaisesMessage(ValueError, msg):
            th.child_set.count()
        # The reverse foreign key manager can be created.
        self.assertEqual(th.child_set.model, Third)

        th.save()
        # Now the model is saved, so we will need to execute a query.
        with self.assertNumQueries(1):
            self.assertEqual(th.child_set.count(), 0)

    def test_related_object(self):
        public_school = School.objects.create(is_public=True)
        public_student = Student.objects.create(school=public_school)

        private_school = School.objects.create(is_public=False)
        private_student = Student.objects.create(school=private_school)

        # Only one school is available via all() due to the custom default manager.
        self.assertSequenceEqual(School.objects.all(), [public_school])

        self.assertEqual(public_student.school, public_school)

        # Make sure the base manager is used so that a student can still access
        # its related school even if the default manager doesn't normally
        # allow it.
        self.assertEqual(private_student.school, private_school)

        School._meta.base_manager_name = "objects"
        School._meta._expire_cache()
        try:
            private_student = Student.objects.get(pk=private_student.pk)
            with self.assertRaises(School.DoesNotExist):
                private_student.school
        finally:
            School._meta.base_manager_name = None
            School._meta._expire_cache()

    def test_hasattr_related_object(self):
        # The exception raised on attribute access when a related object
        # doesn't exist should be an instance of a subclass of `AttributeError`
        # refs #21563
        self.assertFalse(hasattr(Article(), "reporter"))

    def test_create_after_prefetch(self):
        """

        Tests the creation of a new district after a city has been prefetched.

        Verifies that a district can be added to a city that has been retrieved with 
        prefetched related objects. The test case covers the following scenarios:
        - Creating a city and an initial district
        - Prefetching the city with its related districts
        - Verifying that the prefetched city has the expected district
        - Creating a new district for the prefetched city
        - Verifying that the new district is included in the city's districts

        """
        c = City.objects.create(name="Musical City")
        d1 = District.objects.create(name="Ladida", city=c)
        city = City.objects.prefetch_related("districts").get(id=c.id)
        self.assertSequenceEqual(city.districts.all(), [d1])
        d2 = city.districts.create(name="Goa")
        self.assertSequenceEqual(city.districts.all(), [d1, d2])

    def test_clear_after_prefetch(self):
        """
        Tests that the clear method correctly removes all associated districts from a city after they have been prefetched. 

        This test ensures that prefetched related objects can be properly cleared, verifying that the city's districts are correctly removed and the city's state is updated accordingly, leaving it with no associated districts after the clear operation.
        """
        c = City.objects.create(name="Musical City")
        d = District.objects.create(name="Ladida", city=c)
        city = City.objects.prefetch_related("districts").get(id=c.id)
        self.assertSequenceEqual(city.districts.all(), [d])
        city.districts.clear()
        self.assertSequenceEqual(city.districts.all(), [])

    def test_remove_after_prefetch(self):
        c = City.objects.create(name="Musical City")
        d = District.objects.create(name="Ladida", city=c)
        city = City.objects.prefetch_related("districts").get(id=c.id)
        self.assertSequenceEqual(city.districts.all(), [d])
        city.districts.remove(d)
        self.assertSequenceEqual(city.districts.all(), [])

    def test_add_after_prefetch(self):
        c = City.objects.create(name="Musical City")
        District.objects.create(name="Ladida", city=c)
        d2 = District.objects.create(name="Ladidu")
        city = City.objects.prefetch_related("districts").get(id=c.id)
        self.assertEqual(city.districts.count(), 1)
        city.districts.add(d2)
        self.assertEqual(city.districts.count(), 2)

    def test_set_after_prefetch(self):
        """
        Verifies that setting a new set of related objects on a model instance works correctly after prefetching the related objects.

        Tests that the number of related objects is correctly updated and that the new set of objects is returned when accessed.
        This ensures that the related objects are properly replaced and that the prefetching does not interfere with the update operation.

        The test case covers the scenario where an initial related object is created and then replaced with a new one, verifying the correctness of the replacement operation.

        """
        c = City.objects.create(name="Musical City")
        District.objects.create(name="Ladida", city=c)
        d2 = District.objects.create(name="Ladidu")
        city = City.objects.prefetch_related("districts").get(id=c.id)
        self.assertEqual(city.districts.count(), 1)
        city.districts.set([d2])
        self.assertSequenceEqual(city.districts.all(), [d2])

    def test_add_then_remove_after_prefetch(self):
        """

        Test the addition and removal of a district from a city after prefetching.

        Verifies that a city's districts can be correctly added to and removed from
        after the city's districts have been prefetched.

        Confirms the city's districts are accurately counted before and after 
        addition and removal operations.

        """
        c = City.objects.create(name="Musical City")
        District.objects.create(name="Ladida", city=c)
        d2 = District.objects.create(name="Ladidu")
        city = City.objects.prefetch_related("districts").get(id=c.id)
        self.assertEqual(city.districts.count(), 1)
        city.districts.add(d2)
        self.assertEqual(city.districts.count(), 2)
        city.districts.remove(d2)
        self.assertEqual(city.districts.count(), 1)

    def test_cached_relation_invalidated_on_save(self):
        """
        Model.save() invalidates stale ForeignKey relations after a primary key
        assignment.
        """
        self.assertEqual(self.a.reporter, self.r)  # caches a.reporter
        self.a.reporter_id = self.r2.pk
        self.a.save()
        self.assertEqual(self.a.reporter, self.r2)

    def test_cached_foreign_key_with_to_field_not_cleared_by_save(self):
        parent = Parent.objects.create(name="a")
        child = ToFieldChild.objects.create(parent=parent)
        with self.assertNumQueries(0):
            self.assertIs(child.parent, parent)

    def test_reverse_foreign_key_instance_to_field_caching(self):
        """

        Tests the behavior of foreign key instance caching when accessing a related object 
        through a 'to_field' relationship, ensuring that no additional database queries are 
        made when the parent instance is accessed through the cached child instance.

        Checks that the parent instance stored in the child's foreign key is the same instance 
        that was originally used to create the child, confirming proper caching functionality.

        """
        parent = Parent.objects.create(name="a")
        ToFieldChild.objects.create(parent=parent)
        child = parent.to_field_children.get()
        with self.assertNumQueries(0):
            self.assertIs(child.parent, parent)

    def test_add_remove_set_by_pk_raises(self):
        """
        Test that adding, removing, or setting a city to a country by its primary key raises a TypeError.

        This test case checks that passing a primary key (integer) instead of a City instance to the add, remove, or set methods of a country's cities relationship results in a TypeError with a descriptive message.

        The test uses a sample United States country and Chicago city, and verifies that attempting to add, remove, or set the city by its primary key raises a TypeError with the expected error message, indicating that a City instance is expected instead of an integer primary key.
        """
        usa = Country.objects.create(name="United States")
        chicago = City.objects.create(name="Chicago")
        msg = "'City' instance expected, got %s" % chicago.pk
        with self.assertRaisesMessage(TypeError, msg):
            usa.cities.add(chicago.pk)
        with self.assertRaisesMessage(TypeError, msg):
            usa.cities.remove(chicago.pk)
        with self.assertRaisesMessage(TypeError, msg):
            usa.cities.set([chicago.pk])

    def test_get_prefetch_queryset_warning(self):
        """

        Tests that a warning is raised when using the deprecated get_prefetch_queryset method.

        This test case creates a City object, retrieves all City objects, and then calls the
        get_prefetch_queryset method on the City.country attribute, passing the retrieved cities.
        It verifies that a RemovedInDjango60Warning is raised with a message indicating that
        get_prefetch_queryset is deprecated and should be replaced with get_prefetch_querysets.

        """
        City.objects.create(name="Chicago")
        cities = City.objects.all()
        msg = (
            "get_prefetch_queryset() is deprecated. Use get_prefetch_querysets() "
            "instead."
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            City.country.get_prefetch_queryset(cities)

    def test_get_prefetch_queryset_reverse_warning(self):
        """

        Tests the deprecation warning raised when using get_prefetch_queryset() with reverse relations.

        This test case validates that the expected warning message is emitted when the deprecated method is invoked, 
        informing users to use get_prefetch_querysets() instead. It covers the scenario where the method is called 
        on a related object manager with a queryset as an argument, simulating a common use case. 

        The deprecated method's usage is verified to be correctly flagged, ensuring that users are properly notified 
        and can update their code to use the recommended replacement. 

        """
        usa = Country.objects.create(name="United States")
        City.objects.create(name="Chicago")
        countries = Country.objects.all()
        msg = (
            "get_prefetch_queryset() is deprecated. Use get_prefetch_querysets() "
            "instead."
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            usa.cities.get_prefetch_queryset(countries)

    def test_get_prefetch_querysets_invalid_querysets_length(self):
        """
        Test that get_prefetch_querysets() raises a ValueError when the provided querysets argument has an invalid length.

        The function checks that the method enforces the rule that the querysets list should contain exactly one queryset. 

        It creates a test scenario with multiple cities, attempts to call get_prefetch_querysets with multiple querysets, and verifies that a ValueError is raised with the expected error message. 

        This test ensures that the get_prefetch_querysets method correctly validates its input and provides informative error messages when used incorrectly.
        """
        City.objects.create(name="Chicago")
        cities = City.objects.all()
        msg = (
            "querysets argument of get_prefetch_querysets() should have a length of 1."
        )
        with self.assertRaisesMessage(ValueError, msg):
            City.country.get_prefetch_querysets(
                instances=cities,
                querysets=[Country.objects.all(), Country.objects.all()],
            )

    def test_get_prefetch_querysets_reverse_invalid_querysets_length(self):
        usa = Country.objects.create(name="United States")
        City.objects.create(name="Chicago")
        countries = Country.objects.all()
        msg = (
            "querysets argument of get_prefetch_querysets() should have a length of 1."
        )
        with self.assertRaisesMessage(ValueError, msg):
            usa.cities.get_prefetch_querysets(
                instances=countries,
                querysets=[City.objects.all(), City.objects.all()],
            )
