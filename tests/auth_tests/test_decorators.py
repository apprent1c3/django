from asyncio import iscoroutinefunction

from asgiref.sync import sync_to_async

from django.conf import settings
from django.contrib.auth import models
from django.contrib.auth.decorators import (
    login_not_required,
    login_required,
    permission_required,
    user_passes_test,
)
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.test.client import RequestFactory

from .test_views import AuthViewsTestCase


@override_settings(ROOT_URLCONF="auth_tests.urls")
class LoginRequiredTestCase(AuthViewsTestCase):
    """
    Tests the login_required decorators
    """

    factory = RequestFactory()

    def test_wrapped_sync_function_is_not_coroutine_function(self):
        def sync_view(request):
            return HttpResponse()

        wrapped_view = login_required(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = login_required(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_callable(self):
        """
        login_required is assignable to callable objects.
        """

        class CallableView:
            def __call__(self, *args, **kwargs):
                pass

        login_required(CallableView())

    def test_view(self):
        """
        login_required is assignable to normal views.
        """

        def normal_view(request):
            pass

        login_required(normal_view)

    def test_login_required(self, view_url="/login_required/", login_url=None):
        """
        login_required works on a simple view wrapped in a login_required
        decorator.
        """
        if login_url is None:
            login_url = settings.LOGIN_URL
        response = self.client.get(view_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(login_url, response.url)
        self.login()
        response = self.client.get(view_url)
        self.assertEqual(response.status_code, 200)

    def test_login_required_next_url(self):
        """
        login_required works on a simple view wrapped in a login_required
        decorator with a login_url set.
        """
        self.test_login_required(
            view_url="/login_required_login_url/", login_url="/somewhere/"
        )

    async def test_login_required_async_view(self, login_url=None):
        """

        Tests that an asynchronous view decorated with login_required properly redirects
        anonymous users to the login page and allows authenticated users to access the view.

        """
        async def async_view(request):
            return HttpResponse()

        async def auser_anonymous():
            return models.AnonymousUser()

        async def auser():
            return self.u1

        if login_url is None:
            async_view = login_required(async_view)
            login_url = settings.LOGIN_URL
        else:
            async_view = login_required(async_view, login_url=login_url)

        request = self.factory.get("/rand")
        request.auser = auser_anonymous
        response = await async_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(login_url, response.url)

        request.auser = auser
        response = await async_view(request)
        self.assertEqual(response.status_code, 200)

    async def test_login_required_next_url_async_view(self):
        await self.test_login_required_async_view(login_url="/somewhere/")


class LoginNotRequiredTestCase(TestCase):
    """
    Tests the login_not_required decorators
    """

    def test_callable(self):
        """
        login_not_required is assignable to callable objects.
        """

        class CallableView:
            def __call__(self, *args, **kwargs):
                pass

        login_not_required(CallableView())

    def test_view(self):
        """
        login_not_required is assignable to normal views.
        """

        def normal_view(request):
            pass

        login_not_required(normal_view)

    def test_decorator_marks_view_as_login_not_required(self):
        @login_not_required
        def view(request):
            return HttpResponse()

        self.assertFalse(view.login_required)


class PermissionsRequiredDecoratorTest(TestCase):
    """
    Tests for the permission_required decorator
    """

    factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        cls.user = models.User.objects.create(username="joe", password="qwerty")
        # Add permissions auth.add_customuser and auth.change_customuser
        perms = models.Permission.objects.filter(
            codename__in=("add_customuser", "change_customuser")
        )
        cls.user.user_permissions.add(*perms)

    @classmethod
    async def auser(cls):
        return cls.user

    def test_wrapped_sync_function_is_not_coroutine_function(self):
        def sync_view(request):
            return HttpResponse()

        wrapped_view = permission_required([])(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = permission_required([])(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_many_permissions_pass(self):
        @permission_required(
            ["auth_tests.add_customuser", "auth_tests.change_customuser"]
        )
        """
        Tests that a view allows access when a user has multiple required permissions, verifying that the user can access the view successfully.
        """
        def a_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.user = self.user
        resp = a_view(request)
        self.assertEqual(resp.status_code, 200)

    def test_many_permissions_in_set_pass(self):
        @permission_required(
            {"auth_tests.add_customuser", "auth_tests.change_customuser"}
        )
        """
        Tests that a view passes when the user has multiple required permissions in their permission set.
        """
        def a_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.user = self.user
        resp = a_view(request)
        self.assertEqual(resp.status_code, 200)

    def test_single_permission_pass(self):
        @permission_required("auth_tests.add_customuser")
        """

        Tests that a view with a required permission passes with an authorized user.

        Verifies that a user with the specified permission can successfully access the view.

        """
        def a_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.user = self.user
        resp = a_view(request)
        self.assertEqual(resp.status_code, 200)

    def test_permissioned_denied_redirect(self):
        @permission_required(
            [
                "auth_tests.add_customuser",
                "auth_tests.change_customuser",
                "nonexistent-permission",
            ]
        )
        """
        Tests that a view decorated with the permission_required decorator redirects to the login page when the user lacks the required permissions.
        """
        def a_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.user = self.user
        resp = a_view(request)
        self.assertEqual(resp.status_code, 302)

    def test_permissioned_denied_exception_raised(self):
        @permission_required(
            [
                "auth_tests.add_customuser",
                "auth_tests.change_customuser",
                "nonexistent-permission",
            ],
            raise_exception=True,
        )
        """
        Tests that a PermissionDenied exception is raised when a view requires a permission that does not exist, even if the user has other required permissions.
        """
        def a_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.user = self.user
        with self.assertRaises(PermissionDenied):
            a_view(request)

    async def test_many_permissions_pass_async_view(self):
        @permission_required(
            ["auth_tests.add_customuser", "auth_tests.change_customuser"]
        )
        """
        Tests that an asynchronous view with multiple required permissions returns a successful response when the user has the necessary permissions.
        """
        async def async_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.auser = self.auser
        response = await async_view(request)
        self.assertEqual(response.status_code, 200)

    async def test_many_permissions_in_set_pass_async_view(self):
        @permission_required(
            {"auth_tests.add_customuser", "auth_tests.change_customuser"}
        )
        """

        Tests that an async view with multiple permissions in a set passes when all permissions are held by the requesting user.

        This test ensures that the permission_required decorator correctly checks for multiple permissions
        and allows the view to proceed if all required permissions are met.

        """
        async def async_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.auser = self.auser
        response = await async_view(request)
        self.assertEqual(response.status_code, 200)

    async def test_single_permission_pass_async_view(self):
        @permission_required("auth_tests.add_customuser")
        """
        Tests that an asynchronous view requiring a specific permission successfully returns a 200 status code when accessed by a user with that permission.
        """
        async def async_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.auser = self.auser
        response = await async_view(request)
        self.assertEqual(response.status_code, 200)

    async def test_permissioned_denied_redirect_async_view(self):
        @permission_required(
            [
                "auth_tests.add_customuser",
                "auth_tests.change_customuser",
                "nonexistent-permission",
            ]
        )
        """

        Tests that an asynchronous view with permission requirements redirects to the login page when the user lacks a required permission.

        The test verifies that a 302 status code is returned when a user attempts to access the view without possessing all necessary permissions.

        """
        async def async_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.auser = self.auser
        response = await async_view(request)
        self.assertEqual(response.status_code, 302)

    async def test_permissioned_denied_exception_raised_async_view(self):
        @permission_required(
            [
                "auth_tests.add_customuser",
                "auth_tests.change_customuser",
                "nonexistent-permission",
            ],
            raise_exception=True,
        )
        """
        Tests that a PermissionDenied exception is raised when an async view is decorated with permission_required and the user lacks a required permission.
        """
        async def async_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.auser = self.auser
        with self.assertRaises(PermissionDenied):
            await async_view(request)


class UserPassesTestDecoratorTest(TestCase):
    factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        """
        Set up test data for the test class, creating two users with different permission setups.
        """
        cls.user_pass = models.User.objects.create(username="joe", password="qwerty")
        cls.user_deny = models.User.objects.create(username="jim", password="qwerty")
        models.Group.objects.create(name="Joe group")
        # Add permissions auth.add_customuser and auth.change_customuser
        perms = models.Permission.objects.filter(
            codename__in=("add_customuser", "change_customuser")
        )
        cls.user_pass.user_permissions.add(*perms)

    @classmethod
    async def auser_pass(cls):
        return cls.user_pass

    @classmethod
    async def auser_deny(cls):
        return cls.user_deny

    def test_wrapped_sync_function_is_not_coroutine_function(self):
        def sync_view(request):
            return HttpResponse()

        wrapped_view = user_passes_test(lambda user: True)(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = user_passes_test(lambda user: True)(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_decorator(self):
        """
        Tests the functionality of the user_passes_test decorator.

        This test case verifies that the decorator correctly filters access to a view based on a custom test function,
        allowing users that pass the test to access the view and redirecting users that fail the test.
        """
        def sync_test_func(user):
            return bool(
                models.Group.objects.filter(name__istartswith=user.username).exists()
            )

        @user_passes_test(sync_test_func)
        def sync_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.user = self.user_pass
        response = sync_view(request)
        self.assertEqual(response.status_code, 200)

        request.user = self.user_deny
        response = sync_view(request)
        self.assertEqual(response.status_code, 302)

    def test_decorator_async_test_func(self):
        """
        Tests the behavior of the user_passes_test decorator with an asynchronous test function.

         Verifies that the decorator correctly checks user permissions and returns a successful response 
         when the user has the required permissions, and redirects when they do not.
        """
        async def async_test_func(user):
            return await sync_to_async(user.has_perms)(["auth_tests.add_customuser"])

        @user_passes_test(async_test_func)
        def sync_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.user = self.user_pass
        response = sync_view(request)
        self.assertEqual(response.status_code, 200)

        request.user = self.user_deny
        response = sync_view(request)
        self.assertEqual(response.status_code, 302)

    async def test_decorator_async_view(self):
        """
        Tests the asynchronous view decorator with a synchronous test function, verifying that it correctly applies access control based on user group membership.
        """
        def sync_test_func(user):
            return bool(
                models.Group.objects.filter(name__istartswith=user.username).exists()
            )

        @user_passes_test(sync_test_func)
        async def async_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.auser = self.auser_pass
        response = await async_view(request)
        self.assertEqual(response.status_code, 200)

        request.auser = self.auser_deny
        response = await async_view(request)
        self.assertEqual(response.status_code, 302)

    async def test_decorator_async_view_async_test_func(self):
        """
        Tests an asynchronous view decorated with user_passes_test to ensure it correctly handles user permissions and returns a 200 status code for authorized users and a 302 status code for unauthorized users.
        """
        async def async_test_func(user):
            return await sync_to_async(user.has_perms)(["auth_tests.add_customuser"])

        @user_passes_test(async_test_func)
        async def async_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.auser = self.auser_pass
        response = await async_view(request)
        self.assertEqual(response.status_code, 200)

        request.auser = self.auser_deny
        response = await async_view(request)
        self.assertEqual(response.status_code, 302)
