"""
Caching framework.

This package defines set of cache backends that all conform to a simple API.
In a nutshell, a cache is a set of values -- which can be any object that
may be pickled -- identified by string keys.  For the complete API, see
the abstract BaseCache class in django.core.cache.backends.base.

Client code should use the `cache` variable defined here to access the default
cache backend and look up non-default cache backends in the `caches` dict-like
object.

See docs/topics/cache.txt for information on the public API.
"""

from django.core import signals
from django.core.cache.backends.base import (
    BaseCache,
    CacheKeyWarning,
    InvalidCacheBackendError,
    InvalidCacheKey,
)
from django.utils.connection import BaseConnectionHandler, ConnectionProxy
from django.utils.module_loading import import_string

__all__ = [
    "cache",
    "caches",
    "DEFAULT_CACHE_ALIAS",
    "InvalidCacheBackendError",
    "CacheKeyWarning",
    "BaseCache",
    "InvalidCacheKey",
]

DEFAULT_CACHE_ALIAS = "default"


class CacheHandler(BaseConnectionHandler):
    settings_name = "CACHES"
    exception_class = InvalidCacheBackendError

    def create_connection(self, alias):
        """

        Establishes a connection to a caching backend.

        Creates an instance of a cache backend class based on the settings provided
        for the specified alias. The backend class is instantiated with the location
        and additional parameters defined in the settings.

        :raises InvalidCacheBackendError: if the specified backend cannot be found

        """
        params = self.settings[alias].copy()
        backend = params.pop("BACKEND")
        location = params.pop("LOCATION", "")
        try:
            backend_cls = import_string(backend)
        except ImportError as e:
            raise InvalidCacheBackendError(
                "Could not find backend '%s': %s" % (backend, e)
            ) from e
        return backend_cls(location, params)


caches = CacheHandler()

cache = ConnectionProxy(caches, DEFAULT_CACHE_ALIAS)


def close_caches(**kwargs):
    # Some caches need to do a cleanup at the end of a request cycle. If not
    # implemented in a particular backend cache.close() is a no-op.
    caches.close_all()


signals.request_finished.connect(close_caches)
