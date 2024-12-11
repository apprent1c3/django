from urllib.parse import urljoin

from django.conf import STATICFILES_STORAGE_ALIAS
from django.contrib.staticfiles import storage
from django.forms import Media
from django.templatetags.static import static
from django.test import SimpleTestCase, override_settings


class StaticTestStorage(storage.StaticFilesStorage):
    def url(self, name):
        return urljoin("https://example.com/assets/", name)


@override_settings(
    INSTALLED_APPS=("django.contrib.staticfiles",),
    STORAGES={
        STATICFILES_STORAGE_ALIAS: {
            "BACKEND": "staticfiles_tests.test_forms.StaticTestStorage",
            "OPTIONS": {"location": "http://media.example.com/static/"},
        }
    },
)
class StaticFilesFormsMediaTestCase(SimpleTestCase):
    def test_absolute_url(self):
        """
        Tests the rendering of absolute URLs for media assets.

        This test case verifies that absolute URLs are correctly generated for CSS and JavaScript files, 
        including cases where the URLs are absolute, relative, or already point to a secure or external host.

        The test checks the output of the Media object against an expected HTML string, 
        ensuring that all URLs are properly formatted and that the resulting HTML is as expected.
        """
        m = Media(
            css={"all": ("path/to/css1", "/path/to/css2")},
            js=(
                "/path/to/js1",
                "http://media.other.com/path/to/js2",
                "https://secure.other.com/path/to/js3",
                static("relative/path/to/js4"),
            ),
        )
        self.assertEqual(
            str(m),
            '<link href="https://example.com/assets/path/to/css1" media="all" '
            'rel="stylesheet">\n'
            '<link href="/path/to/css2" media="all" rel="stylesheet">\n'
            '<script src="/path/to/js1"></script>\n'
            '<script src="http://media.other.com/path/to/js2"></script>\n'
            '<script src="https://secure.other.com/path/to/js3"></script>\n'
            '<script src="https://example.com/assets/relative/path/to/js4"></script>',
        )
