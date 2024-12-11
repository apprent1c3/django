import copy
import datetime
import pickle
from operator import attrgetter

from django.core.exceptions import FieldError
from django.db import models
from django.test import SimpleTestCase, TestCase, skipUnlessDBFeature
from django.test.utils import isolate_apps
from django.utils import translation
from django.utils.deprecation import RemovedInDjango60Warning

from .models import (
    Article,
    ArticleIdea,
    ArticleTag,
    ArticleTranslation,
    Country,
    Friendship,
    Group,
    Membership,
    NewsArticle,
    Person,
)

# Note that these tests are testing internal implementation details.
# ForeignObject is not part of public API.


class MultiColumnFKTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Creating countries
        cls.usa = Country.objects.create(name="United States of America")
        cls.soviet_union = Country.objects.create(name="Soviet Union")
        # Creating People
        cls.bob = Person.objects.create(name="Bob", person_country=cls.usa)
        cls.jim = Person.objects.create(name="Jim", person_country=cls.usa)
        cls.george = Person.objects.create(name="George", person_country=cls.usa)

        cls.jane = Person.objects.create(name="Jane", person_country=cls.soviet_union)
        cls.mark = Person.objects.create(name="Mark", person_country=cls.soviet_union)
        cls.sam = Person.objects.create(name="Sam", person_country=cls.soviet_union)

        # Creating Groups
        cls.kgb = Group.objects.create(name="KGB", group_country=cls.soviet_union)
        cls.cia = Group.objects.create(name="CIA", group_country=cls.usa)
        cls.republican = Group.objects.create(name="Republican", group_country=cls.usa)
        cls.democrat = Group.objects.create(name="Democrat", group_country=cls.usa)

    def test_get_succeeds_on_multicolumn_match(self):
        # Membership objects have access to their related Person if both
        # country_ids match between them
        membership = Membership.objects.create(
            membership_country_id=self.usa.id,
            person_id=self.bob.id,
            group_id=self.cia.id,
        )

        person = membership.person
        self.assertEqual((person.id, person.name), (self.bob.id, "Bob"))

    def test_get_fails_on_multicolumn_mismatch(self):
        # Membership objects returns DoesNotExist error when there is no
        # Person with the same id and country_id
        """
        Tests that attempting to access a related object ('person') on a Membership instance fails when the underlying database query encounters a multicolumn mismatch.

            Specifically, verifies that a `Person.DoesNotExist` exception is raised when trying to retrieve the 'person' attribute from a Membership object that has been created with an incompatible combination of foreign keys.

            This test case ensures the correctness of the Membership model's relationships and the handling of database query errors in the presence of multicolumn mismatch scenarios.
        """
        membership = Membership.objects.create(
            membership_country_id=self.usa.id,
            person_id=self.jane.id,
            group_id=self.cia.id,
        )

        with self.assertRaises(Person.DoesNotExist):
            getattr(membership, "person")

    def test_reverse_query_returns_correct_result(self):
        # Creating a valid membership because it has the same country has the person
        """

        Test the functionality of reversing the query for membership objects.

        This test case ensures that when querying a person's membership, the correct membership object is returned.
        It verifies that the membership object's group and person attributes match the expected values.
        The test also checks that the query is executed efficiently, using only one database query.

        """
        Membership.objects.create(
            membership_country_id=self.usa.id,
            person_id=self.bob.id,
            group_id=self.cia.id,
        )

        # Creating an invalid membership because it has a different country has
        # the person.
        Membership.objects.create(
            membership_country_id=self.soviet_union.id,
            person_id=self.bob.id,
            group_id=self.republican.id,
        )

        with self.assertNumQueries(1):
            membership = self.bob.membership_set.get()
            self.assertEqual(membership.group_id, self.cia.id)
            self.assertIs(membership.person, self.bob)

    def test_query_filters_correctly(self):
        # Creating a to valid memberships
        Membership.objects.create(
            membership_country_id=self.usa.id,
            person_id=self.bob.id,
            group_id=self.cia.id,
        )
        Membership.objects.create(
            membership_country_id=self.usa.id,
            person_id=self.jim.id,
            group_id=self.cia.id,
        )

        # Creating an invalid membership
        Membership.objects.create(
            membership_country_id=self.soviet_union.id,
            person_id=self.george.id,
            group_id=self.cia.id,
        )

        self.assertQuerySetEqual(
            Membership.objects.filter(person__name__contains="o"),
            [self.bob.id],
            attrgetter("person_id"),
        )

    def test_reverse_query_filters_correctly(self):
        """

        Tests if the reverse query filters for membership date joined correctly.

        This test case checks whether the Person model's filter method with a 
        membership date joined greater than or equal to a specific timestamp 
        returns the correct results. Specifically, it verifies that people who 
        joined a group before the specified timestamp are excluded from the 
        query results, while those who joined on or after the timestamp are 
        included. The test also checks that the filter applies correctly 
        regardless of the membership country, and only returns people who are 
        members of a group with a matching date joined.

        The test query checks if the filtered Person objects match the expected 
        result by comparing the names of the people returned in the query 
        results with the expected names.

        """
        timemark = datetime.datetime.now(tz=datetime.timezone.utc).replace(tzinfo=None)
        timedelta = datetime.timedelta(days=1)

        # Creating a to valid memberships
        Membership.objects.create(
            membership_country_id=self.usa.id,
            person_id=self.bob.id,
            group_id=self.cia.id,
            date_joined=timemark - timedelta,
        )
        Membership.objects.create(
            membership_country_id=self.usa.id,
            person_id=self.jim.id,
            group_id=self.cia.id,
            date_joined=timemark + timedelta,
        )

        # Creating an invalid membership
        Membership.objects.create(
            membership_country_id=self.soviet_union.id,
            person_id=self.george.id,
            group_id=self.cia.id,
            date_joined=timemark + timedelta,
        )

        self.assertQuerySetEqual(
            Person.objects.filter(membership__date_joined__gte=timemark),
            ["Jim"],
            attrgetter("name"),
        )

    def test_forward_in_lookup_filters_correctly(self):
        """

        Tests that forward lookup in filter works correctly with Membership objects.

        Specifically, this test ensures that filtering by a list of Person objects or by a queryset of Person objects returns the expected Membership objects.

        It covers cases where the filter matches multiple Person objects and verifies that only the correct Membership objects are returned.

        """
        Membership.objects.create(
            membership_country_id=self.usa.id,
            person_id=self.bob.id,
            group_id=self.cia.id,
        )
        Membership.objects.create(
            membership_country_id=self.usa.id,
            person_id=self.jim.id,
            group_id=self.cia.id,
        )

        # Creating an invalid membership
        Membership.objects.create(
            membership_country_id=self.soviet_union.id,
            person_id=self.george.id,
            group_id=self.cia.id,
        )

        self.assertQuerySetEqual(
            Membership.objects.filter(person__in=[self.george, self.jim]),
            [
                self.jim.id,
            ],
            attrgetter("person_id"),
        )
        self.assertQuerySetEqual(
            Membership.objects.filter(person__in=Person.objects.filter(name="Jim")),
            [
                self.jim.id,
            ],
            attrgetter("person_id"),
        )

    def test_double_nested_query(self):
        """
        .. method:: test_double_nested_query

           Tests a double nested query to retrieve memberships based on friendship relationships.

           Verifies that the query correctly identifies memberships of people who are friends with others, 
           and also correctly excludes memberships of people who are not friends with anyone. This involves 
           checking for persons who are both the 'from' and 'to' side of a friendship, and then filtering 
           memberships based on these persons.
        """
        m1 = Membership.objects.create(
            membership_country_id=self.usa.id,
            person_id=self.bob.id,
            group_id=self.cia.id,
        )
        m2 = Membership.objects.create(
            membership_country_id=self.usa.id,
            person_id=self.jim.id,
            group_id=self.cia.id,
        )
        Friendship.objects.create(
            from_friend_country_id=self.usa.id,
            from_friend_id=self.bob.id,
            to_friend_country_id=self.usa.id,
            to_friend_id=self.jim.id,
        )
        self.assertSequenceEqual(
            Membership.objects.filter(
                person__in=Person.objects.filter(
                    from_friend__in=Friendship.objects.filter(
                        to_friend__in=Person.objects.all()
                    )
                )
            ),
            [m1],
        )
        self.assertSequenceEqual(
            Membership.objects.exclude(
                person__in=Person.objects.filter(
                    from_friend__in=Friendship.objects.filter(
                        to_friend__in=Person.objects.all()
                    )
                )
            ),
            [m2],
        )

    def test_query_does_not_mutate(self):
        """
        Recompiling the same subquery doesn't mutate it.
        """
        queryset = Friendship.objects.filter(to_friend__in=Person.objects.all())
        self.assertEqual(str(queryset.query), str(queryset.query))

    def test_select_related_foreignkey_forward_works(self):
        """
        Test that using select_related to fetch foreign key relationships 
        in the forward direction works as expected.

        This test checks that the data fetched using select_related 
        is correct and that it achieves the desired optimization 
        of reducing the number of database queries.

        The test creates sample Membership objects and then uses 
        select_related to fetch the related person objects, 
        verifying that the data is correct and that only one 
        database query is executed.
        """
        Membership.objects.create(
            membership_country=self.usa, person=self.bob, group=self.cia
        )
        Membership.objects.create(
            membership_country=self.usa, person=self.jim, group=self.democrat
        )

        with self.assertNumQueries(1):
            people = [
                m.person
                for m in Membership.objects.select_related("person").order_by("pk")
            ]

        normal_people = [m.person for m in Membership.objects.order_by("pk")]
        self.assertEqual(people, normal_people)

    def test_prefetch_foreignkey_forward_works(self):
        Membership.objects.create(
            membership_country=self.usa, person=self.bob, group=self.cia
        )
        Membership.objects.create(
            membership_country=self.usa, person=self.jim, group=self.democrat
        )

        with self.assertNumQueries(2):
            people = [
                m.person
                for m in Membership.objects.prefetch_related("person").order_by("pk")
            ]

        normal_people = [m.person for m in Membership.objects.order_by("pk")]
        self.assertEqual(people, normal_people)

    def test_prefetch_foreignkey_reverse_works(self):
        Membership.objects.create(
            membership_country=self.usa, person=self.bob, group=self.cia
        )
        Membership.objects.create(
            membership_country=self.usa, person=self.jim, group=self.democrat
        )
        with self.assertNumQueries(2):
            membership_sets = [
                list(p.membership_set.all())
                for p in Person.objects.prefetch_related("membership_set").order_by(
                    "pk"
                )
            ]

        with self.assertNumQueries(7):
            normal_membership_sets = [
                list(p.membership_set.all()) for p in Person.objects.order_by("pk")
            ]
        self.assertEqual(membership_sets, normal_membership_sets)

    def test_m2m_through_forward_returns_valid_members(self):
        # We start out by making sure that the Group 'CIA' has no members.
        self.assertQuerySetEqual(self.cia.members.all(), [])

        Membership.objects.create(
            membership_country=self.usa, person=self.bob, group=self.cia
        )
        Membership.objects.create(
            membership_country=self.usa, person=self.jim, group=self.cia
        )

        # Bob and Jim should be members of the CIA.

        self.assertQuerySetEqual(
            self.cia.members.all(), ["Bob", "Jim"], attrgetter("name")
        )

    def test_m2m_through_reverse_returns_valid_members(self):
        # We start out by making sure that Bob is in no groups.
        """
        Tests that the many-to-many relationship through the reverse side returns valid members.

        This test case verifies that a person's group membership is correctly retrieved when 
        the relationship is accessed through the person object. It checks for an initial empty 
        set of groups, then creates memberships for the person in multiple groups, and finally 
        asserts that the person's groups are correctly returned.

        The test covers the scenario where a person has multiple group affiliations, 
        ensuring that the many-to-many relationship through the reverse side accurately 
        represents the person's membership status.
        """
        self.assertQuerySetEqual(self.bob.groups.all(), [])

        Membership.objects.create(
            membership_country=self.usa, person=self.bob, group=self.cia
        )
        Membership.objects.create(
            membership_country=self.usa, person=self.bob, group=self.republican
        )

        # Bob should be in the CIA and a Republican
        self.assertQuerySetEqual(
            self.bob.groups.all(), ["CIA", "Republican"], attrgetter("name")
        )

    def test_m2m_through_forward_ignores_invalid_members(self):
        # We start out by making sure that the Group 'CIA' has no members.
        """
        Tests that the Many-To-Many relationship through the Membership model ignores invalid members when accessing the 'members' attribute of a Group instance.

        In this context, an invalid member refers to a person who is not a valid member of the Group due to the membership not being properly established. The test verifies that the Group's 'members' attribute returns an empty QuerySet, even when a Membership object is created, to ensure that only valid members are considered. 
        """
        self.assertQuerySetEqual(self.cia.members.all(), [])

        # Something adds jane to group CIA but Jane is in Soviet Union which
        # isn't CIA's country.
        Membership.objects.create(
            membership_country=self.usa, person=self.jane, group=self.cia
        )

        # There should still be no members in CIA
        self.assertQuerySetEqual(self.cia.members.all(), [])

    def test_m2m_through_reverse_ignores_invalid_members(self):
        # We start out by making sure that Jane has no groups.
        """
        Tests that many-to-many relationships through reverse relationships ignore invalid members.

        Verifies that a person's groups do not include groups where the person is a member 
        with an invalid membership country. Specifically, adding a membership with an 
        invalid country for a person does not add the corresponding group to the person's 
        groups when queried through the reverse relationship.
        """
        self.assertQuerySetEqual(self.jane.groups.all(), [])

        # Something adds jane to group CIA but Jane is in Soviet Union which
        # isn't CIA's country.
        Membership.objects.create(
            membership_country=self.usa, person=self.jane, group=self.cia
        )

        # Jane should still not be in any groups
        self.assertQuerySetEqual(self.jane.groups.all(), [])

    def test_m2m_through_on_self_works(self):
        """

        Verifies the correctness of many-to-many relationships through self-referential models.

        Tests the creation of a friendship between two individuals and checks if the 
        friendship is correctly reflected in the related objects' querysets.

        The test case ensures that initially, the individual has no friends and 
        subsequently, after creating a friendship with another individual, the 
        friendship is correctly established and the related object is included in 
        the queryset of friends.

        """
        self.assertQuerySetEqual(self.jane.friends.all(), [])

        Friendship.objects.create(
            from_friend_country=self.jane.person_country,
            from_friend=self.jane,
            to_friend_country=self.george.person_country,
            to_friend=self.george,
        )

        self.assertQuerySetEqual(
            self.jane.friends.all(), ["George"], attrgetter("name")
        )

    def test_m2m_through_on_self_ignores_mismatch_columns(self):
        """
        Tests that a many-to-many relationship with a through model ignores mismatched columns when defined on the same model, ensuring that incorrect relationships are not established.

        In this test case, we verify that the friends relationship of a person remains empty even after creating a friendship with a mismatched country. This ensures that the model correctly ignores relationships where the country of the from and to friends do not match.
        """
        self.assertQuerySetEqual(self.jane.friends.all(), [])

        # Note that we use ids instead of instances. This is because instances
        # on ForeignObject properties will set all related field off of the
        # given instance.
        Friendship.objects.create(
            from_friend_id=self.jane.id,
            to_friend_id=self.george.id,
            to_friend_country_id=self.jane.person_country_id,
            from_friend_country_id=self.george.person_country_id,
        )

        self.assertQuerySetEqual(self.jane.friends.all(), [])

    def test_prefetch_related_m2m_forward_works(self):
        Membership.objects.create(
            membership_country=self.usa, person=self.bob, group=self.cia
        )
        Membership.objects.create(
            membership_country=self.usa, person=self.jim, group=self.democrat
        )

        with self.assertNumQueries(2):
            members_lists = [
                list(g.members.all()) for g in Group.objects.prefetch_related("members")
            ]

        normal_members_lists = [list(g.members.all()) for g in Group.objects.all()]
        self.assertEqual(members_lists, normal_members_lists)

    def test_prefetch_related_m2m_reverse_works(self):
        Membership.objects.create(
            membership_country=self.usa, person=self.bob, group=self.cia
        )
        Membership.objects.create(
            membership_country=self.usa, person=self.jim, group=self.democrat
        )

        with self.assertNumQueries(2):
            groups_lists = [
                list(p.groups.all()) for p in Person.objects.prefetch_related("groups")
            ]

        normal_groups_lists = [list(p.groups.all()) for p in Person.objects.all()]
        self.assertEqual(groups_lists, normal_groups_lists)

    @translation.override("fi")
    def test_translations(self):
        a1 = Article.objects.create(pub_date=datetime.date.today())
        at1_fi = ArticleTranslation(
            article=a1, lang="fi", title="Otsikko", body="Diipadaapa"
        )
        at1_fi.save()
        at2_en = ArticleTranslation(
            article=a1, lang="en", title="Title", body="Lalalalala"
        )
        at2_en.save()

        self.assertEqual(Article.objects.get(pk=a1.pk).active_translation, at1_fi)

        with self.assertNumQueries(1):
            fetched = Article.objects.select_related("active_translation").get(
                active_translation__title="Otsikko"
            )
            self.assertEqual(fetched.active_translation.title, "Otsikko")
        a2 = Article.objects.create(pub_date=datetime.date.today())
        at2_fi = ArticleTranslation(
            article=a2, lang="fi", title="Atsikko", body="Diipadaapa", abstract="dipad"
        )
        at2_fi.save()
        a3 = Article.objects.create(pub_date=datetime.date.today())
        at3_en = ArticleTranslation(
            article=a3, lang="en", title="A title", body="lalalalala", abstract="lala"
        )
        at3_en.save()
        # Test model initialization with active_translation field.
        a3 = Article(id=a3.id, pub_date=a3.pub_date, active_translation=at3_en)
        a3.save()
        self.assertEqual(
            list(Article.objects.filter(active_translation__abstract=None)), [a1, a3]
        )
        self.assertEqual(
            list(
                Article.objects.filter(
                    active_translation__abstract=None,
                    active_translation__pk__isnull=False,
                )
            ),
            [a1],
        )

        with translation.override("en"):
            self.assertEqual(
                list(Article.objects.filter(active_translation__abstract=None)),
                [a1, a2],
            )

    def test_foreign_key_raises_informative_does_not_exist(self):
        referrer = ArticleTranslation()
        with self.assertRaisesMessage(
            Article.DoesNotExist, "ArticleTranslation has no article"
        ):
            referrer.article

    def test_foreign_key_related_query_name(self):
        """
        Tests the usage of foreign key related query names to filter objects. Specifically, this test creates an article and associates it with a tag, then verifies that the article can be queried correctly using the tag's name as a lookup. It also checks that attempting to use an incorrect related query name raises a FieldError with the expected error message.
        """
        a1 = Article.objects.create(pub_date=datetime.date.today())
        ArticleTag.objects.create(article=a1, name="foo")
        self.assertEqual(Article.objects.filter(tag__name="foo").count(), 1)
        self.assertEqual(Article.objects.filter(tag__name="bar").count(), 0)
        msg = (
            "Cannot resolve keyword 'tags' into field. Choices are: "
            "active_translation, active_translation_q, articletranslation, "
            "id, idea_things, newsarticle, pub_date, tag"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Article.objects.filter(tags__name="foo")

    def test_many_to_many_related_query_name(self):
        a1 = Article.objects.create(pub_date=datetime.date.today())
        i1 = ArticleIdea.objects.create(name="idea1")
        a1.ideas.add(i1)
        self.assertEqual(Article.objects.filter(idea_things__name="idea1").count(), 1)
        self.assertEqual(Article.objects.filter(idea_things__name="idea2").count(), 0)
        msg = (
            "Cannot resolve keyword 'ideas' into field. Choices are: "
            "active_translation, active_translation_q, articletranslation, "
            "id, idea_things, newsarticle, pub_date, tag"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Article.objects.filter(ideas__name="idea1")

    @translation.override("fi")
    def test_inheritance(self):
        """

        Tests the inheritance mechanism in the NewsArticle model.

        Specifically, this test case verifies that a NewsArticle object can be correctly
        retrieved with its associated translation, and that the active translation can
        be accessed efficiently.

        The test covers the following scenarios:
        - Creating a NewsArticle object with a translation in the Finnish language
        - Retrieving the NewsArticle object with its active translation using select_related
        - Verifying that the active translation's title matches the expected value
        - Ensuring the query is executed efficiently, with only one database query

        """
        na = NewsArticle.objects.create(pub_date=datetime.date.today())
        ArticleTranslation.objects.create(
            article=na, lang="fi", title="foo", body="bar"
        )
        self.assertSequenceEqual(
            NewsArticle.objects.select_related("active_translation"), [na]
        )
        with self.assertNumQueries(1):
            self.assertEqual(
                NewsArticle.objects.select_related("active_translation")[
                    0
                ].active_translation.title,
                "foo",
            )

    @skipUnlessDBFeature("has_bulk_insert")
    def test_batch_create_foreign_object(self):
        objs = [
            Person(name="abcd_%s" % i, person_country=self.usa) for i in range(0, 5)
        ]
        Person.objects.bulk_create(objs, 10)

    def test_isnull_lookup(self):
        """
        Tests the lookup functionality for null values in the 'group' field of the Membership model.

        Verifies that the 'isnull' lookup type correctly identifies memberships with a null group and those with a non-null group. This ensures that database queries can accurately filter memberships based on the presence or absence of a group association.
        """
        m1 = Membership.objects.create(
            membership_country=self.usa, person=self.bob, group_id=None
        )
        m2 = Membership.objects.create(
            membership_country=self.usa, person=self.bob, group=self.cia
        )
        self.assertSequenceEqual(
            Membership.objects.filter(group__isnull=True),
            [m1],
        )
        self.assertSequenceEqual(
            Membership.objects.filter(group__isnull=False),
            [m2],
        )


class TestModelCheckTests(SimpleTestCase):
    @isolate_apps("foreign_object")
    def test_check_composite_foreign_object(self):
        """
        Tests the check functionality of a composite foreign object defined on a model, 
        ensuring that it does not return any errors when correctly configured. 
        The test uses a parent model with a unique composite key and a child model 
        that references this composite key using a ForeignObject field. 
        It verifies that the check method on the ForeignObject field does not 
        report any issues when the from_fields and to_fields are correctly mapped.
        """
        class Parent(models.Model):
            a = models.PositiveIntegerField()
            b = models.PositiveIntegerField()

            class Meta:
                unique_together = (("a", "b"),)

        class Child(models.Model):
            a = models.PositiveIntegerField()
            b = models.PositiveIntegerField()
            value = models.CharField(max_length=255)
            parent = models.ForeignObject(
                Parent,
                on_delete=models.SET_NULL,
                from_fields=("a", "b"),
                to_fields=("a", "b"),
                related_name="children",
            )

        self.assertEqual(Child._meta.get_field("parent").check(from_model=Child), [])

    @isolate_apps("foreign_object")
    def test_check_subset_composite_foreign_object(self):
        """

        Test the validation of a ForeignObject field in a Child model that has a composite unique constraint.

        Checks that the check_subset method of the ForeignObject field does not report any errors when the field references
        a subset of the unique_together fields of the related Parent model.

        The test covers a scenario where the Child model has a ForeignObject field referencing the Parent model with a composite
        unique constraint, ensuring that the field's validation works correctly in this case.

        The expected outcome is an empty list, indicating that the validation does not report any errors.

        """
        class Parent(models.Model):
            a = models.PositiveIntegerField()
            b = models.PositiveIntegerField()
            c = models.PositiveIntegerField()

            class Meta:
                unique_together = (("a", "b"),)

        class Child(models.Model):
            a = models.PositiveIntegerField()
            b = models.PositiveIntegerField()
            c = models.PositiveIntegerField()
            d = models.CharField(max_length=255)
            parent = models.ForeignObject(
                Parent,
                on_delete=models.SET_NULL,
                from_fields=("a", "b", "c"),
                to_fields=("a", "b", "c"),
                related_name="children",
            )

        self.assertEqual(Child._meta.get_field("parent").check(from_model=Child), [])


class TestExtraJoinFilterQ(TestCase):
    @translation.override("fi")
    def test_extra_join_filter_q(self):
        """

        Tests the extra join filter functionality on the active_translation_q attribute.

        This function verifies that the active_translation_q attribute correctly returns the 
        translation object for an article, and checks that the use of select_related can reduce 
        the number of database queries required to retrieve the translation. 

        The test case covers both scenarios where select_related is used and where it is not, 
        to ensure the query optimization is working as expected.

        :param None
        :returns: None

        """
        a = Article.objects.create(pub_date=datetime.datetime.today())
        ArticleTranslation.objects.create(
            article=a, lang="fi", title="title", body="body"
        )
        qs = Article.objects.all()
        with self.assertNumQueries(2):
            self.assertEqual(qs[0].active_translation_q.title, "title")
        qs = qs.select_related("active_translation_q")
        with self.assertNumQueries(1):
            self.assertEqual(qs[0].active_translation_q.title, "title")


class TestCachedPathInfo(TestCase):
    def test_equality(self):
        """
        The path_infos and reverse_path_infos attributes are equivalent to
        calling the get_<method>() with no arguments.
        """
        foreign_object = Membership._meta.get_field("person")
        self.assertEqual(
            foreign_object.path_infos,
            foreign_object.get_path_info(),
        )
        self.assertEqual(
            foreign_object.reverse_path_infos,
            foreign_object.get_reverse_path_info(),
        )

    def test_copy_removes_direct_cached_values(self):
        """
        Shallow copying a ForeignObject (or a ForeignObjectRel) removes the
        object's direct cached PathInfo values.
        """
        foreign_object = Membership._meta.get_field("person")
        # Trigger storage of cached_property into ForeignObject's __dict__.
        foreign_object.path_infos
        foreign_object.reverse_path_infos
        # The ForeignObjectRel doesn't have reverse_path_infos.
        foreign_object.remote_field.path_infos
        self.assertIn("path_infos", foreign_object.__dict__)
        self.assertIn("reverse_path_infos", foreign_object.__dict__)
        self.assertIn("path_infos", foreign_object.remote_field.__dict__)
        # Cached value is removed via __getstate__() on ForeignObjectRel
        # because no __copy__() method exists, so __reduce_ex__() is used.
        remote_field_copy = copy.copy(foreign_object.remote_field)
        self.assertNotIn("path_infos", remote_field_copy.__dict__)
        # Cached values are removed via __copy__() on ForeignObject for
        # consistency of behavior.
        foreign_object_copy = copy.copy(foreign_object)
        self.assertNotIn("path_infos", foreign_object_copy.__dict__)
        self.assertNotIn("reverse_path_infos", foreign_object_copy.__dict__)
        # ForeignObjectRel's remains because it's part of a shallow copy.
        self.assertIn("path_infos", foreign_object_copy.remote_field.__dict__)

    def test_deepcopy_removes_cached_values(self):
        """
        Deep copying a ForeignObject removes the object's cached PathInfo
        values, including those of the related ForeignObjectRel.
        """
        foreign_object = Membership._meta.get_field("person")
        # Trigger storage of cached_property into ForeignObject's __dict__.
        foreign_object.path_infos
        foreign_object.reverse_path_infos
        # The ForeignObjectRel doesn't have reverse_path_infos.
        foreign_object.remote_field.path_infos
        self.assertIn("path_infos", foreign_object.__dict__)
        self.assertIn("reverse_path_infos", foreign_object.__dict__)
        self.assertIn("path_infos", foreign_object.remote_field.__dict__)
        # Cached value is removed via __getstate__() on ForeignObjectRel
        # because no __deepcopy__() method exists, so __reduce_ex__() is used.
        remote_field_copy = copy.deepcopy(foreign_object.remote_field)
        self.assertNotIn("path_infos", remote_field_copy.__dict__)
        # Field.__deepcopy__() internally uses __copy__() on both the
        # ForeignObject and ForeignObjectRel, so all cached values are removed.
        foreign_object_copy = copy.deepcopy(foreign_object)
        self.assertNotIn("path_infos", foreign_object_copy.__dict__)
        self.assertNotIn("reverse_path_infos", foreign_object_copy.__dict__)
        self.assertNotIn("path_infos", foreign_object_copy.remote_field.__dict__)

    def test_pickling_foreignobjectrel(self):
        """
        Pickling a ForeignObjectRel removes the path_infos attribute.

        ForeignObjectRel implements __getstate__(), so copy and pickle modules
        both use that, but ForeignObject implements __reduce__() and __copy__()
        separately, so doesn't share the same behaviour.
        """
        foreign_object_rel = Membership._meta.get_field("person").remote_field
        # Trigger storage of cached_property into ForeignObjectRel's __dict__.
        foreign_object_rel.path_infos
        self.assertIn("path_infos", foreign_object_rel.__dict__)
        foreign_object_rel_restored = pickle.loads(pickle.dumps(foreign_object_rel))
        self.assertNotIn("path_infos", foreign_object_rel_restored.__dict__)

    def test_pickling_foreignobject(self):
        """
        Pickling a ForeignObject does not remove the cached PathInfo values.

        ForeignObject will always keep the path_infos and reverse_path_infos
        attributes within the same process, because of the way
        Field.__reduce__() is used for restoring values.
        """
        foreign_object = Membership._meta.get_field("person")
        # Trigger storage of cached_property into ForeignObjectRel's __dict__
        foreign_object.path_infos
        foreign_object.reverse_path_infos
        self.assertIn("path_infos", foreign_object.__dict__)
        self.assertIn("reverse_path_infos", foreign_object.__dict__)
        foreign_object_restored = pickle.loads(pickle.dumps(foreign_object))
        self.assertIn("path_infos", foreign_object_restored.__dict__)
        self.assertIn("reverse_path_infos", foreign_object_restored.__dict__)


class GetJoiningDeprecationTests(TestCase):
    def test_foreign_object_get_joining_columns_warning(self):
        """
        Tests that a warning is raised when using the deprecated ForeignObject.get_joining_columns() method.

         The function verifies that calling get_joining_columns() on a foreign object field triggers a RemovedInDjango60Warning.
         It checks that the warning message suggests using get_joining_fields() instead of the deprecated method.

         This test ensures that users are properly notified when using outdated functionality and are guided towards the recommended replacement method.
        """
        msg = (
            "ForeignObject.get_joining_columns() is deprecated. Use "
            "get_joining_fields() instead."
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            Membership.person.field.get_joining_columns()

    def test_foreign_object_get_reverse_joining_columns_warning(self):
        msg = (
            "ForeignObject.get_reverse_joining_columns() is deprecated. Use "
            "get_reverse_joining_fields() instead."
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            Membership.person.field.get_reverse_joining_columns()

    def test_foreign_object_rel_get_joining_columns_warning(self):
        msg = (
            "ForeignObjectRel.get_joining_columns() is deprecated. Use "
            "get_joining_fields() instead."
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            Membership.person.field.remote_field.get_joining_columns()

    def test_join_get_joining_columns_warning(self):
        class CustomForeignKey(models.ForeignKey):
            def __getattribute__(self, attr):
                """
                Attribute access override to prevent direct access to the 'get_joining_fields' method. 

                This method ensures that the specified attribute is inaccessible, raising an AttributeError if attempted to be accessed directly, while allowing access to all other attributes and methods through the standard interface inherited from the parent class.
                """
                if attr == "get_joining_fields":
                    raise AttributeError
                return super().__getattribute__(attr)

        class CustomParent(models.Model):
            value = models.CharField(max_length=255)

        class CustomChild(models.Model):
            links = CustomForeignKey(CustomParent, models.CASCADE)

        msg = (
            "The usage of get_joining_columns() in Join is deprecated. Implement "
            "get_joining_fields() instead."
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            CustomChild.objects.filter(links__value="value")
