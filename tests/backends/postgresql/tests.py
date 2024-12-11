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

    Returns a new database connection with pooling disabled.

    The new connection is a copy of the existing connection, with the specified alias.
    It has the same settings as the original connection, but the pooling option is set to False.

    :param alias: Optional alias to use for the new connection.
    :rtype: Database connection object

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
        The _nodb_cursor() fallbacks to the default connection database when
        access to the 'postgres' database is not granted.
        """
        orig_connect = BaseDatabaseWrapper.connect

        def mocked_connect(self):
            """

            Simulates a database connection while ensuring that a database name is specified.

            This method checks if a database name is provided in the settings dictionary.
            If no database name is found, it raises a :exc:`DatabaseError`.
            Otherwise, it proceeds with the original connection process.

            :raises DatabaseError: If the database name is not specified in the settings.

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
        _nodb_cursor() re-raises authentication failure to the 'postgres' db
        when other connection to the PostgreSQL database isn't available.
        """

        def mocked_connect(self):
            raise DatabaseError()

        def mocked_all(self):
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
        with self.assertRaisesMessage(DatabaseError, "exception"):
            with connection._nodb_cursor():
                raise DatabaseError("exception")

    def test_database_name_too_long(self):
        """

        Tests that an ImproperlyConfigured exception is raised when the database name exceeds the maximum allowed length for PostgreSQL.

        This test verifies that the function correctly handles database names that are too long, ensuring they do not exceed the PostgreSQL limit.
        The test checks for the correct error message, which includes the problematic database name and the maximum allowed length.

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

        Tests that an ImproperlyConfigured exception is raised when the 'NAME' parameter 
        in the database settings is empty. This ensures that the DatabaseWrapper correctly 
        validates its input and provides a helpful error message when the configuration is 
        incomplete. The test verifies that the expected error message is raised, which 
        informs the user to supply either the 'NAME' or 'OPTIONS['service']' value. 

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

        Test that the service name is not used when connecting to the default database.

        This test case checks the behavior of the PostgreSQL database wrapper when
        the 'NAME' setting is not specified and the 'service' option is provided.
        It verifies that the connection is made to the default 'postgres' database
        and that the 'service' option is not included in the connection parameters.

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
        PostgreSQL shouldn't roll back SET TIME ZONE, even if the first
        transaction is rolled back (#17062).
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
        The connection wrapper shouldn't believe that autocommit is enabled
        after setting the time zone when AUTOCOMMIT is False (#21452).
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

            Establishes a new database connection and adds it to the pool of active connections.

            Returns:
                The newly established connection object.

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
        new_connection = no_pool_connection(alias="default_pool")
        new_connection.settings_dict["OPTIONS"]["pool"] = True
        try:
            self.assertIsNotNone(new_connection.pool)
        finally:
            new_connection.close_pool()

    @unittest.skipUnless(is_psycopg3, "psycopg3 specific test")
    def test_connect_pool_with_timezone(self):
        """
        Tests connection pooling with timezone awareness.

        Verifies that a database connection's timezone is updated correctly when using a connection pool.
        The test checks that the timezone of a new connection without pooling does not match the expected timezone,
        and then confirms that the timezone is updated correctly when using a connection pool.

        The test scenario involves setting a new timezone ('Africa/Nairobi') and verifying its application
        through a connection pool, ensuring that the timezone is correctly reflected in the database connection.

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

        Tests the behavior of the connection pool's health checks.

        This test case verifies that the connection pool's health checks can be enabled or disabled
        through the CONN_HEALTH_CHECKS setting in the connection's OPTIONS dictionary.
        It checks that when health checks are disabled, the pool's _check attribute is None,
        and when health checks are enabled, the _check attribute is not None.

        The test covers the scenario where the connection pool is created with health checks
        initially disabled, then enabled, to ensure the correct functionality of the health check
        mechanism.

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
        Tests the behavior of attempting to open a new connection within an atomic block.

        This test verifies that a :exc:`ProgrammingError` is raised when trying to establish a new connection
        while already inside an atomic block, as indicated by the error message \"Cannot open a new connection in an atomic block.\" 
        The test covers the scenario where the connection is set to use a pool and is currently in an atomic block and closed in a transaction.
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
        Tests that pooling does not support persistent connections.

        Verifies that attempting to use a connection pool with persistent connections
        configured raises an ImproperlyConfigured exception. This ensures that the
        pooling mechanism correctly handles incompatible settings.

        The test checks for the specific error message indicating that pooling does not
        support persistent connections. If the error message is raised as expected, the
        test passes; otherwise, it fails.

        This test is specific to psycopg3 and is skipped if the required conditions are
        not met.
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
        Tests that the pool setting is ignored when using psycopg2.

        This test validates that when the 'pool' option is enabled in the database settings,
        an ImproperlyConfigured exception is raised with a message indicating that
        database pooling requires psycopg version 3 or higher. The test ensures that
        psycopg2's limitation on connection pooling is handled correctly by raising an
        informative error message instead of attempting to establish a pooled connection.

        """
        new_connection = no_pool_connection()
        new_connection.settings_dict["OPTIONS"]["pool"] = True
        msg = "Database pooling requires psycopg >= 3"
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            new_connection.connect()

    def test_connect_isolation_level(self):
        """
        The transaction level can be configured with
        DATABASES ['OPTIONS']['isolation_level'].
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
        The session role can be configured with DATABASES
        ["OPTIONS"]["assume_role"].
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
        The server-side parameters binding role can be enabled with DATABASES
        ["OPTIONS"]["server_side_binding"].
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
        A custom cursor factory can be configured with DATABASES["options"]
        ["cursor_factory"].
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
        Tests that the connect method of a database connection does not check if the connection is usable when no pooling is used. 

        This test ensures that the connection is established without verifying its usability, 
        and then properly closes the connection after the test is complete, regardless of the outcome. 

        It validates that the is_usable method is not called during the connection process, confirming the expected behavior in a no-pooling scenario.
        """
        new_connection = no_pool_connection()
        try:
            with mock.patch.object(new_connection, "is_usable") as is_usable:
                new_connection.connect()
            is_usable.assert_not_called()
        finally:
            new_connection.close()

    def test_client_encoding_utf8_enforce(self):
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
        with connection.cursor() as cursor:
            cursor.execute("SELECT %s::text[]", (val,))
            return cursor.fetchone()[0]

    def test_select_ascii_array(self):
        """

        Tests the selection of an ASCII array.

        This method verifies that the _select method correctly selects and returns an array containing ASCII characters.
        It checks if the first element of the original array matches the first element of the selected array.

        """
        a = ["awef"]
        b = self._select(a)
        self.assertEqual(a[0], b[0])

    def test_select_unicode_array(self):
        """

        Tests the selection of an array containing a single unicode string.

        Verifies that the _select method correctly handles arrays with unicode characters,
        returning a new array with the same string as the original.

        This test ensures that the _select method preserves the original data, including
        unicode characters, and does not modify or corrupt the string in the process.

        """
        a = ["ᄲawef"]
        b = self._select(a)
        self.assertEqual(a[0], b[0])

    def test_lookup_cast(self):
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

        Test that the lookup_cast method for 'isnull' operations returns the expected result for various field types.

        The function checks the lookup_cast method of the DatabaseOperations class, specifically for the 'isnull' lookup type.
        It verifies that the method returns '%s' for different field types, which indicates a no-op (no operation) behavior.

        This test covers the following field types: CharField, EmailField, and TextField.

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
        Test the extraction of Psycopg version.

        This test case verifies that the psycopg_version function correctly extracts
        the major and minor version numbers from the PostgreSQL database version string.

        It covers two scenarios: one where the version string is a released version
        and another where it is a development version. The test checks that the
        major and minor version numbers are correctly extracted in both cases.
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

        Tests the functionality of copying data from the database using a cursor.

        Specifically, this test checks the behavior of the copy method in the context of
        psychog2 database when DEBUG mode is enabled. It verifies that the SQL query
        used for copying data from the 'django_session' table is correctly executed
        and logged in the connection queries.

        The test skips execution unless the psycopg3 library is being used.

        """
        copy_sql = "COPY django_session TO STDOUT (FORMAT CSV, HEADER)"
        with connection.cursor() as cursor:
            with cursor.copy(copy_sql) as copy:
                for row in copy:
                    pass
        self.assertEqual([q["sql"] for q in connection.queries], [copy_sql])

    def test_get_database_version(self):
        """
        Tests the retrieval of the PostgreSQL database version using the get_database_version method, verifying it returns a tuple containing the major and minor version numbers in the format (major, minor).
        """
        new_connection = no_pool_connection()
        new_connection.pg_version = 140009
        self.assertEqual(new_connection.get_database_version(), (14, 9))

    @mock.patch.object(connection, "get_database_version", return_value=(13,))
    def test_check_database_version_supported(self, mocked_get_database_version):
        msg = "PostgreSQL 14 or later is required (found 13)."
        with self.assertRaisesMessage(NotSupportedError, msg):
            connection.check_database_version_supported()
        self.assertTrue(mocked_get_database_version.called)

    def test_compose_sql_when_no_connection(self):
        """
        Tests the composition of SQL queries when no database connection pool is used.

        Checks that the :meth:`compose_sql` method correctly inserts parameter values into a SQL string,
        resulting in a valid SQL query. This test ensures the method works as expected without a connection pool.

        The test verifies the output of the composed SQL query matches the expected result, 
        and the connection is properly closed after use. 
        """
        new_connection = no_pool_connection()
        try:
            self.assertEqual(
                new_connection.ops.compose_sql("SELECT %s", ["test"]),
                "SELECT 'test'",
            )
        finally:
            new_connection.close()
