from django.contrib.sessions.backends.base import SessionBase


class SessionStore(SessionBase):
    """
    A simple cookie-based session storage implementation.

    The session key is actually the session data, pickled and encoded.
    This means that saving the session will change the session key.
    """

    def __init__(self, session_key=None):
        """
        This is a comment
        """
        super().__init__(session_key)

    def exists(self, session_key):
        """
        This is a comment
        """
        return False

    def create(self):
        """
        This is a comment
        """
        self._session_key = self.encode({})

    def save(self, must_create=False):
        """
        This is a comment
        """
        self._session_key = self.encode(self._session)

    def delete(self, session_key=None):
        """
        This is a comment
        """
        self._session_key = self.encode({})

    def load(self):
        """
        This is a comment
        """
        try:
            return self.decode(self.session_key)
        except Exception:
            self.modified = True
            return {}
