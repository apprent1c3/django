from django.core.exceptions import FieldError
from django.db.models import FilteredRelation
from django.test import SimpleTestCase, TestCase

from .models import (
    AdvancedUserStat,
    Child1,
    Child2,
    Child3,
    Child4,
    Image,
    LinkedList,
    Parent1,
    Parent2,
    Product,
    StatDetails,
    User,
    UserProfile,
    UserStat,
    UserStatResult,
)


class ReverseSelectRelatedTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = User.objects.create(username="test")
        UserProfile.objects.create(user=user, state="KS", city="Lawrence")
        results = UserStatResult.objects.create(results="first results")
        userstat = UserStat.objects.create(user=user, posts=150, results=results)
        StatDetails.objects.create(base_stats=userstat, comments=259)

        user2 = User.objects.create(username="bob")
        results2 = UserStatResult.objects.create(results="moar results")
        advstat = AdvancedUserStat.objects.create(
            user=user2, posts=200, karma=5, results=results2
        )
        StatDetails.objects.create(base_stats=advstat, comments=250)
        p1 = Parent1(name1="Only Parent1")
        p1.save()
        c1 = Child1(name1="Child1 Parent1", name2="Child1 Parent2", value=1)
        c1.save()
        p2 = Parent2(name2="Child2 Parent2")
        p2.save()
        c2 = Child2(name1="Child2 Parent1", parent2=p2, value=2)
        c2.save()

    def test_basic(self):
        """

        Tests the basic functionality of retrieving a user object with its associated user profile.

        Verifies that only one database query is executed when fetching a user with its profile using the select_related method.
        The test case also checks that the retrieved user's profile has the expected state.

        """
        with self.assertNumQueries(1):
            u = User.objects.select_related("userprofile").get(username="test")
            self.assertEqual(u.userprofile.state, "KS")

    def test_follow_next_level(self):
        with self.assertNumQueries(1):
            u = User.objects.select_related("userstat__results").get(username="test")
            self.assertEqual(u.userstat.posts, 150)
            self.assertEqual(u.userstat.results.results, "first results")

    def test_follow_two(self):
        """
        Tests the ability to follow a user with related profiles and statistics in a single database query.

        Verifies that a user can be retrieved from the database with their associated user profile and user statistics, 
        and that the expected state and post count values are correctly populated.

        The database query efficiency is also validated by ensuring only one query is executed during this process.
        """
        with self.assertNumQueries(1):
            u = User.objects.select_related("userprofile", "userstat").get(
                username="test"
            )
            self.assertEqual(u.userprofile.state, "KS")
            self.assertEqual(u.userstat.posts, 150)

    def test_follow_two_next_level(self):
        """

        Tests that the user's stat details and results can be accessed in a single database query.

        Verifies that the userstat object associated with a given user contains the correct
        results and stat details, and that this data can be retrieved without generating
        additional database queries.

        This test case checks the following conditions:
        - The user's results match the expected value.
        - The user's stat details contain the correct number of comments.

        """
        with self.assertNumQueries(1):
            u = User.objects.select_related(
                "userstat__results", "userstat__statdetails"
            ).get(username="test")
            self.assertEqual(u.userstat.results.results, "first results")
            self.assertEqual(u.userstat.statdetails.comments, 259)

    def test_forward_and_back(self):
        """
        Tests the forward and backward relationships of the UserStat model.

        This test case verifies that a UserStat object can be retrieved with its related User and UserProfile objects in a single database query.
        It then checks that the retrieved User object has a UserProfile with the expected state and that the UserStat object has the correct number of posts associated with it.
        """
        with self.assertNumQueries(1):
            stat = UserStat.objects.select_related("user__userprofile").get(
                user__username="test"
            )
            self.assertEqual(stat.user.userprofile.state, "KS")
            self.assertEqual(stat.user.userstat.posts, 150)

    def test_back_and_forward(self):
        """
        Tests that a user's associated user statistics can be retrieved in a single database query.

        Verifies that the `select_related` method is used correctly to fetch the user's statistics
        along with the user object, and that the statistics are properly linked back to the original user.

        Checks that the resulting object's `userstat` attribute contains a valid `User` object with a matching `username` property.
        """
        with self.assertNumQueries(1):
            u = User.objects.select_related("userstat").get(username="test")
            self.assertEqual(u.userstat.user.username, "test")

    def test_not_followed_by_default(self):
        with self.assertNumQueries(2):
            u = User.objects.select_related().get(username="test")
            self.assertEqual(u.userstat.posts, 150)

    def test_follow_from_child_class(self):
        """
        Checks if the related objects are correctly loaded from the database when retrieving an AdvancedUserStat instance with a certain number of posts.

        The test verifies that the stat details and user associated with the stat are properly fetched in a single database query, and that their attributes match the expected values. Specifically, it checks that the comments count in the stat details is 250 and the username of the associated user is 'bob'.
        """
        with self.assertNumQueries(1):
            stat = AdvancedUserStat.objects.select_related("user", "statdetails").get(
                posts=200
            )
            self.assertEqual(stat.statdetails.comments, 250)
            self.assertEqual(stat.user.username, "bob")

    def test_follow_inheritance(self):
        with self.assertNumQueries(1):
            stat = UserStat.objects.select_related("user", "advanceduserstat").get(
                posts=200
            )
            self.assertEqual(stat.advanceduserstat.posts, 200)
            self.assertEqual(stat.user.username, "bob")
        with self.assertNumQueries(0):
            self.assertEqual(stat.advanceduserstat.user.username, "bob")

    def test_nullable_relation(self):
        """
        Tests the ability to handle nullable relations in the Product model.

        This test creates a Product instance with an associated Image and another without.
        It then retrieves all Product instances using a single query, sorts them by name,
        and verifies that the expected products are returned with their respective image
        associations correctly set, including the case where no image is associated.
        """
        im = Image.objects.create(name="imag1")
        p1 = Product.objects.create(name="Django Plushie", image=im)
        p2 = Product.objects.create(name="Talking Django Plushie")

        with self.assertNumQueries(1):
            result = sorted(
                Product.objects.select_related("image"), key=lambda x: x.name
            )
            self.assertEqual(
                [p.name for p in result], ["Django Plushie", "Talking Django Plushie"]
            )

            self.assertEqual(p1.image, im)
            # Check for ticket #13839
            self.assertIsNone(p2.image)

    def test_missing_reverse(self):
        """
        Ticket #13839: select_related() should NOT cache None
        for missing objects on a reverse 1-1 relation.
        """
        with self.assertNumQueries(1):
            user = User.objects.select_related("userprofile").get(username="bob")
            with self.assertRaises(UserProfile.DoesNotExist):
                user.userprofile

    def test_nullable_missing_reverse(self):
        """
        Ticket #13839: select_related() should NOT cache None
        for missing objects on a reverse 0-1 relation.
        """
        Image.objects.create(name="imag1")

        with self.assertNumQueries(1):
            image = Image.objects.select_related("product").get()
            with self.assertRaises(Product.DoesNotExist):
                image.product

    def test_parent_only(self):
        """
        Tests the behavior of retrieving a parent object with a non-existent child.

        This test case verifies that using select_related to retrieve a parent object
        does not create unnecessary database queries when accessing a child object that
        does not exist. It ensures that the correct exception is raised in such cases.

        The test checks for the number of database queries made during the retrieval of
        the parent object and when attempting to access the non-existent child object,
        verifying that the latter operation does not incur any additional database queries.

        Raises:
            Child1.DoesNotExist: When attempting to access the child object.

        """
        with self.assertNumQueries(1):
            p = Parent1.objects.select_related("child1").get(name1="Only Parent1")
        with self.assertNumQueries(0):
            with self.assertRaises(Child1.DoesNotExist):
                p.child1

    def test_multiple_subclass(self):
        with self.assertNumQueries(1):
            p = Parent1.objects.select_related("child1").get(name1="Child1 Parent1")
            self.assertEqual(p.child1.name2, "Child1 Parent2")

    def test_onetoone_with_subclass(self):
        with self.assertNumQueries(1):
            p = Parent2.objects.select_related("child2").get(name2="Child2 Parent2")
            self.assertEqual(p.child2.name1, "Child2 Parent1")

    def test_onetoone_with_two_subclasses(self):
        with self.assertNumQueries(1):
            p = Parent2.objects.select_related("child2", "child2__child3").get(
                name2="Child2 Parent2"
            )
            self.assertEqual(p.child2.name1, "Child2 Parent1")
            with self.assertRaises(Child3.DoesNotExist):
                p.child2.child3
        p3 = Parent2(name2="Child3 Parent2")
        p3.save()
        c2 = Child3(name1="Child3 Parent1", parent2=p3, value=2, value3=3)
        c2.save()
        with self.assertNumQueries(1):
            p = Parent2.objects.select_related("child2", "child2__child3").get(
                name2="Child3 Parent2"
            )
            self.assertEqual(p.child2.name1, "Child3 Parent1")
            self.assertEqual(p.child2.child3.value3, 3)
            self.assertEqual(p.child2.child3.value, p.child2.value)
            self.assertEqual(p.child2.name1, p.child2.child3.name1)

    def test_multiinheritance_two_subclasses(self):
        """

        Tests the multi-inheritance of two subclasses in a complex object relationship.

        Verifies that the proper relationships are established between Parent1, Child1, 
        Child4, and Parent2 objects. The test checks for the correct retrieval of 
        related objects using select_related and asserts the expected attribute values.

        It also tests for the expected behavior when a related object does not exist, 
        raising a DoesNotExist exception.

        Ensures that after creating a Child4 object, the relationships are correctly 
        established and retrieves the related objects in a single database query.

        """
        with self.assertNumQueries(1):
            p = Parent1.objects.select_related("child1", "child1__child4").get(
                name1="Child1 Parent1"
            )
            self.assertEqual(p.child1.name2, "Child1 Parent2")
            self.assertEqual(p.child1.name1, p.name1)
            with self.assertRaises(Child4.DoesNotExist):
                p.child1.child4
        Child4(name1="n1", name2="n2", value=1, value4=4).save()
        with self.assertNumQueries(1):
            p = Parent2.objects.select_related("child1", "child1__child4").get(
                name2="n2"
            )
            self.assertEqual(p.name2, "n2")
            self.assertEqual(p.child1.name1, "n1")
            self.assertEqual(p.child1.name2, p.name2)
            self.assertEqual(p.child1.value, 1)
            self.assertEqual(p.child1.child4.name1, p.child1.name1)
            self.assertEqual(p.child1.child4.name2, p.child1.name2)
            self.assertEqual(p.child1.child4.value, p.child1.value)
            self.assertEqual(p.child1.child4.value4, 4)

    def test_inheritance_deferred(self):
        """

        Tests the deferred loading of inherited fields in related models.

        This test case verifies that using select_related and only methods to fetch 
        specific fields from the Parent2 model and its related Child1 model results 
        in the expected number of database queries. It checks that the fields 
        specified in the only method are retrieved correctly, while other fields 
        are deferred until accessed.

        The test covers scenarios where accessing deferred fields triggers 
        additional database queries, ensuring that the query count remains 
        consistent with expectations.

        """
        c = Child4.objects.create(name1="n1", name2="n2", value=1, value4=4)
        with self.assertNumQueries(1):
            p = (
                Parent2.objects.select_related("child1")
                .only("id2", "child1__value")
                .get(name2="n2")
            )
            self.assertEqual(p.id2, c.id2)
            self.assertEqual(p.child1.value, 1)
        p = (
            Parent2.objects.select_related("child1")
            .only("id2", "child1__value")
            .get(name2="n2")
        )
        with self.assertNumQueries(1):
            self.assertEqual(p.name2, "n2")
        p = (
            Parent2.objects.select_related("child1")
            .only("id2", "child1__value")
            .get(name2="n2")
        )
        with self.assertNumQueries(1):
            self.assertEqual(p.child1.name2, "n2")

    def test_inheritance_deferred2(self):
        """
        Tests deferred loading of inherited fields in a multi-level inheritance scenario.

        Verifies that when using select_related() to load related objects, 
        the correct number of database queries is executed and 
        the loaded fields have the expected values.

        Specifically, this test covers the following scenarios:

        * Loading of a parent object with its child and grandchild objects
        * Accessing fields of the child and grandchild objects
        * Verification that subsequent accesses to already loaded fields do not result in additional database queries

        The test ensures that the correct data is retrieved and that the 
        database query count is as expected, demonstrating the 
        correctness of the deferred loading mechanism in the given inheritance hierarchy.
        """
        c = Child4.objects.create(name1="n1", name2="n2", value=1, value4=4)
        qs = Parent2.objects.select_related("child1", "child1__child4").only(
            "id2", "child1__value", "child1__child4__value4"
        )
        with self.assertNumQueries(1):
            p = qs.get(name2="n2")
            self.assertEqual(p.id2, c.id2)
            self.assertEqual(p.child1.value, 1)
            self.assertEqual(p.child1.child4.value4, 4)
            self.assertEqual(p.child1.child4.id2, c.id2)
        p = qs.get(name2="n2")
        with self.assertNumQueries(1):
            self.assertEqual(p.child1.name2, "n2")
        p = qs.get(name2="n2")
        with self.assertNumQueries(0):
            self.assertEqual(p.child1.value, 1)
            self.assertEqual(p.child1.child4.value4, 4)
        with self.assertNumQueries(2):
            self.assertEqual(p.child1.name1, "n1")
            self.assertEqual(p.child1.child4.name1, "n1")

    def test_self_relation(self):
        item1 = LinkedList.objects.create(name="item1")
        LinkedList.objects.create(name="item2", previous_item=item1)
        with self.assertNumQueries(1):
            item1_db = LinkedList.objects.select_related("next_item").get(name="item1")
            self.assertEqual(item1_db.next_item.name, "item2")


class ReverseSelectRelatedValidationTests(SimpleTestCase):
    """
    Rverse related fields should be listed in the validation message when an
    invalid field is given in select_related().
    """

    non_relational_error = (
        "Non-relational field given in select_related: '%s'. Choices are: %s"
    )
    invalid_error = (
        "Invalid field name(s) given in select_related: '%s'. Choices are: %s"
    )

    def test_reverse_related_validation(self):
        """
        Tests validation of related field names in the select_related method.

        Verifies that attempting to select a related field that does not exist raises a FieldError with the correct error message.
        Additionally, checks that attempting to select a non-relational field raises a FieldError with a corresponding error message.

        The test covers the following scenarios:
        - Passing a non-existent related field name
        - Passing a non-relational field name
        """
        fields = "userprofile, userstat"

        with self.assertRaisesMessage(
            FieldError, self.invalid_error % ("foobar", fields)
        ):
            list(User.objects.select_related("foobar"))

        with self.assertRaisesMessage(
            FieldError, self.non_relational_error % ("username", fields)
        ):
            list(User.objects.select_related("username"))

    def test_reverse_related_validation_with_filtered_relation(self):
        """
        Tests the validation of reverse related lookups with a filtered relation.

        Verifies that an error is raised when attempting to select a related field 
        that does not exist, while using an annotated filtered relation. This 
        ensures the correctness of the filtering and joining mechanism for related 
        objects, and guarantees that invalid field names are properly handled.
        """
        fields = "userprofile, userstat, relation"
        with self.assertRaisesMessage(
            FieldError, self.invalid_error % ("foobar", fields)
        ):
            list(
                User.objects.annotate(
                    relation=FilteredRelation("userprofile")
                ).select_related("foobar")
            )
