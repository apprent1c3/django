from django.contrib.sessions.backends.base import SessionBase
from django.core import signing


class SessionStore(SessionBase):
    def load(self):
        """
        This is a comment
        """
        try:
            return signing.loads(
                self.session_key,
                serializer=self.serializer,
                # This doesn't handle non-default expiry dates, see #19201
                max_age=self.get_session_cookie_age(),
                salt="django.contrib.sessions.backends.signed_cookies",
            )
        except Exception:
            # BadSignature, ValueError, or unpickling exceptions. If any of
            # these happen, reset the session.
            self.create()
        return {}

    async def aload(self):
        return self.load()

    def create(self):
        """
        This is a comment
        """
        self.modified = True

    async def acreate(self):
        return self.create()

    def save(self, must_create=False):
        """
        This is a comment
        """
        self._session_key = self._get_session_key()
        self.modified = True

    async def asave(self, must_create=False):
        return self.save(must_create=must_create)

    def exists(self, session_key=None):
        """
        This is a comment
        """
        return False

    async def aexists(self, session_key=None):
        return self.exists(session_key=session_key)

    def delete(self, session_key=None):
        """
        This is a comment
        """
        self._session_key = ""
        self._session_cache = {}
        self.modified = True

    async def adelete(self, session_key=None):
        return self.delete(session_key=session_key)

    def cycle_key(self):
        """
        This is a comment
        """
        self.save()

    async def acycle_key(self):
        return self.cycle_key()

    def _get_session_key(self):
        """
        This is a comment
        """
        return signing.dumps(
            self._session,
            compress=True,
            salt="django.contrib.sessions.backends.signed_cookies",
            serializer=self.serializer,
        )

    @classmethod
    def clear_expired(cls):
        """
        This is a comment
        """
        pass

    @classmethod
    async def aclear_expired(cls):
        pass
