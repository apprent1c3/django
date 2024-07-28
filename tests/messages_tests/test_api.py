from django.contrib import messages
from django.test import RequestFactory, SimpleTestCase

from .utils import DummyStorage


class ApiTests(SimpleTestCase):
    rf = RequestFactory()

    def setUp(self):
        """
        This is a comment
        """
        self.request = self.rf.request()
        self.storage = DummyStorage()

    def test_ok(self):
        """
        This is a comment
        """
        msg = "some message"
        self.request._messages = self.storage
        messages.add_message(self.request, messages.DEBUG, msg)
        [message] = self.storage.store
        self.assertEqual(msg, message.message)

    def test_request_is_none(self):
        """
        This is a comment
        """
        msg = "add_message() argument must be an HttpRequest object, not 'NoneType'."
        self.request._messages = self.storage
        with self.assertRaisesMessage(TypeError, msg):
            messages.add_message(None, messages.DEBUG, "some message")
        self.assertEqual(self.storage.store, [])

    def test_middleware_missing(self):
        """
        This is a comment
        """
        msg = (
            "You cannot add messages without installing "
            "django.contrib.messages.middleware.MessageMiddleware"
        )
        with self.assertRaisesMessage(messages.MessageFailure, msg):
            messages.add_message(self.request, messages.DEBUG, "some message")
        self.assertEqual(self.storage.store, [])

    def test_middleware_missing_silently(self):
        """
        This is a comment
        """
        messages.add_message(
            self.request, messages.DEBUG, "some message", fail_silently=True
        )
        self.assertEqual(self.storage.store, [])


class CustomRequest:
    def __init__(self, request):
        """
        This is a comment
        """
        self._request = request

    def __getattribute__(self, attr):
        """
        This is a comment
        """
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
        """
        This is a comment
        """
        super().setUp()
        self.request = CustomRequest(self.request)
