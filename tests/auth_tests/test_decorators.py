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
        Verifies that the login_required decorator can be assigned to callable objects, ensuring compatibility with various types of callable instances.
        """

        class CallableView:
            def __call__(self, *args, **kwargs):
                pass

        login_required(CallableView())

    def test_view(self):
        """
        Tests if the login_required decorator can be successfully applied to a normal view function.
        """

        def normal_view(request):
            pass

        login_required(normal_view)

    def test_login_required(self, view_url="/login_required/", login_url=None):
        """
        Tests that a view wrapped in a login_required decorator redirects unauthenticated users to the login page and allows access after successful login.
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
        Tests that an async view decorated with login_required redirects 
        anonymous users to the login URL and allows authenticated users to access the view.
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
        Tests that the login_not_required decorator can be assigned to callable objects.
        """

        class CallableView:
            def __call__(self, *args, **kwargs):
                pass

        login_not_required(CallableView())

    def test_view(self):
        """
        Tests if the login_not_required decorator can be applied to a normal view function.
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
        Tests that a view requires and checks multiple permissions successfully, allowing access when the user has all required permissions.
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
        Tests that multiple permissions in a set are handled correctly.

        Verifies that a view requiring multiple permissions returns a successful response when the user has the required permissions.
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
        Tests that a view decorated with permission_required allows access when the user has the required permission.
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
        Tests that a view with a permission required decorator redirects to the login page when the user lacks the required permissions.
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
        Test that a PermissionDenied exception is raised when a view requires a permission that does not exist.
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
        Tests that an asynchronous view requiring multiple permissions returns a successful response when the user has all required permissions.
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
        Tests that an asynchronous view with multiple required permissions in a set allows access when all permissions are present.
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
        Tests that an asynchronous view with a required permission returns a successful response when the user has the necessary permission.
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

        Tests that an async view decorated with permission_required returns a 302 redirect when the user lacks the required permissions.

        The test simulates a GET request to a view that requires multiple permissions, including a non-existent one, to verify that the permission check fails and a redirect is issued.

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

        Tests that a PermissionDenied exception is raised when an async view requires permissions that the user does not have.

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
        Sets up test data for the test class, creating users with specific permissions and a group, to facilitate testing of user authentication and authorization scenarios.
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

        Verifies that the decorator correctly grants or denies access to a view
        based on the result of a test function, in this case a check for group
        membership.

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
        Tests that the user_passes_test decorator works with asynchronous test functions.

        Verifies that the decorator correctly checks for user permissions and returns a 
        200 status code for users with the required permissions and a 302 status code 
        for users without the required permissions.
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

        Tests the usage of the user_passes_test decorator with an asynchronous view.
        Verifies that the decorator correctly filters access based on the provided test function.

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
        Tests the async view decorator with an async test function.

        Verifies that the decorator correctly applies permission checks to async views,
        redirecting users without required permissions and allowing access to those with permissions.
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
