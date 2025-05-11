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
        """
        Sets up test data for publications and articles, creating a set of predefined publications and articles with associated relationships for testing purposes.
        """
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
        Test the add method of a many-to-many relationship between Article and Publication models. 
        Ensures that attempting to access the relationship before saving the Article instance raises a ValueError, 
        and that adding Publication instances to Article works as expected, including handling duplicate additions and incorrect object types. 
        Also tests the ability to create a new Publication instance directly on the Article instance.
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
        """
        Tests the addition, removal, and replacement of publications by primary key in an Article instance.
        """
        a5 = Article.objects.create(headline="Django lets you create web apps easily")
        a5.publications.add(self.p1.pk)
        self.assertSequenceEqual(a5.publications.all(), [self.p1])
        a5.publications.set([self.p2.pk])
        self.assertSequenceEqual(a5.publications.all(), [self.p2])
        a5.publications.remove(self.p2.pk)
        self.assertSequenceEqual(a5.publications.all(), [])

    def test_add_remove_set_by_to_field(self):
        """
        Tests the addition, removal, and replacement of authors in an Article instance using the to_field argument, ensuring correct functionality of the many-to-many relationship between articles and authors.
        """
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
        $: Tests the behavior of a related manager when the underlying object is refreshed from the database, ensuring that changes to the object and its relations are correctly reflected.
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
        Tests the reverse relationship behavior of articles and publications, 
        ensuring articles are correctly added to a publication and the publications 
        are correctly assigned to the article, and that the many-to-many relationship 
        is maintained in a specific order.
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
        with self.assertNumQueries(1):
            self.a1.publications.add(str(self.p1.pk))
        self.assertEqual(self.a1.publications.get(), self.p1)

    @skipUnlessDBFeature("supports_ignore_conflicts")
    def test_slow_add_ignore_conflicts(self):
        """
        Test that adding a publication with ignore conflicts works as expected when the database supports it, 
        verifying that the required methods are called during the operation.
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
        Tests the relationships between articles and publications, verifying that the correct publications are associated with each article and vice versa.
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
        """
        Tests the filtering and lookup functionality for articles based on their publications.

         Verifies that articles can be retrieved based on publication id, primary key, or publication object, and that lookup types such as 'exact', 'startswith', and 'in' work as expected.

         Also tests the distinct method for removing duplicates and the count method for getting the number of results, as well as the exclude method for excluding articles based on publication.

         Validates the results of these lookups to ensure that the correct articles are returned in the expected order.
        """
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
        """
        Tests the correctness of Django ORM's reverse select queries, ensuring that different lookup methods and syntaxes return the expected publications based on related article instances.
        """
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
        Verifies that publications and articles are correctly removed 
        from the database and their respective relationships are updated.

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
        """

        Tests the functionality of bulk deletion in the database.

        Checks that objects are correctly removed from the database and that 
        related objects are updated accordingly. 

        """
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
        Tests the removal of articles from a publication and the corresponding removal of the publication from the article's publications.

        Verifies that the article set of the publication and the publication set of the articles are correctly updated after removal operations.
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
        Tests the functionality of setting and clearing article sets for publications, ensuring that the articles are correctly added, removed, and updated in both the publication's article set and the article's publications.
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
        """
        Tests the assignment and reassignment of articles to a publication, 
        verifying that the relationships are correctly updated on both the publication 
        and article objects.
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

        # An alternate to calling clear() is to set an empty set.
        self.p2.article_set.set([])
        self.assertSequenceEqual(self.p2.article_set.all(), [])
        self.a4.publications.set([])
        self.assertSequenceEqual(self.a4.publications.all(), [])

    def test_assign_ids(self):
        # Relation sets can also be set using primary key values
        """
        Tests the assignment of IDs to objects in a many-to-many relationship, ensuring correct membership and synchronization between related object sets.
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
        """
        Tests the forward assignment of a queryset to a relation field, verifying that it correctly updates the related objects.
        """
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
        Tests that assigning a queryset to a reverse relationship manager updates the relationship correctly, ensuring that only the objects matching the queryset are retained in the relationship.
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
        """

        Tests the clearing of many-to-many relationships between articles and publications.

        Verifies that clearing a publication's articles removes the relationship from both the publication and the articles.

        """
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
        a4 = Article.objects.prefetch_related("publications").get(id=self.a4.id)
        self.assertSequenceEqual(a4.publications.all(), [self.p2])
        p5 = a4.publications.create(title="Django beats")
        self.assertCountEqual(a4.publications.all(), [self.p2, p5])

    def test_set_after_prefetch(self):
        """
        Tests the ability to set the publications of an article after prefetching the related publications, ensuring the correct count of publications is maintained.
        """
        a4 = Article.objects.prefetch_related("publications").get(id=self.a4.id)
        self.assertEqual(a4.publications.count(), 1)
        a4.publications.set([self.p2, self.p1])
        self.assertEqual(a4.publications.count(), 2)
        a4.publications.set([self.p1])
        self.assertEqual(a4.publications.count(), 1)

    def test_add_then_remove_after_prefetch(self):
        """
        Tests that adding and then removing a publication from an article after prefetching works as expected.
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

        Verifies that a default manager exists and its count and exists methods behave correctly
        by testing the article_set relationship on a Publication instance.

        The test checks that the count and exists methods execute with the expected number of queries
        and that the generated SQL includes a JOIN clause.

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
        」Tests that the count() method of a related fieldset does not perform an SQL JOIN when retrieving the count of related objects, verifying query optimization for foreign key relationships.
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
        """
        Tests the optimization of exists() queries for joined models, ensuring no JOIN is performed in the SQL query when using exists() after a prefetch_related() call or on a nullable foreign key, verifying efficient database query handling.
        """
        with self.assertNumQueries(1) as ctx:
            self.article.publications.exists()
        self.assertNotIn("JOIN", ctx.captured_queries[0]["sql"])

        self.article.publications.prefetch_related()
        with self.assertNumQueries(1) as ctx:
            self.article.publications.exists()
        self.assertNotIn("JOIN", ctx.captured_queries[0]["sql"])
        self.assertIs(self.nullable_target_article.publications.exists(), False)

    def test_exists_join_optimization_disabled(self):
        with (
            mock.patch.object(connection.features, "supports_foreign_keys", False),
            self.assertNumQueries(1) as ctx,
        ):
            self.article.publications.exists()

        self.assertIn("JOIN", ctx.captured_queries[0]["sql"])

    def test_prefetch_related_no_queries_optimization_disabled(self):
        """
        Tests that prefetch_related optimization is disabled when accessing related objects, even after the initial query, ensuring no additional database queries are made.
        """
        qs = Article.objects.prefetch_related("publications")
        article = qs.get()
        with self.assertNumQueries(0):
            article.publications.count()
        with self.assertNumQueries(0):
            article.publications.exists()
