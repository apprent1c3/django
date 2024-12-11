import os
import re
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.db import (
    DEFAULT_DB_ALIAS,
    NotSupportedError,
    connection,
    connections,
    transaction,
)
from django.db.models import Aggregate, Avg, StdDev, Sum, Variance
from django.db.utils import ConnectionHandler
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext, isolate_apps

from ..models import Item, Object, Square


@unittest.skipUnless(connection.vendor == "sqlite", "SQLite tests")
class Tests(TestCase):
    longMessage = True

    def test_aggregation(self):
        """Raise NotSupportedError when aggregating on date/time fields."""
        for aggregate in (Sum, Avg, Variance, StdDev):
            with self.assertRaises(NotSupportedError):
                Item.objects.aggregate(aggregate("time"))
            with self.assertRaises(NotSupportedError):
                Item.objects.aggregate(aggregate("date"))
            with self.assertRaises(NotSupportedError):
                Item.objects.aggregate(aggregate("last_modified"))
            with self.assertRaises(NotSupportedError):
                Item.objects.aggregate(
                    **{
                        "complex": aggregate("last_modified")
                        + aggregate("last_modified")
                    }
                )

    def test_distinct_aggregation(self):
        """

        Tests the aggregation function's support for the DISTINCT keyword.

        This test case verifies that the database backend correctly handles
        aggregate functions with multiple arguments when the DISTINCT keyword is used.
        In particular, it checks that an error is raised when the DISTINCT keyword is
        applied to an aggregate function that accepts multiple arguments, as this is
        not supported by SQLite.

        The test creates a custom aggregate function that allows the use of DISTINCT
        and then attempts to use it with the DISTINCT keyword, expecting a
        NotSupportedError to be raised with a specific error message.

        """
        class DistinctAggregate(Aggregate):
            allow_distinct = True

        aggregate = DistinctAggregate("first", "second", distinct=True)
        msg = (
            "SQLite doesn't support DISTINCT on aggregate functions accepting "
            "multiple arguments."
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            connection.ops.check_expression_support(aggregate)

    def test_distinct_aggregation_multiple_args_no_distinct(self):
        # Aggregate functions accept multiple arguments when DISTINCT isn't
        # used, e.g. GROUP_CONCAT().
        class DistinctAggregate(Aggregate):
            allow_distinct = True

        aggregate = DistinctAggregate("first", "second", distinct=False)
        connection.ops.check_expression_support(aggregate)

    def test_memory_db_test_name(self):
        """A named in-memory db should be allowed where supported."""
        from django.db.backends.sqlite3.base import DatabaseWrapper

        settings_dict = {
            "TEST": {
                "NAME": "file:memorydb_test?mode=memory&cache=shared",
            }
        }
        creation = DatabaseWrapper(settings_dict).creation
        self.assertEqual(
            creation._get_test_db_name(),
            creation.connection.settings_dict["TEST"]["NAME"],
        )

    def test_regexp_function(self):
        tests = (
            ("test", r"[0-9]+", False),
            ("test", r"[a-z]+", True),
            ("test", None, None),
            (None, r"[a-z]+", None),
            (None, None, None),
        )
        for string, pattern, expected in tests:
            with self.subTest((string, pattern)):
                with connection.cursor() as cursor:
                    cursor.execute("SELECT %s REGEXP %s", [string, pattern])
                    value = cursor.fetchone()[0]
                value = bool(value) if value in {0, 1} else value
                self.assertIs(value, expected)

    def test_pathlib_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_dict = {
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": Path(tmp) / "test.db",
                },
            }
            connections = ConnectionHandler(settings_dict)
            connections["default"].ensure_connection()
            connections["default"].close()
            self.assertTrue(os.path.isfile(os.path.join(tmp, "test.db")))

    @mock.patch.object(connection, "get_database_version", return_value=(3, 30))
    def test_check_database_version_supported(self, mocked_get_database_version):
        """

        Checks if the database version is supported by the application.

        currently requires SQLite 3.31 or later to function correctly. This function
        verifies the database version and raises a NotSupportedError if the version
        is not compatible.

        Args:
            None

        Raises:
            NotSupportedError: If the database version is not supported.

        Returns:
            None

        """
        msg = "SQLite 3.31 or later is required (found 3.30)."
        with self.assertRaisesMessage(NotSupportedError, msg):
            connection.check_database_version_supported()
        self.assertTrue(mocked_get_database_version.called)

    def test_init_command(self):
        settings_dict = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
                "OPTIONS": {
                    "init_command": "PRAGMA synchronous=3; PRAGMA cache_size=2000;",
                },
            }
        }
        connections = ConnectionHandler(settings_dict)
        connections["default"].ensure_connection()
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("PRAGMA synchronous")
                value = cursor.fetchone()[0]
                self.assertEqual(value, 3)
                cursor.execute("PRAGMA cache_size")
                value = cursor.fetchone()[0]
                self.assertEqual(value, 2000)
        finally:
            connections["default"]._close()


@unittest.skipUnless(connection.vendor == "sqlite", "SQLite tests")
@isolate_apps("backends")
class SchemaTests(TransactionTestCase):
    available_apps = ["backends"]

    def test_autoincrement(self):
        """
        auto_increment fields are created with the AUTOINCREMENT keyword
        in order to be monotonically increasing (#10164).
        """
        with connection.schema_editor(collect_sql=True) as editor:
            editor.create_model(Square)
            statements = editor.collected_sql
        match = re.search('"id" ([^,]+),', statements[0])
        self.assertIsNotNone(match)
        self.assertEqual(
            "integer NOT NULL PRIMARY KEY AUTOINCREMENT",
            match[1],
            "Wrong SQL used to create an auto-increment column on SQLite",
        )

    def test_disable_constraint_checking_failure_disallowed(self):
        """
        SQLite schema editor is not usable within an outer transaction if
        foreign key constraint checks are not disabled beforehand.
        """
        msg = (
            "SQLite schema editor cannot be used while foreign key "
            "constraint checks are enabled. Make sure to disable them "
            "before entering a transaction.atomic() context because "
            "SQLite does not support disabling them in the middle of "
            "a multi-statement transaction."
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            with transaction.atomic(), connection.schema_editor(atomic=True):
                pass

    def test_constraint_checks_disabled_atomic_allowed(self):
        """
        SQLite schema editor is usable within an outer transaction as long as
        foreign key constraints checks are disabled beforehand.
        """

        def constraint_checks_enabled():
            with connection.cursor() as cursor:
                return bool(cursor.execute("PRAGMA foreign_keys").fetchone()[0])

        with connection.constraint_checks_disabled(), transaction.atomic():
            with connection.schema_editor(atomic=True):
                self.assertFalse(constraint_checks_enabled())
            self.assertFalse(constraint_checks_enabled())
        self.assertTrue(constraint_checks_enabled())


@unittest.skipUnless(connection.vendor == "sqlite", "Test only for SQLite")
@override_settings(DEBUG=True)
class LastExecutedQueryTest(TestCase):
    def test_no_interpolation(self):
        # This shouldn't raise an exception (#17158)
        query = "SELECT strftime('%Y', 'now');"
        with connection.cursor() as cursor:
            cursor.execute(query)
        self.assertEqual(connection.queries[-1]["sql"], query)

    def test_parameter_quoting(self):
        # The implementation of last_executed_queries isn't optimal. It's
        # worth testing that parameters are quoted (#14091).
        query = "SELECT %s"
        params = ["\"'\\"]
        with connection.cursor() as cursor:
            cursor.execute(query, params)
        # Note that the single quote is repeated
        substituted = "SELECT '\"''\\'"
        self.assertEqual(connection.queries[-1]["sql"], substituted)

    def test_large_number_of_parameters(self):
        # If SQLITE_MAX_VARIABLE_NUMBER (default = 999) has been changed to be
        # greater than SQLITE_MAX_COLUMN (default = 2000), last_executed_query
        # can hit the SQLITE_MAX_COLUMN limit (#26063).
        with connection.cursor() as cursor:
            sql = "SELECT MAX(%s)" % ", ".join(["%s"] * 2001)
            params = list(range(2001))
            # This should not raise an exception.
            cursor.db.ops.last_executed_query(cursor.cursor, sql, params)


@unittest.skipUnless(connection.vendor == "sqlite", "SQLite tests")
class EscapingChecks(TestCase):
    """
    All tests in this test case are also run with settings.DEBUG=True in
    EscapingChecksDebug test case, to also test CursorDebugWrapper.
    """

    def test_parameter_escaping(self):
        # '%s' escaping support for sqlite3 (#13648).
        """
        Tests if the parameter escaping functionality is working correctly by executing a SQL query with a current timestamp and verifying that the result is a non-zero integer.
        """
        with connection.cursor() as cursor:
            cursor.execute("select strftime('%s', date('now'))")
            response = cursor.fetchall()[0][0]
        # response should be an non-zero integer
        self.assertTrue(int(response))


@unittest.skipUnless(connection.vendor == "sqlite", "SQLite tests")
@override_settings(DEBUG=True)
class EscapingChecksDebug(EscapingChecks):
    pass


@unittest.skipUnless(connection.vendor == "sqlite", "SQLite tests")
class ThreadSharing(TransactionTestCase):
    available_apps = ["backends"]

    def test_database_sharing_in_threads(self):
        thread_connections = []

        def create_object():
            Object.objects.create()
            thread_connections.append(connections[DEFAULT_DB_ALIAS].connection)

        main_connection = connections[DEFAULT_DB_ALIAS].connection
        try:
            create_object()
            thread = threading.Thread(target=create_object)
            thread.start()
            thread.join()
            self.assertEqual(Object.objects.count(), 2)
        finally:
            for conn in thread_connections:
                if conn is not main_connection:
                    conn.close()


@unittest.skipUnless(connection.vendor == "sqlite", "SQLite tests")
class TestTransactionMode(SimpleTestCase):
    databases = {"default"}

    def test_default_transaction_mode(self):
        with CaptureQueriesContext(connection) as captured_queries:
            with transaction.atomic():
                pass

        begin_query, commit_query = captured_queries
        self.assertEqual(begin_query["sql"], "BEGIN")
        self.assertEqual(commit_query["sql"], "COMMIT")

    def test_invalid_transaction_mode(self):
        """
        Tests that an Invalid Transaction Mode raises an ImproperlyConfigured exception.

        This test verifies that the 'transaction_mode' setting in the database configuration
        is correctly validated. It checks that an 'invalid' mode triggers an error, ensuring
        that only the allowed modes ('DEFERRED', 'EXCLUSIVE', 'IMMEDIATE', or None) are accepted.

        """
        msg = (
            "settings.DATABASES['default']['OPTIONS']['transaction_mode'] is "
            "improperly configured to 'invalid'. Use one of 'DEFERRED', 'EXCLUSIVE', "
            "'IMMEDIATE', or None."
        )
        with self.change_transaction_mode("invalid") as new_connection:
            with self.assertRaisesMessage(ImproperlyConfigured, msg):
                new_connection.ensure_connection()

    def test_valid_transaction_modes(self):
        """
        Tests the validity of different transaction modes.

        This function checks that the database connection correctly applies
        different transaction modes, including deferred, immediate, and exclusive.
        For each mode, it verifies that the corresponding SQL command is executed,
        specifically checking the 'BEGIN' statement with the expected transaction mode.

        The test covers the following scenarios:
        - The connection is set to the specified transaction mode.
        - A new transaction is started with the given mode.
        - The 'BEGIN' SQL statement is captured and verified to match the expected mode.

        The test ensures that the database connection behaves correctly and consistently
        across different transaction modes, providing a reliable foundation for further testing and development.
        """
        valid_transaction_modes = ("deferred", "immediate", "exclusive")
        for transaction_mode in valid_transaction_modes:
            with (
                self.subTest(transaction_mode=transaction_mode),
                self.change_transaction_mode(transaction_mode) as new_connection,
                CaptureQueriesContext(new_connection) as captured_queries,
            ):
                new_connection.set_autocommit(
                    False, force_begin_transaction_with_broken_autocommit=True
                )
                new_connection.commit()
                expected_transaction_mode = transaction_mode.upper()
                begin_sql = captured_queries[0]["sql"]
                self.assertEqual(begin_sql, f"BEGIN {expected_transaction_mode}")

    @contextmanager
    def change_transaction_mode(self, transaction_mode):
        """

        A context manager that temporarily changes the transaction mode for a database connection.

        This method creates a copy of the current connection with the specified transaction mode, 
        allowing for temporary changes to the connection settings without affecting the original connection.

        The new connection is available within the context block, and is automatically closed when the block is exited.

        :param transaction_mode: The transaction mode to use for the temporary connection
        :type transaction_mode: str

        """
        new_connection = connection.copy()
        new_connection.settings_dict["OPTIONS"] = {
            **new_connection.settings_dict["OPTIONS"],
            "transaction_mode": transaction_mode,
        }
        try:
            yield new_connection
        finally:
            new_connection._close()
