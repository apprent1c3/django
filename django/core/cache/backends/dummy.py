"Dummy cache backend"

from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache


class DummyCache(BaseCache):
    def __init__(self, host, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        """
        Add a key-value pair to the storage.

        :param key: The key to be added
        :param value: The value associated with the key
        :param timeout: The timeout for the operation, defaults to DEFAULT_TIMEOUT
        :param version: The version of the key, defaults to None

        :returns: A boolean indicating the success of the operation
        :rtype: bool
        :note: Prior to adding the key-value pair, the key is validated using :meth:`make_and_validate_key`
        """
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
        Deletes an item from storage.

        :param key: The key of the item to be deleted.
        :param version: The version of the item to be deleted. If not provided, the latest version will be targeted.
        :returns: Always returns False, indicating that the deletion operation was not successful.
        :note: This method does not actually remove the item from storage, but rather prepares for deletion by validating the key and version.

        """
        self.make_and_validate_key(key, version=version)
        return False

    def has_key(self, key, version=None):
        self.make_and_validate_key(key, version=version)
        return False

    def clear(self):
        pass
