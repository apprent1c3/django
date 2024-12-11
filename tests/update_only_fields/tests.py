from django.db.models.signals import post_save, pre_save
from django.test import TestCase
from django.utils.deprecation import RemovedInDjango60Warning

from .models import Account, Employee, Person, Profile, ProxyEmployee


class UpdateOnlyFieldsTests(TestCase):
    msg = (
        "The following fields do not exist in this model, are m2m fields, or "
        "are non-concrete fields: %s"
    )

    def test_update_fields_basic(self):
        s = Person.objects.create(name="Sara", gender="F")
        self.assertEqual(s.gender, "F")

        s.gender = "M"
        s.name = "Ian"
        s.save(update_fields=["name"])

        s = Person.objects.get(pk=s.pk)
        self.assertEqual(s.gender, "F")
        self.assertEqual(s.name, "Ian")

    def test_update_fields_deferred(self):
        s = Person.objects.create(name="Sara", gender="F", pid=22)
        self.assertEqual(s.gender, "F")

        s1 = Person.objects.defer("gender", "pid").get(pk=s.pk)
        s1.name = "Emily"
        s1.gender = "M"

        with self.assertNumQueries(1):
            s1.save()

        s2 = Person.objects.get(pk=s1.pk)
        self.assertEqual(s2.name, "Emily")
        self.assertEqual(s2.gender, "M")

    def test_update_fields_only_1(self):
        """
        Tests that updating a model instance using only() updates the changed fields.

        This test case verifies that when retrieving a model instance with only()
        and modifying its fields, the changes are persisted in the database.
        It checks that the update operation only updates the fields that were
        modified, without affecting other fields. The test also ensures that
        the update is performed efficiently, using only a single database query.

        It validates that the updated fields are correctly persisted and 
        retrieved, demonstrating the correctness of the model's update behavior 
        when using only().
        """
        s = Person.objects.create(name="Sara", gender="F")
        self.assertEqual(s.gender, "F")

        s1 = Person.objects.only("name").get(pk=s.pk)
        s1.name = "Emily"
        s1.gender = "M"

        with self.assertNumQueries(1):
            s1.save()

        s2 = Person.objects.get(pk=s1.pk)
        self.assertEqual(s2.name, "Emily")
        self.assertEqual(s2.gender, "M")

    def test_update_fields_only_2(self):
        s = Person.objects.create(name="Sara", gender="F", pid=22)
        self.assertEqual(s.gender, "F")

        s1 = Person.objects.only("name").get(pk=s.pk)
        s1.name = "Emily"
        s1.gender = "M"

        with self.assertNumQueries(2):
            s1.save(update_fields=["pid"])

        s2 = Person.objects.get(pk=s1.pk)
        self.assertEqual(s2.name, "Sara")
        self.assertEqual(s2.gender, "F")

    def test_update_fields_only_repeated(self):
        s = Person.objects.create(name="Sara", gender="F")
        self.assertEqual(s.gender, "F")

        s1 = Person.objects.only("name").get(pk=s.pk)
        s1.gender = "M"
        with self.assertNumQueries(1):
            s1.save()
        # save() should not fetch deferred fields
        s1 = Person.objects.only("name").get(pk=s.pk)
        with self.assertNumQueries(1):
            s1.save()

    def test_update_fields_inheritance_defer(self):
        """
        Tests the update fields functionality when using inheritance and deferred fields.

        Verifies that updating a deferred field, in this case the employee's name, 
        results in a single database query when saving the object. 

        Ensures that the changes are persisted correctly and can be retrieved from the database.
        """
        profile_boss = Profile.objects.create(name="Boss", salary=3000)
        e1 = Employee.objects.create(
            name="Sara", gender="F", employee_num=1, profile=profile_boss
        )
        e1 = Employee.objects.only("name").get(pk=e1.pk)
        e1.name = "Linda"
        with self.assertNumQueries(1):
            e1.save()
        self.assertEqual(Employee.objects.get(pk=e1.pk).name, "Linda")

    def test_update_fields_fk_defer(self):
        """

        Tests the update of fields with foreign key defer.

        This test case checks whether updating a foreign key field
        on an existing model instance results in the expected database queries
        and outcome. It creates two profiles, sets a foreign key reference to one of them,
        updates it to the other, and then back to the first, verifying in each case
        that the correct profile is associated with the employee instance and that the
        update is performed with the expected number of database queries.

        The purpose of this test is to ensure that the foreign key deferral functionality
        is working as expected, allowing for efficient updates of related fields.

        """
        profile_boss = Profile.objects.create(name="Boss", salary=3000)
        profile_receptionist = Profile.objects.create(name="Receptionist", salary=1000)
        e1 = Employee.objects.create(
            name="Sara", gender="F", employee_num=1, profile=profile_boss
        )
        e1 = Employee.objects.only("profile").get(pk=e1.pk)
        e1.profile = profile_receptionist
        with self.assertNumQueries(1):
            e1.save()
        self.assertEqual(Employee.objects.get(pk=e1.pk).profile, profile_receptionist)
        e1.profile_id = profile_boss.pk
        with self.assertNumQueries(1):
            e1.save()
        self.assertEqual(Employee.objects.get(pk=e1.pk).profile, profile_boss)

    def test_select_related_only_interaction(self):
        profile_boss = Profile.objects.create(name="Boss", salary=3000)
        e1 = Employee.objects.create(
            name="Sara", gender="F", employee_num=1, profile=profile_boss
        )
        e1 = (
            Employee.objects.only("profile__salary")
            .select_related("profile")
            .get(pk=e1.pk)
        )
        profile_boss.name = "Clerk"
        profile_boss.salary = 1000
        profile_boss.save()
        # The loaded salary of 3000 gets saved, the name of 'Clerk' isn't
        # overwritten.
        with self.assertNumQueries(1):
            e1.profile.save()
        reloaded_profile = Profile.objects.get(pk=profile_boss.pk)
        self.assertEqual(reloaded_profile.name, profile_boss.name)
        self.assertEqual(reloaded_profile.salary, 3000)

    def test_update_fields_m2m(self):
        profile_boss = Profile.objects.create(name="Boss", salary=3000)
        e1 = Employee.objects.create(
            name="Sara", gender="F", employee_num=1, profile=profile_boss
        )
        a1 = Account.objects.create(num=1)
        a2 = Account.objects.create(num=2)
        e1.accounts.set([a1, a2])

        with self.assertRaisesMessage(ValueError, self.msg % "accounts"):
            e1.save(update_fields=["accounts"])

    def test_update_fields_inheritance(self):
        """

        Tests the behavior of updating specific fields in the Employee model while inheriting from the Profile model.

        Verifies that only the specified fields are updated when using the update_fields parameter in the save method.
        Validates that changes to an Employee instance's profile and other attributes are persisted correctly.
        Also checks that the number of database queries is optimized when updating the profile field by its id.

        """
        profile_boss = Profile.objects.create(name="Boss", salary=3000)
        profile_receptionist = Profile.objects.create(name="Receptionist", salary=1000)
        e1 = Employee.objects.create(
            name="Sara", gender="F", employee_num=1, profile=profile_boss
        )

        e1.name = "Ian"
        e1.gender = "M"
        e1.save(update_fields=["name"])

        e2 = Employee.objects.get(pk=e1.pk)
        self.assertEqual(e2.name, "Ian")
        self.assertEqual(e2.gender, "F")
        self.assertEqual(e2.profile, profile_boss)

        e2.profile = profile_receptionist
        e2.name = "Sara"
        e2.save(update_fields=["profile"])

        e3 = Employee.objects.get(pk=e1.pk)
        self.assertEqual(e3.name, "Ian")
        self.assertEqual(e3.profile, profile_receptionist)

        with self.assertNumQueries(1):
            e3.profile = profile_boss
            e3.save(update_fields=["profile_id"])

        e4 = Employee.objects.get(pk=e3.pk)
        self.assertEqual(e4.profile, profile_boss)
        self.assertEqual(e4.profile_id, profile_boss.pk)

    def test_update_fields_inheritance_with_proxy_model(self):
        profile_boss = Profile.objects.create(name="Boss", salary=3000)
        profile_receptionist = Profile.objects.create(name="Receptionist", salary=1000)
        e1 = ProxyEmployee.objects.create(
            name="Sara", gender="F", employee_num=1, profile=profile_boss
        )

        e1.name = "Ian"
        e1.gender = "M"
        e1.save(update_fields=["name"])

        e2 = ProxyEmployee.objects.get(pk=e1.pk)
        self.assertEqual(e2.name, "Ian")
        self.assertEqual(e2.gender, "F")
        self.assertEqual(e2.profile, profile_boss)

        e2.profile = profile_receptionist
        e2.name = "Sara"
        e2.save(update_fields=["profile"])

        e3 = ProxyEmployee.objects.get(pk=e1.pk)
        self.assertEqual(e3.name, "Ian")
        self.assertEqual(e3.profile, profile_receptionist)

    def test_update_fields_signals(self):
        """
        Tests that the update_fields argument is correctly passed to pre_save and post_save signals when saving a model instance.

        This test creates a Person instance, connects to the pre_save and post_save signals, saves the instance with the update_fields argument set to ['name'], and then checks that the update_fields argument is correctly received by the signal receivers.

        The test verifies that the update_fields argument contains the expected field name ('name') and that the signal receivers are called the expected number of times.

        By testing the update_fields argument in this way, this test ensures that the signals are sent correctly and can be relied upon by other parts of the application that need to respond to model instance updates.
        """
        p = Person.objects.create(name="Sara", gender="F")
        pre_save_data = []

        def pre_save_receiver(**kwargs):
            pre_save_data.append(kwargs["update_fields"])

        pre_save.connect(pre_save_receiver)
        post_save_data = []

        def post_save_receiver(**kwargs):
            post_save_data.append(kwargs["update_fields"])

        post_save.connect(post_save_receiver)
        p.save(update_fields=["name"])
        self.assertEqual(len(pre_save_data), 1)
        self.assertEqual(len(pre_save_data[0]), 1)
        self.assertIn("name", pre_save_data[0])
        self.assertEqual(len(post_save_data), 1)
        self.assertEqual(len(post_save_data[0]), 1)
        self.assertIn("name", post_save_data[0])

        pre_save.disconnect(pre_save_receiver)
        post_save.disconnect(post_save_receiver)

    def test_update_fields_incorrect_params(self):
        s = Person.objects.create(name="Sara", gender="F")

        with self.assertRaisesMessage(ValueError, self.msg % "first_name"):
            s.save(update_fields=["first_name"])

        # "name" is treated as an iterable so the output is something like
        # "n, a, m, e" but the order isn't deterministic.
        with self.assertRaisesMessage(ValueError, self.msg % ""):
            s.save(update_fields="name")

    def test_empty_update_fields(self):
        s = Person.objects.create(name="Sara", gender="F")
        pre_save_data = []

        def pre_save_receiver(**kwargs):
            pre_save_data.append(kwargs["update_fields"])

        pre_save.connect(pre_save_receiver)
        post_save_data = []

        def post_save_receiver(**kwargs):
            post_save_data.append(kwargs["update_fields"])

        post_save.connect(post_save_receiver)
        # Save is skipped.
        with self.assertNumQueries(0):
            s.save(update_fields=[])
        # Signals were skipped, too...
        self.assertEqual(len(pre_save_data), 0)
        self.assertEqual(len(post_save_data), 0)

        pre_save.disconnect(pre_save_receiver)
        post_save.disconnect(post_save_receiver)

    def test_empty_update_fields_positional_save(self):
        """
        Tests that passing positional arguments to the save method raises a RemovedInDjango60Warning.

        Checks that an update_fields positional argument passed to save() correctly triggers a deprecation warning when using the default update_fields behavior, without issuing any database queries.

        This test case verifies the deprecation of positional arguments in the save() method, ensuring that users are notified of the upcoming change in a future Django release.
        """
        s = Person.objects.create(name="Sara", gender="F")

        msg = "Passing positional arguments to save() is deprecated"
        with (
            self.assertWarnsMessage(RemovedInDjango60Warning, msg),
            self.assertNumQueries(0),
        ):
            s.save(False, False, None, [])

    async def test_empty_update_fields_positional_asave(self):
        s = await Person.objects.acreate(name="Sara", gender="F")
        # Workaround for a lack of async assertNumQueries.
        s.name = "Other"

        msg = "Passing positional arguments to asave() is deprecated"
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            await s.asave(False, False, None, [])

        # No save occurred for an empty update_fields.
        await s.arefresh_from_db()
        self.assertEqual(s.name, "Sara")

    def test_num_queries_inheritance(self):
        """

        Tests the number of database queries performed when updating fields of an Employee object
        using model inheritance, ensuring that the update_fields parameter of the save method
        optimizes the number of queries.

        Verifies that updating a single field of the Employee model results in a single query,
        and that updating multiple fields results in the expected number of queries.
        Additionally, confirms that the data is correctly updated in the database.

        """
        s = Employee.objects.create(name="Sara", gender="F")
        s.employee_num = 1
        s.name = "Emily"
        with self.assertNumQueries(1):
            s.save(update_fields=["employee_num"])
        s = Employee.objects.get(pk=s.pk)
        self.assertEqual(s.employee_num, 1)
        self.assertEqual(s.name, "Sara")
        s.employee_num = 2
        s.name = "Emily"
        with self.assertNumQueries(1):
            s.save(update_fields=["name"])
        s = Employee.objects.get(pk=s.pk)
        self.assertEqual(s.name, "Emily")
        self.assertEqual(s.employee_num, 1)
        # A little sanity check that we actually did updates...
        self.assertEqual(Employee.objects.count(), 1)
        self.assertEqual(Person.objects.count(), 1)
        with self.assertNumQueries(2):
            s.save(update_fields=["name", "employee_num"])

    def test_update_non_concrete_field(self):
        """

        Tests that attempting to update a non-concrete field raises a ValueError.

        This test case verifies that when trying to update a field that is not a concrete field,
        the expected error message is raised, preventing incorrect updates to the model instance.

        """
        profile_boss = Profile.objects.create(name="Boss", salary=3000)
        with self.assertRaisesMessage(ValueError, self.msg % "non_concrete"):
            profile_boss.save(update_fields=["non_concrete"])
