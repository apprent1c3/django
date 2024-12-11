from datetime import date

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.views import (
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode

from .client import PasswordResetConfirmClient
from .models import CustomUser


@override_settings(ROOT_URLCONF="auth_tests.urls")
class AuthTemplateTests(TestCase):
    request_factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class, including a test user and a request object.

         The test user is created with a username, email, and password, and then authenticated.
         A request object is created for a specific path and set to be made by the test user.

         The created user and request are stored as class attributes for use in subsequent tests.

         This method is intended to be used as a class-level setup method, running once before all tests in the class.

         :return: None
        """
        user = User.objects.create_user("jsmith", "jsmith@example.com", "pass")
        user = authenticate(username=user.username, password="pass")
        request = cls.request_factory.get("/somepath/")
        request.user = user
        cls.user, cls.request = user, request

    def test_password_reset_view(self):
        response = PasswordResetView.as_view(success_url="dummy/")(self.request)
        self.assertContains(
            response, "<title>Password reset | Django site admin</title>"
        )
        self.assertContains(response, "<h1>Password reset</h1>")

    def test_password_reset_done_view(self):
        response = PasswordResetDoneView.as_view()(self.request)
        self.assertContains(
            response, "<title>Password reset sent | Django site admin</title>"
        )
        self.assertContains(response, "<h1>Password reset sent</h1>")

    def test_password_reset_confirm_view_invalid_token(self):
        # PasswordResetConfirmView invalid token
        client = PasswordResetConfirmClient()
        url = reverse(
            "password_reset_confirm", kwargs={"uidb64": "Bad", "token": "Bad-Token"}
        )
        response = client.get(url)
        self.assertContains(
            response, "<title>Password reset unsuccessful | Django site admin</title>"
        )
        self.assertContains(response, "<h1>Password reset unsuccessful</h1>")

    def test_password_reset_confirm_view_valid_token(self):
        # PasswordResetConfirmView valid token
        """

        Tests the password reset confirm view with a valid token.

        This test case verifies that a user can successfully access the password reset confirm page
        using a valid token. It checks if the page title, heading, and username input field are correctly displayed.

        The test simulates a GET request to the password reset confirm URL with a valid token and
        uidb64 value, and then asserts that the expected HTML elements are present in the response.

        """
        client = PasswordResetConfirmClient()
        default_token_generator = PasswordResetTokenGenerator()
        token = default_token_generator.make_token(self.user)
        uidb64 = urlsafe_base64_encode(str(self.user.pk).encode())
        url = reverse(
            "password_reset_confirm", kwargs={"uidb64": uidb64, "token": token}
        )
        response = client.get(url)
        self.assertContains(
            response, "<title>Enter new password | Django site admin</title>"
        )
        self.assertContains(response, "<h1>Enter new password</h1>")
        # The username is added to the password reset confirmation form to help
        # browser's password managers.
        self.assertContains(
            response,
            '<input class="hidden" autocomplete="username" value="jsmith">',
        )

    @override_settings(AUTH_USER_MODEL="auth_tests.CustomUser")
    def test_password_reset_confirm_view_custom_username_hint(self):
        custom_user = CustomUser.custom_objects.create_user(
            email="joe@example.com",
            date_of_birth=date(1986, 11, 11),
            first_name="Joe",
        )
        client = PasswordResetConfirmClient()
        default_token_generator = PasswordResetTokenGenerator()
        token = default_token_generator.make_token(custom_user)
        uidb64 = urlsafe_base64_encode(str(custom_user.pk).encode())
        url = reverse(
            "password_reset_confirm", kwargs={"uidb64": uidb64, "token": token}
        )
        response = client.get(url)
        self.assertContains(
            response,
            "<title>Enter new password | Django site admin</title>",
        )
        self.assertContains(response, "<h1>Enter new password</h1>")
        # The username field is added to the password reset confirmation form
        # to help browser's password managers.
        self.assertContains(
            response,
            '<input class="hidden" autocomplete="username" value="joe@example.com">',
        )

    def test_password_reset_complete_view(self):
        response = PasswordResetCompleteView.as_view()(self.request)
        self.assertContains(
            response, "<title>Password reset complete | Django site admin</title>"
        )
        self.assertContains(response, "<h1>Password reset complete</h1>")

    def test_password_reset_change_view(self):
        response = PasswordChangeView.as_view(success_url="dummy/")(self.request)
        self.assertContains(
            response, "<title>Password change | Django site admin</title>"
        )
        self.assertContains(response, "<h1>Password change</h1>")

    def test_password_change_done_view(self):
        response = PasswordChangeDoneView.as_view()(self.request)
        self.assertContains(
            response, "<title>Password change successful | Django site admin</title>"
        )
        self.assertContains(response, "<h1>Password change successful</h1>")
