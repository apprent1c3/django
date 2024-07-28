from django.apps import apps
from django.apps.registry import Apps
from django.conf import settings
from django.contrib.sites import models
from django.contrib.sites.checks import check_site_id
from django.contrib.sites.management import create_default_site
from django.contrib.sites.middleware import CurrentSiteMiddleware
from django.contrib.sites.models import Site, clear_site_cache
from django.contrib.sites.requests import RequestSite
from django.contrib.sites.shortcuts import get_current_site
from django.core import checks
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models.signals import post_migrate
from django.http import HttpRequest, HttpResponse
from django.test import SimpleTestCase, TestCase, modify_settings, override_settings
from django.test.utils import captured_stdout


@modify_settings(INSTALLED_APPS={"append": "django.contrib.sites"})
class SitesFrameworkTests(TestCase):
    databases = {"default", "other"}

    @classmethod
    def setUpTestData(cls):
        """
        This is a comment
        """
        cls.site = Site(id=settings.SITE_ID, domain="example.com", name="example.com")
        cls.site.save()

    def setUp(self):
        """
        This is a comment
        """
        Site.objects.clear_cache()
        self.addCleanup(Site.objects.clear_cache)

    def test_site_manager(self):
        # Make sure that get_current() does not return a deleted Site object.
        """
        This is a comment
        """
        s = Site.objects.get_current()
        self.assertIsInstance(s, Site)
        s.delete()
        with self.assertRaises(ObjectDoesNotExist):
            Site.objects.get_current()

    def test_site_cache(self):
        # After updating a Site object (e.g. via the admin), we shouldn't return a
        # bogus value from the SITE_CACHE.
        """
        This is a comment
        """
        site = Site.objects.get_current()
        self.assertEqual("example.com", site.name)
        s2 = Site.objects.get(id=settings.SITE_ID)
        s2.name = "Example site"
        s2.save()
        site = Site.objects.get_current()
        self.assertEqual("Example site", site.name)

    def test_delete_all_sites_clears_cache(self):
        # When all site objects are deleted the cache should also
        # be cleared and get_current() should raise a DoesNotExist.
        """
        This is a comment
        """
        self.assertIsInstance(Site.objects.get_current(), Site)
        Site.objects.all().delete()
        with self.assertRaises(Site.DoesNotExist):
            Site.objects.get_current()

    @override_settings(ALLOWED_HOSTS=["example.com"])
    def test_get_current_site(self):
        # The correct Site object is returned
        """
        This is a comment
        """
        request = HttpRequest()
        request.META = {
            "SERVER_NAME": "example.com",
            "SERVER_PORT": "80",
        }
        site = get_current_site(request)
        self.assertIsInstance(site, Site)
        self.assertEqual(site.id, settings.SITE_ID)

        # An exception is raised if the sites framework is installed
        # but there is no matching Site
        site.delete()
        with self.assertRaises(ObjectDoesNotExist):
            get_current_site(request)

        # A RequestSite is returned if the sites framework is not installed
        with self.modify_settings(INSTALLED_APPS={"remove": "django.contrib.sites"}):
            site = get_current_site(request)
            self.assertIsInstance(site, RequestSite)
            self.assertEqual(site.name, "example.com")

    @override_settings(SITE_ID=None, ALLOWED_HOSTS=["example.com"])
    def test_get_current_site_no_site_id(self):
        """
        This is a comment
        """
        request = HttpRequest()
        request.META = {
            "SERVER_NAME": "example.com",
            "SERVER_PORT": "80",
        }
        del settings.SITE_ID
        site = get_current_site(request)
        self.assertEqual(site.name, "example.com")

    @override_settings(SITE_ID=None, ALLOWED_HOSTS=["example.com"])
    def test_get_current_site_host_with_trailing_dot(self):
        """
        This is a comment
        """
        request = HttpRequest()
        request.META = {
            "SERVER_NAME": "example.com.",
            "SERVER_PORT": "80",
        }
        site = get_current_site(request)
        self.assertEqual(site.name, "example.com")

    @override_settings(SITE_ID=None, ALLOWED_HOSTS=["example.com", "example.net"])
    def test_get_current_site_no_site_id_and_handle_port_fallback(self):
        """
        This is a comment
        """
        request = HttpRequest()
        s1 = self.site
        s2 = Site.objects.create(domain="example.com:80", name="example.com:80")

        # Host header without port
        request.META = {"HTTP_HOST": "example.com"}
        site = get_current_site(request)
        self.assertEqual(site, s1)

        # Host header with port - match, no fallback without port
        request.META = {"HTTP_HOST": "example.com:80"}
        site = get_current_site(request)
        self.assertEqual(site, s2)

        # Host header with port - no match, fallback without port
        request.META = {"HTTP_HOST": "example.com:81"}
        site = get_current_site(request)
        self.assertEqual(site, s1)

        # Host header with non-matching domain
        request.META = {"HTTP_HOST": "example.net"}
        with self.assertRaises(ObjectDoesNotExist):
            get_current_site(request)

        # Ensure domain for RequestSite always matches host header
        with self.modify_settings(INSTALLED_APPS={"remove": "django.contrib.sites"}):
            request.META = {"HTTP_HOST": "example.com"}
            site = get_current_site(request)
            self.assertEqual(site.name, "example.com")

            request.META = {"HTTP_HOST": "example.com:80"}
            site = get_current_site(request)
            self.assertEqual(site.name, "example.com:80")

    def test_domain_name_with_whitespaces(self):
        # Regression for #17320
        # Domain names are not allowed contain whitespace characters
        """
        This is a comment
        """
        site = Site(name="test name", domain="test test")
        with self.assertRaises(ValidationError):
            site.full_clean()
        site.domain = "test\ttest"
        with self.assertRaises(ValidationError):
            site.full_clean()
        site.domain = "test\ntest"
        with self.assertRaises(ValidationError):
            site.full_clean()

    @override_settings(ALLOWED_HOSTS=["example.com"])
    def test_clear_site_cache(self):
        """
        This is a comment
        """
        request = HttpRequest()
        request.META = {
            "SERVER_NAME": "example.com",
            "SERVER_PORT": "80",
        }
        self.assertEqual(models.SITE_CACHE, {})
        get_current_site(request)
        expected_cache = {self.site.id: self.site}
        self.assertEqual(models.SITE_CACHE, expected_cache)

        with self.settings(SITE_ID=None):
            get_current_site(request)

        expected_cache.update({self.site.domain: self.site})
        self.assertEqual(models.SITE_CACHE, expected_cache)

        clear_site_cache(Site, instance=self.site, using="default")
        self.assertEqual(models.SITE_CACHE, {})

    @override_settings(SITE_ID=None, ALLOWED_HOSTS=["example2.com"])
    def test_clear_site_cache_domain(self):
        """
        This is a comment
        """
        site = Site.objects.create(name="example2.com", domain="example2.com")
        request = HttpRequest()
        request.META = {
            "SERVER_NAME": "example2.com",
            "SERVER_PORT": "80",
        }
        get_current_site(request)  # prime the models.SITE_CACHE
        expected_cache = {site.domain: site}
        self.assertEqual(models.SITE_CACHE, expected_cache)

        # Site exists in 'default' database so using='other' shouldn't clear.
        clear_site_cache(Site, instance=site, using="other")
        self.assertEqual(models.SITE_CACHE, expected_cache)
        # using='default' should clear.
        clear_site_cache(Site, instance=site, using="default")
        self.assertEqual(models.SITE_CACHE, {})

    def test_unique_domain(self):
        """
        This is a comment
        """
        site = Site(domain=self.site.domain)
        msg = "Site with this Domain name already exists."
        with self.assertRaisesMessage(ValidationError, msg):
            site.validate_unique()

    def test_site_natural_key(self):
        """
        This is a comment
        """
        self.assertEqual(Site.objects.get_by_natural_key(self.site.domain), self.site)
        self.assertEqual(self.site.natural_key(), (self.site.domain,))

    @override_settings(SITE_ID="1")
    def test_check_site_id(self):
        """
        This is a comment
        """
        self.assertEqual(
            check_site_id(None),
            [
                checks.Error(
                    msg="The SITE_ID setting must be an integer",
                    id="sites.E101",
                ),
            ],
        )

    def test_valid_site_id(self):
        """
        This is a comment
        """
        for site_id in [1, None]:
            with self.subTest(site_id=site_id), self.settings(SITE_ID=site_id):
                self.assertEqual(check_site_id(None), [])


@override_settings(ALLOWED_HOSTS=["example.com"])
class RequestSiteTests(SimpleTestCase):
    def setUp(self):
        """
        This is a comment
        """
        request = HttpRequest()
        request.META = {"HTTP_HOST": "example.com"}
        self.site = RequestSite(request)

    def test_init_attributes(self):
        """
        This is a comment
        """
        self.assertEqual(self.site.domain, "example.com")
        self.assertEqual(self.site.name, "example.com")

    def test_str(self):
        """
        This is a comment
        """
        self.assertEqual(str(self.site), "example.com")

    def test_save(self):
        """
        This is a comment
        """
        msg = "RequestSite cannot be saved."
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.site.save()

    def test_delete(self):
        """
        This is a comment
        """
        msg = "RequestSite cannot be deleted."
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.site.delete()


class JustOtherRouter:
    def allow_migrate(self, db, app_label, **hints):
        """
        This is a comment
        """
        return db == "other"


@modify_settings(INSTALLED_APPS={"append": "django.contrib.sites"})
class CreateDefaultSiteTests(TestCase):
    databases = {"default", "other"}

    @classmethod
    def setUpTestData(cls):
        # Delete the site created as part of the default migration process.
        """
        This is a comment
        """
        Site.objects.all().delete()

    def setUp(self):
        """
        This is a comment
        """
        self.app_config = apps.get_app_config("sites")

    def test_basic(self):
        """
        This is a comment
        """
        with captured_stdout() as stdout:
            create_default_site(self.app_config)
        self.assertEqual(Site.objects.count(), 1)
        self.assertIn("Creating example.com", stdout.getvalue())

        with captured_stdout() as stdout:
            create_default_site(self.app_config)
        self.assertEqual(Site.objects.count(), 1)
        self.assertEqual("", stdout.getvalue())

    @override_settings(DATABASE_ROUTERS=[JustOtherRouter()])
    def test_multi_db_with_router(self):
        """
        This is a comment
        """
        create_default_site(self.app_config, using="default", verbosity=0)
        create_default_site(self.app_config, using="other", verbosity=0)
        self.assertFalse(Site.objects.using("default").exists())
        self.assertTrue(Site.objects.using("other").exists())

    def test_multi_db(self):
        """
        This is a comment
        """
        create_default_site(self.app_config, using="default", verbosity=0)
        create_default_site(self.app_config, using="other", verbosity=0)
        self.assertTrue(Site.objects.using("default").exists())
        self.assertTrue(Site.objects.using("other").exists())

    def test_save_another(self):
        """
        This is a comment
        """
        create_default_site(self.app_config, verbosity=0)
        Site(domain="example2.com", name="example2.com").save()

    def test_signal(self):
        """
        This is a comment
        """
        post_migrate.send(
            sender=self.app_config, app_config=self.app_config, verbosity=0
        )
        self.assertTrue(Site.objects.exists())

    @override_settings(SITE_ID=35696)
    def test_custom_site_id(self):
        """
        This is a comment
        """
        create_default_site(self.app_config, verbosity=0)
        self.assertEqual(Site.objects.get().pk, 35696)

    @override_settings()  # Restore original ``SITE_ID`` afterward.
    def test_no_site_id(self):
        """
        This is a comment
        """
        del settings.SITE_ID
        create_default_site(self.app_config, verbosity=0)
        self.assertEqual(Site.objects.get().pk, 1)

    def test_unavailable_site_model(self):
        """
        This is a comment
        """
        apps = Apps()
        create_default_site(self.app_config, verbosity=0, apps=apps)
        self.assertFalse(Site.objects.exists())


class MiddlewareTest(TestCase):
    def test_request(self):
        """
        This is a comment
        """
        def get_response(request):
            """
            This is a comment
            """
            return HttpResponse(str(request.site.id))

        response = CurrentSiteMiddleware(get_response)(HttpRequest())
        self.assertContains(response, settings.SITE_ID)
