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
        """
        Tests that a synchronous function wrapped with the login_required decorator is not converted into a coroutine function. 

        This checks that the decorator preserves the original function's nature, ensuring it remains suitable for handling synchronous requests. The test verifies that the wrapped function can still be used in synchronous contexts, without being mistakenly treated as an asynchronous coroutine.
        """
        def sync_view(request):
            return HttpResponse()

        wrapped_view = login_required(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        """
        Tests that an asynchronous view function wrapped with login_required remains a coroutine function.

        This ensures that the decorator does not alter the asynchronous nature of the view function, 
        allowing it to be properly handled by asynchronous frameworks and libraries.
        """
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

        Tests an asynchronous view decorated with login_required to ensure it redirects anonymous users to the login page and allows authenticated users to access the view.

        The test creates an asynchronous view, decorates it with login_required, and then tests the view with both an anonymous user and an authenticated user. It verifies that the anonymous user is redirected to the login page and that the authenticated user can access the view.

        :param login_url: The URL to redirect anonymous users to. If not provided, the default LOGIN_URL from the project settings is used.

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
        """

        Tests if a synchronous function remains non-coroutine after being wrapped with permission checks.

        Verifies that applying permission checks to a synchronous view function does not transform it into a coroutine function,
        ensuring its execution characteristics remain unchanged. This is crucial for maintaining the original behavior and performance
        of the wrapped function in a synchronous context.

        """
        def sync_view(request):
            return HttpResponse()

        wrapped_view = permission_required([])(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        """
        Tests that a wrapped asynchronous function remains a coroutine function.

        This test case verifies that when an asynchronous view function is wrapped with 
        a permission_required decorator, the resulting wrapped view function still 
        behaves as a coroutine function. This is crucial to ensure that the 
        asynchronous functionality of the original view is preserved after 
        applying the decorator.

        The test checks the wrapped view function using the iscoroutinefunction 
        utility, confirming that it returns True and thus validating the 
        coroutine nature of the wrapped function.
        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = permission_required([])(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_many_permissions_pass(self):
        @permission_required(
            ["auth_tests.add_customuser", "auth_tests.change_customuser"]
        )
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
        def a_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.user = self.user
        resp = a_view(request)
        self.assertEqual(resp.status_code, 200)

    def test_single_permission_pass(self):
        @permission_required("auth_tests.add_customuser")
        """

        Tests that a view decorated with the permission_required decorator allows a request to pass 
        when the user has the required permission.

        This test case checks if a user with the necessary permission can access a view 
        without being redirected or blocked, resulting in a successful HTTP response.

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

        Tests multiple permission checks for an asynchronous view.

        This test case checks that a user with multiple required permissions can access an asynchronous view.
        The test verifies that the view returns a successful HTTP response (200 status code) when the user has all the necessary permissions.

        The required permissions for this test are:
        - 'auth_tests.add_customuser'
        - 'auth_tests.change_customuser'

        The test covers a typical use case where a user needs to perform multiple actions that require different permissions.

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
        async def async_view(request):
            return HttpResponse()

        request = self.factory.get("/rand")
        request.auser = self.auser
        response = await async_view(request)
        self.assertEqual(response.status_code, 200)

    async def test_single_permission_pass_async_view(self):
        @permission_required("auth_tests.add_customuser")
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

        Tests the behavior of an async view decorated with permission_required when the user lacks a required permission.

        This test case verifies that when an async view is protected by multiple permissions, 
        including a non-existent one, and the user does not have all the required permissions, 
        the view correctly redirects the user with a 302 status code, indicating a redirect response.

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

        Tests that a PermissionDenied exception is raised when an asynchronous view 
        decorated with permission_required is accessed by a user lacking the required 
        permissions.

        The test scenario involves an asynchronous view that requires a set of specific 
        permissions, including a nonexistent permission, to be executed. It verifies 
        that attempting to access this view with a user that does not possess all the 
        necessary permissions results in a PermissionDenied exception being raised.

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
        """
        Tests that a synchronous function wrapped by the user_passes_test decorator remains a synchronous function.

        This test case verifies that the decorator does not convert a synchronous view function into a coroutine function, 
        even after applying the user authentication check. The decorated view should still behave as a regular synchronous function.

        """
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

        Tests the functionality of the user_passes_test decorator when applied to an asynchronous view.

        The test case defines a synchronous test function that checks if a user has a group name starting with their username.
        This function is then used as the test function for the user_passes_test decorator, which is applied to an asynchronous view.

        The test verifies that the decorator correctly allows or denies access to the view based on the test function's result,
        returning a 200 status code for allowed users and a 302 status code for denied users.

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

        Tests the functionality of the user_passes_test decorator when used with an asynchronous view function.

        This test case verifies that the decorator correctly handles asynchronous permission checks.
        It checks that authorized users are granted access to the view, while unauthorized users are redirected.

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
