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

        Tests that calling admin.autodiscover() twice raises an exception with the 'Bad admin module' message.

        This test validates the expected behavior of the autodiscover function when invoked multiple times, 
        ensuring it correctly handles and reports the error due to attempting redundant discoveries.

        """
        with self.assertRaisesMessage(Exception, "Bad admin module"):
            admin.autodiscover()
        # Calling autodiscover again should raise the very same error it did
        # the first time, not an AlreadyRegistered error.
        with self.assertRaisesMessage(Exception, "Bad admin module"):
            admin.autodiscover()
