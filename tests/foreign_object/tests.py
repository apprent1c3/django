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
        membership = Membership.objects.create(
            membership_country_id=self.usa.id,
            person_id=self.jane.id,
            group_id=self.cia.id,
        )

        with self.assertRaises(Person.DoesNotExist):
            getattr(membership, "person")

    def test_reverse_query_returns_correct_result(self):
        # Creating a valid membership because it has the same country has the person
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

        Tests querying memberships based on nested relationships between people, their friendships, and group memberships.

        This test case verifies that it is possible to retrieve memberships of people who are friends with others, 
        and also that it is possible to exclude memberships of people who do not have such friendships.

        The test covers a scenario where two people, Bob and Jim, are members of a group (CIA) and are friends with each other.
        It checks that a query can correctly identify Bob's membership as he has a friend (Jim), 
        and also identify Jim's membership as being excluded from the results since he does not have a friendship initiated by himself.

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
        self.assertQuerySetEqual(self.jane.groups.all(), [])

        # Something adds jane to group CIA but Jane is in Soviet Union which
        # isn't CIA's country.
        Membership.objects.create(
            membership_country=self.usa, person=self.jane, group=self.cia
        )

        # Jane should still not be in any groups
        self.assertQuerySetEqual(self.jane.groups.all(), [])

    def test_m2m_through_on_self_works(self):
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
        """
        Tests whether prefetching related many-to-many objects works as expected.

        This test creates several memberships between people and groups, and then checks that
        prefetching the members of each group using 'prefetch_related' results in the same
        output as retrieving the members normally, while also verifying that the number of
        queries executed is reduced.

        Verifies that 'prefetch_related' correctly fetches the related many-to-many objects
        (in this case, members of a group) in a single query, improving performance by
        reducing the number of database queries.
        """
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
        """
        Tests that prefetching related objects for many-to-many reverse relationships works correctly.

        This test checks if the prefetch_related method can efficiently fetch related objects 
        for a many-to-many reverse relationship, in this case, a person's groups. It compares the 
        results of fetching groups with and without prefetching to ensure they are equivalent.
        The test also verifies that the number of database queries is as expected when prefetching 
        related objects, confirming that the optimization is effective.
        """
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

        Tests the functionality of foreign key related query names.

        This test case verifies that the Django ORM correctly handles query filters on 
        related models, specifically testing the usage of the correct query name for a 
        foreign key relationship. It also checks for an error when an incorrect query 
        name is used.

        The test creates an Article instance and associates it with an ArticleTag, then 
        filters Articles by the ArticleTag name. It asserts that the correct number of 
        results are returned, and that using an incorrect query name raises a FieldError.

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
        """
        Tests the ability to create multiple foreign objects in batches using the bulk_create method. 

        This test case verifies that the database supports bulk insertion of objects with foreign key relationships, ensuring efficient creation of multiple objects in a single operation. 

        It creates a list of Person objects with unique names and associates them with a specific country, then attempts to insert these objects into the database in batches. 

        The test is skipped if the database does not support bulk insert operations.
        """
        objs = [
            Person(name="abcd_%s" % i, person_country=self.usa) for i in range(0, 5)
        ]
        Person.objects.bulk_create(objs, 10)

    def test_isnull_lookup(self):
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

        The test checks that the correct warning message is issued, indicating that users should use the get_joining_fields() method instead, which will become the standard method in Django 6.0.
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
        """

        Tests the deprecation warning for the get_joining_columns() method of ForeignObjectRel.

        The test case checks that using the deprecated get_joining_columns() method raises a RemovedInDjango60Warning,
        with a message recommending the use of get_joining_fields() instead.

        """
        msg = (
            "ForeignObjectRel.get_joining_columns() is deprecated. Use "
            "get_joining_fields() instead."
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            Membership.person.field.remote_field.get_joining_columns()

    def test_join_get_joining_columns_warning(self):
        class CustomForeignKey(models.ForeignKey):
            def __getattribute__(self, attr):
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
