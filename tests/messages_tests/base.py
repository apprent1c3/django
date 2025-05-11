from django.contrib.messages import Message, constants, get_level, set_level
from django.contrib.messages.api import MessageFailure
from django.contrib.messages.constants import DEFAULT_LEVELS
from django.contrib.messages.storage import default_storage
from django.http import HttpRequest, HttpResponse
from django.test import modify_settings, override_settings
from django.urls import reverse
from django.utils.translation import gettext_lazy


def add_level_messages(storage):
    """
    Populates a storage instance with a predefined set of messages representing different logging levels, including a custom level, to facilitate testing or demonstration of logging capabilities.
    """
    storage.add(constants.INFO, "A generic info message")
    storage.add(29, "Some custom level")
    storage.add(constants.DEBUG, "A debugging message", extra_tags="extra-tag")
    storage.add(constants.WARNING, "A warning")
    storage.add(constants.ERROR, "An error")
    storage.add(constants.SUCCESS, "This was a triumph.")


class BaseTests:
    storage_class = default_storage
    levels = {
        "debug": constants.DEBUG,
        "info": constants.INFO,
        "success": constants.SUCCESS,
        "warning": constants.WARNING,
        "error": constants.ERROR,
    }

    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(
            override_settings(
                TEMPLATES=[
                    {
                        "BACKEND": "django.template.backends.django.DjangoTemplates",
                        "DIRS": [],
                        "APP_DIRS": True,
                        "OPTIONS": {
                            "context_processors": (
                                "django.contrib.auth.context_processors.auth",
                                "django.contrib.messages.context_processors.messages",
                            ),
                        },
                    }
                ],
                ROOT_URLCONF="messages_tests.urls",
                MESSAGE_TAGS={},
                MESSAGE_STORAGE=(
                    f"{cls.storage_class.__module__}.{cls.storage_class.__name__}"
                ),
                SESSION_SERIALIZER="django.contrib.sessions.serializers.JSONSerializer",
            )
        )
        super().setUpClass()

    def get_request(self):
        return HttpRequest()

    def get_response(self):
        return HttpResponse()

    def get_storage(self, data=None):
        """
        Return the storage backend, setting its loaded data to the ``data``
        argument.

        This method avoids the storage ``_get`` method from getting called so
        that other parts of the storage backend can be tested independent of
        the message retrieval logic.
        """
        storage = self.storage_class(self.get_request())
        storage._loaded_data = data or []
        return storage

    def test_repr(self):
        request = self.get_request()
        storage = self.storage_class(request)
        self.assertEqual(
            repr(storage),
            f"<{self.storage_class.__qualname__}: request=<HttpRequest>>",
        )

    def test_add(self):
        """
        Tests the add functionality of a storage object, verifying that new messages are successfully added and marked as added, with optional extra tags.
        """
        storage = self.get_storage()
        self.assertFalse(storage.added_new)
        storage.add(constants.INFO, "Test message 1")
        self.assertTrue(storage.added_new)
        storage.add(constants.INFO, "Test message 2", extra_tags="tag")
        self.assertEqual(len(storage), 2)

    def test_add_lazy_translation(self):
        """
        Checks if lazy translations are properly stored when adding a message to a storage and updating a response.
        """
        storage = self.get_storage()
        response = self.get_response()

        storage.add(constants.INFO, gettext_lazy("lazy message"))
        storage.update(response)

        storing = self.stored_messages_count(storage, response)
        self.assertEqual(storing, 1)

    def test_no_update(self):
        """
        Tests that no messages are stored after an update operation.
        """
        storage = self.get_storage()
        response = self.get_response()
        storage.update(response)
        storing = self.stored_messages_count(storage, response)
        self.assertEqual(storing, 0)

    def test_add_update(self):
        """
        Tests the functionality of adding and updating messages in the storage system, 
        verifying that messages are stored correctly with and without extra tags.
        """
        storage = self.get_storage()
        response = self.get_response()

        storage.add(constants.INFO, "Test message 1")
        storage.add(constants.INFO, "Test message 1", extra_tags="tag")
        storage.update(response)

        storing = self.stored_messages_count(storage, response)
        self.assertEqual(storing, 2)

    def test_existing_add_read_update(self):
        """
        Tests the add, read, and update functionality of an existing storage by adding a message, 
         listing the stored messages, updating with a given response, and verifying that no messages are stored.\"\"\"
        _PARAMS(Collision between stored information and the given item seems none, hence param info can be omitted in this instance)_
        """
        storage = self.get_existing_storage()
        response = self.get_response()

        storage.add(constants.INFO, "Test message 3")
        list(storage)  # Simulates a read
        storage.update(response)

        storing = self.stored_messages_count(storage, response)
        self.assertEqual(storing, 0)

    def test_existing_read_add_update(self):
        """
        Tests the functionality of adding and updating a message in an existing storage, verifying that the changes are correctly reflected in the stored messages count.
        """
        storage = self.get_existing_storage()
        response = self.get_response()

        list(storage)  # Simulates a read
        storage.add(constants.INFO, "Test message 3")
        storage.update(response)

        storing = self.stored_messages_count(storage, response)
        self.assertEqual(storing, 1)

    @override_settings(MESSAGE_LEVEL=constants.DEBUG)
    def test_full_request_response_cycle(self):
        """
        Tests that messages are stored and retrieved correctly across a full request/redirect/response cycle when the message middleware is enabled.
        """
        data = {
            "messages": ["Test message %d" % x for x in range(5)],
        }
        show_url = reverse("show_message")
        for level in ("debug", "info", "success", "warning", "error"):
            add_url = reverse("add_message", args=(level,))
            response = self.client.post(add_url, data, follow=True)
            self.assertRedirects(response, show_url)
            self.assertIn("messages", response.context)
            messages = [Message(self.levels[level], msg) for msg in data["messages"]]
            self.assertEqual(list(response.context["messages"]), messages)
            for msg in data["messages"]:
                self.assertContains(response, msg)

    @override_settings(MESSAGE_LEVEL=constants.DEBUG)
    def test_with_template_response(self):
        """
        Tests that template responses are correctly displayed for different message levels, ensuring messages are present after a POST request and absent after a GET request, while redirecting as expected.
        """
        data = {
            "messages": ["Test message %d" % x for x in range(5)],
        }
        show_url = reverse("show_template_response")
        for level in self.levels:
            add_url = reverse("add_template_response", args=(level,))
            response = self.client.post(add_url, data, follow=True)
            self.assertRedirects(response, show_url)
            self.assertIn("messages", response.context)
            for msg in data["messages"]:
                self.assertContains(response, msg)

            # there shouldn't be any messages on second GET request
            response = self.client.get(show_url)
            for msg in data["messages"]:
                self.assertNotContains(response, msg)

    def test_context_processor_message_levels(self):
        show_url = reverse("show_template_response")
        response = self.client.get(show_url)

        self.assertIn("DEFAULT_MESSAGE_LEVELS", response.context)
        self.assertEqual(response.context["DEFAULT_MESSAGE_LEVELS"], DEFAULT_LEVELS)

    @override_settings(MESSAGE_LEVEL=constants.DEBUG)
    def test_multiple_posts(self):
        """
        Tests the persistence of messages when multiple POST requests are made before a GET request, ensuring that all messages are displayed correctly.
        """
        data = {
            "messages": ["Test message %d" % x for x in range(5)],
        }
        show_url = reverse("show_message")
        messages = []
        for level in ("debug", "info", "success", "warning", "error"):
            messages.extend(
                Message(self.levels[level], msg) for msg in data["messages"]
            )
            add_url = reverse("add_message", args=(level,))
            self.client.post(add_url, data)
        response = self.client.get(show_url)
        self.assertIn("messages", response.context)
        self.assertEqual(list(response.context["messages"]), messages)
        for msg in data["messages"]:
            self.assertContains(response, msg)

    @modify_settings(
        INSTALLED_APPS={"remove": "django.contrib.messages"},
        MIDDLEWARE={"remove": "django.contrib.messages.middleware.MessageMiddleware"},
    )
    @override_settings(
        MESSAGE_LEVEL=constants.DEBUG,
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
            }
        ],
    )
    def test_middleware_disabled(self):
        """
        Tests that disabling the message middleware raises an exception when attempting to store a message, ensuring the application behaves correctly without the middleware.
        """
        data = {
            "messages": ["Test message %d" % x for x in range(5)],
        }
        reverse("show_message")
        for level in ("debug", "info", "success", "warning", "error"):
            add_url = reverse("add_message", args=(level,))
            with self.assertRaises(MessageFailure):
                self.client.post(add_url, data, follow=True)

    @modify_settings(
        INSTALLED_APPS={"remove": "django.contrib.messages"},
        MIDDLEWARE={"remove": "django.contrib.messages.middleware.MessageMiddleware"},
    )
    @override_settings(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
            }
        ],
    )
    def test_middleware_disabled_fail_silently(self):
        """
        Tests if setting 'fail_silently' to True prevents exceptions when adding messages with the middleware disabled.
        """
        data = {
            "messages": ["Test message %d" % x for x in range(5)],
            "fail_silently": True,
        }
        show_url = reverse("show_message")
        for level in ("debug", "info", "success", "warning", "error"):
            add_url = reverse("add_message", args=(level,))
            response = self.client.post(add_url, data, follow=True)
            self.assertRedirects(response, show_url)
            self.assertNotIn("messages", response.context)

    def stored_messages_count(self, storage, response):
        """
        Return the number of messages being stored after a
        ``storage.update()`` call.
        """
        raise NotImplementedError("This method must be set by a subclass.")

    def test_get(self):
        raise NotImplementedError("This method must be set by a subclass.")

    def get_existing_storage(self):
        return self.get_storage(
            [
                Message(constants.INFO, "Test message 1"),
                Message(constants.INFO, "Test message 2", extra_tags="tag"),
            ]
        )

    def test_existing_read(self):
        """
        ..: Tests that reading from existing storage preserves data and correctly tracks usage.
        """
        storage = self.get_existing_storage()
        self.assertFalse(storage.used)
        # After iterating the storage engine directly, the used flag is set.
        data = list(storage)
        self.assertTrue(storage.used)
        # The data does not disappear because it has been iterated.
        self.assertEqual(data, list(storage))

    def test_existing_add(self):
        storage = self.get_existing_storage()
        self.assertFalse(storage.added_new)
        storage.add(constants.INFO, "Test message 3")
        self.assertTrue(storage.added_new)

    def test_default_level(self):
        # get_level works even with no storage on the request.
        """
        Tests that the default logging level is correctly set and maintained when using message storage.
        """
        request = self.get_request()
        self.assertEqual(get_level(request), constants.INFO)

        # get_level returns the default level if it hasn't been set.
        storage = self.get_storage()
        request._messages = storage
        self.assertEqual(get_level(request), constants.INFO)

        # Only messages of sufficient level get recorded.
        add_level_messages(storage)
        self.assertEqual(len(storage), 5)

    def test_low_level(self):
        """

        Tests the low-level functionality of setting and retrieving the message level.
        Verifies that the level can be set, retrieved, and used to add corresponding messages to the storage.

        """
        request = self.get_request()
        storage = self.storage_class(request)
        request._messages = storage

        self.assertTrue(set_level(request, 5))
        self.assertEqual(get_level(request), 5)

        add_level_messages(storage)
        self.assertEqual(len(storage), 6)

    def test_high_level(self):
        """
        Verifies the functionality of logging and level settings by testing set, get, and add operations on a request object's message storage, ensuring expected behavior and data consistency at a high level.
        """
        request = self.get_request()
        storage = self.storage_class(request)
        request._messages = storage

        self.assertTrue(set_level(request, 30))
        self.assertEqual(get_level(request), 30)

        add_level_messages(storage)
        self.assertEqual(len(storage), 2)

    @override_settings(MESSAGE_LEVEL=29)
    def test_settings_level(self):
        """
        Tests that setting the MESSAGE_LEVEL to a custom value affects the level of messages stored in the request's message storage.
        """
        request = self.get_request()
        storage = self.storage_class(request)

        self.assertEqual(get_level(request), 29)

        add_level_messages(storage)
        self.assertEqual(len(storage), 3)

    def test_tags(self):
        """
        Verifies the correctness of tags in stored messages by adding various messages with different tags and checking the resulting tags against an expected list.
        """
        storage = self.get_storage()
        storage.level = 0
        add_level_messages(storage)
        storage.add(constants.INFO, "A generic info message", extra_tags=None)
        tags = [msg.tags for msg in storage]
        self.assertEqual(
            tags, ["info", "", "extra-tag debug", "warning", "error", "success", "info"]
        )

    def test_level_tag(self):
        """
        Tests the level tags for a set of predefined log messages, verifying they match the expected output.
        """
        storage = self.get_storage()
        storage.level = 0
        add_level_messages(storage)
        tags = [msg.level_tag for msg in storage]
        self.assertEqual(tags, ["info", "", "debug", "warning", "error", "success"])

    @override_settings(
        MESSAGE_TAGS={
            constants.INFO: "info",
            constants.DEBUG: "",
            constants.WARNING: "",
            constants.ERROR: "bad",
            29: "custom",
        }
    )
    def test_custom_tags(self):
        """
        Tests that custom message tags are applied correctly, verifying that the MESSAGE_TAGS setting is used to determine the correct tags for different message levels.
        """
        storage = self.get_storage()
        storage.level = 0
        add_level_messages(storage)
        tags = [msg.tags for msg in storage]
        self.assertEqual(tags, ["info", "custom", "extra-tag", "", "bad", "success"])
