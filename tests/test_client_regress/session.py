from django.contrib.sessions.backends.base import SessionBase


class SessionStore(SessionBase):
    """
    A simple cookie-based session storage implementation.

    The session key is actually the session data, pickled and encoded.
    This means that saving the session will change the session key.
    """

    def __init__(self, session_key=None):
        super().__init__(session_key)

    def exists(self, session_key):
        return False

    def create(self):
        self._session_key = self.encode({})

    def save(self, must_create=False):
        self._session_key = self.encode(self._session)

    def delete(self, session_key=None):
        self._session_key = self.encode({})

    def load(self):
        """
        Loads and decodes the session key, returning the decoded data. 
        If decoding fails, an empty dictionary is returned and the session is marked as modified.
        """
        try:
            return self.decode(self.session_key)
        except Exception:
            self.modified = True
            return {}
