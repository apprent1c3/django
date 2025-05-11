from django.contrib.staticfiles.utils import check_settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings


class CheckSettingsTests(SimpleTestCase):
    @override_settings(DEBUG=True, MEDIA_URL="static/media/", STATIC_URL="static/")
    def test_media_url_in_static_url(self):
        """
        Tests that the Django settings validation prevents running the development server when MEDIA_URL is a subdirectory of STATIC_URL, as this can cause problems with serving media files, but allows it when DEBUG is set to False, as this case typically corresponds to a production environment where the media serving is handled separately.
        """
        msg = "runserver can't serve media if MEDIA_URL is within STATIC_URL."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            check_settings()
        with self.settings(DEBUG=False):  # Check disabled if DEBUG=False.
            check_settings()
