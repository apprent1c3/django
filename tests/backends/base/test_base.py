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
        Tests database debug logging when committing a transaction.

        Verifies that the start and end of a transaction are logged at the DEBUG level
        when DEBUG mode is enabled, and that the corresponding SQL queries are recorded
        in the queries log.
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
        Tests the logging of rollback operations in Django's database backend when DEBUG mode is enabled, verifying that the rollback query is executed and logged at the DEBUG level.
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
        Tests that no database logs are generated when an operation is rolled back and debug logging is not enabled.
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
        Execute a SQL query with multiple parameters on the database connection.

        Deletes rows from the Square table using a dummy condition and varying parameters. 
        The params argument can be used to specify the values to be used in the query. 
        If not provided, three default values are used. This function appears to test 
        database connectivity and prepared statement functionality with multiple parameters.
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
        Tests that the execute wrapper is correctly invoked and provides expected parameters.

        Verifies the wrapper function is called, the SQL query starts with 'SELECT', 
        parameters are None, and the context contains the connection object.
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
        """
        Tests whether the connection execute wrapper is properly invoked when executing many queries, verifying the wrapper's call arguments, including the SQL statement, parameters, and execution context.
        """
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
        """

        Tests that a database is successfully queried by executing a simple SELECT statement.

        Verifies that the query execution and result retrieval work as expected.

        """
        wrapper = self.mock_wrapper()
        with connection.execute_wrapper(wrapper):
            with connection.cursor() as cursor:
                sql = "SELECT 17" + connection.features.bare_select_suffix
                cursor.execute(sql)
                seventeen = cursor.fetchall()
                self.assertEqual(list(seventeen), [(17,)])
            self.call_executemany(connection)

    def test_nested_wrapper_invoked(self):
        """
        Tests the invocation of nested wrappers in the execute_wrapper context manager.

        Verifies that the inner wrapper is correctly called when using nested wrappers, 
        ensuring the wrapper's call count is incremented as expected for both execute and executemany operations.
        """
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
        """

        Tests that the outer execute wrapper blocks inner wrappers from being called,
        ensuring that only the outermost wrapper executes queries on the database.

        """
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
        Verifies that the SQL query executed by the database cursor is correctly reported by the wrapper.
        """
        wrapper = self.mock_wrapper()
        sql = "SELECT 'aloha'" + connection.features.bare_select_suffix
        with connection.execute_wrapper(wrapper), connection.cursor() as cursor:
            cursor.execute(sql)
        (_, reported_sql, _, _, _), _ = wrapper.call_args
        self.assertEqual(reported_sql, sql)

    def test_wrapper_connection_specific(self):
        """
        Tests the connection-specific execution of a wrapper function, 
        verifying its registration and deregistration with the connection.\"\"\"

        \"\"\" 
            This function tests whether a wrapper function is executed and 
            deregistered properly when using a specific database connection. 
            It ensures that the wrapper is correctly registered with the 
            connection before execution, and removed afterwards. 

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
        Tests that the database query wrapper correctly prepends a comment to the generated SQL query when executing a database query.
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
        connection.close()
        self.addCleanup(connection.close)

    def patch_settings_dict(self, conn_health_checks):
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
        """

        Tests that health checks for database connections are enabled and function correctly.

        Verifies the behavior of connection checks when a connection becomes unusable,
        ensuring a new connection is created when necessary.

        """
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
        """
        Tests that health checks are correctly enabled and handled when errors occur, 
        ensuring that database connections are properly closed and reused as needed.
        """
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

        Verifies the behavior of the database connection when health checks are disabled.

        Tests that the connection is reused even when its usability cannot be confirmed.

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
        """
        Tests the behavior of autocommit mode when connection health checks are enabled.

        Verifies that the connection is recreated only when necessary, i.e., when the
        current connection is unusable, and that the new connection is reused
        appropriately. Ensures that health checks are performed correctly when
        autocommit mode is toggled and queries are executed.
        """
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
        """
        Tests that the database connection state initialization method is idempotent, 
        i.e., it only calls the check database version supported method once, 
        even if called multiple times on the same database connection.
        """
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
