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
        """
        Tests the initialization of the display name attribute.

        Verifies that the BaseDatabaseWrapper class has a default display name of 'unknown',
        and that a connection instance has a display name that is not 'unknown' after initialization.
        """
        self.assertEqual(BaseDatabaseWrapper.display_name, "unknown")
        self.assertNotEqual(connection.display_name, "unknown")

    def test_get_database_version(self):
        """
        Tests that BaseDatabaseWrapper's get_database_version method raises a NotImplementedError.

        This test checks that the base class correctly indicates that subclasses 
        are expected to implement this method by raising an exception with a helpful message.

        The purpose of this test is to ensure that developers implementing 
        subclasses of BaseDatabaseWrapper are aware of the need to provide their own 
        implementation of the get_database_version method.

        Raises:
            NotImplementedError: If get_database_version is not implemented in a subclass.


        """
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
        Tests that database transaction commit operations are properly logged at the DEBUG level.

        This test checks that when a transaction is committed, the corresponding SQL statements (BEGIN and COMMIT) are logged with the expected format and content. 

        It verifies that the logging includes the database alias, time taken to execute the query, and other relevant details, ensuring that the logs can be used for debugging and performance analysis purposes.

        The test also validates the number of queries logged and their order, confirming that the transaction is properly wrapped in a BEGIN and COMMIT block.
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
        Executes a SQL query multiple times with different parameters.

        Deletes data from the Square database table using a prepared statement.
        The function takes an optional parameters list to specify values for the query.
        If no parameters are provided, default values of 0, 1, and 2 are used.

        :param connection: Database connection object
        :param params: Optional list of tuples containing parameter values

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
        Tests if the database execution wrapper is correctly invoked.

        This test case verifies that the execution wrapper is properly called when 
        executing a database query. It checks that the wrapper is invoked with the 
        correct SQL query, parameters, and context. The test also ensures that the 
        wrapper's 'called' attribute is set to True after execution.

        Specifically, the test confirms that the SQL query is a SELECT statement, 
        that no parameters are passed, that the query is executed as a single 
        statement (not multiple), and that the context dictionary contains the 
        expected connection object.
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
        """

        Tests that the database is being queried correctly.

        This test case verifies that a simple SQL query can be executed and that the 
        results are as expected. It also checks that the executemany method is called 
        as expected on the connection object. The test uses a mock wrapper to isolate 
        the database interaction and ensure that the query is executed within a 
        controlled environment.

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
        Tests whether nested wrappers are invoked correctly when executing SQL statements.

        Verifies that both an outer and inner wrapper are called in the correct order,
        and that the inner wrapper's call count is incremented for each execute and executemany operation.

        Ensures that the wrapper functionality is preserved even when using nested wrappers,
        providing a way to compose multiple wrappers for customizing SQL execution behavior.
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

        Tests the behavior of the outer wrapper in blocking and non-blocking scenarios.

        This test case verifies that the outermost wrapper is properly called and blocks 
        the execution of subsequent wrappers when used in a nested context. It checks the 
        call count of the wrapper to ensure it is invoked as expected.

        The test uses a mock wrapper and a blocker function to simulate different 
        scenarios, ensuring the correct functionality of the outer wrapper in various 
        situations. 

        It asserts that the database commands are not executed, confirming the 
        effectiveness of the outer wrapper as a blocker.

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
        wrapper = self.mock_wrapper()
        sql = "SELECT 'aloha'" + connection.features.bare_select_suffix
        with connection.execute_wrapper(wrapper), connection.cursor() as cursor:
            cursor.execute(sql)
        (_, reported_sql, _, _, _), _ = wrapper.call_args
        self.assertEqual(reported_sql, sql)

    def test_wrapper_connection_specific(self):
        """

        Tests the connection-specific behavior of an execute wrapper.

        This function verifies that an execute wrapper is properly registered and 
        unregistered with a specific database connection, and that the wrapper is 
        not executed after the context is exited.

        It checks the following:

        * The execute wrapper is registered with the correct connection.
        * The execute wrapper is not executed after the context is exited.
        * The connection's execute wrappers list is updated correctly.

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
        ``` Marshal
        Tests the SQL query wrapper function with debug comments.

        The test verifies that the wrapper function correctly prefixes SQL queries with a 
        debug comment. It achieves this by executing a query with the wrapper applied, 
        capturing the resulting SQL, and asserting that the captured SQL begins with the 
        expected comment.

        This test helps ensure that the wrapper function behaves as expected and that 
        debug comments are correctly added to executed SQL queries.
        ```
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

        Sets up the test environment by closing the current database connection and ensures it is also closed after the test is completed, regardless of the test outcome.

        This method is used to establish a clean state for each test, preventing any residual effects from previous tests. By closing the connection at the start and scheduling it for closure after the test, it guarantees a fresh connection for each test run.

        """
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
        """

        Executes a simple query to test database connection.

        This method runs a basic SQL query that selects a constant value, 
        primarily used for verifying the database connection is active and functional.

        Returns:
            None

        Notes:
            The query itself is a bare 'SELECT' statement, which is a standard 
            way to test a database connection without relying on any specific 
            table or schema existing in the database.

        """
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

        Tests that health checks are properly disabled for database connections.

        Verifies that when health checks are disabled, the connection is not replaced
        even if its usability is uncertain or an error occurs during the query execution.
        Ensures that the existing connection is reused despite potential issues,
        as expected when health checks are disabled.

        This test requires a database that allows multiple connections to be open simultaneously.

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
