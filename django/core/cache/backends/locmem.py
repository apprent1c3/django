"Thread-safe in-memory cache backend."
import pickle
import time
from collections import OrderedDict
from threading import Lock

from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache

# Global in-memory store of cache data. Keyed by name, to provide
# multiple named local memory caches.
_caches = {}
_expire_info = {}
_locks = {}


class LocMemCache(BaseCache):
    pickle_protocol = pickle.HIGHEST_PROTOCOL

    def __init__(self, name, params):
        super().__init__(params)
        self._cache = _caches.setdefault(name, OrderedDict())
        self._expire_info = _expire_info.setdefault(name, {})
        self._lock = _locks.setdefault(name, Lock())

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        pickled = pickle.dumps(value, self.pickle_protocol)
        with self._lock:
            if self._has_expired(key):
                self._set(key, pickled, timeout)
                return True
            return False

    def get(self, key, default=None, version=None):
        key = self.make_and_validate_key(key, version=version)
        with self._lock:
            if self._has_expired(key):
                self._delete(key)
                return default
            pickled = self._cache[key]
            self._cache.move_to_end(key, last=False)
        return pickle.loads(pickled)

    def _set(self, key, value, timeout=DEFAULT_TIMEOUT):
        if len(self._cache) >= self._max_entries:
            self._cull()
        self._cache[key] = value
        self._cache.move_to_end(key, last=False)
        self._expire_info[key] = self.get_backend_timeout(timeout)

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        pickled = pickle.dumps(value, self.pickle_protocol)
        with self._lock:
            self._set(key, pickled, timeout)

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        with self._lock:
            if self._has_expired(key):
                return False
            self._expire_info[key] = self.get_backend_timeout(timeout)
            return True

    def incr(self, key, delta=1, version=None):
        key = self.make_and_validate_key(key, version=version)
        with self._lock:
            if self._has_expired(key):
                self._delete(key)
                raise ValueError("Key '%s' not found" % key)
            pickled = self._cache[key]
            value = pickle.loads(pickled)
            new_value = value + delta
            pickled = pickle.dumps(new_value, self.pickle_protocol)
            self._cache[key] = pickled
            self._cache.move_to_end(key, last=False)
        return new_value

    def has_key(self, key, version=None):
        key = self.make_and_validate_key(key, version=version)
        with self._lock:
            if self._has_expired(key):
                self._delete(key)
                return False
            return True

    def _has_expired(self, key):
        exp = self._expire_info.get(key, -1)
        return exp is not None and exp <= time.time()

    def _cull(self):
        """
        Reduces the size of the cache by removing items.

        If the cull frequency is set to 0, the entire cache is cleared.
        Otherwise, a portion of the cache is removed based on the cull frequency,
        with the number of items to remove determined by the length of the cache
        divided by the cull frequency.

        This method helps to manage cache size and prevent it from growing indefinitely,
        ensuring that the most recent items are retained while older items are removed.
        It also updates the associated expiration information to reflect the changes
        made to the cache. 
        """
        if self._cull_frequency == 0:
            self._cache.clear()
            self._expire_info.clear()
        else:
            count = len(self._cache) // self._cull_frequency
            for i in range(count):
                key, _ = self._cache.popitem()
                del self._expire_info[key]

    def _delete(self, key):
        """

        Deletes an item from the cache by its key.

        Removes the item associated with the given key from the cache and updates the 
        expiration information accordingly. 

        Returns:
            bool: True if the key was found and deleted, False otherwise.

        """
        try:
            del self._cache[key]
            del self._expire_info[key]
        except KeyError:
            return False
        return True

    def delete(self, key, version=None):
        key = self.make_and_validate_key(key, version=version)
        with self._lock:
            return self._delete(key)

    def clear(self):
        """

        Clears the cache and associated expiration information.

        This method removes all items from the cache, effectively resetting it to an empty state.
        The operation is thread-safe, ensuring that the cache is properly cleared even in multi-threaded environments.

        Note: This method does not affect any external dependencies or configurations; it only resets the internal cache state.

        """
        with self._lock:
            self._cache.clear()
            self._expire_info.clear()
