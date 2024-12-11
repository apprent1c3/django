from django.contrib import messages
from django.test import RequestFactory, SimpleTestCase

from .utils import DummyStorage


class ApiTests(SimpleTestCase):
    rf = RequestFactory()

    def setUp(self):
        """

        Initializes the test setup by creating a new test request and a dummy storage instance.

        This method is used to prepare the environment for subsequent tests, providing a clean request object and a storage instance for testing purposes.

        """
        self.request = self.rf.request()
        self.storage = DummyStorage()

    def test_ok(self):
        """

        Tests that a debug message can be successfully added to the request and stored.

        This test case verifies that the message is correctly added with the DEBUG level
        and that it can be retrieved from the storage, ensuring that the message content
        remains intact throughout the process.

        """
        msg = "some message"
        self.request._messages = self.storage
        messages.add_message(self.request, messages.DEBUG, msg)
        [message] = self.storage.store
        self.assertEqual(msg, message.message)

    def test_request_is_none(self):
        msg = "add_message() argument must be an HttpRequest object, not 'NoneType'."
        self.request._messages = self.storage
        with self.assertRaisesMessage(TypeError, msg):
            messages.add_message(None, messages.DEBUG, "some message")
        self.assertEqual(self.storage.store, [])

    def test_middleware_missing(self):
        """

        Tests that adding a message without installing the required middleware raises an exception.

        This test case verifies that the `messages.add_message` function correctly fails when
        django.contrib.messages.middleware.MessageMiddleware is not installed. It checks that a
        `messages.MessageFailure` exception is raised with a specific error message and that
        no messages are stored.

        """
        msg = (
            "You cannot add messages without installing "
            "django.contrib.messages.middleware.MessageMiddleware"
        )
        with self.assertRaisesMessage(messages.MessageFailure, msg):
            messages.add_message(self.request, messages.DEBUG, "some message")
        self.assertEqual(self.storage.store, [])

    def test_middleware_missing_silently(self):
        messages.add_message(
            self.request, messages.DEBUG, "some message", fail_silently=True
        )
        self.assertEqual(self.storage.store, [])


class CustomRequest:
    def __init__(self, request):
        self._request = request

    def __getattribute__(self, attr):
        try:
            return super().__getattribute__(attr)
        except AttributeError:
            return getattr(self._request, attr)


class CustomRequestApiTests(ApiTests):
    """
    add_message() should use ducktyping to allow request wrappers such as the
    one in Django REST framework.
    """

    def setUp(self):
        super().setUp()
        self.request = CustomRequest(self.request)
