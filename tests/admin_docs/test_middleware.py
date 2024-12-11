from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from .tests import AdminDocsTestCase, TestDataMixin


class XViewMiddlewareTest(TestDataMixin, AdminDocsTestCase):
    def test_xview_func(self):
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
        """
        Checks the \"X-View\" header in the HTTP response from the '/xview/callable_object/' endpoint to ensure it correctly identifies the view function handling the request. The test authenticates as a superuser and uses a HEAD request to verify the view's identity without retrieving the full response body.
        """
        self.client.force_login(self.superuser)
        response = self.client.head("/xview/callable_object/")
        self.assertEqual(
            response.headers["X-View"], "admin_docs.views.XViewCallableObject"
        )

    @override_settings(MIDDLEWARE=[])
    def test_no_auth_middleware(self):
        """

        Test that the XView middleware raises an ImproperlyConfigured exception when 
        the authentication middleware is not installed in the MIDDLEWARE setting.

        This test case checks that the proper error message is displayed when the 'django.contrib.auth.middleware.AuthenticationMiddleware'
        is missing from the MIDDLEWARE setting, to ensure correct configuration of the 
        XView middleware.

        """
        msg = (
            "The XView middleware requires authentication middleware to be "
            "installed. Edit your MIDDLEWARE setting to insert "
            "'django.contrib.auth.middleware.AuthenticationMiddleware'."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.head("/xview/func/")
