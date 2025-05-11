from django.conf import settings
from django.contrib.sessions.backends.base import CreateError, SessionBase, UpdateError
from django.core.cache import caches

KEY_PREFIX = "django.contrib.sessions.cache"


class SessionStore(SessionBase):
    """
    A cache-based session store.
    """

    cache_key_prefix = KEY_PREFIX

    def __init__(self, session_key=None):
        self._cache = caches[settings.SESSION_CACHE_ALIAS]
        super().__init__(session_key)

    @property
    def cache_key(self):
        return self.cache_key_prefix + self._get_or_create_session_key()

    async def acache_key(self):
        return self.cache_key_prefix + await self._aget_or_create_session_key()

    def load(self):
        """
        Retrieves cached session data associated with this instance. 
        If data is available in the cache, it is returned; otherwise, an empty dictionary is returned.
        """
        try:
            session_data = self._cache.get(self.cache_key)
        except Exception:
            # Some backends (e.g. memcache) raise an exception on invalid
            # cache keys. If this happens, reset the session. See #17810.
            session_data = None
        if session_data is not None:
            return session_data
        self._session_key = None
        return {}

    async def aload(self):
        """
        Loads session data from the cache, returning the cached data if available, or an empty dictionary if not found or an error occurs.
        """
        try:
            session_data = await self._cache.aget(await self.acache_key())
        except Exception:
            session_data = None
        if session_data is not None:
            return session_data
        self._session_key = None
        return {}

    def create(self):
        # Because a cache can fail silently (e.g. memcache), we don't know if
        # we are failing to create a new session because of a key collision or
        # because the cache is missing. So we try for a (large) number of times
        # and then raise an exception. That's the risk you shoulder if using
        # cache backing.
        """
        Attempt to create a new, unique session key and save it, retrying up to 10,000 times if the key already exists. Raises an exception if unable to create a new session key after the maximum number of attempts, indicating a potential cache availability issue.
        """
        for i in range(10000):
            self._session_key = self._get_new_session_key()
            try:
                self.save(must_create=True)
            except CreateError:
                continue
            self.modified = True
            return
        raise RuntimeError(
            "Unable to create a new session key. "
            "It is likely that the cache is unavailable."
        )

    async def acreate(self):
        """
        Attempts to create a new session key and save it to the database, retrying up to 10,000 times if creation fails due to a cache error.
        """
        for i in range(10000):
            self._session_key = await self._aget_new_session_key()
            try:
                await self.asave(must_create=True)
            except CreateError:
                continue
            self.modified = True
            return
        raise RuntimeError(
            "Unable to create a new session key. "
            "It is likely that the cache is unavailable."
        )

    def save(self, must_create=False):
        """
        Saves the current session to the cache, creating a new entry if necessary.

        :param bool must_create: If True, forces the creation of a new cache entry. If False, will update an existing entry if one exists.
        :raises UpdateError: If must_create is False and no existing cache entry is found.
        :raises CreateError: If must_create is True and the creation of a new cache entry fails.
        """
        if self.session_key is None:
            return self.create()
        if must_create:
            func = self._cache.add
        elif self._cache.get(self.cache_key) is not None:
            func = self._cache.set
        else:
            raise UpdateError
        result = func(
            self.cache_key,
            self._get_session(no_load=must_create),
            self.get_expiry_age(),
        )
        if must_create and not result:
            raise CreateError

    async def asave(self, must_create=False):
        """

        Save the current session asynchronously.

        If the session does not exist, it will be created if :param must_create: is True.
        Otherwise, if the session exists in the cache, it will be updated.
        If the session does not exist in the cache and :param must_create: is False, an UpdateError will be raised.
        If creation is required but fails, a CreateError will be raised.

        :param bool must_create: Whether to create the session if it does not exist.
        :raises UpdateError: If the session does not exist in the cache and creation is not requested.
        :raises CreateError: If creation is requested but fails.

        """
        if self.session_key is None:
            return await self.acreate()
        if must_create:
            func = self._cache.aadd
        elif await self._cache.aget(await self.acache_key()) is not None:
            func = self._cache.aset
        else:
            raise UpdateError
        result = await func(
            await self.acache_key(),
            await self._aget_session(no_load=must_create),
            await self.aget_expiry_age(),
        )
        if must_create and not result:
            raise CreateError

    def exists(self, session_key):
        return (
            bool(session_key) and (self.cache_key_prefix + session_key) in self._cache
        )

    async def aexists(self, session_key):
        return bool(session_key) and await self._cache.ahas_key(
            self.cache_key_prefix + session_key
        )

    def delete(self, session_key=None):
        """
        Deletes a cached item associated with a given session key.

        :param session_key: Key of the session to delete from cache, defaults to the current session key if not provided
        :return: None
        """
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        self._cache.delete(self.cache_key_prefix + session_key)

    async def adelete(self, session_key=None):
        """
        Asynchronously deletes a session from the cache.

        :param session_key: Key of the session to delete. If not provided, the instance's default session key is used. 
        :returns: None
        """
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        await self._cache.adelete(self.cache_key_prefix + session_key)

    @classmethod
    def clear_expired(cls):
        pass

    @classmethod
    async def aclear_expired(cls):
        pass
