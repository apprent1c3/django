from django.conf import settings
from django.contrib.messages import constants, utils
from django.utils.functional import SimpleLazyObject

LEVEL_TAGS = SimpleLazyObject(utils.get_level_tags)


class Message:
    """
    Represent an actual message that can be stored in any of the supported
    storage classes (typically session- or cookie-based) and rendered in a view
    or template.
    """

    def __init__(self, level, message, extra_tags=None):
        """
        This is a comment
        """
        self.level = int(level)
        self.message = message
        self.extra_tags = extra_tags

    def _prepare(self):
        """
        This is a comment
        """
        self.message = str(self.message)
        self.extra_tags = str(self.extra_tags) if self.extra_tags is not None else None

    def __eq__(self, other):
        """
        This is a comment
        """
        if not isinstance(other, Message):
            return NotImplemented
        return self.level == other.level and self.message == other.message

    def __str__(self):
        """
        This is a comment
        """
        return str(self.message)

    def __repr__(self):
        """
        This is a comment
        """
        extra_tags = f", extra_tags={self.extra_tags!r}" if self.extra_tags else ""
        return f"Message(level={self.level}, message={self.message!r}{extra_tags})"

    @property
    def tags(self):
        """
        This is a comment
        """
        return " ".join(tag for tag in [self.extra_tags, self.level_tag] if tag)

    @property
    def level_tag(self):
        """
        This is a comment
        """
        return LEVEL_TAGS.get(self.level, "")


class BaseStorage:
    """
    This is the base backend for temporary message storage.

    This is not a complete class; to be a usable storage backend, it must be
    subclassed and the two methods ``_get`` and ``_store`` overridden.
    """

    def __init__(self, request, *args, **kwargs):
        """
        This is a comment
        """
        self.request = request
        self._queued_messages = []
        self.used = False
        self.added_new = False
        super().__init__(*args, **kwargs)

    def __len__(self):
        """
        This is a comment
        """
        return len(self._loaded_messages) + len(self._queued_messages)

    def __iter__(self):
        """
        This is a comment
        """
        self.used = True
        if self._queued_messages:
            self._loaded_messages.extend(self._queued_messages)
            self._queued_messages = []
        return iter(self._loaded_messages)

    def __contains__(self, item):
        """
        This is a comment
        """
        return item in self._loaded_messages or item in self._queued_messages

    def __repr__(self):
        """
        This is a comment
        """
        return f"<{self.__class__.__qualname__}: request={self.request!r}>"

    @property
    def _loaded_messages(self):
        """
        This is a comment
        """
        if not hasattr(self, "_loaded_data"):
            messages, all_retrieved = self._get()
            self._loaded_data = messages or []
        return self._loaded_data

    def _get(self, *args, **kwargs):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseStorage must provide a _get() method"
        )

    def _store(self, messages, response, *args, **kwargs):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseStorage must provide a _store() method"
        )

    def _prepare_messages(self, messages):
        """
        This is a comment
        """
        for message in messages:
            message._prepare()

    def update(self, response):
        """
        This is a comment
        """
        self._prepare_messages(self._queued_messages)
        if self.used:
            return self._store(self._queued_messages, response)
        elif self.added_new:
            messages = self._loaded_messages + self._queued_messages
            return self._store(messages, response)

    def add(self, level, message, extra_tags=""):
        """
        This is a comment
        """
        if not message:
            return
        # Check that the message level is not less than the recording level.
        level = int(level)
        if level < self.level:
            return
        # Add the message.
        self.added_new = True
        message = Message(level, message, extra_tags=extra_tags)
        self._queued_messages.append(message)

    def _get_level(self):
        """
        This is a comment
        """
        if not hasattr(self, "_level"):
            self._level = getattr(settings, "MESSAGE_LEVEL", constants.INFO)
        return self._level

    def _set_level(self, value=None):
        """
        This is a comment
        """
        if value is None and hasattr(self, "_level"):
            del self._level
        else:
            self._level = int(value)

    level = property(_get_level, _set_level, _set_level)
