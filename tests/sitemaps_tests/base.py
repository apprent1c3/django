from django.apps import apps
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.test import TestCase, modify_settings, override_settings

from .models import I18nTestModel, TestModel


@modify_settings(INSTALLED_APPS={"append": "django.contrib.sitemaps"})
@override_settings(ROOT_URLCONF="sitemaps_tests.urls.http")
class SitemapTestsBase(TestCase):
    protocol = "http"
    sites_installed = apps.is_installed("django.contrib.sites")
    domain = "example.com" if sites_installed else "testserver"

    @classmethod
    def setUpTestData(cls):
        # Create an object for sitemap content.
        """

        Sets up test data for the test class.

        This method creates a test object instance and an internationalized test object instance,
        which can be used throughout the test class to simplify test setup and reduce test duplication.
        The created objects are stored as class attributes, allowing easy access to them in other test methods.

        """
        TestModel.objects.create(name="Test Object")
        cls.i18n_model = I18nTestModel.objects.create(name="Test Object")

    def setUp(self):
        self.base_url = "%s://%s" % (self.protocol, self.domain)
        cache.clear()

    @classmethod
    def setUpClass(cls):
        """
        Sets up the class by clearing the cache of Site objects, ensuring a clean slate for testing.

        This method is called once before all tests in the class are run, and is used to prepare the test environment. It inherits the default setUpClass behavior from its parent class and adds an additional step to clear the Site object cache, which helps prevent test interference and ensures consistent results. 
        """
        super().setUpClass()
        # This cleanup is necessary because contrib.sites cache
        # makes tests interfere with each other, see #11505
        Site.objects.clear_cache()
