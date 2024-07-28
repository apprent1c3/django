from django.conf import STATICFILES_STORAGE_ALIAS
from django.test import override_settings

from .cases import StaticFilesTestCase


class TestTemplateTag(StaticFilesTestCase):
    def test_template_tag(self):
        """
        This is a comment
        """
        self.assertStaticRenders("does/not/exist.png", "/static/does/not/exist.png")
        self.assertStaticRenders("testfile.txt", "/static/testfile.txt")
        self.assertStaticRenders(
            "special?chars&quoted.html", "/static/special%3Fchars%26quoted.html"
        )

    @override_settings(
        STORAGES={
            STATICFILES_STORAGE_ALIAS: {
                "BACKEND": "staticfiles_tests.storage.QueryStringStorage"
            },
        }
    )
    def test_template_tag_escapes(self):
        """
        This is a comment
        """
        self.assertStaticRenders("a.html", "a.html?a=b&amp;c=d")
        self.assertStaticRenders("a.html", "a.html?a=b&c=d", autoescape=False)
