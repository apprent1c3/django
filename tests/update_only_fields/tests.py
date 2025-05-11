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
        Tests the basic functionality of updating specific fields in a model instance.

        Verifies that only the specified fields are updated when using the update_fields parameter,
        leaving other fields unchanged.
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
        """
        Tests the deferred field update functionality for Person objects, verifying that changes to fields initially deferred are persisted correctly upon saving.
        """
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
        Tests that updating fields on a model instance retrieved with 'only' method 
        successfully updates all fields in the database, not just the ones initially retrieved.
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
        """
        Tests that the update_fields parameter of the save method only updates the specified fields, leaving other fields unchanged.
        """
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
        """
        Tests that updating a model instance with only specified fields will only modify those fields, without reloading the entire object from the database.
        """
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
        Tests that updating fields in a model instance with a deferred field set retrieves the deferred field with the correct value from the database and saves the changes in a single database query.
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
        Tests the update of a foreign key field using the `only` method to defer loading of related objects, verifying that only one database query is executed during the update.
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
        Test that using select_related with only still allows interaction with the related object, but does not update the related object when only some fields are loaded.
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
        Tests that updating many-to-many fields is not allowed when using the update_fields argument.
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
        """
        Tests partial updates of model fields, including inheritance of unchanged fields.

        Verifies that only specified fields are updated, while other fields retain their original values,
        and that updates can be made with partial field specification, including foreign key fields.
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
        """
        Tests that updating specific fields in a proxy model instance, using the update_fields parameter, correctly modifies the instance's data without affecting unrelated fields, while also handling inheritance from the parent model. Verifies that the changes are persisted in the database and that the instance's state remains consistent across multiple retrievals.
        """
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
        Tests that pre_save and post_save signals receive the correct update_fields when saving a model instance with a specified update_fields list.
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
        """
        Tests that attempting to update a field with an incorrect parameter type raises a ValueError, ensuring the update_fields argument accepts only a list of strings as valid input.
        """
        s = Person.objects.create(name="Sara", gender="F")

        with self.assertRaisesMessage(ValueError, self.msg % "first_name"):
            s.save(update_fields=["first_name"])

        # "name" is treated as an iterable so the output is something like
        # "n, a, m, e" but the order isn't deterministic.
        with self.assertRaisesMessage(ValueError, self.msg % ""):
            s.save(update_fields="name")

    def test_empty_update_fields(self):
        """
        Tests that saving a model with an empty update_fields list does not trigger pre_save or post_save signals.
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
        s = Person.objects.create(name="Sara", gender="F")

        msg = "Passing positional arguments to save() is deprecated"
        with (
            self.assertWarnsMessage(RemovedInDjango60Warning, msg),
            self.assertNumQueries(0),
        ):
            s.save(False, False, None, [])

    async def test_empty_update_fields_positional_asave(self):
        """
        Tests that using positional arguments with asave() method triggers a deprecation warning and does not update the object in the database, ensuring that only keyword arguments are accepted for update fields in the future.
        """
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
        Tests the optimization of database queries when updating fields of an Employee instance, ensuring that the number of queries matches expectations when updating individual or multiple fields, and verifying data consistency after updates.
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
