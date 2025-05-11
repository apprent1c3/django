from datetime import date, datetime, timedelta
from operator import attrgetter

from django.db import IntegrityError
from django.test import TestCase

from .models import (
    CustomMembership,
    Employee,
    Event,
    Friendship,
    Group,
    Ingredient,
    Invitation,
    Membership,
    Person,
    PersonChild,
    PersonSelfRefM2M,
    Recipe,
    RecipeIngredient,
    Relationship,
    SymmetricalFriendship,
)


class M2mThroughTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class, creating personas and groups for use in tests.
        """
        cls.bob = Person.objects.create(name="Bob")
        cls.jim = Person.objects.create(name="Jim")
        cls.jane = Person.objects.create(name="Jane")
        cls.rock = Group.objects.create(name="Rock")
        cls.roll = Group.objects.create(name="Roll")

    def test_reverse_inherited_m2m_with_through_fields_list_hashable(self):
        """
        Checks if the reverse many-to-many relationship fields and their hashes are correctly inherited by a subclass.
        """
        reverse_m2m = Person._meta.get_field("events_invited")
        self.assertEqual(reverse_m2m.through_fields, ["event", "invitee"])
        inherited_reverse_m2m = PersonChild._meta.get_field("events_invited")
        self.assertEqual(inherited_reverse_m2m.through_fields, ["event", "invitee"])
        self.assertEqual(hash(reverse_m2m), hash(inherited_reverse_m2m))

    def test_retrieve_intermediate_items(self):
        Membership.objects.create(person=self.jim, group=self.rock)
        Membership.objects.create(person=self.jane, group=self.rock)

        expected = ["Jane", "Jim"]
        self.assertQuerySetEqual(self.rock.members.all(), expected, attrgetter("name"))

    def test_get_on_intermediate_model(self):
        Membership.objects.create(person=self.jane, group=self.rock)

        queryset = Membership.objects.get(person=self.jane, group=self.rock)

        self.assertEqual(repr(queryset), "<Membership: Jane is a member of Rock>")

    def test_filter_on_intermediate_model(self):
        m1 = Membership.objects.create(person=self.jim, group=self.rock)
        m2 = Membership.objects.create(person=self.jane, group=self.rock)

        queryset = Membership.objects.filter(group=self.rock)

        self.assertSequenceEqual(queryset, [m1, m2])

    def test_add_on_m2m_with_intermediate_model(self):
        self.rock.members.add(
            self.bob, through_defaults={"invite_reason": "He is good."}
        )
        self.assertSequenceEqual(self.rock.members.all(), [self.bob])
        self.assertEqual(self.rock.membership_set.get().invite_reason, "He is good.")

    def test_add_on_m2m_with_intermediate_model_callable_through_default(self):
        """
        Tests adding members to a many-to-many relationship with an intermediate model through a callable default value.

        Verifies that the callable is correctly executed to set the 'invite_reason' attribute for each added member.
        """
        def invite_reason_callable():
            return "They were good at %s" % datetime.now()

        self.rock.members.add(
            self.bob,
            self.jane,
            through_defaults={"invite_reason": invite_reason_callable},
        )
        self.assertSequenceEqual(self.rock.members.all(), [self.bob, self.jane])
        self.assertEqual(
            self.rock.membership_set.filter(
                invite_reason__startswith="They were good at ",
            ).count(),
            2,
        )
        # invite_reason_callable() is called once.
        self.assertEqual(
            self.bob.membership_set.get().invite_reason,
            self.jane.membership_set.get().invite_reason,
        )

    def test_set_on_m2m_with_intermediate_model_callable_through_default(self):
        self.rock.members.set(
            [self.bob, self.jane],
            through_defaults={"invite_reason": lambda: "Why not?"},
        )
        self.assertSequenceEqual(self.rock.members.all(), [self.bob, self.jane])
        self.assertEqual(
            self.rock.membership_set.filter(
                invite_reason__startswith="Why not?",
            ).count(),
            2,
        )

    def test_add_on_m2m_with_intermediate_model_value_required(self):
        self.rock.nodefaultsnonulls.add(
            self.jim, through_defaults={"nodefaultnonull": 1}
        )
        self.assertEqual(self.rock.testnodefaultsornulls_set.get().nodefaultnonull, 1)

    def test_add_on_m2m_with_intermediate_model_value_required_fails(self):
        with self.assertRaises(IntegrityError):
            self.rock.nodefaultsnonulls.add(self.jim)

    def test_create_on_m2m_with_intermediate_model(self):
        annie = self.rock.members.create(
            name="Annie", through_defaults={"invite_reason": "She was just awesome."}
        )
        self.assertSequenceEqual(self.rock.members.all(), [annie])
        self.assertEqual(
            self.rock.membership_set.get().invite_reason, "She was just awesome."
        )

    def test_create_on_m2m_with_intermediate_model_callable_through_default(self):
        annie = self.rock.members.create(
            name="Annie",
            through_defaults={"invite_reason": lambda: "She was just awesome."},
        )
        self.assertSequenceEqual(self.rock.members.all(), [annie])
        self.assertEqual(
            self.rock.membership_set.get().invite_reason,
            "She was just awesome.",
        )

    def test_create_on_m2m_with_intermediate_model_value_required(self):
        self.rock.nodefaultsnonulls.create(
            name="Test", through_defaults={"nodefaultnonull": 1}
        )
        self.assertEqual(self.rock.testnodefaultsornulls_set.get().nodefaultnonull, 1)

    def test_create_on_m2m_with_intermediate_model_value_required_fails(self):
        with self.assertRaises(IntegrityError):
            self.rock.nodefaultsnonulls.create(name="Test")

    def test_get_or_create_on_m2m_with_intermediate_model_value_required(self):
        self.rock.nodefaultsnonulls.get_or_create(
            name="Test", through_defaults={"nodefaultnonull": 1}
        )
        self.assertEqual(self.rock.testnodefaultsornulls_set.get().nodefaultnonull, 1)

    def test_get_or_create_on_m2m_with_intermediate_model_value_required_fails(self):
        with self.assertRaises(IntegrityError):
            self.rock.nodefaultsnonulls.get_or_create(name="Test")

    def test_update_or_create_on_m2m_with_intermediate_model_value_required(self):
        self.rock.nodefaultsnonulls.update_or_create(
            name="Test", through_defaults={"nodefaultnonull": 1}
        )
        self.assertEqual(self.rock.testnodefaultsornulls_set.get().nodefaultnonull, 1)

    def test_update_or_create_on_m2m_with_intermediate_model_value_required_fails(self):
        with self.assertRaises(IntegrityError):
            self.rock.nodefaultsnonulls.update_or_create(name="Test")

    def test_remove_on_m2m_with_intermediate_model(self):
        Membership.objects.create(person=self.jim, group=self.rock)
        self.rock.members.remove(self.jim)
        self.assertSequenceEqual(self.rock.members.all(), [])

    def test_remove_on_m2m_with_intermediate_model_multiple(self):
        """

        Tests the removal of an object from a many-to-many relationship 
        with an intermediate model, ensuring multiple instances are removed correctly.

        """
        Membership.objects.create(person=self.jim, group=self.rock, invite_reason="1")
        Membership.objects.create(person=self.jim, group=self.rock, invite_reason="2")
        self.assertSequenceEqual(self.rock.members.all(), [self.jim, self.jim])
        self.rock.members.remove(self.jim)
        self.assertSequenceEqual(self.rock.members.all(), [])

    def test_set_on_m2m_with_intermediate_model(self):
        members = list(Person.objects.filter(name__in=["Bob", "Jim"]))
        self.rock.members.set(members)
        self.assertSequenceEqual(self.rock.members.all(), [self.bob, self.jim])

    def test_set_on_m2m_with_intermediate_model_value_required(self):
        """

        Tests setting many-to-many field with intermediate model where a value is required.

        Verifies that the 'through_defaults' parameter is used to set the required value,
        and that the 'clear' parameter is used to replace the existing value.

        """
        self.rock.nodefaultsnonulls.set(
            [self.jim], through_defaults={"nodefaultnonull": 1}
        )
        self.assertEqual(self.rock.testnodefaultsornulls_set.get().nodefaultnonull, 1)
        self.rock.nodefaultsnonulls.set(
            [self.jim], through_defaults={"nodefaultnonull": 2}
        )
        self.assertEqual(self.rock.testnodefaultsornulls_set.get().nodefaultnonull, 1)
        self.rock.nodefaultsnonulls.set(
            [self.jim], through_defaults={"nodefaultnonull": 2}, clear=True
        )
        self.assertEqual(self.rock.testnodefaultsornulls_set.get().nodefaultnonull, 2)

    def test_set_on_m2m_with_intermediate_model_value_required_fails(self):
        with self.assertRaises(IntegrityError):
            self.rock.nodefaultsnonulls.set([self.jim])

    def test_clear_removes_all_the_m2m_relationships(self):
        Membership.objects.create(person=self.jim, group=self.rock)
        Membership.objects.create(person=self.jane, group=self.rock)

        self.rock.members.clear()

        self.assertQuerySetEqual(self.rock.members.all(), [])

    def test_retrieve_reverse_intermediate_items(self):
        Membership.objects.create(person=self.jim, group=self.rock)
        Membership.objects.create(person=self.jim, group=self.roll)

        expected = ["Rock", "Roll"]
        self.assertQuerySetEqual(self.jim.group_set.all(), expected, attrgetter("name"))

    def test_add_on_reverse_m2m_with_intermediate_model(self):
        self.bob.group_set.add(self.rock)
        self.assertSequenceEqual(self.bob.group_set.all(), [self.rock])

    def test_create_on_reverse_m2m_with_intermediate_model(self):
        funk = self.bob.group_set.create(name="Funk")
        self.assertSequenceEqual(self.bob.group_set.all(), [funk])

    def test_remove_on_reverse_m2m_with_intermediate_model(self):
        Membership.objects.create(person=self.bob, group=self.rock)
        self.bob.group_set.remove(self.rock)
        self.assertSequenceEqual(self.bob.group_set.all(), [])

    def test_set_on_reverse_m2m_with_intermediate_model(self):
        members = list(Group.objects.filter(name__in=["Rock", "Roll"]))
        self.bob.group_set.set(members)
        self.assertSequenceEqual(self.bob.group_set.all(), [self.rock, self.roll])

    def test_clear_on_reverse_removes_all_the_m2m_relationships(self):
        Membership.objects.create(person=self.jim, group=self.rock)
        Membership.objects.create(person=self.jim, group=self.roll)

        self.jim.group_set.clear()

        self.assertQuerySetEqual(self.jim.group_set.all(), [])

    def test_query_model_by_attribute_name_of_related_model(self):
        """
        Tests the ability to query a model based on the attribute name of a related model, ensuring that the correct results are returned when filtering by a property of a related object.
        """
        Membership.objects.create(person=self.jim, group=self.rock)
        Membership.objects.create(person=self.jane, group=self.rock)
        Membership.objects.create(person=self.bob, group=self.roll)
        Membership.objects.create(person=self.jim, group=self.roll)
        Membership.objects.create(person=self.jane, group=self.roll)

        self.assertQuerySetEqual(
            Group.objects.filter(members__name="Bob"), ["Roll"], attrgetter("name")
        )

    def test_order_by_relational_field_through_model(self):
        """
        Tests that ordering by a relational field through a model works as expected.

        This test case verifies that the order_by method returns instances in the correct order 
        based on a related field defined in a custom model, specifically the date they joined a group.
        """
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        CustomMembership.objects.create(
            person=self.jim, group=self.rock, date_joined=yesterday
        )
        CustomMembership.objects.create(
            person=self.bob, group=self.rock, date_joined=today
        )
        CustomMembership.objects.create(
            person=self.jane, group=self.roll, date_joined=yesterday
        )
        CustomMembership.objects.create(
            person=self.jim, group=self.roll, date_joined=today
        )
        self.assertSequenceEqual(
            self.rock.custom_members.order_by("custom_person_related_name"),
            [self.jim, self.bob],
        )
        self.assertSequenceEqual(
            self.roll.custom_members.order_by("custom_person_related_name"),
            [self.jane, self.jim],
        )

    def test_query_first_model_by_intermediate_model_attribute(self):
        """
        Tests querying the first model instance by an attribute of an intermediate model, ensuring correct filtering of related objects.
        """
        Membership.objects.create(
            person=self.jane, group=self.roll, invite_reason="She was just awesome."
        )
        Membership.objects.create(
            person=self.jim, group=self.roll, invite_reason="He is good."
        )
        Membership.objects.create(person=self.bob, group=self.roll)

        qs = Group.objects.filter(membership__invite_reason="She was just awesome.")
        self.assertQuerySetEqual(qs, ["Roll"], attrgetter("name"))

    def test_query_second_model_by_intermediate_model_attribute(self):
        """
        Tests querying a second model by an attribute of an intermediate model, 
        verifying that the expected object is returned when filtering based on a specific attribute.
        """
        Membership.objects.create(
            person=self.jane, group=self.roll, invite_reason="She was just awesome."
        )
        Membership.objects.create(
            person=self.jim, group=self.roll, invite_reason="He is good."
        )
        Membership.objects.create(person=self.bob, group=self.roll)

        qs = Person.objects.filter(membership__invite_reason="She was just awesome.")
        self.assertQuerySetEqual(qs, ["Jane"], attrgetter("name"))

    def test_query_model_by_related_model_name(self):
        """
        Tests querying the Person model by related Group model name, verifying that results match expected members of the specified group.
        """
        Membership.objects.create(person=self.jim, group=self.rock)
        Membership.objects.create(person=self.jane, group=self.rock)
        Membership.objects.create(person=self.bob, group=self.roll)
        Membership.objects.create(person=self.jim, group=self.roll)
        Membership.objects.create(person=self.jane, group=self.roll)

        self.assertQuerySetEqual(
            Person.objects.filter(group__name="Rock"),
            ["Jane", "Jim"],
            attrgetter("name"),
        )

    def test_query_model_by_custom_related_name(self):
        CustomMembership.objects.create(person=self.bob, group=self.rock)
        CustomMembership.objects.create(person=self.jim, group=self.rock)

        self.assertQuerySetEqual(
            Person.objects.filter(custom__name="Rock"),
            ["Bob", "Jim"],
            attrgetter("name"),
        )

    def test_query_model_by_intermediate_can_return_non_unique_queryset(self):
        """

        Tests that the queryset returned by a query model via an intermediate model 
        can contain duplicate results.

        """
        Membership.objects.create(person=self.jim, group=self.rock)
        Membership.objects.create(
            person=self.jane, group=self.rock, date_joined=datetime(2006, 1, 1)
        )
        Membership.objects.create(
            person=self.bob, group=self.roll, date_joined=datetime(2004, 1, 1)
        )
        Membership.objects.create(person=self.jim, group=self.roll)
        Membership.objects.create(
            person=self.jane, group=self.roll, date_joined=datetime(2004, 1, 1)
        )

        qs = Person.objects.filter(membership__date_joined__gt=datetime(2004, 1, 1))
        self.assertQuerySetEqual(qs, ["Jane", "Jim", "Jim"], attrgetter("name"))

    def test_custom_related_name_forward_empty_qs(self):
        self.assertQuerySetEqual(self.rock.custom_members.all(), [])

    def test_custom_related_name_reverse_empty_qs(self):
        self.assertQuerySetEqual(self.bob.custom.all(), [])

    def test_custom_related_name_forward_non_empty_qs(self):
        CustomMembership.objects.create(person=self.bob, group=self.rock)
        CustomMembership.objects.create(person=self.jim, group=self.rock)

        self.assertQuerySetEqual(
            self.rock.custom_members.all(), ["Bob", "Jim"], attrgetter("name")
        )

    def test_custom_related_name_reverse_non_empty_qs(self):
        CustomMembership.objects.create(person=self.bob, group=self.rock)
        CustomMembership.objects.create(person=self.jim, group=self.rock)

        self.assertQuerySetEqual(self.bob.custom.all(), ["Rock"], attrgetter("name"))

    def test_custom_related_name_doesnt_conflict_with_fky_related_name(self):
        c = CustomMembership.objects.create(person=self.bob, group=self.rock)
        self.assertSequenceEqual(self.bob.custom_person_related_name.all(), [c])

    def test_through_fields(self):
        """
        Verifies that many-to-many relationships with intermediary tables containing multiple foreign keys to the related model function correctly, by testing the retrieval of invitees for a given event.
        """
        event = Event.objects.create(title="Rockwhale 2014")
        Invitation.objects.create(event=event, inviter=self.bob, invitee=self.jim)
        Invitation.objects.create(event=event, inviter=self.bob, invitee=self.jane)
        self.assertQuerySetEqual(
            event.invitees.all(), ["Jane", "Jim"], attrgetter("name")
        )


class M2mThroughReferentialTests(TestCase):
    def test_self_referential_empty_qs(self):
        tony = PersonSelfRefM2M.objects.create(name="Tony")
        self.assertQuerySetEqual(tony.friends.all(), [])

    def test_self_referential_non_symmetrical_first_side(self):
        tony = PersonSelfRefM2M.objects.create(name="Tony")
        chris = PersonSelfRefM2M.objects.create(name="Chris")
        Friendship.objects.create(
            first=tony, second=chris, date_friended=datetime.now()
        )

        self.assertQuerySetEqual(tony.friends.all(), ["Chris"], attrgetter("name"))

    def test_self_referential_non_symmetrical_second_side(self):
        tony = PersonSelfRefM2M.objects.create(name="Tony")
        chris = PersonSelfRefM2M.objects.create(name="Chris")
        Friendship.objects.create(
            first=tony, second=chris, date_friended=datetime.now()
        )

        self.assertQuerySetEqual(chris.friends.all(), [])

    def test_self_referential_non_symmetrical_clear_first_side(self):
        """
        Tests the behavior of self-referential non-symmetrical friendships when one side clears their friends, 
        verifying that the clearing action only affects that side's friendship list and not the other's.
        """
        tony = PersonSelfRefM2M.objects.create(name="Tony")
        chris = PersonSelfRefM2M.objects.create(name="Chris")
        Friendship.objects.create(
            first=tony, second=chris, date_friended=datetime.now()
        )

        chris.friends.clear()

        self.assertQuerySetEqual(chris.friends.all(), [])

        # Since this isn't a symmetrical relation, Tony's friend link still exists.
        self.assertQuerySetEqual(tony.friends.all(), ["Chris"], attrgetter("name"))

    def test_self_referential_non_symmetrical_both(self):
        """
        Checks the establishment of non-symmetrical self-referential friendships between two individuals, verifying that each person's friends are correctly retrieved despite the asymmetrical friendship relationship.
        """
        tony = PersonSelfRefM2M.objects.create(name="Tony")
        chris = PersonSelfRefM2M.objects.create(name="Chris")
        Friendship.objects.create(
            first=tony, second=chris, date_friended=datetime.now()
        )
        Friendship.objects.create(
            first=chris, second=tony, date_friended=datetime.now()
        )

        self.assertQuerySetEqual(tony.friends.all(), ["Chris"], attrgetter("name"))

        self.assertQuerySetEqual(chris.friends.all(), ["Tony"], attrgetter("name"))

    def test_through_fields_self_referential(self):
        """
        Tests the correct functionality of traversing through self-referential fields to retrieve a list of subordinates for an employee, covering both direct and indirect relationships.
        """
        john = Employee.objects.create(name="john")
        peter = Employee.objects.create(name="peter")
        mary = Employee.objects.create(name="mary")
        harry = Employee.objects.create(name="harry")

        Relationship.objects.create(source=john, target=peter, another=None)
        Relationship.objects.create(source=john, target=mary, another=None)
        Relationship.objects.create(source=john, target=harry, another=peter)

        self.assertQuerySetEqual(
            john.subordinates.all(), ["peter", "mary", "harry"], attrgetter("name")
        )

    def test_self_referential_symmetrical(self):
        """
        Test the symmetrical nature of self-referential many-to-many relationships, specifically friendships between individuals, verifying that friendships are not automatically reciprocated unless explicitly established in both directions.
        """
        tony = PersonSelfRefM2M.objects.create(name="Tony")
        chris = PersonSelfRefM2M.objects.create(name="Chris")
        SymmetricalFriendship.objects.create(
            first=tony,
            second=chris,
            date_friended=date.today(),
        )
        self.assertSequenceEqual(tony.sym_friends.all(), [chris])
        # Manually created symmetrical m2m relation doesn't add mirror entry
        # automatically.
        self.assertSequenceEqual(chris.sym_friends.all(), [])
        SymmetricalFriendship.objects.create(
            first=chris, second=tony, date_friended=date.today()
        )
        self.assertSequenceEqual(chris.sym_friends.all(), [tony])

    def test_add_on_symmetrical_m2m_with_intermediate_model(self):
        """

        Tests adding a symmetric many-to-many relationship with an intermediate model.

        Verifies that the relationship is correctly established in both directions 
        and that the intermediate model's attributes are properly set.

        """
        tony = PersonSelfRefM2M.objects.create(name="Tony")
        chris = PersonSelfRefM2M.objects.create(name="Chris")
        date_friended = date(2017, 1, 3)
        tony.sym_friends.add(chris, through_defaults={"date_friended": date_friended})
        self.assertSequenceEqual(tony.sym_friends.all(), [chris])
        self.assertSequenceEqual(chris.sym_friends.all(), [tony])
        friendship = tony.symmetricalfriendship_set.get()
        self.assertEqual(friendship.date_friended, date_friended)

    def test_set_on_symmetrical_m2m_with_intermediate_model(self):
        """
        Tests the behavior of a symmetrical many-to-many relationship with an intermediate model, specifically the `set` method of a related manager, when clearing existing relationships and adding new ones with specified through defaults.
        """
        tony = PersonSelfRefM2M.objects.create(name="Tony")
        chris = PersonSelfRefM2M.objects.create(name="Chris")
        anne = PersonSelfRefM2M.objects.create(name="Anne")
        kate = PersonSelfRefM2M.objects.create(name="Kate")
        date_friended_add = date(2013, 1, 5)
        date_friended_set = date.today()
        tony.sym_friends.add(
            anne,
            chris,
            through_defaults={"date_friended": date_friended_add},
        )
        tony.sym_friends.set(
            [anne, kate],
            through_defaults={"date_friended": date_friended_set},
        )
        self.assertSequenceEqual(tony.sym_friends.all(), [anne, kate])
        self.assertSequenceEqual(anne.sym_friends.all(), [tony])
        self.assertSequenceEqual(kate.sym_friends.all(), [tony])
        self.assertEqual(
            kate.symmetricalfriendship_set.get().date_friended,
            date_friended_set,
        )
        # Date is preserved.
        self.assertEqual(
            anne.symmetricalfriendship_set.get().date_friended,
            date_friended_add,
        )
        # Recreate relationship.
        tony.sym_friends.set(
            [anne],
            clear=True,
            through_defaults={"date_friended": date_friended_set},
        )
        self.assertSequenceEqual(tony.sym_friends.all(), [anne])
        self.assertSequenceEqual(anne.sym_friends.all(), [tony])
        self.assertEqual(
            anne.symmetricalfriendship_set.get().date_friended,
            date_friended_set,
        )


class M2mThroughToFieldsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for recipes and ingredients.

        Creates three ingredients (pea, potato, tomato) and one recipe (curry) with
        associated ingredients, making them available as class attributes for test cases.

        """
        cls.pea = Ingredient.objects.create(iname="pea")
        cls.potato = Ingredient.objects.create(iname="potato")
        cls.tomato = Ingredient.objects.create(iname="tomato")
        cls.curry = Recipe.objects.create(rname="curry")
        RecipeIngredient.objects.create(recipe=cls.curry, ingredient=cls.potato)
        RecipeIngredient.objects.create(recipe=cls.curry, ingredient=cls.pea)
        RecipeIngredient.objects.create(recipe=cls.curry, ingredient=cls.tomato)

    def test_retrieval(self):
        # Forward retrieval
        self.assertSequenceEqual(
            self.curry.ingredients.all(), [self.pea, self.potato, self.tomato]
        )
        # Backward retrieval
        self.assertEqual(self.tomato.recipes.get(), self.curry)

    def test_choices(self):
        field = Recipe._meta.get_field("ingredients")
        self.assertEqual(
            [choice[0] for choice in field.get_choices(include_blank=False)],
            ["pea", "potato", "tomato"],
        )
