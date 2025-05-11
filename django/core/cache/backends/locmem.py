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
        Add or update a value in the cache.

        Adds a new key-value pair to the cache if the key does not exist or has expired.
        If the key exists and has not expired, the function returns False without updating
        the value.

        :param key: The key to associate with the value
        :param value: The value to store
        :param timeout: The duration after which the value expires, defaults to DEFAULT_TIMEOUT
        -param version: Optional version to use for key validation
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
        Retrieves the cached value associated with the given key.

        If the key does not exist, or its associated value has expired, returns the provided default value.
        Optionally, a specific version of the key can be specified to retrieve a versioned cache entry.
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
        Sets a value in the cache with the given key and optional timeout, removing the least recently used item if the cache is full.
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
        Update the expiration time of a key in the cache.

        :param key: The key to update
        :param timeout: The new expiration timeout, defaults to DEFAULT_TIMEOUT
        :param version: Optional version of the key
        :return: True if the key was updated, False if it has expired
        """
        key = self.make_and_validate_key(key, version=version)
        with self._lock:
            if self._has_expired(key):
                return False
            self._expire_info[key] = self.get_backend_timeout(timeout)
            return True

    def incr(self, key, delta=1, version=None):
        """
        Increment the value associated with the given key in the cache.

        Increments the value by a specified delta (defaulting to 1) and updates the cache.
        If the key is expired or does not exist, raises a ValueError.
        Returns the new value associated with the key.
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
        Checks if a given key exists in the cache.

        Args:
            key (str): The key to be checked.
            version (str, optional): The version of the key, defaults to None.

        Returns:
            bool: True if the key exists and has not expired, False otherwise.
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
        Reduces the size of the cache by removing items at a specified frequency. 
        When frequency is set to 0, it clears the cache entirely.
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
        Deletes an item from the cache by key and its associated expiration information. Returns True if the key was found and deleted, False otherwise.
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
