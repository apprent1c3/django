from unittest import mock

from django.db import connection, transaction
from django.test import TestCase, skipIfDBFeature, skipUnlessDBFeature
from django.utils.deprecation import RemovedInDjango60Warning

from .models import (
    Article,
    InheritedArticleA,
    InheritedArticleB,
    NullablePublicationThrough,
    NullableTargetArticle,
    Publication,
    User,
)


class ManyToManyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a couple of Publications.
        cls.p1 = Publication.objects.create(title="The Python Journal")
        cls.p2 = Publication.objects.create(title="Science News")
        cls.p3 = Publication.objects.create(title="Science Weekly")
        cls.p4 = Publication.objects.create(title="Highlights for Children")

        cls.a1 = Article.objects.create(
            headline="Django lets you build web apps easily"
        )
        cls.a1.publications.add(cls.p1)

        cls.a2 = Article.objects.create(headline="NASA uses Python")
        cls.a2.publications.add(cls.p1, cls.p2, cls.p3, cls.p4)

        cls.a3 = Article.objects.create(headline="NASA finds intelligent life on Earth")
        cls.a3.publications.add(cls.p2)

        cls.a4 = Article.objects.create(headline="Oxygen-free diet works wonders")
        cls.a4.publications.add(cls.p2)

    def test_add(self):
        # Create an Article.
        """

        Tests the functionality of adding publications to an article.

        This test ensures that an article must be saved before attempting to add publications.
        It verifies that multiple publications can be added to an article and that the publications
        are stored in the order they were added.

        Additionally, it checks for errors when attempting to add an invalid object type to the
        publications, such as another article.

        The test also covers the creation of a new publication directly from an article, and
        verifies that the new publication is properly associated with the article.

        """
        a5 = Article(headline="Django lets you create web apps easily")
        # You can't associate it with a Publication until it's been saved.
        msg = (
            '"<Article: Django lets you create web apps easily>" needs to have '
            'a value for field "id" before this many-to-many relationship can be used.'
        )
        with self.assertRaisesMessage(ValueError, msg):
            getattr(a5, "publications")
        # Save it!
        a5.save()
        # Associate the Article with a Publication.
        a5.publications.add(self.p1)
        self.assertSequenceEqual(a5.publications.all(), [self.p1])
        # Create another Article, and set it to appear in both Publications.
        a6 = Article(headline="ESA uses Python")
        a6.save()
        a6.publications.add(self.p1, self.p2)
        a6.publications.add(self.p3)
        # Adding a second time is OK
        a6.publications.add(self.p3)
        self.assertSequenceEqual(
            a6.publications.all(),
            [self.p2, self.p3, self.p1],
        )

        # Adding an object of the wrong type raises TypeError
        msg = (
            "'Publication' instance expected, got <Article: Django lets you create web "
            "apps easily>"
        )
        with self.assertRaisesMessage(TypeError, msg):
            with transaction.atomic():
                a6.publications.add(a5)

        # Add a Publication directly via publications.add by using keyword arguments.
        p5 = a6.publications.create(title="Highlights for Adults")
        self.assertSequenceEqual(
            a6.publications.all(),
            [p5, self.p2, self.p3, self.p1],
        )

    def test_add_remove_set_by_pk(self):
        a5 = Article.objects.create(headline="Django lets you create web apps easily")
        a5.publications.add(self.p1.pk)
        self.assertSequenceEqual(a5.publications.all(), [self.p1])
        a5.publications.set([self.p2.pk])
        self.assertSequenceEqual(a5.publications.all(), [self.p2])
        a5.publications.remove(self.p2.pk)
        self.assertSequenceEqual(a5.publications.all(), [])

    def test_add_remove_set_by_to_field(self):
        user_1 = User.objects.create(username="Jean")
        user_2 = User.objects.create(username="Joe")
        a5 = Article.objects.create(headline="Django lets you create web apps easily")
        a5.authors.add(user_1.username)
        self.assertSequenceEqual(a5.authors.all(), [user_1])
        a5.authors.set([user_2.username])
        self.assertSequenceEqual(a5.authors.all(), [user_2])
        a5.authors.remove(user_2.username)
        self.assertSequenceEqual(a5.authors.all(), [])

    def test_related_manager_refresh(self):
        """
        Tests the refresh functionality of the related manager for a User instance.

        This test case verifies that when a User's related data (e.g., articles) is updated,
        the changes are correctly reflected after refreshing the User instance from the database.
        It also ensures that the related manager (e.g., article_set) returns the correct data
        after the User's details have been modified.

        The test scenario involves creating two users, assigning them to different articles,
        and then updating the user's username and article assignments. The related manager's data
        is verified at various stages to ensure that it remains consistent with the changes made
        to the User instance and its related data in the database.
        """
        user_1 = User.objects.create(username="Jean")
        user_2 = User.objects.create(username="Joe")
        self.a3.authors.add(user_1.username)
        self.assertSequenceEqual(user_1.article_set.all(), [self.a3])
        # Change the username on a different instance of the same user.
        user_1_from_db = User.objects.get(pk=user_1.pk)
        self.assertSequenceEqual(user_1_from_db.article_set.all(), [self.a3])
        user_1_from_db.username = "Paul"
        self.a3.authors.set([user_2.username])
        user_1_from_db.save()
        # Assign a different article.
        self.a4.authors.add(user_1_from_db.username)
        self.assertSequenceEqual(user_1_from_db.article_set.all(), [self.a4])
        # Refresh the instance with an evaluated related manager.
        user_1.refresh_from_db()
        self.assertEqual(user_1.username, "Paul")
        self.assertSequenceEqual(user_1.article_set.all(), [self.a4])

    def test_add_remove_invalid_type(self):
        msg = "Field 'id' expected a number but got 'invalid'."
        for method in ["add", "remove"]:
            with self.subTest(method), self.assertRaisesMessage(ValueError, msg):
                getattr(self.a1.publications, method)("invalid")

    def test_reverse_add(self):
        # Adding via the 'other' end of an m2m
        """

        Tests the addition of articles to a publication and the automatic reversal of the article-publication relationship.

        This test case verifies that when an article is added to a publication, the publication is also added to the article's publication set.
        Additionally, it checks that the articles in a publication's article set are ordered in reverse based on the order in which they were added.

        The test covers the following scenarios:
        - Adding an existing article to a publication
        - Creating a new article and adding it to a publication
        - Verifying the automatic reversal of the article-publication relationship after adding an article to a publication
        - Checking the ordering of articles in a publication's article set after adding new articles

        """
        a5 = Article(headline="NASA finds intelligent life on Mars")
        a5.save()
        self.p2.article_set.add(a5)
        self.assertSequenceEqual(
            self.p2.article_set.all(),
            [self.a3, a5, self.a2, self.a4],
        )
        self.assertSequenceEqual(a5.publications.all(), [self.p2])

        # Adding via the other end using keywords
        a6 = self.p2.article_set.create(headline="Carbon-free diet works wonders")
        self.assertSequenceEqual(
            self.p2.article_set.all(),
            [a6, self.a3, a5, self.a2, self.a4],
        )
        a6 = self.p2.article_set.all()[3]
        self.assertSequenceEqual(
            a6.publications.all(),
            [self.p4, self.p2, self.p3, self.p1],
        )

    @skipUnlessDBFeature("supports_ignore_conflicts")
    def test_fast_add_ignore_conflicts(self):
        """
        A single query is necessary to add auto-created through instances if
        the database backend supports bulk_create(ignore_conflicts) and no
        m2m_changed signals receivers are connected.
        """
        with self.assertNumQueries(1):
            self.a1.publications.add(self.p1, self.p2)

    @skipIfDBFeature("supports_ignore_conflicts")
    def test_add_existing_different_type(self):
        # A single SELECT query is necessary to compare existing values to the
        # provided one; no INSERT should be attempted.
        """
        Tests adding an existing object of a different type to a collection.

        This test case verifies that adding an object that already exists in the collection,
        but with a different type (e.g. a string primary key instead of an object),
        results in the correct object being retrieved. The test also ensures that only
        a single database query is executed during this operation.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Raises
        ------
        AssertionError : If the test fails to add the existing object or retrieve it correctly.

        """
        with self.assertNumQueries(1):
            self.a1.publications.add(str(self.p1.pk))
        self.assertEqual(self.a1.publications.get(), self.p1)

    @skipUnlessDBFeature("supports_ignore_conflicts")
    def test_slow_add_ignore_conflicts(self):
        """

        Tests whether the add operation with ignore conflicts functionality works correctly.

        This test case specifically checks if the _get_missing_target_ids method is called 
        when adding a publication with ignore conflicts option. 

        The test simulates a scenario where a publication is added to a list of publications 
        while ignoring any conflicts that may arise during the addition process. 

        It verifies that the required methods are called as expected, ensuring the correct 
        functionality of the add operation with ignore conflicts.

        """
        manager_cls = self.a1.publications.__class__
        # Simulate a race condition between the missing ids retrieval and
        # the bulk insertion attempt.
        missing_target_ids = {self.p1.id}
        # Disable fast-add to test the case where the slow add path is taken.
        add_plan = (True, False, False)
        with mock.patch.object(
            manager_cls, "_get_missing_target_ids", return_value=missing_target_ids
        ) as mocked:
            with mock.patch.object(manager_cls, "_get_add_plan", return_value=add_plan):
                self.a1.publications.add(self.p1)
        mocked.assert_called_once()

    def test_related_sets(self):
        # Article objects have access to their related Publication objects.
        """

        Tests the relationships between articles and publications in the database.

        Verifies that each article is correctly associated with its related publications and
        that each publication is correctly associated with its related articles.
        The test checks the following relationships:
        - An article's publications
        - A publication's related articles

        The function uses the Django testing framework to assert that the expected
        sequences of objects match the actual sequences retrieved from the database.

        """
        self.assertSequenceEqual(self.a1.publications.all(), [self.p1])
        self.assertSequenceEqual(
            self.a2.publications.all(),
            [self.p4, self.p2, self.p3, self.p1],
        )
        # Publication objects have access to their related Article objects.
        self.assertSequenceEqual(
            self.p2.article_set.all(),
            [self.a3, self.a2, self.a4],
        )
        self.assertSequenceEqual(
            self.p1.article_set.all(),
            [self.a1, self.a2],
        )
        self.assertSequenceEqual(
            Publication.objects.get(id=self.p4.id).article_set.all(),
            [self.a2],
        )

    def test_selects(self):
        # We can perform kwarg queries across m2m relationships
        self.assertSequenceEqual(
            Article.objects.filter(publications__id__exact=self.p1.id),
            [self.a1, self.a2],
        )
        self.assertSequenceEqual(
            Article.objects.filter(publications__pk=self.p1.id),
            [self.a1, self.a2],
        )
        self.assertSequenceEqual(
            Article.objects.filter(publications=self.p1.id),
            [self.a1, self.a2],
        )
        self.assertSequenceEqual(
            Article.objects.filter(publications=self.p1),
            [self.a1, self.a2],
        )
        self.assertSequenceEqual(
            Article.objects.filter(publications__title__startswith="Science"),
            [self.a3, self.a2, self.a2, self.a4],
        )
        self.assertSequenceEqual(
            Article.objects.filter(
                publications__title__startswith="Science"
            ).distinct(),
            [self.a3, self.a2, self.a4],
        )

        # The count() function respects distinct() as well.
        self.assertEqual(
            Article.objects.filter(publications__title__startswith="Science").count(), 4
        )
        self.assertEqual(
            Article.objects.filter(publications__title__startswith="Science")
            .distinct()
            .count(),
            3,
        )
        self.assertSequenceEqual(
            Article.objects.filter(
                publications__in=[self.p1.id, self.p2.id]
            ).distinct(),
            [self.a1, self.a3, self.a2, self.a4],
        )
        self.assertSequenceEqual(
            Article.objects.filter(publications__in=[self.p1.id, self.p2]).distinct(),
            [self.a1, self.a3, self.a2, self.a4],
        )
        self.assertSequenceEqual(
            Article.objects.filter(publications__in=[self.p1, self.p2]).distinct(),
            [self.a1, self.a3, self.a2, self.a4],
        )

        # Excluding a related item works as you would expect, too (although the SQL
        # involved is a little complex).
        self.assertSequenceEqual(
            Article.objects.exclude(publications=self.p2),
            [self.a1],
        )

    def test_reverse_selects(self):
        # Reverse m2m queries are supported (i.e., starting at the table that
        # doesn't have a ManyToManyField).
        python_journal = [self.p1]
        self.assertSequenceEqual(
            Publication.objects.filter(id__exact=self.p1.id), python_journal
        )
        self.assertSequenceEqual(
            Publication.objects.filter(pk=self.p1.id), python_journal
        )
        self.assertSequenceEqual(
            Publication.objects.filter(article__headline__startswith="NASA"),
            [self.p4, self.p2, self.p2, self.p3, self.p1],
        )

        self.assertSequenceEqual(
            Publication.objects.filter(article__id__exact=self.a1.id), python_journal
        )
        self.assertSequenceEqual(
            Publication.objects.filter(article__pk=self.a1.id), python_journal
        )
        self.assertSequenceEqual(
            Publication.objects.filter(article=self.a1.id), python_journal
        )
        self.assertSequenceEqual(
            Publication.objects.filter(article=self.a1), python_journal
        )

        self.assertSequenceEqual(
            Publication.objects.filter(article__in=[self.a1.id, self.a2.id]).distinct(),
            [self.p4, self.p2, self.p3, self.p1],
        )
        self.assertSequenceEqual(
            Publication.objects.filter(article__in=[self.a1.id, self.a2]).distinct(),
            [self.p4, self.p2, self.p3, self.p1],
        )
        self.assertSequenceEqual(
            Publication.objects.filter(article__in=[self.a1, self.a2]).distinct(),
            [self.p4, self.p2, self.p3, self.p1],
        )

    def test_delete(self):
        # If we delete a Publication, its Articles won't be able to access it.
        """

        Tests the deletion of publications and articles.

        This test case verifies the correct deletion of publications and articles, 
        ensuring that the relationships between them are properly updated. 
        It checks that the deleted publication is removed from the list of all publications 
        and from the article it was associated with. 
        Additionally, it tests the deletion of an article and verifies that the remaining 
        articles are correctly associated with their respective publications.

        """
        self.p1.delete()
        self.assertSequenceEqual(
            Publication.objects.all(),
            [self.p4, self.p2, self.p3],
        )
        self.assertSequenceEqual(self.a1.publications.all(), [])
        # If we delete an Article, its Publications won't be able to access it.
        self.a2.delete()
        self.assertSequenceEqual(
            Article.objects.all(),
            [self.a1, self.a3, self.a4],
        )
        self.assertSequenceEqual(
            self.p2.article_set.all(),
            [self.a3, self.a4],
        )

    def test_bulk_delete(self):
        # Bulk delete some Publications - references to deleted publications should go
        Publication.objects.filter(title__startswith="Science").delete()
        self.assertSequenceEqual(
            Publication.objects.all(),
            [self.p4, self.p1],
        )
        self.assertSequenceEqual(
            Article.objects.all(),
            [self.a1, self.a3, self.a2, self.a4],
        )
        self.assertSequenceEqual(
            self.a2.publications.all(),
            [self.p4, self.p1],
        )

        # Bulk delete some articles - references to deleted objects should go
        q = Article.objects.filter(headline__startswith="Django")
        self.assertSequenceEqual(q, [self.a1])
        q.delete()
        # After the delete, the QuerySet cache needs to be cleared,
        # and the referenced objects should be gone
        self.assertSequenceEqual(q, [])
        self.assertSequenceEqual(self.p1.article_set.all(), [self.a2])

    def test_remove(self):
        # Removing publication from an article:
        """
        Tests the removal of articles from a publication.

        Verifies that articles can be successfully removed from a publication, and that the removal is reflected on both the publication and the article. Checks that the publication's article set is updated correctly and that the article's publication set is cleared.

        This test case covers the following scenarios:

        * Removing an article from a publication
        * Verifying the publication's article set after removal
        * Verifying the article's publication set after removal
        """
        self.assertSequenceEqual(
            self.p2.article_set.all(),
            [self.a3, self.a2, self.a4],
        )
        self.a4.publications.remove(self.p2)
        self.assertSequenceEqual(
            self.p2.article_set.all(),
            [self.a3, self.a2],
        )
        self.assertSequenceEqual(self.a4.publications.all(), [])
        # And from the other end
        self.p2.article_set.remove(self.a3)
        self.assertSequenceEqual(self.p2.article_set.all(), [self.a2])
        self.assertSequenceEqual(self.a3.publications.all(), [])

    def test_set(self):
        """
        ýviges an article set.

        Tests setting, updating and clearing of article sets for publications 
        and the corresponding publication sets for articles. It covers the 
        following scenarios:

        *   Setting an article set for a publication and verifying the publication 
            is added to the publication set of the respective articles.
        *   Updating an article set by replacing the current set with a new one 
            and checking the changes are reflected correctly in both article set 
            and publication set.
        *   Clearing an article set and verifying the publication set of the 
            respective articles is updated accordingly.
        *   Using the `clear=True` parameter to replace the current set entirely 
            with a new one and ensuring the changes are correctly reflected in 
            both the article set and publication set.
        """
        self.p2.article_set.set([self.a4, self.a3])
        self.assertSequenceEqual(
            self.p2.article_set.all(),
            [self.a3, self.a4],
        )
        self.assertSequenceEqual(self.a4.publications.all(), [self.p2])
        self.a4.publications.set([self.p3.id])
        self.assertSequenceEqual(self.p2.article_set.all(), [self.a3])
        self.assertSequenceEqual(self.a4.publications.all(), [self.p3])

        self.p2.article_set.set([])
        self.assertSequenceEqual(self.p2.article_set.all(), [])
        self.a4.publications.set([])
        self.assertSequenceEqual(self.a4.publications.all(), [])

        self.p2.article_set.set([self.a4, self.a3], clear=True)
        self.assertSequenceEqual(
            self.p2.article_set.all(),
            [self.a3, self.a4],
        )
        self.assertSequenceEqual(self.a4.publications.all(), [self.p2])
        self.a4.publications.set([self.p3.id], clear=True)
        self.assertSequenceEqual(self.p2.article_set.all(), [self.a3])
        self.assertSequenceEqual(self.a4.publications.all(), [self.p3])

        self.p2.article_set.set([], clear=True)
        self.assertSequenceEqual(self.p2.article_set.all(), [])
        self.a4.publications.set([], clear=True)
        self.assertSequenceEqual(self.a4.publications.all(), [])

    def test_set_existing_different_type(self):
        # Existing many-to-many relations remain the same for values provided
        # with a different type.
        """
        .EventArgs are not relevant for this test
        Tests that setting the article set on a publication with existing articles of a different type (string id) retains the previously associated articles.
        """
        ids = set(
            Publication.article_set.through.objects.filter(
                article__in=[self.a4, self.a3],
                publication=self.p2,
            ).values_list("id", flat=True)
        )
        self.p2.article_set.set([str(self.a4.pk), str(self.a3.pk)])
        new_ids = set(
            Publication.article_set.through.objects.filter(
                publication=self.p2,
            ).values_list("id", flat=True)
        )
        self.assertEqual(ids, new_ids)

    def test_assign_forward(self):
        msg = (
            "Direct assignment to the reverse side of a many-to-many set is "
            "prohibited. Use article_set.set() instead."
        )
        with self.assertRaisesMessage(TypeError, msg):
            self.p2.article_set = [self.a4, self.a3]

    def test_assign_reverse(self):
        msg = (
            "Direct assignment to the forward side of a many-to-many "
            "set is prohibited. Use publications.set() instead."
        )
        with self.assertRaisesMessage(TypeError, msg):
            self.a1.publications = [self.p1, self.p2]

    def test_assign(self):
        # Relation sets can be assigned using set().
        self.p2.article_set.set([self.a4, self.a3])
        self.assertSequenceEqual(
            self.p2.article_set.all(),
            [self.a3, self.a4],
        )
        self.assertSequenceEqual(self.a4.publications.all(), [self.p2])
        self.a4.publications.set([self.p3.id])
        self.assertSequenceEqual(self.p2.article_set.all(), [self.a3])
        self.assertSequenceEqual(self.a4.publications.all(), [self.p3])

        # An alternate to calling clear() is to set an empty set.
        self.p2.article_set.set([])
        self.assertSequenceEqual(self.p2.article_set.all(), [])
        self.a4.publications.set([])
        self.assertSequenceEqual(self.a4.publications.all(), [])

    def test_assign_ids(self):
        # Relation sets can also be set using primary key values
        """

        Tests the assignment of IDs to articles and publications, ensuring correct
        establishment and removal of relationships between them.

        Verifies that articles can be correctly added and removed from a publication,
        and that the corresponding publications are also updated in the article's
        publication list. This ensures data consistency and proper management of many-to-many relationships.

        """
        self.p2.article_set.set([self.a4.id, self.a3.id])
        self.assertSequenceEqual(
            self.p2.article_set.all(),
            [self.a3, self.a4],
        )
        self.assertSequenceEqual(self.a4.publications.all(), [self.p2])
        self.a4.publications.set([self.p3.id])
        self.assertSequenceEqual(self.p2.article_set.all(), [self.a3])
        self.assertSequenceEqual(self.a4.publications.all(), [self.p3])

    def test_forward_assign_with_queryset(self):
        # Querysets used in m2m assignments are pre-evaluated so their value
        # isn't affected by the clearing operation in ManyRelatedManager.set()
        # (#19816).
        self.a1.publications.set([self.p1, self.p2])

        qs = self.a1.publications.filter(title="The Python Journal")
        self.a1.publications.set(qs)

        self.assertEqual(1, self.a1.publications.count())
        self.assertEqual(1, qs.count())

    def test_reverse_assign_with_queryset(self):
        # Querysets used in M2M assignments are pre-evaluated so their value
        # isn't affected by the clearing operation in ManyRelatedManager.set()
        # (#19816).
        """

        Tests the behavior of assigning a queryset to a reverse relationship attribute.

        Verifies that when a queryset is assigned to a reverse relationship attribute,
        only the objects matching the queryset filter are retained in the relationship,
        and the count of related objects is updated accordingly.

        Checks for the expected count of related objects both before and after the assignment,
        ensuring that the queryset filter is applied correctly.

        """
        self.p1.article_set.set([self.a1, self.a2])

        qs = self.p1.article_set.filter(
            headline="Django lets you build web apps easily"
        )
        self.p1.article_set.set(qs)

        self.assertEqual(1, self.p1.article_set.count())
        self.assertEqual(1, qs.count())

    def test_clear(self):
        # Relation sets can be cleared:
        self.p2.article_set.clear()
        self.assertSequenceEqual(self.p2.article_set.all(), [])
        self.assertSequenceEqual(self.a4.publications.all(), [])

        # And you can clear from the other end
        self.p2.article_set.add(self.a3, self.a4)
        self.assertSequenceEqual(
            self.p2.article_set.all(),
            [self.a3, self.a4],
        )
        self.assertSequenceEqual(self.a4.publications.all(), [self.p2])
        self.a4.publications.clear()
        self.assertSequenceEqual(self.a4.publications.all(), [])
        self.assertSequenceEqual(self.p2.article_set.all(), [self.a3])

    def test_clear_after_prefetch(self):
        a4 = Article.objects.prefetch_related("publications").get(id=self.a4.id)
        self.assertSequenceEqual(a4.publications.all(), [self.p2])
        a4.publications.clear()
        self.assertSequenceEqual(a4.publications.all(), [])

    def test_remove_after_prefetch(self):
        """

        Tests the removal of a publication from an article after prefetching related publications.

        This test case verifies that a publication is correctly removed from an article's
        publications set after the article's publications have been prefetched. It checks
        that the publication exists in the article's publications before removal and that
        it no longer exists after removal.

        """
        a4 = Article.objects.prefetch_related("publications").get(id=self.a4.id)
        self.assertSequenceEqual(a4.publications.all(), [self.p2])
        a4.publications.remove(self.p2)
        self.assertSequenceEqual(a4.publications.all(), [])

    def test_add_after_prefetch(self):
        a4 = Article.objects.prefetch_related("publications").get(id=self.a4.id)
        self.assertEqual(a4.publications.count(), 1)
        a4.publications.add(self.p1)
        self.assertEqual(a4.publications.count(), 2)

    def test_create_after_prefetch(self):
        """
        Tests the creation of a new publication after prefetching related publications for an article, verifying that the newly created publication is included in the article's publications.
        """
        a4 = Article.objects.prefetch_related("publications").get(id=self.a4.id)
        self.assertSequenceEqual(a4.publications.all(), [self.p2])
        p5 = a4.publications.create(title="Django beats")
        self.assertCountEqual(a4.publications.all(), [self.p2, p5])

    def test_set_after_prefetch(self):
        """
        Tests the ability to set publications on an article after prefetching related objects.

        This test case verifies that the count of publications associated with an article is correctly updated
        when the set of publications is modified after prefetching the related objects.

        The test checks the following scenarios:
        - The initial count of publications after prefetching
        - The count after adding a publication to the set
        - The count after removing a publication from the set

        It ensures that the database is updated correctly and that the article object reflects the changes
        made to its publications set.
        """
        a4 = Article.objects.prefetch_related("publications").get(id=self.a4.id)
        self.assertEqual(a4.publications.count(), 1)
        a4.publications.set([self.p2, self.p1])
        self.assertEqual(a4.publications.count(), 2)
        a4.publications.set([self.p1])
        self.assertEqual(a4.publications.count(), 1)

    def test_add_then_remove_after_prefetch(self):
        """

        Tests the addition and subsequent removal of a publication from an article 
        after prefetching its publications.

        Verifies that the article starts with a single publication, adds a new publication 
        successfully, and then removes the added publication, restoring the original state.

        """
        a4 = Article.objects.prefetch_related("publications").get(id=self.a4.id)
        self.assertEqual(a4.publications.count(), 1)
        a4.publications.add(self.p1)
        self.assertEqual(a4.publications.count(), 2)
        a4.publications.remove(self.p1)
        self.assertSequenceEqual(a4.publications.all(), [self.p2])

    def test_inherited_models_selects(self):
        """
        #24156 - Objects from child models where the parent's m2m field uses
        related_name='+' should be retrieved correctly.
        """
        a = InheritedArticleA.objects.create()
        b = InheritedArticleB.objects.create()
        a.publications.add(self.p1, self.p2)
        self.assertSequenceEqual(
            a.publications.all(),
            [self.p2, self.p1],
        )
        self.assertSequenceEqual(b.publications.all(), [])
        b.publications.add(self.p3)
        self.assertSequenceEqual(
            a.publications.all(),
            [self.p2, self.p1],
        )
        self.assertSequenceEqual(b.publications.all(), [self.p3])

    def test_custom_default_manager_exists_count(self):
        """
        Tests if the custom default manager correctly handles the exists and count methods for related articles.

        This test case verifies that the count and exists methods are correctly implemented 
        for the article_set manager, ensuring that the number of articles and the existence 
        of articles are accurately determined for a given publication. It also checks that 
        the SQL queries generated by these methods include the necessary JOIN operations.

        The test covers two main scenarios: one where a publication has associated articles 
        and another where a publication does not have any associated articles. In both cases, 
        it validates the behavior of the exists and count methods, as well as the generated SQL queries.
        """
        a5 = Article.objects.create(headline="deleted")
        a5.publications.add(self.p2)
        with self.assertNumQueries(2) as ctx:
            self.assertEqual(
                self.p2.article_set.count(), self.p2.article_set.all().count()
            )
        self.assertIn("JOIN", ctx.captured_queries[0]["sql"])
        with self.assertNumQueries(2) as ctx:
            self.assertEqual(
                self.p3.article_set.exists(), self.p3.article_set.all().exists()
            )
        self.assertIn("JOIN", ctx.captured_queries[0]["sql"])

    def test_get_prefetch_queryset_warning(self):
        """

        Tests that a warning is raised when the deprecated get_prefetch_queryset method is used.

        The function verifies that using get_prefetch_queryset triggers a RemovedInDjango60Warning, 
        indicating that this method will be removed in Django 6.0 and should be replaced with get_prefetch_querysets.

        """
        articles = Article.objects.all()
        msg = (
            "get_prefetch_queryset() is deprecated. Use get_prefetch_querysets() "
            "instead."
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            self.a1.publications.get_prefetch_queryset(articles)

    def test_get_prefetch_querysets_invalid_querysets_length(self):
        articles = Article.objects.all()
        msg = (
            "querysets argument of get_prefetch_querysets() should have a length of 1."
        )
        with self.assertRaisesMessage(ValueError, msg):
            self.a1.publications.get_prefetch_querysets(
                instances=articles,
                querysets=[Publication.objects.all(), Publication.objects.all()],
            )


class ManyToManyQueryTests(TestCase):
    """
    SQL is optimized to reference the through table without joining against the
    related table when using count() and exists() functions on a queryset for
    many to many relations. The optimization applies to the case where there
    are no filters.
    """

    @classmethod
    def setUpTestData(cls):
        cls.article = Article.objects.create(
            headline="Django lets you build Web apps easily"
        )
        cls.nullable_target_article = NullableTargetArticle.objects.create(
            headline="The python is good"
        )
        NullablePublicationThrough.objects.create(
            article=cls.nullable_target_article, publication=None
        )

    @skipUnlessDBFeature("supports_foreign_keys")
    def test_count_join_optimization(self):
        """

        Tests the optimization of count queries on related objects.

        Verifies that when counting related objects using a foreign key, the database
        query does not include a JOIN statement, which can improve performance.
        Additionally, confirms that the count is accurate for a relationship where the
        target object is nullable, returning 0 when no related objects exist.

        """
        with self.assertNumQueries(1) as ctx:
            self.article.publications.count()
        self.assertNotIn("JOIN", ctx.captured_queries[0]["sql"])

        with self.assertNumQueries(1) as ctx:
            self.article.publications.count()
        self.assertNotIn("JOIN", ctx.captured_queries[0]["sql"])
        self.assertEqual(self.nullable_target_article.publications.count(), 0)

    def test_count_join_optimization_disabled(self):
        with (
            mock.patch.object(connection.features, "supports_foreign_keys", False),
            self.assertNumQueries(1) as ctx,
        ):
            self.article.publications.count()

        self.assertIn("JOIN", ctx.captured_queries[0]["sql"])

    @skipUnlessDBFeature("supports_foreign_keys")
    def test_exists_join_optimization(self):
        with self.assertNumQueries(1) as ctx:
            self.article.publications.exists()
        self.assertNotIn("JOIN", ctx.captured_queries[0]["sql"])

        self.article.publications.prefetch_related()
        with self.assertNumQueries(1) as ctx:
            self.article.publications.exists()
        self.assertNotIn("JOIN", ctx.captured_queries[0]["sql"])
        self.assertIs(self.nullable_target_article.publications.exists(), False)

    def test_exists_join_optimization_disabled(self):
        """

        Tests that when join optimization is disabled, the exists query for a related object set uses a JOIN operation.

        This test case verifies that the database query generated by the `exists` method
        includes a JOIN clause when the database connection does not support foreign keys,
        ensuring the correct query is executed even in the absence of foreign key support.

        The test confirms that exactly one database query is executed and that the query's
        SQL contains a JOIN operation, demonstrating the expected behavior.

        """
        with (
            mock.patch.object(connection.features, "supports_foreign_keys", False),
            self.assertNumQueries(1) as ctx,
        ):
            self.article.publications.exists()

        self.assertIn("JOIN", ctx.captured_queries[0]["sql"])

    def test_prefetch_related_no_queries_optimization_disabled(self):
        """

        Tests that prefetch_related optimization is disabled when counting or checking existence of related objects.

        When an ORM query uses prefetch_related to fetch related objects, subsequent operations on those related objects 
        should not generate additional database queries if they have already been prefetched. This test verifies that 
        counting and existence checks on prefetched related objects do not incur additional queries.

        """
        qs = Article.objects.prefetch_related("publications")
        article = qs.get()
        with self.assertNumQueries(0):
            article.publications.count()
        with self.assertNumQueries(0):
            article.publications.exists()
