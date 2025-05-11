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
        """
        Adds or updates a key-value pair in the cache with an optional expiration time.

        :param key: The key to be added or updated.
        :param value: The value associated with the key.
        :param timeout: The expiration time of the key-value pair in seconds (default: DEFAULT_TIMEOUT).
        :param version: The version of the key (optional).

        :returns: True if the key-value pair was successfully added or updated, False otherwise.
        """
        key = self.make_and_validate_key(key, version=version)
        pickled = pickle.dumps(value, self.pickle_protocol)
        with self._lock:
            if self._has_expired(key):
                self._set(key, pickled, timeout)
                return True
            return False

    def get(self, key, default=None, version=None):
        """
        Retrieves a value from the cache by its key, returning a default value if the key is not found or has expired. 

        The key can be versioned, allowing for multiple values to be stored under the same key but with different versions. If a version is not provided, it uses the default version. 

        The cache has a least recently used (LRU) ordering, where accessing a key moves it to the most recently used position.
        """
        key = self.make_and_validate_key(key, version=version)
        with self._lock:
            if self._has_expired(key):
                self._delete(key)
                return default
            pickled = self._cache[key]
            self._cache.move_to_end(key, last=False)
        return pickle.loads(pickled)

    def _set(self, key, value, timeout=DEFAULT_TIMEOUT):
        """
        Sets a value in the cache with a specified key and optional timeout, enforcing the maximum number of cache entries and updating expiration information.
        """
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
        """
        Update the expiration time of a key in the cache, preventing its removal due to inactivity.

        :param key: The key to be updated.
        :param timeout: The new timeout for the key; defaults to DEFAULT_TIMEOUT.
        :param version: The version of the key.
        :return: True if the update was successful, False if the key had expired.
        """
        key = self.make_and_validate_key(key, version=version)
        with self._lock:
            if self._has_expired(key):
                return False
            self._expire_info[key] = self.get_backend_timeout(timeout)
            return True

    def incr(self, key, delta=1, version=None):
        """
        Increments the value associated with the given key in the cache by a specified delta.

        :param key: The key whose value will be incremented.
        :param delta: The amount by which to increment the value. Defaults to 1.
        :param version: The version of the key, used for validation.
        :raises ValueError: If the key has expired or is not found.
        :return: The new value associated with the key after incrementing.
        """
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
        """
        Checks if a given key exists in the data store.

        :param key: The key to check for existence.
        :param version: Optional version number to consider when checking the key.
        :returns: True if the key exists and has not expired, False otherwise.
        """
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
        Reduces the size of the cache by removing a number of entries based on the cull frequency, or clears the cache entirely if the frequency is 0.
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
        Remove an item from the cache by its key.

        Returns:
            bool: True if the item was found and removed, False otherwise.
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
        with self._lock:
            self._cache.clear()
            self._expire_info.clear()
