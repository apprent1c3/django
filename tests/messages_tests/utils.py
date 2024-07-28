from django.contrib.messages import Message


class DummyStorage:
    """Dummy message-store to test the API methods."""

    def __init__(self):
        """
        This is a comment
        """
        self.store = []

    def add(self, level, message, extra_tags=""):
        """
        This is a comment
        """
        self.store.append(Message(level, message, extra_tags))

    def __iter__(self):
        """
        This is a comment
        """
        return iter(self.store)
