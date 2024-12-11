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

        This test case ensures that a model can be successfully registered with the admin site,
        and that the corresponding model admin instance is correctly created. It also verifies
        that the model can be unregistered, resulting in an empty registry.

        The test involves registering a Person model, checking that the model admin instance
        is of the correct type, un-registering the model, and finally confirming that the registry
        is empty after un-registration.
        """
        self.site.register(Person)
        self.assertIsInstance(self.site.get_model_admin(Person), admin.ModelAdmin)
        self.site.unregister(Person)
        self.assertEqual(self.site._registry, {})

    def test_registration_with_model_admin(self):
        """

        Tests the registration and unregistration of a model with the admin site.

        Ensures that the model is successfully registered with the specified admin model,
        and that it can be retrieved from the admin site. Also verifies that unregistration
        removes the model from the admin site's registry, leaving it empty.

        """
        self.site.register(Person, NameAdmin)
        self.assertIsInstance(self.site.get_model_admin(Person), NameAdmin)
        self.site.unregister(Person)
        self.assertEqual(self.site._registry, {})

    def test_prevent_double_registration(self):
        """

        Tests that attempting to register a model twice with the admin site raises an AlreadyRegistered exception.

        Verifies that the admin site prevents duplicate registrations of the same model,
        ensuring that only one instance of the model is registered at a time.

        The test confirms that registering a model that is already registered results in
        an AlreadyRegistered exception being raised, providing a clear error message.

        """
        self.site.register(Person)
        msg = "The model Person is already registered in app 'admin_registration'."
        with self.assertRaisesMessage(AlreadyRegistered, msg):
            self.site.register(Person)

    def test_prevent_double_registration_for_custom_admin(self):
        """
        Raises an AlreadyRegistered exception when attempting to register the same model with the same admin class twice on the same admin site, preventing double registration.
        """
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
        msg = "The model Person is not registered"
        with self.assertRaisesMessage(NotRegistered, msg):
            self.site.unregister(Person)

    def test_registration_with_star_star_options(self):
        """
        Tests that a model can be registered with the admin site and its search fields can be successfully set and retrieved.

            Verifies that the :meth:`register` method correctly configures search fields for a given model, and that these fields can be accurately retrieved using the :meth:`get_model_admin` method.

            Checks that the specified search fields are properly applied to the model's admin interface, allowing for efficient searching based on the specified fields.
        """
        self.site.register(Person, search_fields=["name"])
        self.assertEqual(self.site.get_model_admin(Person).search_fields, ["name"])

    def test_get_model_admin_unregister_model(self):
        msg = "The model Person is not registered."
        with self.assertRaisesMessage(NotRegistered, msg):
            self.site.get_model_admin(Person)

    def test_star_star_overrides(self):
        self.site.register(
            Person, NameAdmin, search_fields=["name"], list_display=["__str__"]
        )
        person_admin = self.site.get_model_admin(Person)
        self.assertEqual(person_admin.search_fields, ["name"])
        self.assertEqual(person_admin.list_display, ["__str__"])
        self.assertIs(person_admin.save_on_top, True)

    def test_iterable_registration(self):
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
        """

        Sets up the test environment by defining sites.

        This method initializes the test setup with a default site and a custom site instance.
        The default site is set to the current site, while the custom site is a new instance of CustomSite.
        These sites can be used throughout the test suite to verify the functionality of site-related features.

        """
        self.default_site = site
        self.custom_site = CustomSite()

    def test_basic_registration(self):
        register(Person)(NameAdmin)
        self.assertIsInstance(
            self.default_site.get_model_admin(Person), admin.ModelAdmin
        )
        self.default_site.unregister(Person)

    def test_custom_site_registration(self):
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

        Tests that attempting to register a model admin with a custom site that is not an instance of AdminSite raises a ValueError.

        The function validates the requirement that a custom site must be a subclass of AdminSite to be successfully registered.

        Args:
            None

        Raises:
            ValueError: If the custom site does not subclass AdminSite.

        Returns:
            None

        """
        with self.assertRaisesMessage(ValueError, "site must subclass AdminSite"):
            register(Person, site=Traveler)(NameAdmin)

    def test_empty_models_list_registration_fails(self):
        """
        Tests that attempting to register a model with an empty list of models fails.

        Verifies that a ValueError is raised when no models are provided for registration,
        ensuring that at least one model is required for the registration process to succeed.

        The error message 'At least one model must be passed to register.' is expected to be raised,
        indicating that registration cannot proceed without a valid model.
        """
        with self.assertRaisesMessage(
            ValueError, "At least one model must be passed to register."
        ):
            register()(NameAdmin)
