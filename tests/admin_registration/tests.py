from django.contrib import admin
from django.contrib.admin.decorators import register
from django.contrib.admin.exceptions import AlreadyRegistered, NotRegistered
from django.contrib.admin.sites import site
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from .models import Location, Person, Place, Traveler


class NameAdmin(admin.ModelAdmin):
    list_display = ["name"]
    save_on_top = True


class CustomSite(admin.AdminSite):
    pass


class TestRegistration(SimpleTestCase):
    def setUp(self):
        self.site = admin.AdminSite()

    def test_bare_registration(self):
        """
        Tests the registration and unregistration of a model with the admin site.

        Verifies that a model can be successfully registered and an instance of ModelAdmin is returned.
        Also checks that unregistration removes the model from the admin site's registry, resulting in an empty registry.

        This test case ensures basic functionality of the admin site's registration and unregistration mechanisms.
        """
        self.site.register(Person)
        self.assertIsInstance(self.site.get_model_admin(Person), admin.ModelAdmin)
        self.site.unregister(Person)
        self.assertEqual(self.site._registry, {})

    def test_registration_with_model_admin(self):
        """
        Tests the registration and unregistration of a model with a custom model admin class.

        Verifies that a model can be successfully registered with a model admin class, 
        and that the registered admin class is correctly retrieved from the site. 
        Additionally, checks that unregistration of the model results in an empty registry.
        """
        self.site.register(Person, NameAdmin)
        self.assertIsInstance(self.site.get_model_admin(Person), NameAdmin)
        self.site.unregister(Person)
        self.assertEqual(self.site._registry, {})

    def test_prevent_double_registration(self):
        """
        Tests that attempting to register a model with the admin site that is already registered raises an AlreadyRegistered exception.

        This ensures that the admin site prevents duplicate registrations of the same model, helping to avoid potential errors and inconsistencies in the application.

        :raises: AlreadyRegistered
        :note: This test case checks the behavior of the admin site's register method when a model is registered multiple times.
        """
        self.site.register(Person)
        msg = "The model Person is already registered in app 'admin_registration'."
        with self.assertRaisesMessage(AlreadyRegistered, msg):
            self.site.register(Person)

    def test_prevent_double_registration_for_custom_admin(self):
        class PersonAdmin(admin.ModelAdmin):
            pass

        self.site.register(Person, PersonAdmin)
        msg = (
            "The model Person is already registered with "
            "'admin_registration.PersonAdmin'."
        )
        with self.assertRaisesMessage(AlreadyRegistered, msg):
            self.site.register(Person, PersonAdmin)

    def test_unregister_unregistered_model(self):
        """
        Tests that attempting to unregister a model that has not been previously registered raises a NotRegistered exception.

        This test case ensures that the unregister method correctly handles unregistered models by checking for the expected exception and error message.

        :raises: NotRegistered if the model is not registered

        """
        msg = "The model Person is not registered"
        with self.assertRaisesMessage(NotRegistered, msg):
            self.site.unregister(Person)

    def test_registration_with_star_star_options(self):
        """
        Tests the registration of a model with search fields specified using the `search_fields` option.

        Verifies that when a model is registered with the `search_fields` option, the specified fields are correctly set for the model admin.

        The test case checks if the `search_fields` attribute of the model admin is updated correctly after registration, ensuring that the model can be searched based on the specified fields.

        Args:
            None

        Returns:
            None
        """
        self.site.register(Person, search_fields=["name"])
        self.assertEqual(self.site.get_model_admin(Person).search_fields, ["name"])

    def test_get_model_admin_unregister_model(self):
        msg = "The model Person is not registered."
        with self.assertRaisesMessage(NotRegistered, msg):
            self.site.get_model_admin(Person)

    def test_star_star_overrides(self):
        """
        Tests if overriding model admin options specified in **kwargs (like search_fields, list_display) takes precedence over model admin class options.

         Verifies that search fields and list display can be successfully overridden and that other attributes like save_on_top are correctly set by default.
        """
        self.site.register(
            Person, NameAdmin, search_fields=["name"], list_display=["__str__"]
        )
        person_admin = self.site.get_model_admin(Person)
        self.assertEqual(person_admin.search_fields, ["name"])
        self.assertEqual(person_admin.list_display, ["__str__"])
        self.assertIs(person_admin.save_on_top, True)

    def test_iterable_registration(self):
        """

        Tests the registration of multiple models as iterable to the admin site.

        Verifies that registering a list of models with specific search fields results 
        in each model being successfully registered with the specified search fields. 
        Also, confirms that unregistering the models removes them from the site's registry.

        """
        self.site.register([Person, Place], search_fields=["name"])
        self.assertIsInstance(self.site.get_model_admin(Person), admin.ModelAdmin)
        self.assertEqual(self.site.get_model_admin(Person).search_fields, ["name"])
        self.assertIsInstance(self.site.get_model_admin(Place), admin.ModelAdmin)
        self.assertEqual(self.site.get_model_admin(Place).search_fields, ["name"])
        self.site.unregister([Person, Place])
        self.assertEqual(self.site._registry, {})

    def test_abstract_model(self):
        """
        Exception is raised when trying to register an abstract model.
        Refs #12004.
        """
        msg = "The model Location is abstract, so it cannot be registered with admin."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.site.register(Location)

    def test_is_registered_model(self):
        "Checks for registered models should return true."
        self.site.register(Person)
        self.assertTrue(self.site.is_registered(Person))

    def test_is_registered_not_registered_model(self):
        "Checks for unregistered models should return false."
        self.assertFalse(self.site.is_registered(Person))


class TestRegistrationDecorator(SimpleTestCase):
    """
    Tests the register decorator in admin.decorators

    For clarity:

        @register(Person)
        class AuthorAdmin(ModelAdmin):
            pass

    is functionally equal to (the way it is written in these tests):

        AuthorAdmin = register(Person)(AuthorAdmin)
    """

    def setUp(self):
        self.default_site = site
        self.custom_site = CustomSite()

    def test_basic_registration(self):
        """

        Tests the basic registration of a model with the admin site.

        Verifies that a model can be successfully registered with a custom ModelAdmin class,
        and that the registration can be subsequently unregistered.

        This test case ensures that the fundamental registration mechanism is working correctly,
        providing a foundation for more complex registration scenarios.

        """
        register(Person)(NameAdmin)
        self.assertIsInstance(
            self.default_site.get_model_admin(Person), admin.ModelAdmin
        )
        self.default_site.unregister(Person)

    def test_custom_site_registration(self):
        """
        Tests the registration of a custom admin site.

         Verifies that a model can be successfully registered with a custom admin site,
         and that the site returns the expected model admin class.

         This test case checks the integration of the custom admin site with the model
         registration process, ensuring that the correct admin class is associated
         with the registered model.
        """
        register(Person, site=self.custom_site)(NameAdmin)
        self.assertIsInstance(
            self.custom_site.get_model_admin(Person), admin.ModelAdmin
        )

    def test_multiple_registration(self):
        register(Traveler, Place)(NameAdmin)
        self.assertIsInstance(
            self.default_site.get_model_admin(Traveler), admin.ModelAdmin
        )
        self.default_site.unregister(Traveler)
        self.assertIsInstance(
            self.default_site.get_model_admin(Place), admin.ModelAdmin
        )
        self.default_site.unregister(Place)

    def test_wrapped_class_not_a_model_admin(self):
        with self.assertRaisesMessage(
            ValueError, "Wrapped class must subclass ModelAdmin."
        ):
            register(Person)(CustomSite)

    def test_custom_site_not_an_admin_site(self):
        """
        Tests that attempting to register a model with a custom site that does not subclass AdminSite raises a ValueError.

        This test case ensures that the register function enforces the requirement that the provided site must be a subclass of AdminSite, preventing potential errors or security vulnerabilities.

        :raises: ValueError if the site does not subclass AdminSite
        """
        with self.assertRaisesMessage(ValueError, "site must subclass AdminSite"):
            register(Person, site=Traveler)(NameAdmin)

    def test_empty_models_list_registration_fails(self):
        """
        Tests the registration of models with an empty list, verifying that it fails as expected.

        When registering models, this test checks that a ValueError is raised with a specific message, 
        indicating that at least one model must be provided for the registration to succeed.

        The test case validates the error handling mechanism, ensuring that invalid input is properly 
        rejected and meaningful error messages are provided to the user.
        """
        with self.assertRaisesMessage(
            ValueError, "At least one model must be passed to register."
        ):
            register()(NameAdmin)
