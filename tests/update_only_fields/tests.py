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
        """

        Tests the update_fields parameter of the save method on a model instance.

        This test case verifies that when only certain fields are specified for update,
        only those fields are actually updated in the database, while other fields remain unchanged.

        The test creates a Person instance, modifies its name and gender, saves it with only the name
        field updated, and then checks that the name has been updated correctly and the gender remains
        the same as its original value.

        """
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

        This test creates employee profiles and tests the foreign key assignment 
        with deferred loading, ensuring that the updates are performed efficiently 
        with a minimal number of database queries. The test case verifies that 
        the employee's profile can be updated successfully and that the changes 
        are persisted in the database. It also checks that the foreign key 
        assignment and the subsequent save operation are performed within a 
        single database query, optimizing performance.

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
        """

        Tests the behavior of Django's select_related method when used with only method.
        Verifies that when a model instance is retrieved with select_related and only,
        any subsequent modifications to the related model instance are not reflected
        in the originally retrieved instance, even if the related instance is saved.
        This ensures that the select_related method does indeed retrieve a snapshot
        of the related instance at the time of the original query, rather than a live
        reference to the related instance.

        """
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
        """
        Tests that attempting to save a model instance with a many-to-many field 
        update raises a ValueError.

        Verifies that an error is correctly raised when trying to update a many-to-many 
        field using the `update_fields` argument, as this operation is not supported 
        and can lead to data inconsistencies.

        It checks the case when an employee instance has multiple accounts assigned, 
        and then an attempt is made to save the instance with the `update_fields` 
        parameter set to the many-to-many field 'accounts', expecting a ValueError 
        with a specific message to be raised. 

        Args:
            None

        Returns:
            None

        Raises:
            ValueError: If a many-to-many field is included in the `update_fields` 
                         argument when saving the instance
        """
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
        """
        ..:param: 
        Test that an empty list passed to update_fields results in no database query and no signal receivers being called when a model instance is saved. 

        This test function creates a new instance of the Person model, then connects signal receivers to the pre_save and post_save signals. 
        It then attempts to save the instance with an empty update_fields list and checks that no database queries were made and that neither signal receiver was called. 
        Finally, it disconnects the signal receivers.
        """
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
        Tests deprecation warning for passing positional arguments to the save method.

        This test case checks that a warning is emitted when positional arguments are used
        to call the save method on a model instance, which is deprecated and scheduled for
        removal in Django 6.0. The test also verifies that no database queries are executed
        in this scenario, as no update operation is performed.

        It creates a Person instance, then attempts to save it with positional arguments,
        asserting that the expected deprecation warning is raised and no database queries
        are executed. The test uses a specific message to identify the warning, ensuring
        that the correct deprecation warning is triggered by the deprecated positional
        argument usage. 

        The return value of this function is the assertion result which indicates whether 
        the test was successful or not.
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

        Test that the number of database queries is correctly optimized when updating 
        fields on a model instance that uses multi-table inheritance.

        Verifies that updating a single field on the child model or the parent model 
        triggers only one database query, and that updating fields on both the child 
        and parent models triggers the expected number of queries.

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
        profile_boss = Profile.objects.create(name="Boss", salary=3000)
        with self.assertRaisesMessage(ValueError, self.msg % "non_concrete"):
            profile_boss.save(update_fields=["non_concrete"])
