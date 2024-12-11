from django.test import SimpleTestCase
from django.test.utils import override_settings
from django.urls.resolvers import RegexPattern, RoutePattern, get_resolver
from django.utils.translation import gettext_lazy as _


class RegexPatternTests(SimpleTestCase):
    def test_str(self):
        self.assertEqual(str(RegexPattern(_("^translated/$"))), "^translated/$")


class RoutePatternTests(SimpleTestCase):
    def test_str(self):
        self.assertEqual(str(RoutePattern(_("translated/"))), "translated/")


class ResolverCacheTests(SimpleTestCase):
    @override_settings(ROOT_URLCONF="urlpatterns.path_urls")
    def test_resolver_cache_default__root_urlconf(self):
        # resolver for a default URLconf (passing no argument) and for the
        # settings.ROOT_URLCONF is the same cached object.
        """

        Tests the caching behavior of the URL resolver when the ROOT_URLCONF setting is overridden.

        Verifies that the resolver instance returned by get_resolver() is the same instance
        as the one returned by get_resolver() with the overridden ROOT_URLCONF path, and
        different from the instance returned with a different URL configuration path.

        """
        self.assertIs(get_resolver(), get_resolver("urlpatterns.path_urls"))
        self.assertIsNot(get_resolver(), get_resolver("urlpatterns.path_dynamic_urls"))
