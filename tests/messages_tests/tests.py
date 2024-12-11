import importlib
import sys
from unittest import mock

from django.conf import settings
from django.contrib.messages import Message, add_message, constants
from django.contrib.messages.storage import base
from django.contrib.messages.test import MessagesTestMixin
from django.test import RequestFactory, SimpleTestCase, override_settings

from .utils import DummyStorage


class MessageTests(SimpleTestCase):
    def test_eq(self):
        """
        Tests the equality of Message objects based on their attributes.

        This test case checks the following scenarios:

        *Equality of a Message object with itself
        *Equality of a Message object with any other object (using mock.ANY)
        *Inequality of Message objects with different messages but the same level
        *Inequality of Message objects with the same message but different levels
        *Inequality of Message objects with different messages and levels

        The purpose of this test is to ensure that the equality operator for Message objects behaves as expected and distinguishes between objects based on their attributes.
        """
        msg_1 = Message(constants.INFO, "Test message 1")
        msg_2 = Message(constants.INFO, "Test message 2")
        msg_3 = Message(constants.WARNING, "Test message 1")
        self.assertEqual(msg_1, msg_1)
        self.assertEqual(msg_1, mock.ANY)
        self.assertNotEqual(msg_1, msg_2)
        self.assertNotEqual(msg_1, msg_3)
        self.assertNotEqual(msg_2, msg_3)

    @override_settings(
        MESSAGE_TAGS={
            constants.WARNING: "caution",
            constants.ERROR: "",
            12: "custom",
        }
    )
    def test_repr(self):
        tests = [
            (constants.INFO, "thing", "", "Message(level=20, message='thing')"),
            (
                constants.WARNING,
                "careful",
                "tag1 tag2",
                "Message(level=30, message='careful', extra_tags='tag1 tag2')",
            ),
            (
                constants.ERROR,
                "oops",
                "tag",
                "Message(level=40, message='oops', extra_tags='tag')",
            ),
            (12, "custom", "", "Message(level=12, message='custom')"),
        ]
        for level, message, extra_tags, expected in tests:
            with self.subTest(level=level, message=message):
                msg = Message(level, message, extra_tags=extra_tags)
                self.assertEqual(repr(msg), expected)


class TestLevelTags(SimpleTestCase):
    message_tags = {
        constants.INFO: "info",
        constants.DEBUG: "",
        constants.WARNING: "",
        constants.ERROR: "bad",
        constants.SUCCESS: "",
        12: "custom",
    }

    @override_settings(MESSAGE_TAGS=message_tags)
    def test_override_settings_level_tags(self):
        self.assertEqual(base.LEVEL_TAGS, self.message_tags)

    def test_lazy(self):
        storage_base_import_path = "django.contrib.messages.storage.base"
        in_use_base = sys.modules.pop(storage_base_import_path)
        self.addCleanup(sys.modules.__setitem__, storage_base_import_path, in_use_base)
        # Don't use @override_settings to avoid calling the setting_changed
        # signal, but ensure that base.LEVEL_TAGS hasn't been read yet (this
        # means that we need to ensure the `base` module is freshly imported).
        base = importlib.import_module(storage_base_import_path)
        old_message_tags = getattr(settings, "MESSAGE_TAGS", None)
        settings.MESSAGE_TAGS = {constants.ERROR: "bad"}
        try:
            self.assertEqual(base.LEVEL_TAGS[constants.ERROR], "bad")
        finally:
            if old_message_tags is None:
                del settings.MESSAGE_TAGS
            else:
                settings.MESSAGE_TAGS = old_message_tags

    @override_settings(MESSAGE_TAGS=message_tags)
    def test_override_settings_lazy(self):
        # The update_level_tags handler has been called at least once before
        # running this code when using @override_settings.
        """

        Tests the override_settings decorator's ability to lazily apply changed settings.

        This test verifies that changes made to a setting within a test case are properly
        reflected in other parts of the system that rely on that setting, ensuring that
        the override_settings decorator works as intended in a dynamic environment.

        :raises AssertionError: if the setting override is not successfully applied.

        """
        settings.MESSAGE_TAGS = {constants.ERROR: "very-bad"}
        self.assertEqual(base.LEVEL_TAGS[constants.ERROR], "very-bad")


class FakeResponse:
    def __init__(self):
        request = RequestFactory().get("/")
        request._messages = DummyStorage()
        self.wsgi_request = request


class AssertMessagesTest(MessagesTestMixin, SimpleTestCase):
    def test_assertion(self):
        response = FakeResponse()
        add_message(response.wsgi_request, constants.DEBUG, "DEBUG message.")
        add_message(response.wsgi_request, constants.INFO, "INFO message.")
        add_message(response.wsgi_request, constants.SUCCESS, "SUCCESS message.")
        add_message(response.wsgi_request, constants.WARNING, "WARNING message.")
        add_message(response.wsgi_request, constants.ERROR, "ERROR message.")
        self.assertMessages(
            response,
            [
                Message(constants.DEBUG, "DEBUG message."),
                Message(constants.INFO, "INFO message."),
                Message(constants.SUCCESS, "SUCCESS message."),
                Message(constants.WARNING, "WARNING message."),
                Message(constants.ERROR, "ERROR message."),
            ],
        )

    def test_with_tags(self):
        response = FakeResponse()
        add_message(
            response.wsgi_request,
            constants.INFO,
            "INFO message.",
            extra_tags="extra-info",
        )
        add_message(
            response.wsgi_request,
            constants.SUCCESS,
            "SUCCESS message.",
            extra_tags="extra-success",
        )
        add_message(
            response.wsgi_request,
            constants.WARNING,
            "WARNING message.",
            extra_tags="extra-warning",
        )
        add_message(
            response.wsgi_request,
            constants.ERROR,
            "ERROR message.",
            extra_tags="extra-error",
        )
        self.assertMessages(
            response,
            [
                Message(constants.INFO, "INFO message.", "extra-info"),
                Message(constants.SUCCESS, "SUCCESS message.", "extra-success"),
                Message(constants.WARNING, "WARNING message.", "extra-warning"),
                Message(constants.ERROR, "ERROR message.", "extra-error"),
            ],
        )

    @override_settings(MESSAGE_TAGS={42: "CUSTOM"})
    def test_custom_levelname(self):
        response = FakeResponse()
        add_message(response.wsgi_request, 42, "CUSTOM message.")
        self.assertMessages(response, [Message(42, "CUSTOM message.")])

    def test_ordered(self):
        """
        Tests that messages are correctly stored in the request, and can be asserted 
        in an unordered manner. 

        The purpose of this test is to ensure that the :func:`add_message` function 
        correctly adds messages to the request, regardless of their order. It verifies 
        that the :func:`assertMessages` function works as expected when the 'ordered' 
        parameter is set to False, allowing for messages to be in any order. Additionally, 
        it checks that an AssertionError is raised when the 'ordered' parameter is not 
        specified or set to True, and the messages are not in the expected order.
        """
        response = FakeResponse()
        add_message(response.wsgi_request, constants.INFO, "First message.")
        add_message(response.wsgi_request, constants.WARNING, "Second message.")
        expected_messages = [
            Message(constants.WARNING, "Second message."),
            Message(constants.INFO, "First message."),
        ]
        self.assertMessages(response, expected_messages, ordered=False)
        with self.assertRaisesMessage(AssertionError, "Lists differ: "):
            self.assertMessages(response, expected_messages)

    def test_mismatching_length(self):
        """
        Tests that the assertMessages method raises an AssertionError when the expected and actual message lists have mismatching lengths.

        This test case verifies that the method correctly identifies and reports a difference in the number of messages when comparing two lists, and that it provides a meaningful error message indicating the extra or missing messages.

        The test includes a scenario where a single message is added to the request, and then the assertMessages method is called with an empty list of expected messages, resulting in an AssertionError being raised with a specific error message.

        """
        response = FakeResponse()
        add_message(response.wsgi_request, constants.INFO, "INFO message.")
        msg = (
            "Lists differ: [Message(level=20, message='INFO message.')] != []\n\n"
            "First list contains 1 additional elements.\n"
            "First extra element 0:\n"
            "Message(level=20, message='INFO message.')\n\n"
            "- [Message(level=20, message='INFO message.')]\n"
            "+ []"
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertMessages(response, [])
