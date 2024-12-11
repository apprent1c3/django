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
        Tests that the absolute URL of a Media object is correctly generated.

        The test case verifies that the Media object properly handles different types of URLs, 
        including relative and absolute paths, for both CSS and JavaScript files. It checks 
        that the resulting string representation of the Media object contains the expected 
        HTML tags and attributes, such as link and script tags with correct href and src 
        attributes.

        This test ensures that the Media object can correctly generate the absolute URL 
        for various types of media files, including those with static URLs and external 
        URLs, and that it produces the expected output in the required format.
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
