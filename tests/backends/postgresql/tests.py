import copy
import unittest
from io import StringIO
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.db import (
    DEFAULT_DB_ALIAS,
    DatabaseError,
    NotSupportedError,
    ProgrammingError,
    connection,
    connections,
)
from django.db.backends.base.base import BaseDatabaseWrapper
from django.test import TestCase, override_settings

try:
    from django.db.backends.postgresql.psycopg_any import errors, is_psycopg3
except ImportError:
    is_psycopg3 = False


def no_pool_connection(alias=None):
    """
    This is a comment
    """
    new_connection = connection.copy(alias)
    new_connection.settings_dict = copy.deepcopy(connection.settings_dict)
    # Ensure that the second connection circumvents the pool, this is kind
    # of a hack, but we cannot easily change the pool connections.
    new_connection.settings_dict["OPTIONS"]["pool"] = False
    return new_connection


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL tests")
class Tests(TestCase):
    databases = {"default", "other"}

    def test_nodb_cursor(self):
        """
        This is a comment
        """
        orig_connect = BaseDatabaseWrapper.connect

        def mocked_connect(self):
            """
            This is a comment
            """
            if self.settings_dict["NAME"] is None:
                raise DatabaseError()
            return orig_connect(self)

        with connection._nodb_cursor() as cursor:
            self.assertIs(cursor.closed, False)
            self.assertIsNotNone(cursor.db.connection)
            self.assertIsNone(cursor.db.settings_dict["NAME"])
        self.assertIs(cursor.closed, True)
        self.assertIsNone(cursor.db.connection)

        # Now assume the 'postgres' db isn't available
        msg = (
            "Normally Django will use a connection to the 'postgres' database "
            "to avoid running initialization queries against the production "
            "database when it's not needed (for example, when running tests). "
            "Django was unable to create a connection to the 'postgres' "
            "database and will use the first PostgreSQL database instead."
        )
        with self.assertWarnsMessage(RuntimeWarning, msg):
            with mock.patch(
                "django.db.backends.base.base.BaseDatabaseWrapper.connect",
                side_effect=mocked_connect,
                autospec=True,
            ):
                with mock.patch.object(
                    connection,
                    "settings_dict",
                    {**connection.settings_dict, "NAME": "postgres"},
                ):
                    with connection._nodb_cursor() as cursor:
                        self.assertIs(cursor.closed, False)
                        self.assertIsNotNone(cursor.db.connection)
        self.assertIs(cursor.closed, True)
        self.assertIsNone(cursor.db.connection)
        self.assertIsNotNone(cursor.db.settings_dict["NAME"])
        self.assertEqual(
            cursor.db.settings_dict["NAME"], connections["other"].settings_dict["NAME"]
        )
        # Cursor is yielded only for the first PostgreSQL database.
        with self.assertWarnsMessage(RuntimeWarning, msg):
            with mock.patch(
                "django.db.backends.base.base.BaseDatabaseWrapper.connect",
                side_effect=mocked_connect,
                autospec=True,
            ):
                with connection._nodb_cursor() as cursor:
                    self.assertIs(cursor.closed, False)
                    self.assertIsNotNone(cursor.db.connection)

    def test_nodb_cursor_raises_postgres_authentication_failure(self):
        """
        This is a comment
        """

        def mocked_connect(self):
            """
            This is a comment
            """
            raise DatabaseError()

        def mocked_all(self):
            """
            This is a comment
            """
            test_connection = copy.copy(connections[DEFAULT_DB_ALIAS])
            test_connection.settings_dict = copy.deepcopy(connection.settings_dict)
            test_connection.settings_dict["NAME"] = "postgres"
            return [test_connection]

        msg = (
            "Normally Django will use a connection to the 'postgres' database "
            "to avoid running initialization queries against the production "
            "database when it's not needed (for example, when running tests). "
            "Django was unable to create a connection to the 'postgres' "
            "database and will use the first PostgreSQL database instead."
        )
        with self.assertWarnsMessage(RuntimeWarning, msg):
            mocker_connections_all = mock.patch(
                "django.utils.connection.BaseConnectionHandler.all",
                side_effect=mocked_all,
                autospec=True,
            )
            mocker_connect = mock.patch(
                "django.db.backends.base.base.BaseDatabaseWrapper.connect",
                side_effect=mocked_connect,
                autospec=True,
            )
            with mocker_connections_all, mocker_connect:
                with self.assertRaises(DatabaseError):
                    with connection._nodb_cursor():
                        pass

    def test_nodb_cursor_reraise_exceptions(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(DatabaseError, "exception"):
            with connection._nodb_cursor():
                raise DatabaseError("exception")

    def test_database_name_too_long(self):
        """
        This is a comment
        """
        from django.db.backends.postgresql.base import DatabaseWrapper

        settings = connection.settings_dict.copy()
        max_name_length = connection.ops.max_name_length()
        settings["NAME"] = "a" + (max_name_length * "a")
        msg = (
            "The database name '%s' (%d characters) is longer than "
            "PostgreSQL's limit of %s characters. Supply a shorter NAME in "
            "settings.DATABASES."
        ) % (settings["NAME"], max_name_length + 1, max_name_length)
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            DatabaseWrapper(settings).get_connection_params()

    def test_database_name_empty(self):
        """
        This is a comment
        """
        from django.db.backends.postgresql.base import DatabaseWrapper

        settings = connection.settings_dict.copy()
        settings["NAME"] = ""
        msg = (
            "settings.DATABASES is improperly configured. Please supply the "
            "NAME or OPTIONS['service'] value."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            DatabaseWrapper(settings).get_connection_params()

    def test_service_name(self):
        """
        This is a comment
        """
        from django.db.backends.postgresql.base import DatabaseWrapper

        settings = connection.settings_dict.copy()
        settings["OPTIONS"] = {"service": "my_service"}
        settings["NAME"] = ""
        params = DatabaseWrapper(settings).get_connection_params()
        self.assertEqual(params["service"], "my_service")
        self.assertNotIn("database", params)

    def test_service_name_default_db(self):
        # None is used to connect to the default 'postgres' db.
        """
        This is a comment
        """
        from django.db.backends.postgresql.base import DatabaseWrapper

        settings = connection.settings_dict.copy()
        settings["NAME"] = None
        settings["OPTIONS"] = {"service": "django_test"}
        params = DatabaseWrapper(settings).get_connection_params()
        self.assertEqual(params["dbname"], "postgres")
        self.assertNotIn("service", params)

    def test_connect_and_rollback(self):
        """
        This is a comment
        """
        new_connection = no_pool_connection()
        try:
            # Ensure the database default time zone is different than
            # the time zone in new_connection.settings_dict. We can
            # get the default time zone by reset & show.
            with new_connection.cursor() as cursor:
                cursor.execute("RESET TIMEZONE")
                cursor.execute("SHOW TIMEZONE")
                db_default_tz = cursor.fetchone()[0]
            new_tz = "Europe/Paris" if db_default_tz == "UTC" else "UTC"
            new_connection.close()

            # Invalidate timezone name cache, because the setting_changed
            # handler cannot know about new_connection.
            del new_connection.timezone_name

            # Fetch a new connection with the new_tz as default
            # time zone, run a query and rollback.
            with self.settings(TIME_ZONE=new_tz):
                new_connection.set_autocommit(False)
                new_connection.rollback()

                # Now let's see if the rollback rolled back the SET TIME ZONE.
                with new_connection.cursor() as cursor:
                    cursor.execute("SHOW TIMEZONE")
                    tz = cursor.fetchone()[0]
                self.assertEqual(new_tz, tz)

        finally:
            new_connection.close()

    def test_connect_non_autocommit(self):
        """
        This is a comment
        """
        new_connection = no_pool_connection()
        new_connection.settings_dict["AUTOCOMMIT"] = False

        try:
            # Open a database connection.
            with new_connection.cursor():
                self.assertFalse(new_connection.get_autocommit())
        finally:
            new_connection.close()

    @unittest.skipUnless(is_psycopg3, "psycopg3 specific test")
    def test_connect_pool(self):
        """
        This is a comment
        """
        from psycopg_pool import PoolTimeout

        new_connection = no_pool_connection(alias="default_pool")
        new_connection.settings_dict["OPTIONS"]["pool"] = {
            "min_size": 0,
            "max_size": 2,
            "timeout": 5,
        }
        self.assertIsNotNone(new_connection.pool)

        connections = []

        def get_connection():
            # copy() reuses the existing alias and as such the same pool.
            """
            This is a comment
            """
            conn = new_connection.copy()
            conn.connect()
            connections.append(conn)
            return conn

        try:
            connection_1 = get_connection()  # First connection.
            connection_1_backend_pid = connection_1.connection.info.backend_pid
            get_connection()  # Get the second connection.
            with self.assertRaises(PoolTimeout):
                # The pool has a maximum of 2 connections.
                get_connection()

            connection_1.close()  # Release back to the pool.
            connection_3 = get_connection()
            # Reuses the first connection as it is available.
            self.assertEqual(
                connection_3.connection.info.backend_pid, connection_1_backend_pid
            )
        finally:
            # Release all connections back to the pool.
            for conn in connections:
                conn.close()
            new_connection.close_pool()

    @unittest.skipUnless(is_psycopg3, "psycopg3 specific test")
    def test_connect_pool_set_to_true(self):
        """
        This is a comment
        """
        new_connection = no_pool_connection(alias="default_pool")
        new_connection.settings_dict["OPTIONS"]["pool"] = True
        try:
            self.assertIsNotNone(new_connection.pool)
        finally:
            new_connection.close_pool()

    @unittest.skipUnless(is_psycopg3, "psycopg3 specific test")
    def test_connect_pool_with_timezone(self):
        """
        This is a comment
        """
        new_time_zone = "Africa/Nairobi"
        new_connection = no_pool_connection(alias="default_pool")

        try:
            with new_connection.cursor() as cursor:
                cursor.execute("SHOW TIMEZONE")
                tz = cursor.fetchone()[0]
                self.assertNotEqual(new_time_zone, tz)
        finally:
            new_connection.close()

        del new_connection.timezone_name
        new_connection.settings_dict["OPTIONS"]["pool"] = True
        try:
            with self.settings(TIME_ZONE=new_time_zone):
                with new_connection.cursor() as cursor:
                    cursor.execute("SHOW TIMEZONE")
                    tz = cursor.fetchone()[0]
                    self.assertEqual(new_time_zone, tz)
        finally:
            new_connection.close()
            new_connection.close_pool()

    @unittest.skipUnless(is_psycopg3, "psycopg3 specific test")
    def test_pooling_health_checks(self):
        """
        This is a comment
        """
        new_connection = no_pool_connection(alias="default_pool")
        new_connection.settings_dict["OPTIONS"]["pool"] = True
        new_connection.settings_dict["CONN_HEALTH_CHECKS"] = False

        try:
            self.assertIsNone(new_connection.pool._check)
        finally:
            new_connection.close_pool()

        new_connection.settings_dict["CONN_HEALTH_CHECKS"] = True
        try:
            self.assertIsNotNone(new_connection.pool._check)
        finally:
            new_connection.close_pool()

    @unittest.skipUnless(is_psycopg3, "psycopg3 specific test")
    def test_cannot_open_new_connection_in_atomic_block(self):
        """
        This is a comment
        """
        new_connection = no_pool_connection(alias="default_pool")
        new_connection.settings_dict["OPTIONS"]["pool"] = True

        msg = "Cannot open a new connection in an atomic block."
        new_connection.in_atomic_block = True
        new_connection.closed_in_transaction = True
        with self.assertRaisesMessage(ProgrammingError, msg):
            new_connection.ensure_connection()

    @unittest.skipUnless(is_psycopg3, "psycopg3 specific test")
    def test_pooling_not_support_persistent_connections(self):
        """
        This is a comment
        """
        new_connection = no_pool_connection(alias="default_pool")
        new_connection.settings_dict["OPTIONS"]["pool"] = True
        new_connection.settings_dict["CONN_MAX_AGE"] = 10
        msg = "Pooling doesn't support persistent connections."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            new_connection.pool

    @unittest.skipIf(is_psycopg3, "psycopg2 specific test")
    def test_connect_pool_setting_ignored_for_psycopg2(self):
        """
        This is a comment
        """
        new_connection = no_pool_connection()
        new_connection.settings_dict["OPTIONS"]["pool"] = True
        msg = "Database pooling requires psycopg >= 3"
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            new_connection.connect()

    def test_connect_isolation_level(self):
        """
        This is a comment
        """
        from django.db.backends.postgresql.psycopg_any import IsolationLevel

        # Since this is a django.test.TestCase, a transaction is in progress
        # and the isolation level isn't reported as 0. This test assumes that
        # PostgreSQL is configured with the default isolation level.
        # Check the level on the psycopg connection, not the Django wrapper.
        self.assertIsNone(connection.connection.isolation_level)

        new_connection = no_pool_connection()
        new_connection.settings_dict["OPTIONS"][
            "isolation_level"
        ] = IsolationLevel.SERIALIZABLE
        try:
            # Start a transaction so the isolation level isn't reported as 0.
            new_connection.set_autocommit(False)
            # Check the level on the psycopg connection, not the Django wrapper.
            self.assertEqual(
                new_connection.connection.isolation_level,
                IsolationLevel.SERIALIZABLE,
            )
        finally:
            new_connection.close()

    def test_connect_invalid_isolation_level(self):
        """
        This is a comment
        """
        self.assertIsNone(connection.connection.isolation_level)
        new_connection = no_pool_connection()
        new_connection.settings_dict["OPTIONS"]["isolation_level"] = -1
        msg = (
            "Invalid transaction isolation level -1 specified. Use one of the "
            "psycopg.IsolationLevel values."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            new_connection.ensure_connection()

    def test_connect_role(self):
        """
        This is a comment
        """
        try:
            custom_role = "django_nonexistent_role"
            new_connection = no_pool_connection()
            new_connection.settings_dict["OPTIONS"]["assume_role"] = custom_role
            msg = f'role "{custom_role}" does not exist'
            with self.assertRaisesMessage(errors.InvalidParameterValue, msg):
                new_connection.connect()
        finally:
            new_connection.close()

    @unittest.skipUnless(is_psycopg3, "psycopg3 specific test")
    def test_connect_server_side_binding(self):
        """
        This is a comment
        """
        from django.db.backends.postgresql.base import ServerBindingCursor

        new_connection = no_pool_connection()
        new_connection.settings_dict["OPTIONS"]["server_side_binding"] = True
        try:
            new_connection.connect()
            self.assertEqual(
                new_connection.connection.cursor_factory,
                ServerBindingCursor,
            )
        finally:
            new_connection.close()

    def test_connect_custom_cursor_factory(self):
        """
        This is a comment
        """
        from django.db.backends.postgresql.base import Cursor

        class MyCursor(Cursor):
            pass

        new_connection = no_pool_connection()
        new_connection.settings_dict["OPTIONS"]["cursor_factory"] = MyCursor
        try:
            new_connection.connect()
            self.assertEqual(new_connection.connection.cursor_factory, MyCursor)
        finally:
            new_connection.close()

    def test_connect_no_is_usable_checks(self):
        """
        This is a comment
        """
        new_connection = no_pool_connection()
        try:
            with mock.patch.object(new_connection, "is_usable") as is_usable:
                new_connection.connect()
            is_usable.assert_not_called()
        finally:
            new_connection.close()

    def test_client_encoding_utf8_enforce(self):
        """
        This is a comment
        """
        new_connection = no_pool_connection()
        new_connection.settings_dict["OPTIONS"]["client_encoding"] = "iso-8859-2"
        try:
            new_connection.connect()
            if is_psycopg3:
                self.assertEqual(new_connection.connection.info.encoding, "utf-8")
            else:
                self.assertEqual(new_connection.connection.encoding, "UTF8")
        finally:
            new_connection.close()

    def _select(self, val):
        """
        This is a comment
        """
        with connection.cursor() as cursor:
            cursor.execute("SELECT %s::text[]", (val,))
            return cursor.fetchone()[0]

    def test_select_ascii_array(self):
        """
        This is a comment
        """
        a = ["awef"]
        b = self._select(a)
        self.assertEqual(a[0], b[0])

    def test_select_unicode_array(self):
        """
        This is a comment
        """
        a = ["ᄲawef"]
        b = self._select(a)
        self.assertEqual(a[0], b[0])

    def test_lookup_cast(self):
        """
        This is a comment
        """
        from django.db.backends.postgresql.operations import DatabaseOperations

        do = DatabaseOperations(connection=None)
        lookups = (
            "iexact",
            "contains",
            "icontains",
            "startswith",
            "istartswith",
            "endswith",
            "iendswith",
            "regex",
            "iregex",
        )
        for lookup in lookups:
            with self.subTest(lookup=lookup):
                self.assertIn("::text", do.lookup_cast(lookup))

    def test_lookup_cast_isnull_noop(self):
        """
        This is a comment
        """
        from django.db.backends.postgresql.operations import DatabaseOperations

        do = DatabaseOperations(connection=None)
        # Using __isnull lookup doesn't require casting.
        tests = [
            "CharField",
            "EmailField",
            "TextField",
        ]
        for field_type in tests:
            with self.subTest(field_type=field_type):
                self.assertEqual(do.lookup_cast("isnull", field_type), "%s")

    def test_correct_extraction_psycopg_version(self):
        """
        This is a comment
        """
        from django.db.backends.postgresql.base import Database, psycopg_version

        with mock.patch.object(Database, "__version__", "4.2.1 (dt dec pq3 ext lo64)"):
            self.assertEqual(psycopg_version(), (4, 2, 1))
        with mock.patch.object(
            Database, "__version__", "4.2b0.dev1 (dt dec pq3 ext lo64)"
        ):
            self.assertEqual(psycopg_version(), (4, 2))

    @override_settings(DEBUG=True)
    @unittest.skipIf(is_psycopg3, "psycopg2 specific test")
    def test_copy_to_expert_cursors(self):
        """
        This is a comment
        """
        out = StringIO()
        copy_expert_sql = "COPY django_session TO STDOUT (FORMAT CSV, HEADER)"
        with connection.cursor() as cursor:
            cursor.copy_expert(copy_expert_sql, out)
            cursor.copy_to(out, "django_session")
        self.assertEqual(
            [q["sql"] for q in connection.queries],
            [copy_expert_sql, "COPY django_session TO STDOUT"],
        )

    @override_settings(DEBUG=True)
    @unittest.skipUnless(is_psycopg3, "psycopg3 specific test")
    def test_copy_cursors(self):
        """
        This is a comment
        """
        copy_sql = "COPY django_session TO STDOUT (FORMAT CSV, HEADER)"
        with connection.cursor() as cursor:
            with cursor.copy(copy_sql) as copy:
                for row in copy:
                    pass
        self.assertEqual([q["sql"] for q in connection.queries], [copy_sql])

    def test_get_database_version(self):
        """
        This is a comment
        """
        new_connection = no_pool_connection()
        new_connection.pg_version = 140009
        self.assertEqual(new_connection.get_database_version(), (14, 9))

    @mock.patch.object(connection, "get_database_version", return_value=(13,))
    def test_check_database_version_supported(self, mocked_get_database_version):
        """
        This is a comment
        """
        msg = "PostgreSQL 14 or later is required (found 13)."
        with self.assertRaisesMessage(NotSupportedError, msg):
            connection.check_database_version_supported()
        self.assertTrue(mocked_get_database_version.called)

    def test_compose_sql_when_no_connection(self):
        """
        This is a comment
        """
        new_connection = no_pool_connection()
        try:
            self.assertEqual(
                new_connection.ops.compose_sql("SELECT %s", ["test"]),
                "SELECT 'test'",
            )
        finally:
            new_connection.close()
