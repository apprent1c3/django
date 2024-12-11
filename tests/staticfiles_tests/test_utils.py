from django.contrib.staticfiles.utils import check_settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings


class CheckSettingsTests(SimpleTestCase):
    @override_settings(DEBUG=True, MEDIA_URL="static/media/", STATIC_URL="static/")
    def test_media_url_in_static_url(self):
        """
        Tests that the runserver command correctly handles MEDIA_URL within STATIC_URL.

        This function checks that an ImproperlyConfigured exception is raised when MEDIA_URL is
        a subdirectory of STATIC_URL and the DEBUG setting is enabled. The test also verifies
        that no exception is raised when the DEBUG setting is disabled, allowing the runserver
        command to serve media files.

        The purpose of this test is to ensure that the application correctly handles the
        configuration of media and static file serving in different deployment environments.
        """
        msg = "runserver can't serve media if MEDIA_URL is within STATIC_URL."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            check_settings()
        with self.settings(DEBUG=False):  # Check disabled if DEBUG=False.
            check_settings()
