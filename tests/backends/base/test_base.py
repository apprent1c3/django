from unittest.mock import MagicMock, patch

from django.db import DEFAULT_DB_ALIAS, connection, connections, transaction
from django.db.backends.base.base import BaseDatabaseWrapper
from django.test import (
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    skipUnlessDBFeature,
)
from django.test.utils import CaptureQueriesContext, override_settings

from ..models import Person, Square


class DatabaseWrapperTests(SimpleTestCase):
    def test_repr(self):
        """

        Tests the string representation of a database connection.

        Verifies that the repr() function returns a string that accurately reflects the
        database connection's vendor and alias.

        The expected output format is `<DatabaseWrapper vendor=<vendor> alias='default'>`, 
        where `<vendor>` is the actual database vendor. This test ensures that the connection 
        object's string representation is correctly formatted and contains the expected information.

        """
        conn = connections[DEFAULT_DB_ALIAS]
        self.assertEqual(
            repr(conn),
            f"<DatabaseWrapper vendor={connection.vendor!r} alias='default'>",
        )

    def test_initialization_class_attributes(self):
        """
        The "initialization" class attributes like client_class and
        creation_class should be set on the class and reflected in the
        corresponding instance attributes of the instantiated backend.
        """
        conn = connections[DEFAULT_DB_ALIAS]
        conn_class = type(conn)
        attr_names = [
            ("client_class", "client"),
            ("creation_class", "creation"),
            ("features_class", "features"),
            ("introspection_class", "introspection"),
            ("ops_class", "ops"),
            ("validation_class", "validation"),
        ]
        for class_attr_name, instance_attr_name in attr_names:
            class_attr_value = getattr(conn_class, class_attr_name)
            self.assertIsNotNone(class_attr_value)
            instance_attr_value = getattr(conn, instance_attr_name)
            self.assertIsInstance(instance_attr_value, class_attr_value)

    def test_initialization_display_name(self):
        self.assertEqual(BaseDatabaseWrapper.display_name, "unknown")
        self.assertNotEqual(connection.display_name, "unknown")

    def test_get_database_version(self):
        with patch.object(BaseDatabaseWrapper, "__init__", return_value=None):
            msg = (
                "subclasses of BaseDatabaseWrapper may require a "
                "get_database_version() method."
            )
            with self.assertRaisesMessage(NotImplementedError, msg):
                BaseDatabaseWrapper().get_database_version()

    def test_check_database_version_supported_with_none_as_database_version(self):
        with patch.object(connection.features, "minimum_database_version", None):
            connection.check_database_version_supported()


class DatabaseWrapperLoggingTests(TransactionTestCase):
    available_apps = ["backends"]

    @override_settings(DEBUG=True)
    def test_commit_debug_log(self):
        """

        Tests the behavior of the database commit operation when debug logging is enabled.

        This test case verifies that the necessary database queries are executed and logged at the DEBUG level.
        It ensures that the transaction is properly started and committed, and that the corresponding SQL statements
        are recorded in the query log. Additionally, it checks that the log output matches the expected format for
        BEGIN and COMMIT statements.

        """
        conn = connections[DEFAULT_DB_ALIAS]
        with CaptureQueriesContext(conn):
            with self.assertLogs("django.db.backends", "DEBUG") as cm:
                with transaction.atomic():
                    Person.objects.create(first_name="first", last_name="last")

                self.assertGreaterEqual(len(conn.queries_log), 3)
                self.assertEqual(conn.queries_log[-3]["sql"], "BEGIN")
                self.assertRegex(
                    cm.output[0],
                    r"DEBUG:django.db.backends:\(\d+.\d{3}\) "
                    rf"BEGIN; args=None; alias={DEFAULT_DB_ALIAS}",
                )
                self.assertEqual(conn.queries_log[-1]["sql"], "COMMIT")
                self.assertRegex(
                    cm.output[-1],
                    r"DEBUG:django.db.backends:\(\d+.\d{3}\) "
                    rf"COMMIT; args=None; alias={DEFAULT_DB_ALIAS}",
                )

    @override_settings(DEBUG=True)
    def test_rollback_debug_log(self):
        """

        Tests the behavior of a database transaction when an exception is raised and 
        the DEBUG logging setting is enabled.

        Verifies that the transaction is properly rolled back and that a DEBUG-level 
        log message is generated to indicate the rollback.

        This test ensures that the database connection correctly handles the rollback 
        operation and that the logging mechanism accurately reports the event.

        """
        conn = connections[DEFAULT_DB_ALIAS]
        with CaptureQueriesContext(conn):
            with self.assertLogs("django.db.backends", "DEBUG") as cm:
                with self.assertRaises(Exception), transaction.atomic():
                    Person.objects.create(first_name="first", last_name="last")
                    raise Exception("Force rollback")

                self.assertEqual(conn.queries_log[-1]["sql"], "ROLLBACK")
                self.assertRegex(
                    cm.output[-1],
                    r"DEBUG:django.db.backends:\(\d+.\d{3}\) "
                    rf"ROLLBACK; args=None; alias={DEFAULT_DB_ALIAS}",
                )

    def test_no_logs_without_debug(self):
        """
        #: Test that no database logs are generated when an operation fails without debug mode enabled.
        #: 
        #: This function simulates a failed database transaction and verifies that no log messages are 
        #: recorded at the DEBUG level for the 'django.db.backends' logger. It also checks that no 
        #: queries are logged in the database connection. The test case ensures that the database 
        #: operations are properly rolled back when an exception occurs, and no unnecessary log 
        #: entries are created.
        """
        with self.assertNoLogs("django.db.backends", "DEBUG"):
            with self.assertRaises(Exception), transaction.atomic():
                Person.objects.create(first_name="first", last_name="last")
                raise Exception("Force rollback")

            conn = connections[DEFAULT_DB_ALIAS]
            self.assertEqual(len(conn.queries_log), 0)


class ExecuteWrapperTests(TestCase):
    @staticmethod
    def call_execute(connection, params=None):
        ret_val = "1" if params is None else "%s"
        sql = "SELECT " + ret_val + connection.features.bare_select_suffix
        with connection.cursor() as cursor:
            cursor.execute(sql, params)

    def call_executemany(self, connection, params=None):
        # executemany() must use an update query. Make sure it does nothing
        # by putting a false condition in the WHERE clause.
        """

        Execute a SQL query with multiple parameters to test database connection.

        This method sends a dummy DELETE query to the database. The query always evaluates to false,
        so no actual data is deleted. It is designed to test the connection to the database.

        :param connection: A database connection object.
        :param params: Optional list of tuples, where each tuple contains a single parameter.
                       If not provided, default parameters will be used.

        """
        sql = "DELETE FROM {} WHERE 0=1 AND 0=%s".format(Square._meta.db_table)
        if params is None:
            params = [(i,) for i in range(3)]
        with connection.cursor() as cursor:
            cursor.executemany(sql, params)

    @staticmethod
    def mock_wrapper():
        return MagicMock(side_effect=lambda execute, *args: execute(*args))

    def test_wrapper_invoked(self):
        """
        Verifies that a database query execution wrapper is properly invoked.

        This test checks that a wrapper function is called when executing a database query,
        and that the wrapper receives the correct arguments, including the SQL query string,
        parameters, and execution context. The test asserts that the wrapper is invoked with
        a SELECT query, no query parameters, and a single execution (not multiple executions).
        The test also verifies that the wrapper has access to the underlying database connection.

        The test covers the basic functionality of a query execution wrapper, ensuring that it
        is correctly integrated with the database query execution mechanism.
        """
        wrapper = self.mock_wrapper()
        with connection.execute_wrapper(wrapper):
            self.call_execute(connection)
        self.assertTrue(wrapper.called)
        (_, sql, params, many, context), _ = wrapper.call_args
        self.assertIn("SELECT", sql)
        self.assertIsNone(params)
        self.assertIs(many, False)
        self.assertEqual(context["connection"], connection)

    def test_wrapper_invoked_many(self):
        wrapper = self.mock_wrapper()
        with connection.execute_wrapper(wrapper):
            self.call_executemany(connection)
        self.assertTrue(wrapper.called)
        (_, sql, param_list, many, context), _ = wrapper.call_args
        self.assertIn("DELETE", sql)
        self.assertIsInstance(param_list, (list, tuple))
        self.assertIs(many, True)
        self.assertEqual(context["connection"], connection)

    def test_database_queried(self):
        wrapper = self.mock_wrapper()
        with connection.execute_wrapper(wrapper):
            with connection.cursor() as cursor:
                sql = "SELECT 17" + connection.features.bare_select_suffix
                cursor.execute(sql)
                seventeen = cursor.fetchall()
                self.assertEqual(list(seventeen), [(17,)])
            self.call_executemany(connection)

    def test_nested_wrapper_invoked(self):
        outer_wrapper = self.mock_wrapper()
        inner_wrapper = self.mock_wrapper()
        with (
            connection.execute_wrapper(outer_wrapper),
            connection.execute_wrapper(inner_wrapper),
        ):
            self.call_execute(connection)
            self.assertEqual(inner_wrapper.call_count, 1)
            self.call_executemany(connection)
            self.assertEqual(inner_wrapper.call_count, 2)

    def test_outer_wrapper_blocks(self):
        def blocker(*args):
            pass

        wrapper = self.mock_wrapper()
        c = connection  # This alias shortens the next line.
        with (
            c.execute_wrapper(wrapper),
            c.execute_wrapper(blocker),
            c.execute_wrapper(wrapper),
        ):
            with c.cursor() as cursor:
                cursor.execute("The database never sees this")
                self.assertEqual(wrapper.call_count, 1)
                cursor.executemany("The database never sees this %s", [("either",)])
                self.assertEqual(wrapper.call_count, 2)

    def test_wrapper_gets_sql(self):
        """

        Tests that the wrapper correctly captures and reports the SQL query executed.

        This test verifies that when a SQL query is executed within the context of the wrapper,
        the wrapper accurately records and reports the SQL query as executed, including any
        necessary suffixes required by the database connection features.

        """
        wrapper = self.mock_wrapper()
        sql = "SELECT 'aloha'" + connection.features.bare_select_suffix
        with connection.execute_wrapper(wrapper), connection.cursor() as cursor:
            cursor.execute(sql)
        (_, reported_sql, _, _, _), _ = wrapper.call_args
        self.assertEqual(reported_sql, sql)

    def test_wrapper_connection_specific(self):
        """

        Tests the usage of an execute wrapper within a specific database connection.

        This function verifies that the execute wrapper is properly set and called 
        for a specific database connection, and checks the expected behavior when 
        the connection is closed. It ensures that the wrapper is only associated 
        with the connection it was set for, and that it is properly reset once 
        the connection is closed.

        The test covers the following scenarios:
        - The execute wrapper is correctly assigned to the connection.
        - The execute wrapper is not called within the scope of the connection.
        - The execute wrapper is properly removed from the connection once the 
          connection is closed.
        - The execute wrapper is not associated with other connections.

        """
        wrapper = self.mock_wrapper()
        with connections["other"].execute_wrapper(wrapper):
            self.assertEqual(connections["other"].execute_wrappers, [wrapper])
            self.call_execute(connection)
        self.assertFalse(wrapper.called)
        self.assertEqual(connection.execute_wrappers, [])
        self.assertEqual(connections["other"].execute_wrappers, [])

    def test_wrapper_debug(self):
        """

        Tests that a custom SQL comment is successfully prepended to the query when using the execute wrapper.

        This test case verifies that the provided wrapper function correctly modifies the SQL query by adding a comment before execution.
        The comment is then checked to be present in the captured query, ensuring the wrapper's functionality.

        """
        def wrap_with_comment(execute, sql, params, many, context):
            return execute(f"/* My comment */ {sql}", params, many, context)

        with CaptureQueriesContext(connection) as ctx:
            with connection.execute_wrapper(wrap_with_comment):
                list(Person.objects.all())
        last_query = ctx.captured_queries[-1]["sql"]
        self.assertTrue(last_query.startswith("/* My comment */"))


class ConnectionHealthChecksTests(SimpleTestCase):
    databases = {"default"}

    def setUp(self):
        # All test cases here need newly configured and created connections.
        # Use the default db connection for convenience.
        """
        Sets up the test environment by closing the existing database connection and ensuring it is closed after the test is completed, regardless of the test outcome, to prevent resource leaks and ensure a clean state for subsequent tests.
        """
        connection.close()
        self.addCleanup(connection.close)

    def patch_settings_dict(self, conn_health_checks):
        """
        Patches the database connection settings dictionary with specified health check settings.

        Temporarily modifies the connection settings to disable connection aging and set the specified health checks. The original settings are restored when the patch is stopped, which is automatically done during cleanup.

        :param conn_health_checks: Dictionary of health check settings to apply to the connection.

        """
        self.settings_dict_patcher = patch.dict(
            connection.settings_dict,
            {
                **connection.settings_dict,
                "CONN_MAX_AGE": None,
                "CONN_HEALTH_CHECKS": conn_health_checks,
            },
        )
        self.settings_dict_patcher.start()
        self.addCleanup(self.settings_dict_patcher.stop)

    def run_query(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 42" + connection.features.bare_select_suffix)

    @skipUnlessDBFeature("test_db_allows_multiple_connections")
    def test_health_checks_enabled(self):
        self.patch_settings_dict(conn_health_checks=True)
        self.assertIsNone(connection.connection)
        # Newly created connections are considered healthy without performing
        # the health check.
        with patch.object(connection, "is_usable", side_effect=AssertionError):
            self.run_query()

        old_connection = connection.connection
        # Simulate request_finished.
        connection.close_if_unusable_or_obsolete()
        self.assertIs(old_connection, connection.connection)

        # Simulate connection health check failing.
        with patch.object(
            connection, "is_usable", return_value=False
        ) as mocked_is_usable:
            self.run_query()
            new_connection = connection.connection
            # A new connection is established.
            self.assertIsNot(new_connection, old_connection)
            # Only one health check per "request" is performed, so the next
            # query will carry on even if the health check fails. Next query
            # succeeds because the real connection is healthy and only the
            # health check failure is mocked.
            self.run_query()
            self.assertIs(new_connection, connection.connection)
        self.assertEqual(mocked_is_usable.call_count, 1)

        # Simulate request_finished.
        connection.close_if_unusable_or_obsolete()
        # The underlying connection is being reused further with health checks
        # succeeding.
        self.run_query()
        self.run_query()
        self.assertIs(new_connection, connection.connection)

    @skipUnlessDBFeature("test_db_allows_multiple_connections")
    def test_health_checks_enabled_errors_occurred(self):
        self.patch_settings_dict(conn_health_checks=True)
        self.assertIsNone(connection.connection)
        # Newly created connections are considered healthy without performing
        # the health check.
        with patch.object(connection, "is_usable", side_effect=AssertionError):
            self.run_query()

        old_connection = connection.connection
        # Simulate errors_occurred.
        connection.errors_occurred = True
        # Simulate request_started (the connection is healthy).
        connection.close_if_unusable_or_obsolete()
        # Persistent connections are enabled.
        self.assertIs(old_connection, connection.connection)
        # No additional health checks after the one in
        # close_if_unusable_or_obsolete() are executed during this "request"
        # when running queries.
        with patch.object(connection, "is_usable", side_effect=AssertionError):
            self.run_query()

    @skipUnlessDBFeature("test_db_allows_multiple_connections")
    def test_health_checks_disabled(self):
        """
        Tests the behavior of the database connection when health checks are disabled.

            This test case verifies that when health checks are turned off, the connection
            is not replaced even if it is unusable. It checks that the connection remains
            the same after attempting to run queries, closing the connection if it's
            unusable or obsolete, and after multiple query executions.

            The test emulates a scenario where the connection's usability check raises an
            exception, ensuring that the connection is not replaced in such cases when
            health checks are disabled. The goal is to confirm that the connection
            persistence behavior is correct under these specific conditions.
        """
        self.patch_settings_dict(conn_health_checks=False)
        self.assertIsNone(connection.connection)
        # Newly created connections are considered healthy without performing
        # the health check.
        with patch.object(connection, "is_usable", side_effect=AssertionError):
            self.run_query()

        old_connection = connection.connection
        # Simulate request_finished.
        connection.close_if_unusable_or_obsolete()
        # Persistent connections are enabled (connection is not).
        self.assertIs(old_connection, connection.connection)
        # Health checks are not performed.
        with patch.object(connection, "is_usable", side_effect=AssertionError):
            self.run_query()
            # Health check wasn't performed and the connection is unchanged.
            self.assertIs(old_connection, connection.connection)
            self.run_query()
            # The connection is unchanged after the next query either during
            # the current "request".
            self.assertIs(old_connection, connection.connection)

    @skipUnlessDBFeature("test_db_allows_multiple_connections")
    def test_set_autocommit_health_checks_enabled(self):
        self.patch_settings_dict(conn_health_checks=True)
        self.assertIsNone(connection.connection)
        # Newly created connections are considered healthy without performing
        # the health check.
        with patch.object(connection, "is_usable", side_effect=AssertionError):
            # Simulate outermost atomic block: changing autocommit for
            # a connection.
            connection.set_autocommit(False)
            self.run_query()
            connection.commit()
            connection.set_autocommit(True)

        old_connection = connection.connection
        # Simulate request_finished.
        connection.close_if_unusable_or_obsolete()
        # Persistent connections are enabled.
        self.assertIs(old_connection, connection.connection)

        # Simulate connection health check failing.
        with patch.object(
            connection, "is_usable", return_value=False
        ) as mocked_is_usable:
            # Simulate outermost atomic block: changing autocommit for
            # a connection.
            connection.set_autocommit(False)
            new_connection = connection.connection
            self.assertIsNot(new_connection, old_connection)
            # Only one health check per "request" is performed, so a query will
            # carry on even if the health check fails. This query succeeds
            # because the real connection is healthy and only the health check
            # failure is mocked.
            self.run_query()
            connection.commit()
            connection.set_autocommit(True)
            # The connection is unchanged.
            self.assertIs(new_connection, connection.connection)
        self.assertEqual(mocked_is_usable.call_count, 1)

        # Simulate request_finished.
        connection.close_if_unusable_or_obsolete()
        # The underlying connection is being reused further with health checks
        # succeeding.
        connection.set_autocommit(False)
        self.run_query()
        connection.commit()
        connection.set_autocommit(True)
        self.assertIs(new_connection, connection.connection)


class MultiDatabaseTests(TestCase):
    databases = {"default", "other"}

    def test_multi_database_init_connection_state_called_once(self):
        for db in self.databases:
            with self.subTest(database=db):
                with patch.object(connections[db], "commit", return_value=None):
                    with patch.object(
                        connections[db],
                        "check_database_version_supported",
                    ) as mocked_check_database_version_supported:
                        connections[db].init_connection_state()
                        after_first_calls = len(
                            mocked_check_database_version_supported.mock_calls
                        )
                        connections[db].init_connection_state()
                        self.assertEqual(
                            len(mocked_check_database_version_supported.mock_calls),
                            after_first_calls,
                        )
