from django.contrib.auth import (
    aauthenticate,
    aget_user,
    alogin,
    alogout,
    aupdate_session_auth_hash,
)
from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpRequest
from django.test import TestCase, override_settings


class AsyncAuthTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.test_user = User.objects.create_user(
            "testuser", "test@example.com", "testpw"
        )

    async def test_aauthenticate(self):
        """
        Tests the asynchronous authentication function to verify it correctly authenticates users and handles inactive accounts.
        """
        user = await aauthenticate(username="testuser", password="testpw")
        self.assertIsInstance(user, User)
        self.assertEqual(user.username, self.test_user.username)
        user.is_active = False
        await user.asave()
        self.assertIsNone(await aauthenticate(username="testuser", password="testpw"))

    async def test_alogin(self):
        """
        Verifies the asynchronous login functionality by simulating a login request and checking if the logged-in user is correctly retrieved and matches the expected user.
        """
        request = HttpRequest()
        request.session = await self.client.asession()
        await alogin(request, self.test_user)
        user = await aget_user(request)
        self.assertIsInstance(user, User)
        self.assertEqual(user.username, self.test_user.username)

    async def test_alogin_without_user(self):
        """
        Tests if the asynchronous login function can successfully authenticate a user with the provided request. Verifies that the user returned by the authentication function matches the expected user.
        """
        request = HttpRequest()
        request.user = self.test_user
        request.session = await self.client.asession()
        await alogin(request, None)
        user = await aget_user(request)
        self.assertIsInstance(user, User)
        self.assertEqual(user.username, self.test_user.username)

    async def test_alogout(self):
        """
        Tests the asynchronous logout functionality to ensure a user is returned as anonymous after logging out.
        """
        await self.client.alogin(username="testuser", password="testpw")
        request = HttpRequest()
        request.session = await self.client.asession()
        await alogout(request)
        user = await aget_user(request)
        self.assertIsInstance(user, AnonymousUser)

    async def test_client_alogout(self):
        """

        Tests that a client's logout functionality correctly resets their session to an anonymous user.

        """
        await self.client.alogin(username="testuser", password="testpw")
        request = HttpRequest()
        request.session = await self.client.asession()
        await self.client.alogout()
        user = await aget_user(request)
        self.assertIsInstance(user, AnonymousUser)

    async def test_change_password(self):
        """
        Tests the password change functionality by simulating a login and verifying the user's authentication session.
        """
        await self.client.alogin(username="testuser", password="testpw")
        request = HttpRequest()
        request.session = await self.client.asession()
        request.user = self.test_user
        await aupdate_session_auth_hash(request, self.test_user)
        user = await aget_user(request)
        self.assertIsInstance(user, User)

    async def test_invalid_login(self):
        self.assertEqual(
            await self.client.alogin(username="testuser", password=""), False
        )

    async def test_client_aforce_login(self):
        """
        Tests that aforce_login sets the user correctly in the session.\"\"\"

         \"\"\"Verifies that after forcing a login using the test user, 
            the user is correctly retrieved from the request session.
        """
        await self.client.aforce_login(self.test_user)
        request = HttpRequest()
        request.session = await self.client.asession()
        user = await aget_user(request)
        self.assertEqual(user.username, self.test_user.username)

    @override_settings(
        AUTHENTICATION_BACKENDS=[
            "django.contrib.auth.backends.ModelBackend",
            "django.contrib.auth.backends.AllowAllUsersModelBackend",
        ]
    )
    async def test_client_aforce_login_backend(self):
        """
        Tests aforce_login functionality with AllowAllUsersModelBackend, verifying that an inactive user can be logged in successfully using this backend.
        """
        self.test_user.is_active = False
        await self.test_user.asave()
        await self.client.aforce_login(
            self.test_user,
            backend="django.contrib.auth.backends.AllowAllUsersModelBackend",
        )
        request = HttpRequest()
        request.session = await self.client.asession()
        user = await aget_user(request)
        self.assertEqual(user.username, self.test_user.username)
