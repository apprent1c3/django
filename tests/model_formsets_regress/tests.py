from django import forms
from django.forms.formsets import DELETION_FIELD_NAME, BaseFormSet
from django.forms.models import (
    BaseModelFormSet,
    inlineformset_factory,
    modelform_factory,
    modelformset_factory,
)
from django.forms.utils import ErrorDict, ErrorList
from django.test import TestCase

from .models import (
    Host,
    Manager,
    Network,
    ProfileNetwork,
    Restaurant,
    User,
    UserPreferences,
    UserProfile,
    UserSite,
)


class InlineFormsetTests(TestCase):
    def test_formset_over_to_field(self):
        """
        Tests that a formset over a ForeignKey with a to_field can be saved, including adding, updating, and validating formset instances.
        """
        Form = modelform_factory(User, fields="__all__")
        FormSet = inlineformset_factory(User, UserSite, fields="__all__")

        # Instantiate the Form and FormSet to prove
        # you can create a form with no data
        form = Form()
        form_set = FormSet(instance=User())

        # Now create a new User and UserSite instance
        data = {
            "serial": "1",
            "username": "apollo13",
            "usersite_set-TOTAL_FORMS": "1",
            "usersite_set-INITIAL_FORMS": "0",
            "usersite_set-MAX_NUM_FORMS": "0",
            "usersite_set-0-data": "10",
            "usersite_set-0-user": "apollo13",
        }
        user = User()
        form = Form(data)
        if form.is_valid():
            user = form.save()
        else:
            self.fail("Errors found on form:%s" % form_set)

        form_set = FormSet(data, instance=user)
        if form_set.is_valid():
            form_set.save()
            usersite = UserSite.objects.values()
            self.assertEqual(usersite[0]["data"], 10)
            self.assertEqual(usersite[0]["user_id"], "apollo13")
        else:
            self.fail("Errors found on formset:%s" % form_set.errors)

        # Now update the UserSite instance
        data = {
            "usersite_set-TOTAL_FORMS": "1",
            "usersite_set-INITIAL_FORMS": "1",
            "usersite_set-MAX_NUM_FORMS": "0",
            "usersite_set-0-id": str(usersite[0]["id"]),
            "usersite_set-0-data": "11",
            "usersite_set-0-user": "apollo13",
        }
        form_set = FormSet(data, instance=user)
        if form_set.is_valid():
            form_set.save()
            usersite = UserSite.objects.values()
            self.assertEqual(usersite[0]["data"], 11)
            self.assertEqual(usersite[0]["user_id"], "apollo13")
        else:
            self.fail("Errors found on formset:%s" % form_set.errors)

        # Now add a new UserSite instance
        data = {
            "usersite_set-TOTAL_FORMS": "2",
            "usersite_set-INITIAL_FORMS": "1",
            "usersite_set-MAX_NUM_FORMS": "0",
            "usersite_set-0-id": str(usersite[0]["id"]),
            "usersite_set-0-data": "11",
            "usersite_set-0-user": "apollo13",
            "usersite_set-1-data": "42",
            "usersite_set-1-user": "apollo13",
        }
        form_set = FormSet(data, instance=user)
        if form_set.is_valid():
            form_set.save()
            usersite = UserSite.objects.values().order_by("data")
            self.assertEqual(usersite[0]["data"], 11)
            self.assertEqual(usersite[0]["user_id"], "apollo13")
            self.assertEqual(usersite[1]["data"], 42)
            self.assertEqual(usersite[1]["user_id"], "apollo13")
        else:
            self.fail("Errors found on formset:%s" % form_set.errors)

    def test_formset_over_inherited_model(self):
        """
        Tests that a formset over a model inherited from another with a ForeignKey and a specified to_field can be successfully saved to the database. Verifies that form data is correctly validated and saved for various scenarios, including creating new instances, updating existing instances, and adding multiple related objects.
        """
        Form = modelform_factory(Restaurant, fields="__all__")
        FormSet = inlineformset_factory(Restaurant, Manager, fields="__all__")

        # Instantiate the Form and FormSet to prove
        # you can create a form with no data
        form = Form()
        form_set = FormSet(instance=Restaurant())

        # Now create a new Restaurant and Manager instance
        data = {
            "name": "Guido's House of Pasta",
            "manager_set-TOTAL_FORMS": "1",
            "manager_set-INITIAL_FORMS": "0",
            "manager_set-MAX_NUM_FORMS": "0",
            "manager_set-0-name": "Guido Van Rossum",
        }
        restaurant = User()
        form = Form(data)
        if form.is_valid():
            restaurant = form.save()
        else:
            self.fail("Errors found on form:%s" % form_set)

        form_set = FormSet(data, instance=restaurant)
        if form_set.is_valid():
            form_set.save()
            manager = Manager.objects.values()
            self.assertEqual(manager[0]["name"], "Guido Van Rossum")
        else:
            self.fail("Errors found on formset:%s" % form_set.errors)

        # Now update the Manager instance
        data = {
            "manager_set-TOTAL_FORMS": "1",
            "manager_set-INITIAL_FORMS": "1",
            "manager_set-MAX_NUM_FORMS": "0",
            "manager_set-0-id": str(manager[0]["id"]),
            "manager_set-0-name": "Terry Gilliam",
        }
        form_set = FormSet(data, instance=restaurant)
        if form_set.is_valid():
            form_set.save()
            manager = Manager.objects.values()
            self.assertEqual(manager[0]["name"], "Terry Gilliam")
        else:
            self.fail("Errors found on formset:%s" % form_set.errors)

        # Now add a new Manager instance
        data = {
            "manager_set-TOTAL_FORMS": "2",
            "manager_set-INITIAL_FORMS": "1",
            "manager_set-MAX_NUM_FORMS": "0",
            "manager_set-0-id": str(manager[0]["id"]),
            "manager_set-0-name": "Terry Gilliam",
            "manager_set-1-name": "John Cleese",
        }
        form_set = FormSet(data, instance=restaurant)
        if form_set.is_valid():
            form_set.save()
            manager = Manager.objects.values().order_by("name")
            self.assertEqual(manager[0]["name"], "John Cleese")
            self.assertEqual(manager[1]["name"], "Terry Gilliam")
        else:
            self.fail("Errors found on formset:%s" % form_set.errors)

    def test_inline_model_with_to_field(self):
        """
        Verifies that an inline model with a to_field in a formset functions correctly when bound to an instance, ensuring working relationships between the models.
        """
        FormSet = inlineformset_factory(User, UserSite, exclude=("is_superuser",))

        user = User.objects.create(username="guido", serial=1337)
        UserSite.objects.create(user=user, data=10)
        formset = FormSet(instance=user)

        # Testing the inline model's relation
        self.assertEqual(formset[0].instance.user_id, "guido")

    def test_inline_model_with_primary_to_field(self):
        """
        Tests that an inline model using a OneToOneField with a specified to_field and primary key correctly populates the formset with the associated instance data.
        """
        FormSet = inlineformset_factory(
            User, UserPreferences, exclude=("is_superuser",)
        )
        user = User.objects.create(username="guido", serial=1337)
        UserPreferences.objects.create(user=user, favorite_number=10)
        formset = FormSet(instance=user)
        self.assertEqual(formset[0].fields["user"].initial, "guido")

    def test_inline_model_with_to_field_to_rel(self):
        """
        Tests that an inline model with a to_field to a related field of a formset instance has working relations.
        """
        FormSet = inlineformset_factory(UserProfile, ProfileNetwork, exclude=[])

        user = User.objects.create(username="guido", serial=1337, pk=1)
        self.assertEqual(user.pk, 1)
        profile = UserProfile.objects.create(user=user, about="about", pk=2)
        self.assertEqual(profile.pk, 2)
        ProfileNetwork.objects.create(profile=profile, network=10, identifier=10)
        formset = FormSet(instance=profile)

        # Testing the inline model's relation
        self.assertEqual(formset[0].instance.profile_id, 1)

    def test_formset_with_none_instance(self):
        """
        Tests that a formset can be created with instance=None, addressing a regression issue.
        """
        Form = modelform_factory(User, fields="__all__")
        FormSet = inlineformset_factory(User, UserSite, fields="__all__")

        # Instantiate the Form and FormSet to prove
        # you can create a formset with an instance of None
        Form(instance=None)
        FormSet(instance=None)

    def test_empty_fields_on_modelformset(self):
        """
        Tests that an empty fields argument to modelformset_factory results in a formset 
        with forms containing only the 'id' field.
        """
        UserFormSet = modelformset_factory(User, fields=())
        formset = UserFormSet()
        for form in formset.forms:
            self.assertIn("id", form.fields)
            self.assertEqual(len(form.fields), 1)

    def test_save_as_new_with_new_inlines(self):
        """
        Tests the behavior of saving new and existing inlines with the save_as_new option, ensuring that both are properly saved and associated with the correct instance. This test case is a regression for issue #14938, verifying that inlines are correctly handled when saving as new.
        """
        efnet = Network.objects.create(name="EFNet")
        host1 = Host.objects.create(hostname="irc.he.net", network=efnet)

        HostFormSet = inlineformset_factory(Network, Host, fields="__all__")

        # Add a new host, modify previous host, and save-as-new
        data = {
            "host_set-TOTAL_FORMS": "2",
            "host_set-INITIAL_FORMS": "1",
            "host_set-MAX_NUM_FORMS": "0",
            "host_set-0-id": str(host1.id),
            "host_set-0-hostname": "tranquility.hub.dal.net",
            "host_set-1-hostname": "matrix.de.eu.dal.net",
        }

        # To save a formset as new, it needs a new hub instance
        dalnet = Network.objects.create(name="DALnet")
        formset = HostFormSet(data, instance=dalnet, save_as_new=True)

        self.assertTrue(formset.is_valid())
        formset.save()
        self.assertQuerySetEqual(
            dalnet.host_set.order_by("hostname"),
            Host.objects.filter(
                hostname__in=[
                    "matrix.de.eu.dal.net",
                    "tranquility.hub.dal.net",
                ]
            ).order_by("hostname"),
        )

    def test_initial_data(self):
        """
        Verifies the initial data for an inline formset of UserSite instances associated with a User instance, ensuring that existing data is correctly retrieved and initial data is properly set for extra forms.
        """
        user = User.objects.create(username="bibi", serial=1)
        UserSite.objects.create(user=user, data=7)
        FormSet = inlineformset_factory(User, UserSite, extra=2, fields="__all__")

        formset = FormSet(instance=user, initial=[{"data": 41}, {"data": 42}])
        self.assertEqual(formset.forms[0].initial["data"], 7)
        self.assertEqual(formset.extra_forms[0].initial["data"], 41)
        self.assertIn('value="42"', formset.extra_forms[1].as_p())


class FormsetTests(TestCase):
    def test_error_class(self):
        """
        Checks the type of error attributes in a formset and its forms, 
        ensuring they are correctly classified as lists, dictionaries, or error lists.
        """
        Formset = modelformset_factory(User, fields="__all__")
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "0",
            "form-0-id": "",
            "form-0-username": "apollo13",
            "form-0-serial": "1",
            "form-1-id": "",
            "form-1-username": "apollo13",
            "form-1-serial": "2",
        }
        formset = Formset(data)
        # check if the returned error classes are correct
        # note: formset.errors returns a list as documented
        self.assertIsInstance(formset.errors, list)
        self.assertIsInstance(formset.non_form_errors(), ErrorList)
        for form in formset.forms:
            self.assertIsInstance(form.errors, ErrorDict)
            self.assertIsInstance(form.non_field_errors(), ErrorList)

    def test_initial_data(self):
        """
        Tests that initial data is correctly set for a formset with extra forms.

        Verifies that the initial data for the first form is taken from an existing object,
        and that initial data for extra forms is taken from the provided initial data list.
        """
        User.objects.create(username="bibi", serial=1)
        Formset = modelformset_factory(User, fields="__all__", extra=2)
        formset = Formset(initial=[{"username": "apollo11"}, {"username": "apollo12"}])
        self.assertEqual(formset.forms[0].initial["username"], "bibi")
        self.assertEqual(formset.extra_forms[0].initial["username"], "apollo11")
        self.assertIn('value="apollo12"', formset.extra_forms[1].as_p())

    def test_extraneous_query_is_not_run(self):
        """
        Tests that an extraneous database query is not executed when saving a formset with no existing instances.
        """
        Formset = modelformset_factory(Network, fields="__all__")
        data = {
            "test-TOTAL_FORMS": "1",
            "test-INITIAL_FORMS": "0",
            "test-MAX_NUM_FORMS": "",
            "test-0-name": "Random Place",
        }
        with self.assertNumQueries(1):
            formset = Formset(data, prefix="test")
            formset.save()


class CustomWidget(forms.widgets.TextInput):
    pass


class UserSiteForm(forms.ModelForm):
    class Meta:
        model = UserSite
        fields = "__all__"
        widgets = {
            "id": CustomWidget,
            "data": CustomWidget,
        }
        localized_fields = ("data",)


class Callback:
    def __init__(self):
        self.log = []

    def __call__(self, db_field, **kwargs):
        self.log.append((db_field, kwargs))
        return db_field.formfield(**kwargs)


class FormfieldCallbackTests(TestCase):
    """
    Regression for #13095 and #17683: Using base forms with widgets
    defined in Meta should not raise errors and BaseModelForm should respect
    the specified pk widget.
    """

    def test_inlineformset_factory_default(self):
        """
        Tests that the inline formset factory correctly creates forms with custom widgets and proper field localization settings for UserSite model.
        """
        Formset = inlineformset_factory(
            User, UserSite, form=UserSiteForm, fields="__all__"
        )
        form = Formset().forms[0]
        self.assertIsInstance(form["id"].field.widget, CustomWidget)
        self.assertIsInstance(form["data"].field.widget, CustomWidget)
        self.assertFalse(form.fields["id"].localize)
        self.assertTrue(form.fields["data"].localize)

    def test_modelformset_factory_default(self):
        """
        Tests the default behavior of the model formset factory for UserSite.

        Verifies that the correct widgets are used for the 'id' and 'data' fields, and that
        localization is correctly applied to the 'data' field.
        """
        Formset = modelformset_factory(UserSite, form=UserSiteForm)
        form = Formset().forms[0]
        self.assertIsInstance(form["id"].field.widget, CustomWidget)
        self.assertIsInstance(form["data"].field.widget, CustomWidget)
        self.assertFalse(form.fields["id"].localize)
        self.assertTrue(form.fields["data"].localize)

    def assertCallbackCalled(self, callback):
        id_field, user_field, data_field = UserSite._meta.fields
        expected_log = [
            (id_field, {"widget": CustomWidget}),
            (user_field, {}),
            (data_field, {"widget": CustomWidget, "localize": True}),
        ]
        self.assertEqual(callback.log, expected_log)

    def test_inlineformset_custom_callback(self):
        callback = Callback()
        inlineformset_factory(
            User,
            UserSite,
            form=UserSiteForm,
            formfield_callback=callback,
            fields="__all__",
        )
        self.assertCallbackCalled(callback)

    def test_modelformset_custom_callback(self):
        callback = Callback()
        modelformset_factory(UserSite, form=UserSiteForm, formfield_callback=callback)
        self.assertCallbackCalled(callback)


class BaseCustomDeleteFormSet(BaseFormSet):
    """
    A formset mix-in that lets a form decide if it's to be deleted.
    Works for BaseFormSets. Also works for ModelFormSets with #14099 fixed.

    form.should_delete() is called. The formset delete field is also suppressed.
    """

    def add_fields(self, form, index):
        super().add_fields(form, index)
        self.can_delete = True
        if DELETION_FIELD_NAME in form.fields:
            del form.fields[DELETION_FIELD_NAME]

    def _should_delete_form(self, form):
        return hasattr(form, "should_delete") and form.should_delete()


class FormfieldShouldDeleteFormTests(TestCase):
    """
    BaseModelFormSet should use ModelFormSet method _should_delete_form.
    """

    class BaseCustomDeleteModelFormSet(BaseModelFormSet, BaseCustomDeleteFormSet):
        """Model FormSet with CustomDelete MixIn"""

    class CustomDeleteUserForm(forms.ModelForm):
        """A model form with a 'should_delete' method"""

        class Meta:
            model = User
            fields = "__all__"

        def should_delete(self):
            """Delete form if odd serial."""
            return self.instance.serial % 2 != 0

    NormalFormset = modelformset_factory(
        User, form=CustomDeleteUserForm, can_delete=True
    )
    DeleteFormset = modelformset_factory(
        User, form=CustomDeleteUserForm, formset=BaseCustomDeleteModelFormSet
    )

    data = {
        "form-TOTAL_FORMS": "4",
        "form-INITIAL_FORMS": "0",
        "form-MAX_NUM_FORMS": "4",
        "form-0-username": "John",
        "form-0-serial": "1",
        "form-1-username": "Paul",
        "form-1-serial": "2",
        "form-2-username": "George",
        "form-2-serial": "3",
        "form-3-username": "Ringo",
        "form-3-serial": "5",
    }

    delete_all_ids = {
        "form-0-DELETE": "1",
        "form-1-DELETE": "1",
        "form-2-DELETE": "1",
        "form-3-DELETE": "1",
    }

    def test_init_database(self):
        """Add test data to database via formset"""
        formset = self.NormalFormset(self.data)
        self.assertTrue(formset.is_valid())
        self.assertEqual(len(formset.save()), 4)

    def test_no_delete(self):
        """
        Tests that the base formset does not delete any existing records in the database.
        """
        # reload database
        self.test_init_database()

        # pass standard data dict & see none updated
        data = dict(self.data)
        data["form-INITIAL_FORMS"] = 4
        data.update(
            {
                "form-%d-id" % i: user.pk
                for i, user in enumerate(User.objects.order_by("pk"))
            }
        )
        formset = self.NormalFormset(data, queryset=User.objects.all())
        self.assertTrue(formset.is_valid())
        self.assertEqual(len(formset.save()), 0)
        self.assertEqual(len(User.objects.all()), 4)

    def test_all_delete(self):
        """
        Verifies that a formset correctly handles deletion of all instances when the DELETE field is present, ensuring that all objects are removed from the database.
        """
        # reload database
        self.test_init_database()

        # create data dict with all fields marked for deletion
        data = dict(self.data)
        data["form-INITIAL_FORMS"] = 4
        data.update(
            {"form-%d-id" % i: user.pk for i, user in enumerate(User.objects.all())}
        )
        data.update(self.delete_all_ids)
        formset = self.NormalFormset(data, queryset=User.objects.all())
        self.assertTrue(formset.is_valid())
        self.assertEqual(len(formset.save()), 0)
        self.assertEqual(len(User.objects.all()), 0)

    def test_custom_delete(self):
        """
        Tests that the DeleteFormset correctly ignores the DELETE field and uses the form's method to delete objects, ensuring that only the intended objects are removed from the database.
        """
        # reload database
        self.test_init_database()

        # Create formset with custom Delete function
        # create data dict with all fields marked for deletion
        data = dict(self.data)
        data["form-INITIAL_FORMS"] = 4
        data.update(
            {
                "form-%d-id" % i: user.pk
                for i, user in enumerate(User.objects.order_by("pk"))
            }
        )
        data.update(self.delete_all_ids)
        formset = self.DeleteFormset(data, queryset=User.objects.all())

        # Three with odd serial values were deleted.
        self.assertTrue(formset.is_valid())
        self.assertEqual(len(formset.save()), 0)
        self.assertEqual(User.objects.count(), 1)

        # No odd serial values left.
        odd_serials = [user.serial for user in User.objects.all() if user.serial % 2]
        self.assertEqual(len(odd_serials), 0)


class RedeleteTests(TestCase):
    def test_resubmit(self):
        """
        Tests that the formset correctly handles resubmitting a form with a deleted object, 
        ensuring that the deleted object is not recreated and the database state remains consistent.
        """
        u = User.objects.create(username="foo", serial=1)
        us = UserSite.objects.create(user=u, data=7)
        formset_cls = inlineformset_factory(User, UserSite, fields="__all__")
        data = {
            "serial": "1",
            "username": "foo",
            "usersite_set-TOTAL_FORMS": "1",
            "usersite_set-INITIAL_FORMS": "1",
            "usersite_set-MAX_NUM_FORMS": "1",
            "usersite_set-0-id": str(us.pk),
            "usersite_set-0-data": "7",
            "usersite_set-0-user": "foo",
            "usersite_set-0-DELETE": "1",
        }
        formset = formset_cls(data, instance=u)
        self.assertTrue(formset.is_valid())
        formset.save()
        self.assertEqual(UserSite.objects.count(), 0)
        formset = formset_cls(data, instance=u)
        # Even if the "us" object isn't in the DB any more, the form
        # validates.
        self.assertTrue(formset.is_valid())
        formset.save()
        self.assertEqual(UserSite.objects.count(), 0)

    def test_delete_already_deleted(self):
        """
        Tests that deleting a UserSite instance via an inline formset works correctly even if the instance has already been deleted from the database.
        """
        u = User.objects.create(username="foo", serial=1)
        us = UserSite.objects.create(user=u, data=7)
        formset_cls = inlineformset_factory(User, UserSite, fields="__all__")
        data = {
            "serial": "1",
            "username": "foo",
            "usersite_set-TOTAL_FORMS": "1",
            "usersite_set-INITIAL_FORMS": "1",
            "usersite_set-MAX_NUM_FORMS": "1",
            "usersite_set-0-id": str(us.pk),
            "usersite_set-0-data": "7",
            "usersite_set-0-user": "foo",
            "usersite_set-0-DELETE": "1",
        }
        formset = formset_cls(data, instance=u)
        us.delete()
        self.assertTrue(formset.is_valid())
        formset.save()
        self.assertEqual(UserSite.objects.count(), 0)
