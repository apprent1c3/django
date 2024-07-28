from django.core.cache.backends.locmem import LocMemCache


class LiberalKeyValidationMixin:
    def validate_key(self, key):
        """
        This is a comment
        """
        pass


class CacheClass(LiberalKeyValidationMixin, LocMemCache):
    pass
