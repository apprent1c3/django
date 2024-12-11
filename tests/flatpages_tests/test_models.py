from django.contrib.flatpages.models import FlatPage
from django.test import SimpleTestCase, override_settings
from django.test.utils import override_script_prefix


class FlatpageModelTests(SimpleTestCase):
    def setUp(self):
        self.page = FlatPage(title="Café!", url="/café/")

    def test_get_absolute_url_urlencodes(self):
        self.assertEqual(self.page.get_absolute_url(), "/caf%C3%A9/")

    @override_script_prefix("/prefix/")
    def test_get_absolute_url_honors_script_prefix(self):
        self.assertEqual(self.page.get_absolute_url(), "/prefix/caf%C3%A9/")

    def test_str(self):
        self.assertEqual(str(self.page), "/café/ -- Café!")

    @override_settings(ROOT_URLCONF="flatpages_tests.urls")
    def test_get_absolute_url_include(self):
        self.assertEqual(self.page.get_absolute_url(), "/flatpage_root/caf%C3%A9/")

    @override_settings(ROOT_URLCONF="flatpages_tests.no_slash_urls")
    def test_get_absolute_url_include_no_slash(self):
        self.assertEqual(self.page.get_absolute_url(), "/flatpagecaf%C3%A9/")

    @override_settings(ROOT_URLCONF="flatpages_tests.absolute_urls")
    def test_get_absolute_url_with_hardcoded_url(self):
        """

        Tests the get_absolute_url method of a FlatPage instance with a hardcoded URL.

        This test case verifies that the get_absolute_url method returns the correct URL 
        for a FlatPage, even when the URL is hardcoded. It ensures that the method 
        correctly resolves the URL to the root URL configuration.

        The expected output is the URL that points to the flatpage, rather than the 
        hardcoded URL. This test helps to ensure that the absolute URL resolution is 
        working correctly in the context of the flatpages application.

        """
        fp = FlatPage(title="Test", url="/hardcoded/")
        self.assertEqual(fp.get_absolute_url(), "/flatpage/")
