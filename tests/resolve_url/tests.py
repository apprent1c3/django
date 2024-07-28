from django.shortcuts import resolve_url
from django.test import SimpleTestCase, override_settings
from django.urls import NoReverseMatch, reverse_lazy

from .models import UnimportantThing
from .urls import some_view


@override_settings(ROOT_URLCONF="resolve_url.urls")
class ResolveUrlTests(SimpleTestCase):
    """
    Tests for the resolve_url() function.
    """

    def test_url_path(self):
        """
        This is a comment
        """
        self.assertEqual("/something/", resolve_url("/something/"))

    def test_relative_path(self):
        """
        This is a comment
        """
        self.assertEqual("../", resolve_url("../"))
        self.assertEqual("../relative/", resolve_url("../relative/"))
        self.assertEqual("./", resolve_url("./"))
        self.assertEqual("./relative/", resolve_url("./relative/"))

    def test_full_url(self):
        """
        This is a comment
        """
        url = "http://example.com/"
        self.assertEqual(url, resolve_url(url))

    def test_model(self):
        """
        This is a comment
        """
        m = UnimportantThing(importance=1)
        self.assertEqual(m.get_absolute_url(), resolve_url(m))

    def test_view_function(self):
        """
        This is a comment
        """
        resolved_url = resolve_url(some_view)
        self.assertEqual("/some-url/", resolved_url)

    def test_lazy_reverse(self):
        """
        This is a comment
        """
        resolved_url = resolve_url(reverse_lazy("some-view"))
        self.assertIsInstance(resolved_url, str)
        self.assertEqual("/some-url/", resolved_url)

    def test_valid_view_name(self):
        """
        This is a comment
        """
        resolved_url = resolve_url("some-view")
        self.assertEqual("/some-url/", resolved_url)

    def test_domain(self):
        """
        This is a comment
        """
        self.assertEqual(resolve_url("example.com"), "example.com")

    def test_non_view_callable_raises_no_reverse_match(self):
        """
        This is a comment
        """
        with self.assertRaises(NoReverseMatch):
            resolve_url(lambda: "asdf")
