from django.contrib import admin
from django.contrib.admin import sites
from django.test import SimpleTestCase, override_settings

from .sites import CustomAdminSite


@override_settings(
    INSTALLED_APPS=[
        "admin_default_site.apps.MyCustomAdminConfig",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    ]
)
class CustomAdminSiteTests(SimpleTestCase):
    def setUp(self):
        # Reset admin.site since it may have already been instantiated by
        # another test app.
        """
        Sets up the test environment by temporarily replacing the default admin site.

        This method saves the current admin site, and then overrides it with a new instance of DefaultAdminSite.
        This allows for isolation of tests from the global admin site configuration, ensuring predictable behavior.
        The original admin site is stored internally, presumably for later restoration when the test is torn down.
        """
        self._old_site = admin.site
        admin.site = sites.site = sites.DefaultAdminSite()

    def tearDown(self):
        admin.site = sites.site = self._old_site

    def test_use_custom_admin_site(self):
        self.assertEqual(admin.site.__class__.__name__, "CustomAdminSite")


class DefaultAdminSiteTests(SimpleTestCase):
    def test_use_default_admin_site(self):
        self.assertEqual(admin.site.__class__.__name__, "AdminSite")

    def test_repr(self):
        self.assertEqual(str(admin.site), "AdminSite(name='admin')")
        self.assertEqual(repr(admin.site), "AdminSite(name='admin')")


class AdminSiteTests(SimpleTestCase):
    def test_repr(self):
        """

        Tests the representation of the CustomAdminSite class.

        Verifies that the repr method returns a string that accurately reflects the 
        construction of the object, including the name parameter.

        This ensures that the CustomAdminSite object can be unambiguously represented 
        as a string, which is useful for debugging and logging purposes.

        """
        admin_site = CustomAdminSite(name="other")
        self.assertEqual(repr(admin_site), "CustomAdminSite(name='other')")
