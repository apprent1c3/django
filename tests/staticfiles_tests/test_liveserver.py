"""
A subset of the tests in tests/servers/tests exercising
django.contrib.staticfiles.testing.StaticLiveServerTestCase instead of
django.test.LiveServerTestCase.
"""

import os
from urllib.request import urlopen

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.exceptions import ImproperlyConfigured
from django.test import modify_settings, override_settings

TEST_ROOT = os.path.dirname(__file__)
TEST_SETTINGS = {
    "MEDIA_URL": "media/",
    "STATIC_URL": "static/",
    "MEDIA_ROOT": os.path.join(TEST_ROOT, "project", "site_media", "media"),
    "STATIC_ROOT": os.path.join(TEST_ROOT, "project", "site_media", "static"),
}


class LiveServerBase(StaticLiveServerTestCase):
    available_apps = []

    @classmethod
    def setUpClass(cls):
        """
        Set up the class-level context for testing.

        This class method prepares the environment for test class execution by entering a specific context and applying test settings.
        It ensures that the test class is properly initialized, allowing for reliable and consistent testing.
        The method invokes the superclass's setup to maintain the standard class setup behavior.

        """
        cls.enterClassContext(override_settings(**TEST_SETTINGS))
        super().setUpClass()


class StaticLiveServerChecks(LiveServerBase):
    @classmethod
    def setUpClass(cls):
        # If contrib.staticfiles isn't configured properly, the exception
        # should bubble up to the main thread.
        """
        Set up the class by temporarily modifying the STATIC_URL setting in TEST_SETTINGS.

        This class method is used to create a setup for testing by overriding the STATIC_URL setting to None.
        It then calls the raises_exception method and ensures that the original STATIC_URL setting is restored,
        regardless of the outcome of the method call, to prevent test pollution.

        The purpose of this method is to provide a clean and isolated environment for testing,
        by resetting the STATIC_URL setting to its original value after the test is completed.
        """
        old_STATIC_URL = TEST_SETTINGS["STATIC_URL"]
        TEST_SETTINGS["STATIC_URL"] = None
        try:
            cls.raises_exception()
        finally:
            TEST_SETTINGS["STATIC_URL"] = old_STATIC_URL

    @classmethod
    def tearDownClass(cls):
        # skip it, as setUpClass doesn't call its parent either
        pass

    @classmethod
    def raises_exception(cls):
        """
        Tests that the setUpClass method correctly raises an exception.

        This class method attempts to call the setUpClass method of the parent class.
        If the method does not raise an ImproperlyConfigured exception as expected,
        it raises an Exception to indicate that the test has failed.

        It is used to validate the configuration of the class setup process.
        The method does not take any arguments and does not return any value.
        It only checks for the presence of an exception, making it a self-contained test.
        """
        try:
            super().setUpClass()
        except ImproperlyConfigured:
            # This raises ImproperlyConfigured("You're using the staticfiles
            # app without having set the required STATIC_URL setting.")
            pass
        else:
            raise Exception("setUpClass() should have raised an exception.")

    def test_test_test(self):
        # Intentionally empty method so that the test is picked up by the
        # test runner and the overridden setUpClass() method is executed.
        pass


class StaticLiveServerView(LiveServerBase):
    def urlopen(self, url):
        return urlopen(self.live_server_url + url)

    # The test is going to access a static file stored in this application.
    @modify_settings(INSTALLED_APPS={"append": "staticfiles_tests.apps.test"})
    def test_collectstatic_emulation(self):
        """
        StaticLiveServerTestCase use of staticfiles' serve() allows it
        to discover app's static assets without having to collectstatic first.
        """
        with self.urlopen("/static/test/file.txt") as f:
            self.assertEqual(f.read().rstrip(b"\r\n"), b"In static directory.")
