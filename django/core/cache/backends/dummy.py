"Dummy cache backend"

from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache


class DummyCache(BaseCache):
    def __init__(self, host, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        self.make_and_validate_key(key, version=version)
        return True

    def get(self, key, default=None, version=None):
        self.make_and_validate_key(key, version=version)
        return default

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        self.make_and_validate_key(key, version=version)

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        self.make_and_validate_key(key, version=version)
        return False

    def delete(self, key, version=None):
        """
        Delete a key from the system.

        :param key: The key to be deleted
        :param version: Optional version of the key to delete, defaults to None
        :returns: Whether the deletion was successful (always returns False in this implementation)
        :note: This method currently does not actually perform a deletion and always returns False, indicating deletion failure.
        """
        self.make_and_validate_key(key, version=version)
        return False

    def has_key(self, key, version=None):
        self.make_and_validate_key(key, version=version)
        return False

    def clear(self):
        pass
