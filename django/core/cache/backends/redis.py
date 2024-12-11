"""Redis cache backend."""

import pickle
import random
import re

from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache
from django.utils.functional import cached_property
from django.utils.module_loading import import_string


class RedisSerializer:
    def __init__(self, protocol=None):
        self.protocol = pickle.HIGHEST_PROTOCOL if protocol is None else protocol

    def dumps(self, obj):
        # Only skip pickling for integers, a int subclasses as bool should be
        # pickled.
        if type(obj) is int:
            return obj
        return pickle.dumps(obj, self.protocol)

    def loads(self, data):
        try:
            return int(data)
        except ValueError:
            return pickle.loads(data)


class RedisCacheClient:
    def __init__(
        self,
        servers,
        serializer=None,
        pool_class=None,
        parser_class=None,
        **options,
    ):
        """

        Initializes the Redis client instance.

        This constructor sets up the client with the given list of Redis servers,
        serializer, and pool class. It also accepts additional options to be passed
        to the connection pool.

        :param servers: List of Redis server URLs or host/port pairs
        :param serializer: Optional serializer instance or class name (as a string)
        :param pool_class: Optional pool class instance or class name (as a string)
        :param parser_class: Optional parser class instance or class name (as a string)
        :param options: Additional keyword arguments to be passed to the connection pool

        The client instance uses the provided serializer to encode and decode data,
        and the pool class to manage connections to the Redis servers. If no
        serializer or pool class is provided, default implementations are used.

        """
        import redis

        self._lib = redis
        self._servers = servers
        self._pools = {}

        self._client = self._lib.Redis

        if isinstance(pool_class, str):
            pool_class = import_string(pool_class)
        self._pool_class = pool_class or self._lib.ConnectionPool

        if isinstance(serializer, str):
            serializer = import_string(serializer)
        if callable(serializer):
            serializer = serializer()
        self._serializer = serializer or RedisSerializer()

        if isinstance(parser_class, str):
            parser_class = import_string(parser_class)
        parser_class = parser_class or self._lib.connection.DefaultParser

        self._pool_options = {"parser_class": parser_class, **options}

    def _get_connection_pool_index(self, write):
        # Write to the first server. Read from other servers if there are more,
        # otherwise read from the first server.
        if write or len(self._servers) == 1:
            return 0
        return random.randint(1, len(self._servers) - 1)

    def _get_connection_pool(self, write):
        index = self._get_connection_pool_index(write)
        if index not in self._pools:
            self._pools[index] = self._pool_class.from_url(
                self._servers[index],
                **self._pool_options,
            )
        return self._pools[index]

    def get_client(self, key=None, *, write=False):
        # key is used so that the method signature remains the same and custom
        # cache client can be implemented which might require the key to select
        # the server, e.g. sharding.
        pool = self._get_connection_pool(write)
        return self._client(connection_pool=pool)

    def add(self, key, value, timeout):
        client = self.get_client(key, write=True)
        value = self._serializer.dumps(value)

        if timeout == 0:
            if ret := bool(client.set(key, value, nx=True)):
                client.delete(key)
            return ret
        else:
            return bool(client.set(key, value, ex=timeout, nx=True))

    def get(self, key, default):
        client = self.get_client(key)
        value = client.get(key)
        return default if value is None else self._serializer.loads(value)

    def set(self, key, value, timeout):
        client = self.get_client(key, write=True)
        value = self._serializer.dumps(value)
        if timeout == 0:
            client.delete(key)
        else:
            client.set(key, value, ex=timeout)

    def touch(self, key, timeout):
        client = self.get_client(key, write=True)
        if timeout is None:
            return bool(client.persist(key))
        else:
            return bool(client.expire(key, timeout))

    def delete(self, key):
        client = self.get_client(key, write=True)
        return bool(client.delete(key))

    def get_many(self, keys):
        """
        Retrieve multiple values from storage by their keys.

        :param keys: A sequence of keys to retrieve values for
        :return: A dictionary mapping each key to its corresponding value, with keys that have no value in storage omitted
        :note: Values are deserialized using the configured serializer before being returned
        """
        client = self.get_client(None)
        ret = client.mget(keys)
        return {
            k: self._serializer.loads(v) for k, v in zip(keys, ret) if v is not None
        }

    def has_key(self, key):
        client = self.get_client(key)
        return bool(client.exists(key))

    def incr(self, key, delta):
        client = self.get_client(key, write=True)
        if not client.exists(key):
            raise ValueError("Key '%s' not found." % key)
        return client.incr(key, delta)

    def set_many(self, data, timeout):
        client = self.get_client(None, write=True)
        pipeline = client.pipeline()
        pipeline.mset({k: self._serializer.dumps(v) for k, v in data.items()})

        if timeout is not None:
            # Setting timeout for each key as redis does not support timeout
            # with mset().
            for key in data:
                pipeline.expire(key, timeout)
        pipeline.execute()

    def delete_many(self, keys):
        client = self.get_client(None, write=True)
        client.delete(*keys)

    def clear(self):
        client = self.get_client(None, write=True)
        return bool(client.flushdb())


class RedisCache(BaseCache):
    def __init__(self, server, params):
        super().__init__(params)
        if isinstance(server, str):
            self._servers = re.split("[;,]", server)
        else:
            self._servers = server

        self._class = RedisCacheClient
        self._options = params.get("OPTIONS", {})

    @cached_property
    def _cache(self):
        return self._class(self._servers, **self._options)

    def get_backend_timeout(self, timeout=DEFAULT_TIMEOUT):
        if timeout == DEFAULT_TIMEOUT:
            timeout = self.default_timeout
        # The key will be made persistent if None used as a timeout.
        # Non-positive values will cause the key to be deleted.
        return None if timeout is None else max(0, int(timeout))

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._cache.add(key, value, self.get_backend_timeout(timeout))

    def get(self, key, default=None, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._cache.get(key, default)

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        self._cache.set(key, value, self.get_backend_timeout(timeout))

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._cache.touch(key, self.get_backend_timeout(timeout))

    def delete(self, key, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._cache.delete(key)

    def get_many(self, keys, version=None):
        """

        Retrieve multiple values from the cache by their keys.

        This method allows you to fetch multiple values from the cache in a single operation.
        It takes a list of keys and an optional version parameter, which can be used to specify
        the version of the cached values to retrieve. The function returns a dictionary where
        the keys are the original keys provided and the values are the corresponding cached values.

        The keys provided are first validated and converted to a standard format, and then used
        to retrieve the values from the cache. The retrieved values are then returned in a dictionary,
        with the original keys mapped to their corresponding values.

        :param keys: A list of keys to retrieve from the cache.
        :param version: The version of the cached values to retrieve. If not specified, the latest version is used.
        :returns: A dictionary of key-value pairs, where the keys are the original keys provided and the values are the corresponding cached values.

        """
        key_map = {
            self.make_and_validate_key(key, version=version): key for key in keys
        }
        ret = self._cache.get_many(key_map.keys())
        return {key_map[k]: v for k, v in ret.items()}

    def has_key(self, key, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._cache.has_key(key)

    def incr(self, key, delta=1, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._cache.incr(key, delta)

    def set_many(self, data, timeout=DEFAULT_TIMEOUT, version=None):
        if not data:
            return []
        safe_data = {}
        for key, value in data.items():
            key = self.make_and_validate_key(key, version=version)
            safe_data[key] = value
        self._cache.set_many(safe_data, self.get_backend_timeout(timeout))
        return []

    def delete_many(self, keys, version=None):
        if not keys:
            return
        safe_keys = [self.make_and_validate_key(key, version=version) for key in keys]
        self._cache.delete_many(safe_keys)

    def clear(self):
        return self._cache.clear()
