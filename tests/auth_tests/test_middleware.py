from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.middleware import (
    AuthenticationMiddleware,
    LoginRequiredMiddleware,
)
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.test import TestCase, modify_settings, override_settings
from django.urls import reverse


class TestAuthenticationMiddleware(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "test_user", "test@example.com", "test_password"
        )

    def setUp(self):
        """
        Sets up the environment for testing authentication-related functionality.

        This method initializes the necessary objects for simulating an HTTP request, 
        including an instance of :class:`AuthenticationMiddleware`, a test client with 
        a logged-in user, and an :class:`HttpRequest` object with a session.

        It prepares the groundwork for testing scenarios that involve user authentication 
        and authorization, allowing for more focused and efficient testing of specific 
        components or features.

        Returns:
            None
        """
        self.middleware = AuthenticationMiddleware(lambda req: HttpResponse())
        self.client.force_login(self.user)
        self.request = HttpRequest()
        self.request.session = self.client.session

    def test_no_password_change_doesnt_invalidate_session(self):
        """

        Tests that a session remains valid when no password change occurs.

        Verifies that the user's session is not invalidated when their password is not changed,
        ensuring that they remain logged in and authenticated.

        """
        self.request.session = self.client.session
        self.middleware(self.request)
        self.assertIsNotNone(self.request.user)
        self.assertFalse(self.request.user.is_anonymous)

    def test_changed_password_invalidates_session(self):
        # After password change, user should be anonymous
        """
        Tests that changing a user's password invalidates their current session.

        This test verifies that after a user changes their password, their existing session
        is no longer valid. It checks that the user is treated as anonymous and that their
        session key is removed, effectively logging them out and requiring them to log in
        again with their new password.
        """
        self.user.set_password("new_password")
        self.user.save()
        self.middleware(self.request)
        self.assertIsNotNone(self.request.user)
        self.assertTrue(self.request.user.is_anonymous)
        # session should be flushed
        self.assertIsNone(self.request.session.session_key)

    def test_no_session(self):
        msg = (
            "The Django authentication middleware requires session middleware "
            "to be installed. Edit your MIDDLEWARE setting to insert "
            "'django.contrib.sessions.middleware.SessionMiddleware' before "
            "'django.contrib.auth.middleware.AuthenticationMiddleware'."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.middleware(HttpRequest())

    async def test_auser(self):
        """
        Tests the retrieval of the authenticated user (auser) from the request.

        Verifies that the auser object is correctly retrieved and cached, ensuring that
        subsequent requests for the auser return the same object instance.

        This test checks the following conditions:

        * The auser object is equal to the expected user object
        * The auser object is cached, and subsequent requests return the same instance
        """
        self.middleware(self.request)
        auser = await self.request.auser()
        self.assertEqual(auser, self.user)
        auser_second = await self.request.auser()
        self.assertIs(auser, auser_second)


@override_settings(ROOT_URLCONF="auth_tests.urls")
@modify_settings(
    MIDDLEWARE={"append": "django.contrib.auth.middleware.LoginRequiredMiddleware"}
)
class TestLoginRequiredMiddleware(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "test_user", "test@example.com", "test_password"
        )

    def setUp(self):
        """

        Sets up the test environment for LoginRequiredMiddleware tests.

        This method initializes the middleware instance and a mock HTTP request object,
        preparing the state for subsequent test cases to verify the behavior of the
        LoginRequiredMiddleware under various conditions.

        """
        self.middleware = LoginRequiredMiddleware(lambda req: HttpResponse())
        self.request = HttpRequest()

    def test_public_paths(self):
        """
        Tests that publicly accessible paths return a successful HTTP response.

        This test case verifies that the specified public paths can be accessed without any restrictions, 
        resulting in a HTTP status code of 200 (OK). The paths being tested are those that are intended to 
        be accessible by all users, regardless of their authentication status.
        """
        paths = ["public_view", "public_function_view"]
        for path in paths:
            response = self.client.get(f"/{path}/")
            self.assertEqual(response.status_code, 200)

    def test_protected_paths(self):
        """

        Test that protected paths redirect to the login page when accessed anonymously.

        Checks that accessing the listed protected paths without authentication
        results in a redirect to the login page with the original path as the next URL.

        """
        paths = ["protected_view", "protected_function_view"]
        for path in paths:
            response = self.client.get(f"/{path}/")
            self.assertRedirects(
                response,
                settings.LOGIN_URL + f"?next=/{path}/",
                fetch_redirect_response=False,
            )

    def test_login_required_paths(self):
        paths = ["login_required_cbv_view", "login_required_decorator_view"]
        for path in paths:
            response = self.client.get(f"/{path}/")
            self.assertRedirects(
                response,
                "/custom_login/" + f"?step=/{path}/",
                fetch_redirect_response=False,
            )

    def test_admin_path(self):
        admin_url = reverse("admin:index")
        response = self.client.get(admin_url)
        self.assertRedirects(
            response,
            reverse("admin:login") + f"?next={admin_url}",
            target_status_code=200,
        )

    def test_non_existent_path(self):
        response = self.client.get("/non_existent/")
        self.assertEqual(response.status_code, 404)

    def test_paths_with_logged_in_user(self):
        paths = [
            "public_view",
            "public_function_view",
            "protected_view",
            "protected_function_view",
            "login_required_cbv_view",
            "login_required_decorator_view",
        ]
        self.client.login(username="test_user", password="test_password")
        for path in paths:
            response = self.client.get(f"/{path}/")
            self.assertEqual(response.status_code, 200)

    def test_get_login_url_from_view_func(self):
        def view_func(request):
            """

            Tests retrieval of the login URL from the project settings.

            This test case ensures that the get_login_url method of the middleware correctly
            fetches the login URL defined in the project settings. The test overrides the
            LOGIN_URL setting to '/settings_login/' and verifies that the middleware returns
            this URL when requested.

            """
            return HttpResponse()

        view_func.login_url = "/custom_login/"
        login_url = self.middleware.get_login_url(view_func)
        self.assertEqual(login_url, "/custom_login/")

    @override_settings(LOGIN_URL="/settings_login/")
    def test_get_login_url_from_settings(self):
        login_url = self.middleware.get_login_url(lambda: None)
        self.assertEqual(login_url, "/settings_login/")

    @override_settings(LOGIN_URL=None)
    def test_get_login_url_no_login_url(self):
        with self.assertRaises(ImproperlyConfigured) as e:
            self.middleware.get_login_url(lambda: None)
        self.assertEqual(
            str(e.exception),
            "No login URL to redirect to. Define settings.LOGIN_URL or provide "
            "a login_url via the 'django.contrib.auth.decorators.login_required' "
            "decorator.",
        )

    def test_get_redirect_field_name_from_view_func(self):
        def view_func(request):
            return HttpResponse()

        view_func.redirect_field_name = "next_page"
        redirect_field_name = self.middleware.get_redirect_field_name(view_func)
        self.assertEqual(redirect_field_name, "next_page")

    @override_settings(
        MIDDLEWARE=[
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "auth_tests.test_checks.LoginRequiredMiddlewareSubclass",
        ],
        LOGIN_URL="/settings_login/",
    )
    def test_login_url_resolve_logic(self):
        """

        Tests the logic for resolving login URLs when accessing protected views.

        This test case covers two main scenarios: views that are decorated with a login
        required decorator and views that are protected by a login required mixin.

        It verifies that when an unauthenticated user attempts to access a protected view,
        they are redirected to the login page with the correct redirect URL.
        The redirect URL is determined by the specific middleware and decorator or mixin
        used to protect the view.

        Two types of login URLs are tested: a custom login URL and the default login URL
        defined in the settings. The test ensures that the correct login URL is used
        for each type of protected view.

        """
        paths = ["login_required_cbv_view", "login_required_decorator_view"]
        for path in paths:
            response = self.client.get(f"/{path}/")
            self.assertRedirects(
                response,
                "/custom_login/" + f"?step=/{path}/",
                fetch_redirect_response=False,
            )
        paths = ["protected_view", "protected_function_view"]
        for path in paths:
            response = self.client.get(f"/{path}/")
            self.assertRedirects(
                response,
                f"/settings_login/?redirect_to=/{path}/",
                fetch_redirect_response=False,
            )

    def test_get_redirect_field_name_default(self):
        redirect_field_name = self.middleware.get_redirect_field_name(lambda: None)
        self.assertEqual(redirect_field_name, REDIRECT_FIELD_NAME)
