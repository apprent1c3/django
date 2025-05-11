"""
Cached, database-backed sessions.
"""

import logging

from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore as DBStore
from django.core.cache import caches

KEY_PREFIX = "django.contrib.sessions.cached_db"

logger = logging.getLogger("django.contrib.sessions")


class SessionStore(DBStore):
    """
    Implement cached, database backed sessions.
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
        ..: Loads cached data for the current object, retrieving from the database and decoding if cache is empty. Returns the loaded data or an empty dictionary if no data is found.
        """
        try:
            data = self._cache.get(self.cache_key)
        except Exception:
            # Some backends (e.g. memcache) raise an exception on invalid
            # cache keys. If this happens, reset the session. See #17810.
            data = None

        if data is None:
            s = self._get_session_from_db()
            if s:
                data = self.decode(s.session_data)
                self._cache.set(
                    self.cache_key, data, self.get_expiry_age(expiry=s.expire_date)
                )
            else:
                data = {}
        return data

    async def aload(self):
        """
        Loads data from cache or database, decrypting and decoding it if necessary, and stores the result in the cache for future use with a specified expiry age. Returns the loaded data.
        """
        try:
            data = await self._cache.aget(await self.acache_key())
        except Exception:
            # Some backends (e.g. memcache) raise an exception on invalid
            # cache keys. If this happens, reset the session. See #17810.
            data = None

        if data is None:
            s = await self._aget_session_from_db()
            if s:
                data = self.decode(s.session_data)
                await self._cache.aset(
                    await self.acache_key(),
                    data,
                    await self.aget_expiry_age(expiry=s.expire_date),
                )
            else:
                data = {}
        return data

    def exists(self, session_key):
        return (
            session_key
            and (self.cache_key_prefix + session_key) in self._cache
            or super().exists(session_key)
        )

    async def aexists(self, session_key):
        return (
            session_key
            and (self.cache_key_prefix + session_key) in self._cache
            or await super().aexists(session_key)
        )

    def save(self, must_create=False):
        """
        Saves the object and updates the cache with its current state.

        :param bool must_create: whether the object must be created
        :raises Exception: if an error occurs while saving to the cache
        """
        super().save(must_create)
        try:
            self._cache.set(self.cache_key, self._session, self.get_expiry_age())
        except Exception:
            logger.exception("Error saving to cache (%s)", self._cache)

    async def asave(self, must_create=False):
        """
        .. method:: asave(must_create=False)

            Saves the object to storage and updates the cache accordingly. The :paramref:`must_create` parameter determines if the object should be created if it does not already exist. If an error occurs while saving to the cache, it is logged and the object is still saved to storage.
        """
        await super().asave(must_create)
        try:
            await self._cache.aset(
                await self.acache_key(),
                self._session,
                await self.aget_expiry_age(),
            )
        except Exception:
            logger.exception("Error saving to cache (%s)", self._cache)

    def delete(self, session_key=None):
        """
        Deletes the session data and removes it from the cache.

        Removes the session data using the provided session key, or the instance's session key if none is specified.
        The corresponding cache entry is also deleted to ensure data consistency.
        """
        super().delete(session_key)
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        self._cache.delete(self.cache_key_prefix + session_key)

    async def adelete(self, session_key=None):
        """
        Delete the associate session data asynchronously.

        This method extends the parent class's deletion logic by also removing the session data from the cache. If no session key is provided, it defaults to the instance's session key.
        """
        await super().adelete(session_key)
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        await self._cache.adelete(self.cache_key_prefix + session_key)

    def flush(self):
        """
        Remove the current session data from the database and regenerate the
        key.
        """
        self.clear()
        self.delete(self.session_key)
        self._session_key = None

    async def aflush(self):
        """See flush()."""
        self.clear()
        await self.adelete(self.session_key)
        self._session_key = None
