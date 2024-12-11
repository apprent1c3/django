from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from .tests import AdminDocsTestCase, TestDataMixin


class XViewMiddlewareTest(TestDataMixin, AdminDocsTestCase):
    def test_xview_func(self):
        """

        Tests the functionality of the X-View header in responses from the /xview/func/ endpoint.

        This test case ensures that the X-View header is present in the response only when the
        request is made by a logged-in staff user. The test covers various scenarios, including:
        - Anonymous users
        - Logged-in non-staff users
        - Logged-in staff users
        - Logged-in inactive staff users

        Verifies that the X-View header contains the expected view function name when the
        request is made by a logged-in staff user.

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
