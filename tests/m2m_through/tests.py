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
        cls.bob = Person.objects.create(name="Bob")
        cls.jim = Person.objects.create(name="Jim")
        cls.jane = Person.objects.create(name="Jane")
        cls.rock = Group.objects.create(name="Rock")
        cls.roll = Group.objects.create(name="Roll")

    def test_reverse_inherited_m2m_with_through_fields_list_hashable(self):
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
        Tests adding objects to a many-to-many relationship with an intermediate model, 
        using a callable to set default values.

        This function verifies that the many-to-many relationship is correctly established 
        between objects, and that the default values set by the callable are applied 
        to the intermediate model instances. It checks the resulting membership 
        set for the correct invite reasons and ensures that the sequence of 
        members added is preserved. The callable used in this test generates 
        an invite reason string based on the current date and time.
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
        """
        Tests that setting a many-to-many relationship with an intermediate model 
        using a callable through default values works as expected.

        The test verifies that when setting multiple objects in a many-to-many 
        relationship, the through defaults are correctly applied to the intermediate 
        model instances. Specifically, it checks that the objects are correctly 
        associated and that the specified default value is applied to the intermediate 
        model instance.

        The test case covers a scenario where an invite reason is set to a callable 
        that returns a string, demonstrating that such callables are evaluated and 
        applied as expected when setting the relationship through defaults.
        """
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
        """
        Tests adding an instance to a many-to-many relationship with an intermediate model that has a value required.

        Verifies that when an instance is added to a many-to-many field through an intermediate model, 
        the required value is correctly set and retrieved from the database.

        Checks the functionality of the many-to-many relationship with an intermediate model, 
        ensuring data consistency and integrity.
        """
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
        """
        Tests the get_or_create method on a many-to-many relationship with an intermediate model.
        The function verifies that the method correctly sets the required value in the intermediate model.
        It checks that a new instance is created with the specified name and the required value is populated as expected in the intermediate model.
        """
        self.rock.nodefaultsnonulls.get_or_create(
            name="Test", through_defaults={"nodefaultnonull": 1}
        )
        self.assertEqual(self.rock.testnodefaultsornulls_set.get().nodefaultnonull, 1)

    def test_get_or_create_on_m2m_with_intermediate_model_value_required_fails(self):
        """
        Test that a get_or_create operation on a many-to-many relationship with an intermediate model fails when a required value is not provided, resulting in an IntegrityError.
        """
        with self.assertRaises(IntegrityError):
            self.rock.nodefaultsnonulls.get_or_create(name="Test")

    def test_update_or_create_on_m2m_with_intermediate_model_value_required(self):
        """

        Tests the update or creation of an instance with a many-to-many relationship 
        using an intermediate model, where a specific value is required.

        This test case checks if the update_or_create method correctly sets the 
        required value on the intermediate model when establishing the many-to-many 
        relationship. It verifies that the value is properly persisted and can be 
        retrieved for validation purposes. 

        The test covers the scenario where the intermediate model has a field with a 
        specific value requirement, ensuring data consistency and integrity in the 
        many-to-many relationship.

        """
        self.rock.nodefaultsnonulls.update_or_create(
            name="Test", through_defaults={"nodefaultnonull": 1}
        )
        self.assertEqual(self.rock.testnodefaultsornulls_set.get().nodefaultnonull, 1)

    def test_update_or_create_on_m2m_with_intermediate_model_value_required_fails(self):
        with self.assertRaises(IntegrityError):
            self.rock.nodefaultsnonulls.update_or_create(name="Test")

    def test_remove_on_m2m_with_intermediate_model(self):
        """
        Tests that removing an object from a many-to-many relationship using an intermediate model correctly updates the relationship. 

        This test case creates a membership between a person and a group, then removes the person from the group and asserts that the group has no members afterwards.
        """
        Membership.objects.create(person=self.jim, group=self.rock)
        self.rock.members.remove(self.jim)
        self.assertSequenceEqual(self.rock.members.all(), [])

    def test_remove_on_m2m_with_intermediate_model_multiple(self):
        Membership.objects.create(person=self.jim, group=self.rock, invite_reason="1")
        Membership.objects.create(person=self.jim, group=self.rock, invite_reason="2")
        self.assertSequenceEqual(self.rock.members.all(), [self.jim, self.jim])
        self.rock.members.remove(self.jim)
        self.assertSequenceEqual(self.rock.members.all(), [])

    def test_set_on_m2m_with_intermediate_model(self):
        """
        Tests setting a many-to-many relationship using an intermediate model.

        This test case verifies that a set of objects can be assigned to a many-to-many
        field on a model instance, and that the resulting set of related objects is as
        expected.

        The test specifically checks the following:

        * That a list of objects can be set on the many-to-many field
        * That the set of related objects matches the expected set after assignment

        This ensures that the many-to-many relationship is correctly established and
        maintained using the intermediate model.
        """
        members = list(Person.objects.filter(name__in=["Bob", "Jim"]))
        self.rock.members.set(members)
        self.assertSequenceEqual(self.rock.members.all(), [self.bob, self.jim])

    def test_set_on_m2m_with_intermediate_model_value_required(self):
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
        """

        Tests the addition of an object to a reverse many-to-many field with an intermediate model.

        This test case verifies that the many-to-many relationship is correctly established
        when an object is added to the reverse side of the relationship. It checks that the
        added object is properly included in the set of related objects.

        The test scenario involves a user (Bob) being added to a group through an intermediate model.
        The test asserts that Bob's group set contains the expected group (Rock) after addition.

        """
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
        Tests querying a model by attribute name of a related model.

        This test case checks if it's possible to filter a query set of models based on an attribute of a related model.
        In this specific case, it tests if a group can be retrieved by the name of one of its members.
        The test creates some memberships between people and groups, then asserts that the group 'Roll' is the only group that has a member named 'Bob' (case-sensitive).

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
        Test ordering of members in a custom group by a relational field through a custom model.

        This test creates custom memberships for individuals in different groups and verifies that
        the members are ordered correctly based on a related field. It checks if the ordering
        is applied correctly when accessing the custom members of a group through the custom model.

        The test covers scenarios where members join a group on different dates, ensuring that the
        ordering is applied as expected in various cases. The result is verified using assertions
        to confirm that the members are in the correct order based on the related field.
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
        Tests the functionality of querying a model through an intermediate relationship, 
        ensuring that a non-unique queryset can be returned as expected.

        This test case verifies that when filtering a model based on a condition applied 
        to a related model through an intermediate relationship, the resulting queryset 
        may contain duplicate entries if the intermediate relationship is not unique. 

        In this context, it checks that people who have joined a group after a certain 
        date are correctly retrieved, even if they have multiple memberships.
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
        Relations with intermediary tables with multiple FKs
        to the M2M's ``to`` model are possible.
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
        """

        Tests the creation of a self-referential non-symmetrical friendship relation.

        This test case verifies that when a friendship is established from one person to another,
        the first person's friends are correctly populated. Specifically, it checks that 
        the first person in the friendship is correctly associated with the second person's name.

        """
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

        Tests self-referential relationships between employees through fields.

        This test case verifies that an employee's subordinates can be correctly retrieved, 
        including those with indirect relationships. It creates a network of employee relationships 
        and checks that the 'subordinates' attribute returns all expected subordinates by name.

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

        Tests the functionality of a symmetrical many-to-many relationship with an intermediate model.

        Specifically, this test case checks the behavior of adding, setting, and clearing friends for a person in a symmetrical many-to-many relationship.
        It verifies that the friends are correctly added, removed, and updated, and that the date of friendship is correctly set and updated.
        The test also checks that the symmetrical relationship is correctly established and maintained.

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
        cls.pea = Ingredient.objects.create(iname="pea")
        cls.potato = Ingredient.objects.create(iname="potato")
        cls.tomato = Ingredient.objects.create(iname="tomato")
        cls.curry = Recipe.objects.create(rname="curry")
        RecipeIngredient.objects.create(recipe=cls.curry, ingredient=cls.potato)
        RecipeIngredient.objects.create(recipe=cls.curry, ingredient=cls.pea)
        RecipeIngredient.objects.create(recipe=cls.curry, ingredient=cls.tomato)

    def test_retrieval(self):
        # Forward retrieval
        """
        Tests the retrieval of ingredients and their associated recipes.

        Verifies that the ingredients of a specific dish (curry) are correctly retrieved and that the dish is correctly linked to one of its ingredients (tomato).
        """
        self.assertSequenceEqual(
            self.curry.ingredients.all(), [self.pea, self.potato, self.tomato]
        )
        # Backward retrieval
        self.assertEqual(self.tomato.recipes.get(), self.curry)

    def test_choices(self):
        """
        Tests the choices available for the 'ingredients' field in the Recipe model.

        Verifies that the choices include 'pea', 'potato', and 'tomato', and only these options, 
        exactly matching the expected set of ingredients.
        """
        field = Recipe._meta.get_field("ingredients")
        self.assertEqual(
            [choice[0] for choice in field.get_choices(include_blank=False)],
            ["pea", "potato", "tomato"],
        )
