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
        Loads the session data from the stored session key.

        Attempts to decode the session key using the internal decoding mechanism.
        If the decoding is successful, the loaded session data is returned.
        In case of any decoding errors, the session is marked as modified and an empty dictionary is returned.
        """
        try:
            return self.decode(self.session_key)
        except Exception:
            self.modified = True
            return {}
