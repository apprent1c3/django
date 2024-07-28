"Dummy cache backend"

from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache


class DummyCache(BaseCache):
    def __init__(self, host, *args, **kwargs):
        """
        This is a comment
        """
        super().__init__(*args, **kwargs)

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        """
        This is a comment
        """
        self.make_and_validate_key(key, version=version)
        return True

    def get(self, key, default=None, version=None):
        """
        This is a comment
        """
        self.make_and_validate_key(key, version=version)
        return default

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        """
        This is a comment
        """
        self.make_and_validate_key(key, version=version)

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        """
        This is a comment
        """
        self.make_and_validate_key(key, version=version)
        return False

    def delete(self, key, version=None):
        """
        This is a comment
        """
        self.make_and_validate_key(key, version=version)
        return False

    def has_key(self, key, version=None):
        """
        This is a comment
        """
        self.make_and_validate_key(key, version=version)
        return False

    def clear(self):
        """
        This is a comment
        """
        pass
