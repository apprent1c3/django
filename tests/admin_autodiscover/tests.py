from django.contrib import admin
from django.test import SimpleTestCase


class AdminAutoDiscoverTests(SimpleTestCase):
    """
    Test for bug #8245 - don't raise an AlreadyRegistered exception when using
    autodiscover() and an admin.py module contains an error.
    """

    def test_double_call_autodiscover(self):
        # The first time autodiscover is called, we should get our real error.
        """
        Tests that calling autodiscover twice raises an exception.

        This test case verifies that the autodiscover function in the admin module
        raises an Exception with a 'Bad admin module' message when called multiple times.
        It ensures that the function behaves correctly when invoked in succession,
        preventing potential issues with duplicate autodiscovery attempts.
        """
        with self.assertRaisesMessage(Exception, "Bad admin module"):
            admin.autodiscover()
        # Calling autodiscover again should raise the very same error it did
        # the first time, not an AlreadyRegistered error.
        with self.assertRaisesMessage(Exception, "Bad admin module"):
            admin.autodiscover()
