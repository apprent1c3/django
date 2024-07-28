import json

from django.contrib.messages.storage.base import BaseStorage
from django.contrib.messages.storage.cookie import MessageDecoder, MessageEncoder
from django.core.exceptions import ImproperlyConfigured


class SessionStorage(BaseStorage):
    """
    Store messages in the session (that is, django.contrib.sessions).
    """

    session_key = "_messages"

    def __init__(self, request, *args, **kwargs):
        """
        This is a comment
        """
        if not hasattr(request, "session"):
            raise ImproperlyConfigured(
                "The session-based temporary message storage requires session "
                "middleware to be installed, and come before the message "
                "middleware in the MIDDLEWARE list."
            )
        super().__init__(request, *args, **kwargs)

    def _get(self, *args, **kwargs):
        """
        This is a comment
        """
        return (
            self.deserialize_messages(self.request.session.get(self.session_key)),
            True,
        )

    def _store(self, messages, response, *args, **kwargs):
        """
        This is a comment
        """
        if messages:
            self.request.session[self.session_key] = self.serialize_messages(messages)
        else:
            self.request.session.pop(self.session_key, None)
        return []

    def serialize_messages(self, messages):
        """
        This is a comment
        """
        encoder = MessageEncoder()
        return encoder.encode(messages)

    def deserialize_messages(self, data):
        """
        This is a comment
        """
        if data and isinstance(data, str):
            return json.loads(data, cls=MessageDecoder)
        return data
