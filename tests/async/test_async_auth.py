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

        Tests the asynchronous authentication function.

        This test case verifies that a user can be successfully authenticated with a valid username and password,
        and that the returned user object is of the correct type and has the expected properties.
        Additionally, it checks that authentication fails when the user account is inactive.

        The test covers the following scenarios:
        - Successful authentication with valid credentials
        - Authentication failure due to inactive user account

        """
        user = await aauthenticate(username="testuser", password="testpw")
        self.assertIsInstance(user, User)
        self.assertEqual(user.username, self.test_user.username)
        user.is_active = False
        await user.asave()
        self.assertIsNone(await aauthenticate(username="testuser", password="testpw"))

    async def test_alogin(self):
        """

        Tests asynchronous login functionality.

        This test case simulates a user login by creating an HTTP request, initializing a session,
        performing an asynchronous login, and then verifying that the logged-in user is correctly
        retrieved from the request. It checks if the retrieved user is an instance of the User class
        and if the username matches the one used for login.

        """
        request = HttpRequest()
        request.session = await self.client.asession()
        await alogin(request, self.test_user)
        user = await aget_user(request)
        self.assertIsInstance(user, User)
        self.assertEqual(user.username, self.test_user.username)

    async def test_alogin_without_user(self):
        request = HttpRequest()
        request.user = self.test_user
        request.session = await self.client.asession()
        await alogin(request, None)
        user = await aget_user(request)
        self.assertIsInstance(user, User)
        self.assertEqual(user.username, self.test_user.username)

    async def test_alogout(self):
        """

        Tests the asynchronous logout functionality.

        This test verifies that after a successful asynchronous login, the user can be logged out
        and their session is properly terminated. It checks that after logout, the user is 
        identified as an anonymous user, confirming a successful logout.

        """
        await self.client.alogin(username="testuser", password="testpw")
        request = HttpRequest()
        request.session = await self.client.asession()
        await alogout(request)
        user = await aget_user(request)
        self.assertIsInstance(user, AnonymousUser)

    async def test_client_alogout(self):
        await self.client.alogin(username="testuser", password="testpw")
        request = HttpRequest()
        request.session = await self.client.asession()
        await self.client.alogout()
        user = await aget_user(request)
        self.assertIsInstance(user, AnonymousUser)

    async def test_change_password(self):
        """

        Test the password change functionality for a user.

        This test case authenticates a user, retrieves their session, and verifies their 
        identity after a successful login. It checks the type of the retrieved user 
        object to ensure it is an instance of the User class.

        The test involves authenticating with a predefined test username and password, 
        then updating the session authentication hash. The test concludes by asserting 
        that the retrieved user object matches the expected User type.

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

        Tests the aforce_login functionality of the client by simulating a login 
        with a test user and verifying the user's identity in the resulting session.

        This test case ensures that the aforce_login method correctly sets up the 
        session with the specified user's credentials, allowing for proper user 
        identification and authentication in subsequent requests.

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
