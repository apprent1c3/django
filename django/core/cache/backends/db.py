"Database cache backend."
import base64
import pickle
from datetime import datetime, timezone

from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache
from django.db import DatabaseError, connections, models, router, transaction
from django.utils.timezone import now as tz_now


class Options:
    """A class that will quack like a Django model _meta class.

    This allows cache operations to be controlled by the router
    """

    def __init__(self, table):
        self.db_table = table
        self.app_label = "django_cache"
        self.model_name = "cacheentry"
        self.verbose_name = "cache entry"
        self.verbose_name_plural = "cache entries"
        self.object_name = "CacheEntry"
        self.abstract = False
        self.managed = True
        self.proxy = False
        self.swapped = False


class BaseDatabaseCache(BaseCache):
    def __init__(self, table, params):
        super().__init__(params)
        self._table = table

        class CacheEntry:
            _meta = Options(table)

        self.cache_model_class = CacheEntry


class DatabaseCache(BaseDatabaseCache):
    # This class uses cursors provided by the database connection. This means
    # it reads expiration values as aware or naive datetimes, depending on the
    # value of USE_TZ and whether the database supports time zones. The ORM's
    # conversion and adaptation infrastructure is then used to avoid comparing
    # aware and naive datetimes accidentally.

    pickle_protocol = pickle.HIGHEST_PROTOCOL

    def get(self, key, default=None, version=None):
        return self.get_many([key], version).get(key, default)

    def get_many(self, keys, version=None):
        if not keys:
            return {}

        key_map = {
            self.make_and_validate_key(key, version=version): key for key in keys
        }

        db = router.db_for_read(self.cache_model_class)
        connection = connections[db]
        quote_name = connection.ops.quote_name
        table = quote_name(self._table)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT %s, %s, %s FROM %s WHERE %s IN (%s)"
                % (
                    quote_name("cache_key"),
                    quote_name("value"),
                    quote_name("expires"),
                    table,
                    quote_name("cache_key"),
                    ", ".join(["%s"] * len(key_map)),
                ),
                list(key_map),
            )
            rows = cursor.fetchall()

        result = {}
        expired_keys = []
        expression = models.Expression(output_field=models.DateTimeField())
        converters = connection.ops.get_db_converters(
            expression
        ) + expression.get_db_converters(connection)
        for key, value, expires in rows:
            for converter in converters:
                expires = converter(expires, expression, connection)
            if expires < tz_now():
                expired_keys.append(key)
            else:
                value = connection.ops.process_clob(value)
                value = pickle.loads(base64.b64decode(value.encode()))
                result[key_map.get(key)] = value
        self._base_delete_many(expired_keys)
        return result

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        self._base_set("set", key, value, timeout)

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._base_set("add", key, value, timeout)

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        """

        Update the expiration time of a key.

        This function \"touches\" a key, resetting its expiration time to the current time
        plus the specified timeout. This is useful for keeping keys from expiring when
        they are still being actively used.

        :param key: The key to update.
        :param timeout: The new expiration time in seconds; defaults to DEFAULT_TIMEOUT.
        :param version: Optional version number for the key.

        :return: The result of the touch operation.

        """
        key = self.make_and_validate_key(key, version=version)
        return self._base_set("touch", key, None, timeout)

    def _base_set(self, mode, key, value, timeout=DEFAULT_TIMEOUT):
        timeout = self.get_backend_timeout(timeout)
        db = router.db_for_write(self.cache_model_class)
        connection = connections[db]
        quote_name = connection.ops.quote_name
        table = quote_name(self._table)

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM %s" % table)
            num = cursor.fetchone()[0]
            now = tz_now()
            now = now.replace(microsecond=0)
            if timeout is None:
                exp = datetime.max
            else:
                tz = timezone.utc if settings.USE_TZ else None
                exp = datetime.fromtimestamp(timeout, tz=tz)
            exp = exp.replace(microsecond=0)
            if num > self._max_entries:
                self._cull(db, cursor, now, num)
            pickled = pickle.dumps(value, self.pickle_protocol)
            # The DB column is expecting a string, so make sure the value is a
            # string, not bytes. Refs #19274.
            b64encoded = base64.b64encode(pickled).decode("latin1")
            try:
                # Note: typecasting for datetimes is needed by some 3rd party
                # database backends. All core backends work without typecasting,
                # so be careful about changes here - test suite will NOT pick
                # regressions.
                with transaction.atomic(using=db):
                    cursor.execute(
                        "SELECT %s, %s FROM %s WHERE %s = %%s"
                        % (
                            quote_name("cache_key"),
                            quote_name("expires"),
                            table,
                            quote_name("cache_key"),
                        ),
                        [key],
                    )
                    result = cursor.fetchone()

                    if result:
                        current_expires = result[1]
                        expression = models.Expression(
                            output_field=models.DateTimeField()
                        )
                        for converter in connection.ops.get_db_converters(
                            expression
                        ) + expression.get_db_converters(connection):
                            current_expires = converter(
                                current_expires, expression, connection
                            )

                    exp = connection.ops.adapt_datetimefield_value(exp)
                    if result and mode == "touch":
                        cursor.execute(
                            "UPDATE %s SET %s = %%s WHERE %s = %%s"
                            % (table, quote_name("expires"), quote_name("cache_key")),
                            [exp, key],
                        )
                    elif result and (
                        mode == "set" or (mode == "add" and current_expires < now)
                    ):
                        cursor.execute(
                            "UPDATE %s SET %s = %%s, %s = %%s WHERE %s = %%s"
                            % (
                                table,
                                quote_name("value"),
                                quote_name("expires"),
                                quote_name("cache_key"),
                            ),
                            [b64encoded, exp, key],
                        )
                    elif mode != "touch":
                        cursor.execute(
                            "INSERT INTO %s (%s, %s, %s) VALUES (%%s, %%s, %%s)"
                            % (
                                table,
                                quote_name("cache_key"),
                                quote_name("value"),
                                quote_name("expires"),
                            ),
                            [key, b64encoded, exp],
                        )
                    else:
                        return False  # touch failed.
            except DatabaseError:
                # To be threadsafe, updates/inserts are allowed to fail silently
                return False
            else:
                return True

    def delete(self, key, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._base_delete_many([key])

    def delete_many(self, keys, version=None):
        keys = [self.make_and_validate_key(key, version=version) for key in keys]
        self._base_delete_many(keys)

    def _base_delete_many(self, keys):
        """
        Delete multiple cache entries from the database.

        This method takes a list of keys as input and removes the corresponding cache entries from the database.
        It uses the database connection configured for the model to execute a SQL query that deletes the specified entries.
        The method returns True if any entries were deleted, and False otherwise. It does not raise an error if no entries are deleted or if the input list is empty, but returns False in such cases.
        """
        if not keys:
            return False

        db = router.db_for_write(self.cache_model_class)
        connection = connections[db]
        quote_name = connection.ops.quote_name
        table = quote_name(self._table)

        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM %s WHERE %s IN (%s)"
                % (
                    table,
                    quote_name("cache_key"),
                    ", ".join(["%s"] * len(keys)),
                ),
                keys,
            )
            return bool(cursor.rowcount)

    def has_key(self, key, version=None):
        key = self.make_and_validate_key(key, version=version)

        db = router.db_for_read(self.cache_model_class)
        connection = connections[db]
        quote_name = connection.ops.quote_name

        now = tz_now().replace(microsecond=0, tzinfo=None)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT %s FROM %s WHERE %s = %%s and %s > %%s"
                % (
                    quote_name("cache_key"),
                    quote_name(self._table),
                    quote_name("cache_key"),
                    quote_name("expires"),
                ),
                [key, connection.ops.adapt_datetimefield_value(now)],
            )
            return cursor.fetchone() is not None

    def _cull(self, db, cursor, now, num):
        if self._cull_frequency == 0:
            self.clear()
        else:
            connection = connections[db]
            table = connection.ops.quote_name(self._table)
            cursor.execute(
                "DELETE FROM %s WHERE %s < %%s"
                % (
                    table,
                    connection.ops.quote_name("expires"),
                ),
                [connection.ops.adapt_datetimefield_value(now)],
            )
            deleted_count = cursor.rowcount
            remaining_num = num - deleted_count
            if remaining_num > self._max_entries:
                cull_num = remaining_num // self._cull_frequency
                cursor.execute(
                    connection.ops.cache_key_culling_sql() % table, [cull_num]
                )
                last_cache_key = cursor.fetchone()
                if last_cache_key:
                    cursor.execute(
                        "DELETE FROM %s WHERE %s < %%s"
                        % (
                            table,
                            connection.ops.quote_name("cache_key"),
                        ),
                        [last_cache_key[0]],
                    )

    def clear(self):
        db = router.db_for_write(self.cache_model_class)
        connection = connections[db]
        table = connection.ops.quote_name(self._table)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM %s" % table)
