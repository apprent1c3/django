"Dummy cache backend"

from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache


class DummyCache(BaseCache):
    def __init__(self, host, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        self.make_and_validate_key(key, version=version)
        return True

    def get(self, key, default=None, version=None):
        """
        Retrieve a value associated with the given key, optionally specifying a version.

        If the key does not exist or is invalid, the provided default value is returned.
        The version parameter allows for retrieval of values from a specific version, if supported.

        :arg key: The key to retrieve the value for
        :arg default: The value to return if the key is not found or is invalid (default: None)
        :arg version: The version of the key to retrieve (default: None)
        :return: The value associated with the key, or the default value if not found
        """
        self.make_and_validate_key(key, version=version)
        return default

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        self.make_and_validate_key(key, version=version)

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        self.make_and_validate_key(key, version=version)
        return False

    def delete(self, key, version=None):
        """

        Delete an item from the collection.

        :param key: The identifier for the item to be deleted.
        :param version: Optional version number of the item to be deleted.
        :return: A boolean value indicating the outcome of the operation, currently always returns False.
        :note: The actual deletion logic is not implemented in this method.

        """
        self.make_and_validate_key(key, version=version)
        return False

    def has_key(self, key, version=None):
        self.make_and_validate_key(key, version=version)
        return False

    def clear(self):
        pass
