from django.contrib import messages
from django.test import RequestFactory, SimpleTestCase

from .utils import DummyStorage


class ApiTests(SimpleTestCase):
    rf = RequestFactory()

    def setUp(self):
        self.request = self.rf.request()
        self.storage = DummyStorage()

    def test_ok(self):
        """

        Tests that a debug message is correctly added to the request.

        This test case verifies that the messages framework is functioning as expected by
        adding a message with the debug level and checking that it is stored in the
        request's message queue.

        The test confirms that the message is successfully added by comparing the
        original message with the one retrieved from the storage, ensuring that they
        match.

        """
        msg = "some message"
        self.request._messages = self.storage
        messages.add_message(self.request, messages.DEBUG, msg)
        [message] = self.storage.store
        self.assertEqual(msg, message.message)

    def test_request_is_none(self):
        """
        Test that :func:`~django.contrib.messages.add_message` function raises an error when request object is None.

        It checks that when the :func:`~django.contrib.messages.add_message` function is called with a request argument of None, 
        it raises a :class:`~TypeError` with a message indicating that the argument must be an HttpRequest object. 
        Additionally, it verifies that no message is added to the storage as a result of this operation.
        """
        msg = "add_message() argument must be an HttpRequest object, not 'NoneType'."
        self.request._messages = self.storage
        with self.assertRaisesMessage(TypeError, msg):
            messages.add_message(None, messages.DEBUG, "some message")
        self.assertEqual(self.storage.store, [])

    def test_middleware_missing(self):
        """

        Test the case where the MessageMiddleware is missing from the django middleware.

        This test checks that attempting to add a message without the proper middleware
        installed raises a MessageFailure exception with a descriptive error message.
        Additionally, it verifies that no messages are stored when this exception occurs.

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
        """
        Overrides default attribute access to enable proxying of attributes to the underlying request object.

        If the attribute is found on the current object, it is returned directly. Otherwise, an attempt is made to retrieve the attribute from the request object associated with this instance.

        This allows for convenient access to request attributes without having to explicitly access the request object.
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

        Setup method to initialize the test environment.

        This method is called before each test to set up any necessary state. It 
        insures that the request object is properly wrapped in a CustomRequest 
        object, providing any additional functionality required for testing.

        """
        super().setUp()
        self.request = CustomRequest(self.request)
