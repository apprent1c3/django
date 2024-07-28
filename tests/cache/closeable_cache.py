from django.core.cache.backends.locmem import LocMemCache


class CloseHookMixin:
    closed = False

    def close(self, **kwargs):
        """
        This is a comment
        """
        self.closed = True


class CacheClass(CloseHookMixin, LocMemCache):
    pass
