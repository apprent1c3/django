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
        Sets up test data for the class, creating entities that can be shared across multiple tests to reduce duplication and improve performance. 
        This includes creating three people, 'Bob', 'Jim', and 'Jane', as well as two groups, 'Rock' and 'Roll', which can be used as a foundation for various test scenarios.
        """
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
        """
        Test that retrieving intermediate items from a many-to-many relationship returns the correct results.

        This test case verifies that the `members` attribute of a group returns a QuerySet containing the names of all members in that group, in a specific order. The test creates test data, including two memberships between people and a group, and then checks that the QuerySet returned by `group.members.all()` contains the names of the people in the expected order.
        """
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
        """

        Tests adding a member to a many-to-many relationship with an intermediate model.

        Verifies that a member can be successfully added to the relationship with custom
        attributes set through the intermediate model, and that the resulting membership
        can be retrieved and its attributes validated.

        """
        self.rock.members.add(
            self.bob, through_defaults={"invite_reason": "He is good."}
        )
        self.assertSequenceEqual(self.rock.members.all(), [self.bob])
        self.assertEqual(self.rock.membership_set.get().invite_reason, "He is good.")

    def test_add_on_m2m_with_intermediate_model_callable_through_default(self):
        """
        Determines if many-to-many relationships with intermediate models can be created using a callable when specifying default values.

        The function tests whether the `add` method on a many-to-many field can successfully create intermediate model instances using a callable to generate a default value for one of the model's fields. It checks that the related objects are correctly associated with the main model and that the default values were applied as expected to the intermediate model instances.
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
        Tests setting many-to-many relationships through an intermediate model using callable default values.

        This test case verifies that the many-to-many relationship can be successfully established between two models with an intermediate model, 
        using a callable default value for one of the intermediate model's fields. The test checks that the relationship is correctly set up 
        for multiple instances and that the default value is correctly applied to the intermediate model instances.
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

        Tests adding a relationship to a Many-to-Many field with an intermediate model where a value is required.

        Verifies that when a new relationship is created, the required value is properly set on the intermediate model.

        The test case ensures data consistency by checking the assigned value is correctly stored in the database.

        """
        self.rock.nodefaultsnonulls.add(
            self.jim, through_defaults={"nodefaultnonull": 1}
        )
        self.assertEqual(self.rock.testnodefaultsornulls_set.get().nodefaultnonull, 1)

    def test_add_on_m2m_with_intermediate_model_value_required_fails(self):
        """
        **:param self: Test instance
            :return: None
            :raises IntegrityError: When attempting to add a value to a many-to-many relationship with an intermediate model that requires a value.

            Tests that adding a value to a many-to-many relationship with an intermediate model that has required fields fails as expected, causing an integrity error. This ensures that the relationship is properly enforced and that required fields in the intermediate model cannot be left empty or null.```
        """
        with self.assertRaises(IntegrityError):
            self.rock.nodefaultsnonulls.add(self.jim)

    def test_create_on_m2m_with_intermediate_model(self):
        """
        Tests creation of a many-to-many relationship with an intermediate model.

        This test case verifies the functionality of creating a new instance of the many-to-many relationship 
        with an intermediate model and checks if the instance is correctly associated with the parent object.
        It also validates that the through defaults are properly applied to the intermediate model instance.
        The test ensures that the resulting relationship is correctly established and the intermediate model 
        instance is populated with the expected data.
        """
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
        """
        Tests the creation of an instance with a many-to-many relationship using an intermediate model, 
        where one of the fields on the intermediate model is required.

        Verifies that the instance can be successfully created with the required field populated, 
        and that the value is correctly set on the intermediate model instance. 
        """
        self.rock.nodefaultsnonulls.create(
            name="Test", through_defaults={"nodefaultnonull": 1}
        )
        self.assertEqual(self.rock.testnodefaultsornulls_set.get().nodefaultnonull, 1)

    def test_create_on_m2m_with_intermediate_model_value_required_fails(self):
        """

        Tests that creating an instance on a many-to-many relationship with an intermediate model
        where a value is required fails as expected.

        Checks for the correct raising of an IntegrityError when attempting to create a new instance
        without providing the required value, ensuring data integrity and consistency.

        """
        with self.assertRaises(IntegrityError):
            self.rock.nodefaultsnonulls.create(name="Test")

    def test_get_or_create_on_m2m_with_intermediate_model_value_required(self):
        """
        Tests the get_or_create method on a many-to-many relationship with an intermediate model that has a value required. 

        Verifies that when creating a new instance, the required value is correctly set on the intermediate model. 

        The function checks the behavior of the get_or_create method when there are no existing instances that match the given criteria, and ensures that the default value is applied as specified. 

        It validates the result by asserting that the value on the intermediate model matches the expected value.
        """
        self.rock.nodefaultsnonulls.get_or_create(
            name="Test", through_defaults={"nodefaultnonull": 1}
        )
        self.assertEqual(self.rock.testnodefaultsornulls_set.get().nodefaultnonull, 1)

    def test_get_or_create_on_m2m_with_intermediate_model_value_required_fails(self):
        """

        Tests that get_or_create on a many-to-many relationship with an intermediate model fails 
        when a required value is not provided, resulting in an IntegrityError.

        This test case verifies the expected behavior when attempting to create a new instance 
        without supplying all necessary fields, ensuring data consistency and integrity.

        """
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
        Tests removal of an object from a many-to-many relationship with an intermediate model when there are multiple relationships between the objects.

        This test case creates multiple memberships between a person and a group using an intermediate model, then verifies that removing the person from the group correctly removes all associated memberships.

        It ensures that the many-to-many relationship is properly updated and that all intermediate model instances are removed when the related object is removed from the relationship.
        """
        Membership.objects.create(person=self.jim, group=self.rock, invite_reason="1")
        Membership.objects.create(person=self.jim, group=self.rock, invite_reason="2")
        self.assertSequenceEqual(self.rock.members.all(), [self.jim, self.jim])
        self.rock.members.remove(self.jim)
        self.assertSequenceEqual(self.rock.members.all(), [])

    def test_set_on_m2m_with_intermediate_model(self):
        """

        Tests the ability to set a many-to-many relationship with an intermediate model.

        This test case verifies that setting the members of an object (in this case, a rock)
        using a list of Person objects results in the correct associated members.
        It checks that after setting the members, the associated members are correctly retrieved.

        """
        members = list(Person.objects.filter(name__in=["Bob", "Jim"]))
        self.rock.members.set(members)
        self.assertSequenceEqual(self.rock.members.all(), [self.bob, self.jim])

    def test_set_on_m2m_with_intermediate_model_value_required(self):
        """

        Test setting values on a many-to-many relationship with an intermediate model 
        that has a value required.

        This test case covers the scenario where a many-to-many relationship is 
        established through an intermediate model, where the intermediate model has 
        a required field. The test verifies that the value of this required field is 
        correctly set when adding or updating the relationship, and that the existing 
        value is replaced when the clear option is used.

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
        /gtest_set_on_m2m_with_intermediate_model_value_required_fails(

            Tests that setting a Many-To-Many relationship with an intermediate model 
            that has a value required field fails when the value is not provided.

            This test case verifies that an IntegrityError is raised when attempting to 
            set the relationship without specifying the required value, ensuring data 
            consistency and integrity.
        )
        """
        with self.assertRaises(IntegrityError):
            self.rock.nodefaultsnonulls.set([self.jim])

    def test_clear_removes_all_the_m2m_relationships(self):
        """
        Tests the clear method of a Many-To-Many field to ensure it removes all related objects.

        Verifies that calling clear on a Many-To-Many relationship field successfully removes all associated relationships, 
        leaving the field with no related objects. This test is crucial for ensuring data integrity when modifying relationships 
        between models. It checks the expected behavior of the clear method in a real-world scenario, such as removing all 
        members from a group. The test confirms that after clearing the relationships, querying the related objects returns an 
        empty set, as expected.
        """
        Membership.objects.create(person=self.jim, group=self.rock)
        Membership.objects.create(person=self.jane, group=self.rock)

        self.rock.members.clear()

        self.assertQuerySetEqual(self.rock.members.all(), [])

    def test_retrieve_reverse_intermediate_items(self):
        """

        Tests the retrieval of reverse intermediate items for a person's group memberships.

        Verifies that the function correctly retrieves and returns a list of group names 
        associated with a person, in the expected order. 

        """
        Membership.objects.create(person=self.jim, group=self.rock)
        Membership.objects.create(person=self.jim, group=self.roll)

        expected = ["Rock", "Roll"]
        self.assertQuerySetEqual(self.jim.group_set.all(), expected, attrgetter("name"))

    def test_add_on_reverse_m2m_with_intermediate_model(self):
        self.bob.group_set.add(self.rock)
        self.assertSequenceEqual(self.bob.group_set.all(), [self.rock])

    def test_create_on_reverse_m2m_with_intermediate_model(self):
        """
        Tests the creation of an instance on a reverse many-to-many relationship with an intermediate model.

        Verifies that when a new instance is created, it is correctly associated with the related object and that the relationship can be queried to retrieve the expected instance.

        This test covers the scenario where a new group is created for a given user and ensures that the group is properly linked to the user and can be retrieved through the user's group set.
        """
        funk = self.bob.group_set.create(name="Funk")
        self.assertSequenceEqual(self.bob.group_set.all(), [funk])

    def test_remove_on_reverse_m2m_with_intermediate_model(self):
        """
        Stores a person in a group and then removes them, verifying that removal from a many-to-many relationship via an intermediate model functions as expected, specifically checking that the person's group set is emptied after removal.
        """
        Membership.objects.create(person=self.bob, group=self.rock)
        self.bob.group_set.remove(self.rock)
        self.assertSequenceEqual(self.bob.group_set.all(), [])

    def test_set_on_reverse_m2m_with_intermediate_model(self):
        members = list(Group.objects.filter(name__in=["Rock", "Roll"]))
        self.bob.group_set.set(members)
        self.assertSequenceEqual(self.bob.group_set.all(), [self.rock, self.roll])

    def test_clear_on_reverse_removes_all_the_m2m_relationships(self):
        """
        Checks that clearing the many-to-many relationship between a person and groups removes all existing relationships. 

        This test ensures that when a person's group set is cleared, all associated group memberships are deleted, resulting in an empty group set.
        """
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
        """
        ### test_query_second_model_by_intermediate_model_attribute

        Tests querying a model (Person) based on attributes of an intermediate model (Membership) that it is related to.

        This test case verifies that a Person can be successfully filtered by a specific attribute (invite_reason) of their Membership instance, demonstrating the ability to traverse relationships and apply filters across models. The test creates multiple memberships with different invite reasons, then queries for the person with a specific invite reason, asserting that the correct person is returned.
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
        This function tests the ability of the Person model to be queried based on the name of a related model, specifically the Group model. It checks if the correct Person instances are returned when filtering by the Group name, ensuring that the model relationships are correctly established and the query is executed as expected. The test covers scenarios where multiple persons are part of the same group, verifying that the filtering works accurately and returns the correct persons associated with a group by name.
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
        """
        Tests the querying of the Person model using a custom related name.

        This function creates custom membership relationships between persons and groups, then verifies that the Person model can be queried using the custom related name 'custom'. It checks that the query correctly returns a queryset of persons that are members of a group with the name 'Rock', and that the persons are returned in the expected order.

        The function covers the following scenarios:
        - Creation of custom membership relationships
        - Querying the Person model using the custom related name
        - Verification of the results of the query, including the expected persons and their order.
        """
        CustomMembership.objects.create(person=self.bob, group=self.rock)
        CustomMembership.objects.create(person=self.jim, group=self.rock)

        self.assertQuerySetEqual(
            Person.objects.filter(custom__name="Rock"),
            ["Bob", "Jim"],
            attrgetter("name"),
        )

    def test_query_model_by_intermediate_can_return_non_unique_queryset(self):
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
        """
        Tests that a custom related name can be successfully used to traverse relationships in the reverse direction with a non-empty queryset.

        This test case creates multiple custom membership instances and verifies that the related objects are correctly retrieved using the custom related name, ensuring that the resulting queryset is populated with the expected values.

        The test asserts that the custom related name 'custom' on the person model correctly returns all groups that the person is a member of, by comparing the resulting queryset to an expected list of group names.
        """
        CustomMembership.objects.create(person=self.bob, group=self.rock)
        CustomMembership.objects.create(person=self.jim, group=self.rock)

        self.assertQuerySetEqual(self.bob.custom.all(), ["Rock"], attrgetter("name"))

    def test_custom_related_name_doesnt_conflict_with_fky_related_name(self):
        """

        Tests that a custom related name on a model does not conflict with the related name generated by a foreign key.

        This test ensures that a custom related name can be used without interfering with the automatically generated related name
        from a foreign key, allowing for correct retrieval of related objects.

        Verifies that the custom related name :attr:`custom_person_related_name` returns the expected related object.

        """
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
        Tests that a newly created PersonSelfRefM2M instance has an empty queryset of friends.

        Verifies that when a new person is created, their friends many-to-many relationship is correctly initialized as empty, confirming proper data integrity and relationship setup.

        """
        tony = PersonSelfRefM2M.objects.create(name="Tony")
        self.assertQuerySetEqual(tony.friends.all(), [])

    def test_self_referential_non_symmetrical_first_side(self):
        """
        Tests the establishment of a self-referential non-symmetrical friendship from the first side.

        This test case verifies that when a friendship is created with a person as the first participant,
        the person's friends are correctly queried. It checks that the friend of the first person is 
        correctly identified and their name is retrieved as expected.
        """
        tony = PersonSelfRefM2M.objects.create(name="Tony")
        chris = PersonSelfRefM2M.objects.create(name="Chris")
        Friendship.objects.create(
            first=tony, second=chris, date_friended=datetime.now()
        )

        self.assertQuerySetEqual(tony.friends.all(), ["Chris"], attrgetter("name"))

    def test_self_referential_non_symmetrical_second_side(self):
        """

        Tests a non-symmetrical self-referential many-to-many relationship.

        Verifies that when a person is friends with another, the friendship is not automatically
        reciprocated. In this case, when 'Tony' becomes friends with 'Chris', 'Chris' should
        not have 'Tony' as a friend unless explicitly added.

        Ensures that the query to retrieve a person's friends returns an empty set when no
        friendship has been established from their side.

        """
        tony = PersonSelfRefM2M.objects.create(name="Tony")
        chris = PersonSelfRefM2M.objects.create(name="Chris")
        Friendship.objects.create(
            first=tony, second=chris, date_friended=datetime.now()
        )

        self.assertQuerySetEqual(chris.friends.all(), [])

    def test_self_referential_non_symmetrical_clear_first_side(self):
        """

        Tests the removal of friendships from one side of a self-referential many-to-many relationship.

        Checks that when a person clears their friends, the friendship is removed from their side,
        but the other person still appears as a friend to the original person, demonstrating
        the non-symmetrical nature of the relationship.

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
        Tests that symmetrical friendships are correctly established between two individuals.

        This test verifies that when a friendship is created from one person to another,
        the reverse relationship is not automatically established. It then checks that
        when the reciprocal friendship is created, the relationship becomes symmetrical
        and is correctly reflected in both individuals' friends lists.

        The test case covers the following scenarios:
        - Creating a one-way friendship between two individuals
        - Verifying that the friendship is not automatically reciprocal
        - Establishing the reciprocal friendship
        - Confirming that the friendship is now symmetrical
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
        Tests the behavior of setting many-to-many relationships with an intermediate model on a symmetrical relationship.

        Verifies that the addition and replacement of related objects, as well as the updating of intermediate model fields, is correctly handled in both directions of the relationship. 

        The test case covers scenarios such as adding and setting related objects, checking the equality of the sequence of related objects on both sides of the relationship, and verifying the correctness of the intermediate model fields after these operations. 

        Specifically, it checks that the relationships are correctly established and updated when using the `add` and `set` methods, including when using the `through_defaults` parameter to set fields on the intermediate model. 

        It also tests that the relationships are correctly cleared and recreated when using the `set` method with the `clear=True` parameter, ensuring that the intermediate model fields are updated correctly in this scenario as well. 
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

        Tests the retrieval of associated recipes and ingredients.

        Verifies that the ingredients of the curry recipe are correctly retrieved and
        that the tomato ingredient is associated with the expected curry recipe.

        """
        self.assertSequenceEqual(
            self.curry.ingredients.all(), [self.pea, self.potato, self.tomato]
        )
        # Backward retrieval
        self.assertEqual(self.tomato.recipes.get(), self.curry)

    def test_choices(self):
        """
        Checks if the 'ingredients' field of the Recipe model has the correct choices.

        The function verifies that the 'ingredients' field provides the expected list of options, excluding any blank choices. It asserts that the choices match a predefined set of ingredients, specifically 'pea', 'potato', and 'tomato'.
        """
        field = Recipe._meta.get_field("ingredients")
        self.assertEqual(
            [choice[0] for choice in field.get_choices(include_blank=False)],
            ["pea", "potato", "tomato"],
        )
