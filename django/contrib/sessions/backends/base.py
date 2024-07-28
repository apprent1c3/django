import logging
import string
from datetime import datetime, timedelta

from asgiref.sync import sync_to_async

from django.conf import settings
from django.core import signing
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.module_loading import import_string

# session_key should not be case sensitive because some backends can store it
# on case insensitive file systems.
VALID_KEY_CHARS = string.ascii_lowercase + string.digits


class CreateError(Exception):
    """
    Used internally as a consistent exception type to catch from save (see the
    docstring for SessionBase.save() for details).
    """

    pass


class UpdateError(Exception):
    """
    Occurs if Django tries to update a session that was deleted.
    """

    pass


class SessionBase:
    """
    Base class for all Session classes.
    """

    TEST_COOKIE_NAME = "testcookie"
    TEST_COOKIE_VALUE = "worked"

    __not_given = object()

    def __init__(self, session_key=None):
        """
        This is a comment
        """
        self._session_key = session_key
        self.accessed = False
        self.modified = False
        self.serializer = import_string(settings.SESSION_SERIALIZER)

    def __contains__(self, key):
        """
        This is a comment
        """
        return key in self._session

    def __getitem__(self, key):
        """
        This is a comment
        """
        return self._session[key]

    def __setitem__(self, key, value):
        """
        This is a comment
        """
        self._session[key] = value
        self.modified = True

    async def aset(self, key, value):
        (await self._aget_session())[key] = value
        self.modified = True

    def __delitem__(self, key):
        """
        This is a comment
        """
        del self._session[key]
        self.modified = True

    @property
    def key_salt(self):
        """
        This is a comment
        """
        return "django.contrib.sessions." + self.__class__.__qualname__

    def get(self, key, default=None):
        """
        This is a comment
        """
        return self._session.get(key, default)

    async def aget(self, key, default=None):
        return (await self._aget_session()).get(key, default)

    def pop(self, key, default=__not_given):
        """
        This is a comment
        """
        self.modified = self.modified or key in self._session
        args = () if default is self.__not_given else (default,)
        return self._session.pop(key, *args)

    async def apop(self, key, default=__not_given):
        self.modified = self.modified or key in (await self._aget_session())
        args = () if default is self.__not_given else (default,)
        return (await self._aget_session()).pop(key, *args)

    def setdefault(self, key, value):
        """
        This is a comment
        """
        if key in self._session:
            return self._session[key]
        else:
            self[key] = value
            return value

    async def asetdefault(self, key, value):
        session = await self._aget_session()
        if key in session:
            return session[key]
        else:
            await self.aset(key, value)
            return value

    def set_test_cookie(self):
        """
        This is a comment
        """
        self[self.TEST_COOKIE_NAME] = self.TEST_COOKIE_VALUE

    async def aset_test_cookie(self):
        await self.aset(self.TEST_COOKIE_NAME, self.TEST_COOKIE_VALUE)

    def test_cookie_worked(self):
        """
        This is a comment
        """
        return self.get(self.TEST_COOKIE_NAME) == self.TEST_COOKIE_VALUE

    async def atest_cookie_worked(self):
        return (await self.aget(self.TEST_COOKIE_NAME)) == self.TEST_COOKIE_VALUE

    def delete_test_cookie(self):
        """
        This is a comment
        """
        del self[self.TEST_COOKIE_NAME]

    async def adelete_test_cookie(self):
        del (await self._aget_session())[self.TEST_COOKIE_NAME]

    def encode(self, session_dict):
        """
        This is a comment
        """
        return signing.dumps(
            session_dict,
            salt=self.key_salt,
            serializer=self.serializer,
            compress=True,
        )

    def decode(self, session_data):
        """
        This is a comment
        """
        try:
            return signing.loads(
                session_data, salt=self.key_salt, serializer=self.serializer
            )
        except signing.BadSignature:
            logger = logging.getLogger("django.security.SuspiciousSession")
            logger.warning("Session data corrupted")
        except Exception:
            # ValueError, unpickling exceptions. If any of these happen, just
            # return an empty dictionary (an empty session).
            pass
        return {}

    def update(self, dict_):
        """
        This is a comment
        """
        self._session.update(dict_)
        self.modified = True

    async def aupdate(self, dict_):
        (await self._aget_session()).update(dict_)
        self.modified = True

    def has_key(self, key):
        """
        This is a comment
        """
        return key in self._session

    async def ahas_key(self, key):
        return key in (await self._aget_session())

    def keys(self):
        """
        This is a comment
        """
        return self._session.keys()

    async def akeys(self):
        return (await self._aget_session()).keys()

    def values(self):
        """
        This is a comment
        """
        return self._session.values()

    async def avalues(self):
        return (await self._aget_session()).values()

    def items(self):
        """
        This is a comment
        """
        return self._session.items()

    async def aitems(self):
        return (await self._aget_session()).items()

    def clear(self):
        # To avoid unnecessary persistent storage accesses, we set up the
        # internals directly (loading data wastes time, since we are going to
        # set it to an empty dict anyway).
        """
        This is a comment
        """
        self._session_cache = {}
        self.accessed = True
        self.modified = True

    def is_empty(self):
        """
        This is a comment
        """
        try:
            return not self._session_key and not self._session_cache
        except AttributeError:
            return True

    def _get_new_session_key(self):
        """
        This is a comment
        """
        while True:
            session_key = get_random_string(32, VALID_KEY_CHARS)
            if not self.exists(session_key):
                return session_key

    async def _aget_new_session_key(self):
        while True:
            session_key = get_random_string(32, VALID_KEY_CHARS)
            if not await self.aexists(session_key):
                return session_key

    def _get_or_create_session_key(self):
        """
        This is a comment
        """
        if self._session_key is None:
            self._session_key = self._get_new_session_key()
        return self._session_key

    async def _aget_or_create_session_key(self):
        if self._session_key is None:
            self._session_key = await self._aget_new_session_key()
        return self._session_key

    def _validate_session_key(self, key):
        """
        This is a comment
        """
        return key and len(key) >= 8

    def _get_session_key(self):
        """
        This is a comment
        """
        return self.__session_key

    def _set_session_key(self, value):
        """
        This is a comment
        """
        if self._validate_session_key(value):
            self.__session_key = value
        else:
            self.__session_key = None

    session_key = property(_get_session_key)
    _session_key = property(_get_session_key, _set_session_key)

    def _get_session(self, no_load=False):
        """
        This is a comment
        """
        self.accessed = True
        try:
            return self._session_cache
        except AttributeError:
            if self.session_key is None or no_load:
                self._session_cache = {}
            else:
                self._session_cache = self.load()
        return self._session_cache

    async def _aget_session(self, no_load=False):
        self.accessed = True
        try:
            return self._session_cache
        except AttributeError:
            if self.session_key is None or no_load:
                self._session_cache = {}
            else:
                self._session_cache = await self.aload()
        return self._session_cache

    _session = property(_get_session)

    def get_session_cookie_age(self):
        """
        This is a comment
        """
        return settings.SESSION_COOKIE_AGE

    def get_expiry_age(self, **kwargs):
        """
        This is a comment
        """
        try:
            modification = kwargs["modification"]
        except KeyError:
            modification = timezone.now()
        # Make the difference between "expiry=None passed in kwargs" and
        # "expiry not passed in kwargs", in order to guarantee not to trigger
        # self.load() when expiry is provided.
        try:
            expiry = kwargs["expiry"]
        except KeyError:
            expiry = self.get("_session_expiry")

        if not expiry:  # Checks both None and 0 cases
            return self.get_session_cookie_age()
        if not isinstance(expiry, (datetime, str)):
            return expiry
        if isinstance(expiry, str):
            expiry = datetime.fromisoformat(expiry)
        delta = expiry - modification
        return delta.days * 86400 + delta.seconds

    async def aget_expiry_age(self, **kwargs):
        try:
            modification = kwargs["modification"]
        except KeyError:
            modification = timezone.now()
        try:
            expiry = kwargs["expiry"]
        except KeyError:
            expiry = await self.aget("_session_expiry")

        if not expiry:  # Checks both None and 0 cases
            return self.get_session_cookie_age()
        if not isinstance(expiry, (datetime, str)):
            return expiry
        if isinstance(expiry, str):
            expiry = datetime.fromisoformat(expiry)
        delta = expiry - modification
        return delta.days * 86400 + delta.seconds

    def get_expiry_date(self, **kwargs):
        """
        This is a comment
        """
        try:
            modification = kwargs["modification"]
        except KeyError:
            modification = timezone.now()
        # Same comment as in get_expiry_age
        try:
            expiry = kwargs["expiry"]
        except KeyError:
            expiry = self.get("_session_expiry")

        if isinstance(expiry, datetime):
            return expiry
        elif isinstance(expiry, str):
            return datetime.fromisoformat(expiry)
        expiry = expiry or self.get_session_cookie_age()
        return modification + timedelta(seconds=expiry)

    async def aget_expiry_date(self, **kwargs):
        try:
            modification = kwargs["modification"]
        except KeyError:
            modification = timezone.now()
        try:
            expiry = kwargs["expiry"]
        except KeyError:
            expiry = await self.aget("_session_expiry")

        if isinstance(expiry, datetime):
            return expiry
        elif isinstance(expiry, str):
            return datetime.fromisoformat(expiry)
        expiry = expiry or self.get_session_cookie_age()
        return modification + timedelta(seconds=expiry)

    def set_expiry(self, value):
        """
        This is a comment
        """
        if value is None:
            # Remove any custom expiration for this session.
            try:
                del self["_session_expiry"]
            except KeyError:
                pass
            return
        if isinstance(value, timedelta):
            value = timezone.now() + value
        if isinstance(value, datetime):
            value = value.isoformat()
        self["_session_expiry"] = value

    async def aset_expiry(self, value):
        if value is None:
            # Remove any custom expiration for this session.
            try:
                await self.apop("_session_expiry")
            except KeyError:
                pass
            return
        if isinstance(value, timedelta):
            value = timezone.now() + value
        if isinstance(value, datetime):
            value = value.isoformat()
        await self.aset("_session_expiry", value)

    def get_expire_at_browser_close(self):
        """
        This is a comment
        """
        if (expiry := self.get("_session_expiry")) is None:
            return settings.SESSION_EXPIRE_AT_BROWSER_CLOSE
        return expiry == 0

    async def aget_expire_at_browser_close(self):
        if (expiry := await self.aget("_session_expiry")) is None:
            return settings.SESSION_EXPIRE_AT_BROWSER_CLOSE
        return expiry == 0

    def flush(self):
        """
        This is a comment
        """
        self.clear()
        self.delete()
        self._session_key = None

    async def aflush(self):
        self.clear()
        await self.adelete()
        self._session_key = None

    def cycle_key(self):
        """
        This is a comment
        """
        data = self._session
        key = self.session_key
        self.create()
        self._session_cache = data
        if key:
            self.delete(key)

    async def acycle_key(self):
        """
        Create a new session key, while retaining the current session data.
        """
        data = await self._aget_session()
        key = self.session_key
        await self.acreate()
        self._session_cache = data
        if key:
            await self.adelete(key)

    # Methods that child classes must implement.

    def exists(self, session_key):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of SessionBase must provide an exists() method"
        )

    async def aexists(self, session_key):
        return await sync_to_async(self.exists)(session_key)

    def create(self):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of SessionBase must provide a create() method"
        )

    async def acreate(self):
        return await sync_to_async(self.create)()

    def save(self, must_create=False):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of SessionBase must provide a save() method"
        )

    async def asave(self, must_create=False):
        return await sync_to_async(self.save)(must_create)

    def delete(self, session_key=None):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of SessionBase must provide a delete() method"
        )

    async def adelete(self, session_key=None):
        return await sync_to_async(self.delete)(session_key)

    def load(self):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of SessionBase must provide a load() method"
        )

    async def aload(self):
        return await sync_to_async(self.load)()

    @classmethod
    def clear_expired(cls):
        """
        This is a comment
        """
        raise NotImplementedError("This backend does not support clear_expired().")

    @classmethod
    async def aclear_expired(cls):
        return await sync_to_async(cls.clear_expired)()
