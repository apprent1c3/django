from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from .tests import AdminDocsTestCase, TestDataMixin


class XViewMiddlewareTest(TestDataMixin, AdminDocsTestCase):
    def test_xview_func(self):
        """

        Tests the functionality of the X-View header in an HTTP response.

        This test case verifies that the X-View header is included in the response
        only when the user is logged in as a staff member with an active account.
        It checks the following scenarios:
        - Anonymous user access
        - Logged-in superuser access
        - Non-staff user access
        - Inactive staff user access

        The test ensures that the X-View header contains the correct view function
        name when the user has the required permissions.

        """
        user = User.objects.get(username="super")
        response = self.client.head("/xview/func/")
        self.assertNotIn("X-View", response)
        self.client.force_login(self.superuser)
        response = self.client.head("/xview/func/")
        self.assertIn("X-View", response)
        self.assertEqual(response.headers["X-View"], "admin_docs.views.xview")
        user.is_staff = False
        user.save()
        response = self.client.head("/xview/func/")
        self.assertNotIn("X-View", response)
        user.is_staff = True
        user.is_active = False
        user.save()
        response = self.client.head("/xview/func/")
        self.assertNotIn("X-View", response)

    def test_xview_class(self):
        user = User.objects.get(username="super")
        response = self.client.head("/xview/class/")
        self.assertNotIn("X-View", response)
        self.client.force_login(self.superuser)
        response = self.client.head("/xview/class/")
        self.assertIn("X-View", response)
        self.assertEqual(response.headers["X-View"], "admin_docs.views.XViewClass")
        user.is_staff = False
        user.save()
        response = self.client.head("/xview/class/")
        self.assertNotIn("X-View", response)
        user.is_staff = True
        user.is_active = False
        user.save()
        response = self.client.head("/xview/class/")
        self.assertNotIn("X-View", response)

    def test_callable_object_view(self):
        self.client.force_login(self.superuser)
        response = self.client.head("/xview/callable_object/")
        self.assertEqual(
            response.headers["X-View"], "admin_docs.views.XViewCallableObject"
        )

    @override_settings(MIDDLEWARE=[])
    def test_no_auth_middleware(self):
        msg = (
            "The XView middleware requires authentication middleware to be "
            "installed. Edit your MIDDLEWARE setting to insert "
            "'django.contrib.auth.middleware.AuthenticationMiddleware'."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.head("/xview/func/")
