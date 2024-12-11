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
        """

        Tests the reverse Many-To-Many relationship with through fields for inherited models.

        Specifically, it checks that the through fields for the 'events_invited' field are correctly
        defined as ['event', 'invitee'] for both the base model (Person) and an inherited model (PersonChild).
        Additionally, it verifies that the hash values of the reverse Many-To-Many fields for the base and
        inherited models are equal, indicating that they are considered identical.

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
        """

        Tests the retrieval of a membership object from the database based on intermediate model constraints.

        This function creates a new membership record for a person and a group, then attempts to retrieve the same record using the person and group as filters.
        It verifies that the retrieved object's string representation matches the expected format, indicating successful retrieval and correct representation of the membership.

        """
        Membership.objects.create(person=self.jane, group=self.rock)

        queryset = Membership.objects.get(person=self.jane, group=self.rock)

        self.assertEqual(repr(queryset), "<Membership: Jane is a member of Rock>")

    def test_filter_on_intermediate_model(self):
        m1 = Membership.objects.create(person=self.jim, group=self.rock)
        m2 = Membership.objects.create(person=self.jane, group=self.rock)

        queryset = Membership.objects.filter(group=self.rock)

        self.assertSequenceEqual(queryset, [m1, m2])

    def test_add_on_m2m_with_intermediate_model(self):
        """
        Tests the addition of a member to a many-to-many relationship with an intermediate model, ensuring the correct assignment of the member and the associated attributes, such as the invite reason.
        """
        self.rock.members.add(
            self.bob, through_defaults={"invite_reason": "He is good."}
        )
        self.assertSequenceEqual(self.rock.members.all(), [self.bob])
        self.assertEqual(self.rock.membership_set.get().invite_reason, "He is good.")

    def test_add_on_m2m_with_intermediate_model_callable_through_default(self):
        """

        Tests the addition of objects to a many-to-many relationship with an intermediate model.
        The test verifies that the intermediate model's fields can be populated using a callable as the default value.
        In this case, the `invite_reason` field is populated with a dynamically generated string.
        The test checks that the objects are correctly added to the relationship, and that the intermediate model's fields are correctly populated.

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
        """
        Tests adding an instance to a many-to-many relationship with an intermediate model when a value is required.

        This test case verifies that when an instance is added to a many-to-many relationship 
        with an intermediate model, the required value is correctly set. The test checks that 
        the intermediate model's attribute is populated with the provided value after the add operation.

        Verifies the expected behavior of adding instances to many-to-many relationships 
        with intermediate models that have required fields, ensuring data consistency and integrity.
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
        """

        Tests the creation of a many-to-many relationship with an intermediate model through a callable default value.

        This test case verifies that when creating an instance and establishing an m2m relationship, 
        the intermediate model is correctly populated with the result of the callable default value.

        The test checks that the newly created instance is properly linked to the parent instance 
        and that the intermediate model contains the expected values as determined by the callable default.

        """
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
        """
        Tests that attempting to get or create an instance with required M2M relation values through the `get_or_create` method fails when no values are provided for the intermediate model, raising an IntegrityError. This ensures the integrity of the data model by preventing the creation of instances with missing required relationships.
        """
        with self.assertRaises(IntegrityError):
            self.rock.nodefaultsnonulls.get_or_create(name="Test")

    def test_update_or_create_on_m2m_with_intermediate_model_value_required(self):
        """
        Tests the update_or_create method on a many-to-many relationship with an intermediate model.

            The purpose of this test is to verify that when updating or creating an object in a many-to-many relationship,
            the through_defaults parameter correctly sets the value of the intermediate model.

            Specifically, it checks that when a value is required for the intermediate model, it is properly set
            and then successfully retrieved from the database.

            Args:
                None

            Returns:
                None

            Raises:
                AssertionError: If the test fails to verify the correct update of the intermediate model value
        """
        self.rock.nodefaultsnonulls.update_or_create(
            name="Test", through_defaults={"nodefaultnonull": 1}
        )
        self.assertEqual(self.rock.testnodefaultsornulls_set.get().nodefaultnonull, 1)

    def test_update_or_create_on_m2m_with_intermediate_model_value_required_fails(self):
        """

        Tests that updating or creating a many-to-many relationship with an intermediate model 
        where a value is required fails with an IntegrityError when the required value is not provided.

        The test case verifies that attempting to update or create an instance without specifying 
        the necessary value for the intermediate model results in a database integrity error, 
        ensuring data consistency and preventing invalid data from being stored.

        """
        with self.assertRaises(IntegrityError):
            self.rock.nodefaultsnonulls.update_or_create(name="Test")

    def test_remove_on_m2m_with_intermediate_model(self):
        Membership.objects.create(person=self.jim, group=self.rock)
        self.rock.members.remove(self.jim)
        self.assertSequenceEqual(self.rock.members.all(), [])

    def test_remove_on_m2m_with_intermediate_model_multiple(self):
        """
        Tests the removal of an object from a many-to-many relationship with an intermediate model, 
        where the relationship is established multiple times. 

        This test case verifies that removing an object from the relationship deletes all associated 
        intermediate model instances, ensuring the relationship is fully severed. 

        It checks the initial state of the relationship, adds multiple instances of the same object, 
        then removes the object and confirms the relationship is empty afterwards.
        """
        Membership.objects.create(person=self.jim, group=self.rock, invite_reason="1")
        Membership.objects.create(person=self.jim, group=self.rock, invite_reason="2")
        self.assertSequenceEqual(self.rock.members.all(), [self.jim, self.jim])
        self.rock.members.remove(self.jim)
        self.assertSequenceEqual(self.rock.members.all(), [])

    def test_set_on_m2m_with_intermediate_model(self):
        """
        Tests setting many-to-many relationship with an intermediate model on the 'Rock' model instance.

        Verifies that the 'members' attribute of the 'Rock' instance can be successfully set to a list of 'Person' objects, 
        and checks that the resulting many-to-many relationship matches the set of 'Person' objects.
        """
        members = list(Person.objects.filter(name__in=["Bob", "Jim"]))
        self.rock.members.set(members)
        self.assertSequenceEqual(self.rock.members.all(), [self.bob, self.jim])

    def test_set_on_m2m_with_intermediate_model_value_required(self):
        """

        Tests setting a Many-To-Many relationship with an intermediate model when a value is required.

        This function checks the behavior of setting a Many-To-Many relationship through an intermediate model, 
        where one of the fields in the intermediate model requires a value. It verifies that setting the relationship 
        with a required value succeeds, and that subsequent sets with a different required value do not override the 
        existing value unless the clear flag is used.

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
        """
        Tests whether setting a many-to-many relationship with an intermediate model that has a required value fails as expected when the required value is not provided. 

        The test verifies that attempting to set the relationship without providing the necessary value raises an IntegrityError, ensuring data consistency and integrity.
        """
        with self.assertRaises(IntegrityError):
            self.rock.nodefaultsnonulls.set([self.jim])

    def test_clear_removes_all_the_m2m_relationships(self):
        """

        Tests that the clear method on a Many-To-Many field removes all relationships.

        This test case verifies that when the clear method is called on a Many-To-Many field,
        all existing relationships between objects are removed, leaving the field empty.

        The test starts with a predefined group and creates membership relationships between
        the group and two individuals. It then clears the Many-To-Many relationship and
        asserts that the group's member list is empty after the operation.

        """
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

        Checks that adding an object to a reverse many-to-many field through an intermediate model 
        is successful and the resulting collection is correctly ordered. 

        Tests the case where an object is added to a group set, 
        then verifies that this object is correctly retrieved when fetching all objects from the group set.

        """
        self.bob.group_set.add(self.rock)
        self.assertSequenceEqual(self.bob.group_set.all(), [self.rock])

    def test_create_on_reverse_m2m_with_intermediate_model(self):
        """

        Tests the creation of a many-to-many relationship with an intermediate model in reverse.

        This test case verifies that creating a new instance of the related model and associating it with the source object
        results in the correct many-to-many relationship being established. The test asserts that the newly created instance
        is correctly retrieved and listed as part of the related object set.

        The test covers the scenario where an object (in this case, 'bob') has a many-to-many relationship with another model
        ('group_set') through an intermediate model. It ensures that creating a new 'group_set' instance and associating it
        with 'bob' updates 'bob's relationships correctly.

        """
        funk = self.bob.group_set.create(name="Funk")
        self.assertSequenceEqual(self.bob.group_set.all(), [funk])

    def test_remove_on_reverse_m2m_with_intermediate_model(self):
        Membership.objects.create(person=self.bob, group=self.rock)
        self.bob.group_set.remove(self.rock)
        self.assertSequenceEqual(self.bob.group_set.all(), [])

    def test_set_on_reverse_m2m_with_intermediate_model(self):
        """
        Tests setting a reverse many-to-many relationship with an intermediate model.

        Verifies that setting a reverse many-to-many field using the set method updates the relationship correctly.
        The test checks the membership of an object in a group by adding it to the group set and then asserting that the object is a member of the expected groups.

        The test uses a sample dataset with predefined groups and an object to validate the reverse many-to-many relationship.
        It covers the scenario where an object's group membership is updated and verified against the expected groups.

        This test is useful for ensuring the correct operation of the set method on reverse many-to-many fields with intermediate models, 
        which is essential for maintaining data consistency and integrity in the application's data model.
        """
        members = list(Group.objects.filter(name__in=["Rock", "Roll"]))
        self.bob.group_set.set(members)
        self.assertSequenceEqual(self.bob.group_set.all(), [self.rock, self.roll])

    def test_clear_on_reverse_removes_all_the_m2m_relationships(self):
        Membership.objects.create(person=self.jim, group=self.rock)
        Membership.objects.create(person=self.jim, group=self.roll)

        self.jim.group_set.clear()

        self.assertQuerySetEqual(self.jim.group_set.all(), [])

    def test_query_model_by_attribute_name_of_related_model(self):
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

        Tests the functionality of ordering custom membership records by a relational field 
        through the model. This includes verifying that the custom_members manager returns 
        members in the correct order when ordered by the 'custom_person_related_name' field.

        The test cases cover various scenarios, including members joining on different dates 
        and being part of different groups, to ensure the ordering works correctly across 
        different relational fields and models.

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
        Tests querying the first model instance by an attribute of an intermediate model.

        Verifies the correctness of a query that filters the first model (Group) based on a 
        specific attribute of an intermediate model (Membership). The test case creates 
        multiple instances of the intermediate model with different attributes and then 
        queries the first model to retrieve instances that match a specific attribute 
        value in the intermediate model.

        The query filters Groups where there exists a Membership with a specific invite 
        reason, and asserts that the resulting query set matches the expected Group 
        instance, identified by its name.
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
        """

        Tests querying the model by a custom related name.

        This function verifies that the model can be queried using a custom related name, 
        in this case, the 'custom' attribute of the Person model, which references a group by its name.

        It tests whether the query returns the expected results, specifically the names of people 
        who belong to a group with the name 'Rock', and checks for the correct output.

        """
        CustomMembership.objects.create(person=self.bob, group=self.rock)
        CustomMembership.objects.create(person=self.jim, group=self.rock)

        self.assertQuerySetEqual(
            Person.objects.filter(custom__name="Rock"),
            ["Bob", "Jim"],
            attrgetter("name"),
        )

    def test_query_model_by_intermediate_can_return_non_unique_queryset(self):
        """

        Tests the ability to query a model using an intermediate model and returns a non-unique queryset.

        This function creates multiple memberships for individuals in different groups, with varying dates of joining.
        It then queries the Person model using a filter on the Membership model, retrieving people who joined a group after a specific date.
        The function asserts that the retrieved queryset matches the expected list of people, ordered by their names.

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
        """
        Tests the custom related name feature for forward relationships with non-empty querysets.

        Verifies that when custom memberships are created between people and a group, 
        the group's custom members can be successfully retrieved using the custom related name.
        The test checks if the custom members are returned in the correct order and with the expected names.
        """
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
        """
        Tests that a newly created instance of PersonSelfRefM2M with no friends has an empty queryset for its friends. Verifies that the many-to-many self-referential relationship is correctly initialized with no related objects.
        """
        tony = PersonSelfRefM2M.objects.create(name="Tony")
        self.assertQuerySetEqual(tony.friends.all(), [])

    def test_self_referential_non_symmetrical_first_side(self):
        """

        Tests the self-referential many-to-many relationship in the PersonSelfRefM2M model 
        where a friendship is established from one person to another but not the other way around.
        Verifies that the friends of the person who initiated the friendship are correctly queried.

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
        """

        Tests the behavior of self-referential, non-symmetrical many-to-many relationships
        when the first side of the relationship is cleared.

        Verifies that when a person clears their friendships, the relationship is removed
        only from their side, and the other person still appears as a friend to them.

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

        Tests a self-referential many-to-many relationship where the friendships are not symmetrical.
        Verifies that each person can correctly retrieve their friends, demonstrating that the relationship
        is established and queried accurately in both directions. This test ensures the data model correctly
        handles non-symmetrical friendships, where person A can be friends with person B without person B
        necessarily being friends with person A, although in this test case, the friendship is mutual.

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

        Tests the creation and retrieval of symmetrical friendships between individuals.

        Verifies that friendships are correctly established and retrieved in both directions, 
        ensuring that the relationship is not automatically symmetrical. The test covers the 
        scenarios where a friendship is initiated by one person and then reciprocated by 
        the other, checking that the friendship list is updated correctly for both individuals.

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

        Tests the functionality of setting relationships on a symmetrical many-to-many field 
        with an intermediate model. Specifically, it checks that the set method correctly 
        replaces existing relationships and updates the through model defaults.

        Verifies the expected behavior when adding and setting relationships, including:
        - Adding multiple relationships to an instance and checking the resulting related objects.
        - Setting relationships on an instance to a new set of related objects, with updated through model defaults.
        - Verifying the correct removal of existing relationships when using the clear parameter.
        - Confirming the through model defaults are correctly updated for the new relationships.

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
        Sets up test data for the class, creating a set of ingredients and a recipe instance,
        populating the recipe with the created ingredients. This method is used to establish a
        consistent test environment, reducing the amount of setup code required in individual
        tests. The created test data includes three ingredients (pea, potato, and tomato) and
        one recipe (curry), with the recipe being associated with all three ingredients.
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
        """
        Tests the retrieval of ingredients and recipes.

         Verifies that all ingredients associated with a curry recipe are correctly retrieved, 
         and that a specific ingredient (tomato) is correctly linked to its corresponding recipe (curry).
        """
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
