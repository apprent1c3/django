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
        Checks that class attributes related to backend initialization are correctly set and reflected in instance attributes of the backend. Verifies that these attributes have a valid value and the correct type.
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

        Tests that database queries related to atomic transaction are correctly logged at the DEBUG level.

        Verifies that the log messages for BEGIN and COMMIT statements are emitted and contain the expected information.

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
        Tests that a rollback is properly logged at the DEBUG level when an exception occurs within a transaction.
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
        Checks that no database queries are logged when an atomic transaction is rolled back without debug logging enabled.
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

        Executes a SQL query that deletes rows from the Square table using executemany.

        The query is a placeholder that always evaluates to false, effectively 
        not deleting any rows, while still exercising the executemany functionality.

        :param connection: Database connection object
        :param params: Optional list of parameters to pass to executemany, defaults to a list of integers from 0 to 2

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
        Tests that the execute wrapper is invoked correctly.

        Verifies that the wrapper is called and that it receives the expected SQL query and context parameters when executing a query.

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
        Tests that the execute wrapper is properly invoked when used in conjunction with executemany, verifying that it correctly captures the SQL statement, parameters, and execution context.
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
        Test that the database is being queried correctly by executing a simple SQL statement and verifying the result.
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
        Tests the invocation of a nested wrapper, verifying that the inner wrapper is called as expected when execute and executemany operations are performed.
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

        Tests whether outer wrappers can block execution of SQL statements.

        Checks that the outer wrappers intercept and prevent the execution of
        SQL statements, while also verifying the correct call count of the
        wrapper function.

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
        Verifies that the database wrapper correctly reports the executed SQL query.
        """
        wrapper = self.mock_wrapper()
        sql = "SELECT 'aloha'" + connection.features.bare_select_suffix
        with connection.execute_wrapper(wrapper), connection.cursor() as cursor:
            cursor.execute(sql)
        (_, reported_sql, _, _, _), _ = wrapper.call_args
        self.assertEqual(reported_sql, sql)

    def test_wrapper_connection_specific(self):
        """
        Tests the connection-specific behavior of the execute wrapper. Verifies that the wrapper is properly applied and removed for a given connection, and that the wrapper's called status is correctly reset after execution.
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
        Tests that the query wrapper correctly prepends a SQL comment to the executed query, verifying that the comment is included in the captured query.
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
        Tests that health checks are enabled and functioning correctly for database connections.

        This test verifies that the connection is renewed when a previous connection is found to be unusable, and that health checks are only performed when necessary.
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
        Tests that a new connection is not created when health checks are enabled and errors occur, 
        if the previous connection is still usable despite an error occurring during a query.
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
        Tests the behavior of database connections when health checks are disabled, verifying that the connection is not replaced when an error occurs.
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
        Tests the behavior of database connection autocommit mode when connection health checks are enabled, verifying that a new connection is established when the existing one is unusable or obsolete, but an existing usable connection is reused.
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

        Verifies that the init_connection_state method of a database connection is called only once when the connection is initialized multiple times.

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
