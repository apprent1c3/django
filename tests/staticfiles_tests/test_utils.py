from django.contrib.staticfiles.utils import check_settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings


class CheckSettingsTests(SimpleTestCase):
    @override_settings(DEBUG=True, MEDIA_URL="static/media/", STATIC_URL="static/")
    def test_media_url_in_static_url(self):
        """
        Tests that an error is raised when MEDIA_URL is nested within STATIC_URL and the application is running in debug mode, ensuring correct configuration of media and static files serving.
        """
        msg = "runserver can't serve media if MEDIA_URL is within STATIC_URL."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            check_settings()
        with self.settings(DEBUG=False):  # Check disabled if DEBUG=False.
            check_settings()
