from unittest import mock

from django.contrib.auth import models
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.views.generic import View


class AlwaysTrueMixin(UserPassesTestMixin):
    def test_func(self):
        return True


class AlwaysFalseMixin(UserPassesTestMixin):
    def test_func(self):
        return False


class EmptyResponseView(View):
    def get(self, request, *args, **kwargs):
        return HttpResponse()


class AlwaysTrueView(AlwaysTrueMixin, EmptyResponseView):
    pass


class AlwaysFalseView(AlwaysFalseMixin, EmptyResponseView):
    pass


class StackedMixinsView1(
    LoginRequiredMixin, PermissionRequiredMixin, EmptyResponseView
):
    permission_required = ["auth_tests.add_customuser", "auth_tests.change_customuser"]
    raise_exception = True


class StackedMixinsView2(
    PermissionRequiredMixin, LoginRequiredMixin, EmptyResponseView
):
    permission_required = ["auth_tests.add_customuser", "auth_tests.change_customuser"]
    raise_exception = True


class AccessMixinTests(TestCase):
    factory = RequestFactory()

    def test_stacked_mixins_success(self):
        """
        Tests the successful application of stacked mixins in views with a user having specific permissions, verifying that the views return a 200 status code.
        """
        user = models.User.objects.create(username="joe", password="qwerty")
        perms = models.Permission.objects.filter(
            codename__in=("add_customuser", "change_customuser")
        )
        user.user_permissions.add(*perms)
        request = self.factory.get("/rand")
        request.user = user

        view = StackedMixinsView1.as_view()
        response = view(request)
        self.assertEqual(response.status_code, 200)

        view = StackedMixinsView2.as_view()
        response = view(request)
        self.assertEqual(response.status_code, 200)

    def test_stacked_mixins_missing_permission(self):
        """
        Tests that StackedMixinsView1 and StackedMixinsView2 correctly raise a PermissionDenied exception when a user with insufficient permissions attempts to access the view.
        """
        user = models.User.objects.create(username="joe", password="qwerty")
        perms = models.Permission.objects.filter(codename__in=("add_customuser",))
        user.user_permissions.add(*perms)
        request = self.factory.get("/rand")
        request.user = user

        view = StackedMixinsView1.as_view()
        with self.assertRaises(PermissionDenied):
            view(request)

        view = StackedMixinsView2.as_view()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_access_mixin_permission_denied_response(self):
        """
        Tests that the Access Mixin correctly returns a 302 redirect to the login page when an unauthenticated user attempts to access a view, and raises a PermissionDenied exception when an authenticated user is explicitly denied permission.
        """
        user = models.User.objects.create(username="joe", password="qwerty")
        # Authenticated users receive PermissionDenied.
        request = self.factory.get("/rand")
        request.user = user
        view = AlwaysFalseView.as_view()
        with self.assertRaises(PermissionDenied):
            view(request)
        # Anonymous users are redirected to the login page.
        request.user = AnonymousUser()
        response = view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/accounts/login/?next=/rand")

    def test_access_mixin_permission_denied_remote_login_url(self):
        """
        Tests that a mixin using AlwaysFalseView correctly redirects an anonymous user to a remote login URL when access is denied.
        """
        class AView(AlwaysFalseView):
            login_url = "https://www.remote.example.com/login"

        view = AView.as_view()
        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        response = view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            "https://www.remote.example.com/login?next=http%3A//testserver/rand",
        )

    @mock.patch.object(models.User, "is_authenticated", False)
    def test_stacked_mixins_not_logged_in(self):
        """
        Tests that StackedMixinsView1 and StackedMixinsView2 raise a PermissionDenied 
        exception when accessed by a non-authenticated user with specific permissions.
        """
        user = models.User.objects.create(username="joe", password="qwerty")
        perms = models.Permission.objects.filter(
            codename__in=("add_customuser", "change_customuser")
        )
        user.user_permissions.add(*perms)
        request = self.factory.get("/rand")
        request.user = user

        view = StackedMixinsView1.as_view()
        with self.assertRaises(PermissionDenied):
            view(request)

        view = StackedMixinsView2.as_view()
        with self.assertRaises(PermissionDenied):
            view(request)


class UserPassesTestTests(SimpleTestCase):
    factory = RequestFactory()

    def _test_redirect(self, view=None, url="/accounts/login/?next=/rand"):
        """
        Tests that a view redirects to the login page when accessed anonymously.

            Verifies that an HTTP redirect (302) is issued with the correct URL,
            which by default includes a 'next' parameter to redirect back to the original page after login.

        """
        if not view:
            view = AlwaysFalseView.as_view()
        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        response = view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)

    def test_default(self):
        self._test_redirect()

    def test_custom_redirect_url(self):
        class AView(AlwaysFalseView):
            login_url = "/login/"

        self._test_redirect(AView.as_view(), "/login/?next=/rand")

    def test_custom_redirect_parameter(self):
        class AView(AlwaysFalseView):
            redirect_field_name = "goto"

        self._test_redirect(AView.as_view(), "/accounts/login/?goto=/rand")

    def test_no_redirect_parameter(self):
        class AView(AlwaysFalseView):
            redirect_field_name = None

        self._test_redirect(AView.as_view(), "/accounts/login/")

    def test_raise_exception(self):
        """
        Tests that a view raises a PermissionDenied exception when its raise_exception attribute is set to True and the user does not have permission to access the view.
        """
        class AView(AlwaysFalseView):
            raise_exception = True

        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        with self.assertRaises(PermissionDenied):
            AView.as_view()(request)

    def test_raise_exception_custom_message(self):
        """
        Tests that a PermissionDenied exception is raised with a custom message when accessing a view that requires authentication.
        """
        msg = "You don't have access here"

        class AView(AlwaysFalseView):
            raise_exception = True
            permission_denied_message = msg

        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        view = AView.as_view()
        with self.assertRaisesMessage(PermissionDenied, msg):
            view(request)

    def test_raise_exception_custom_message_function(self):
        """

        Tests that when a view raises a PermissionDenied exception with a custom message,
        the correct error message is propagated.

        The test case verifies that the permission denied message is correctly set
        and the exception is raised when an anonymous user attempts to access a view.

        """
        msg = "You don't have access here"

        class AView(AlwaysFalseView):
            raise_exception = True

            def get_permission_denied_message(self):
                return msg

        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        view = AView.as_view()
        with self.assertRaisesMessage(PermissionDenied, msg):
            view(request)

    def test_user_passes(self):
        """
        Tests whether an unauthenticated user can access a view that always returns a successful response.
        """
        view = AlwaysTrueView.as_view()
        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        response = view(request)
        self.assertEqual(response.status_code, 200)


class LoginRequiredMixinTests(TestCase):
    factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        cls.user = models.User.objects.create(username="joe", password="qwerty")

    def test_login_required(self):
        """
        Checks that the login_required decorator correctly redirects unauthorized users to the login page, while allowing authenticated users to access the view.
        """

        class AView(LoginRequiredMixin, EmptyResponseView):
            pass

        view = AView.as_view()

        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        response = view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/accounts/login/?next=/rand", response.url)
        request = self.factory.get("/rand")
        request.user = self.user
        response = view(request)
        self.assertEqual(response.status_code, 200)


class PermissionsRequiredMixinTests(TestCase):
    factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        cls.user = models.User.objects.create(username="joe", password="qwerty")
        perms = models.Permission.objects.filter(
            codename__in=("add_customuser", "change_customuser")
        )
        cls.user.user_permissions.add(*perms)

    def test_many_permissions_pass(self):
        """
        Tests that a view with multiple required permissions passes when all permissions are held by the current user.
        """
        class AView(PermissionRequiredMixin, EmptyResponseView):
            permission_required = [
                "auth_tests.add_customuser",
                "auth_tests.change_customuser",
            ]

        request = self.factory.get("/rand")
        request.user = self.user
        resp = AView.as_view()(request)
        self.assertEqual(resp.status_code, 200)

    def test_single_permission_pass(self):
        """
        Tests that a view with a single permission requirement allows access when the user has the required permission.
        """
        class AView(PermissionRequiredMixin, EmptyResponseView):
            permission_required = "auth_tests.add_customuser"

        request = self.factory.get("/rand")
        request.user = self.user
        resp = AView.as_view()(request)
        self.assertEqual(resp.status_code, 200)

    def test_permissioned_denied_redirect(self):
        """
        Tests that a view using PermissionRequiredMixin redirects to the login page when 
        the user is anonymous and raises a PermissionDenied exception for authenticated users 
        lacking required permissions.
        """
        class AView(PermissionRequiredMixin, EmptyResponseView):
            permission_required = [
                "auth_tests.add_customuser",
                "auth_tests.change_customuser",
                "nonexistent-permission",
            ]

        # Authenticated users receive PermissionDenied.
        request = self.factory.get("/rand")
        request.user = self.user
        with self.assertRaises(PermissionDenied):
            AView.as_view()(request)
        # Anonymous users are redirected to the login page.
        request.user = AnonymousUser()
        resp = AView.as_view()(request)
        self.assertEqual(resp.status_code, 302)

    def test_permissioned_denied_exception_raised(self):
        """

        Tests that a PermissionDenied exception is raised when a view's required permissions include a nonexistent permission.

        """
        class AView(PermissionRequiredMixin, EmptyResponseView):
            permission_required = [
                "auth_tests.add_customuser",
                "auth_tests.change_customuser",
                "nonexistent-permission",
            ]
            raise_exception = True

        request = self.factory.get("/rand")
        request.user = self.user
        with self.assertRaises(PermissionDenied):
            AView.as_view()(request)
