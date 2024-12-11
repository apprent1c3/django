"""Tests for django.db.utils."""

import unittest

from django.core.exceptions import ImproperlyConfigured
from django.db import DEFAULT_DB_ALIAS, ProgrammingError, connection
from django.db.utils import ConnectionHandler, load_backend
from django.test import SimpleTestCase, TestCase
from django.utils.connection import ConnectionDoesNotExist


class ConnectionHandlerTests(SimpleTestCase):
    def test_connection_handler_no_databases(self):
        """
        Empty DATABASES and empty 'default' settings default to the dummy
        backend.
        """
        for DATABASES in (
            {},  # Empty DATABASES setting.
            {"default": {}},  # Empty 'default' database.
        ):
            with self.subTest(DATABASES=DATABASES):
                self.assertImproperlyConfigured(DATABASES)

    def assertImproperlyConfigured(self, DATABASES):
        """
        Asserts that the DATABASES setting is improperly configured to use a dummy database engine.

        When the database connection is attempted to be established with an improperly configured ENGINE setting in the DATABASES dictionary, this function checks that the expected ImproperlyConfigured exception is raised with a specific error message.

        The error message indicates that the ENGINE value in the DATABASES setting is missing or invalid, and directs the user to check the settings documentation for more information on proper configuration.
        """
        conns = ConnectionHandler(DATABASES)
        self.assertEqual(
            conns[DEFAULT_DB_ALIAS].settings_dict["ENGINE"], "django.db.backends.dummy"
        )
        msg = (
            "settings.DATABASES is improperly configured. Please supply the "
            "ENGINE value. Check settings documentation for more details."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            conns[DEFAULT_DB_ALIAS].ensure_connection()

    def test_no_default_database(self):
        """

        Verifies that attempting to access a non-default database raises an error if no default database is defined.

        Tests the behavior of the ConnectionHandler when no 'default' database is present in the provided DATABASES configuration.
        The test expects an ImproperlyConfigured exception to be raised with a specific message, ensuring proper handling of invalid configurations.

        Parameters are set in the test, including a DATABASES dictionary with a single non-default database ('other') and no 'default' database defined.

        """
        DATABASES = {"other": {}}
        conns = ConnectionHandler(DATABASES)
        msg = "You must define a 'default' database."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            conns["other"].ensure_connection()

    def test_databases_property(self):
        # The "databases" property is maintained for backwards compatibility
        # with 3rd party packages. It should be an alias of the "settings"
        # property.
        conn = ConnectionHandler({})
        self.assertNotEqual(conn.settings, {})
        self.assertEqual(conn.settings, conn.databases)

    def test_nonexistent_alias(self):
        """

        Tests that attempting to access a nonexistent database alias raises a ConnectionDoesNotExist exception.

        The test case checks if the connection handler correctly handles the case where a requested alias does not exist in the connections configuration.

        :raises: ConnectionDoesNotExist

        """
        msg = "The connection 'nonexistent' doesn't exist."
        conns = ConnectionHandler(
            {
                DEFAULT_DB_ALIAS: {"ENGINE": "django.db.backends.dummy"},
            }
        )
        with self.assertRaisesMessage(ConnectionDoesNotExist, msg):
            conns["nonexistent"]


class DatabaseErrorWrapperTests(TestCase):
    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL test")
    def test_reraising_backend_specific_database_exception(self):
        """
        Tests that a backend-specific database exception is properly reraised when executing a PostgreSQL query.

        This test ensures that when a PostgreSQL database query fails, the resulting exception is correctly wrapped and reraised as a Django database exception. Specifically, it verifies that the reraised exception contains the original backend-specific exception as its cause, and that the cause exception contains relevant error details, such as the SQL state or PostgreSQL error code and message.

        The test is skipped unless the PostgreSQL database backend is being used.
        """
        from django.db.backends.postgresql.psycopg_any import is_psycopg3

        with connection.cursor() as cursor:
            msg = 'table "X" does not exist'
            with self.assertRaisesMessage(ProgrammingError, msg) as cm:
                cursor.execute('DROP TABLE "X"')
        self.assertNotEqual(type(cm.exception), type(cm.exception.__cause__))
        self.assertIsNotNone(cm.exception.__cause__)
        if is_psycopg3:
            self.assertIsNotNone(cm.exception.__cause__.diag.sqlstate)
            self.assertIsNotNone(cm.exception.__cause__.diag.message_primary)
        else:
            self.assertIsNotNone(cm.exception.__cause__.pgcode)
            self.assertIsNotNone(cm.exception.__cause__.pgerror)


class LoadBackendTests(SimpleTestCase):
    def test_load_backend_invalid_name(self):
        msg = (
            "'foo' isn't an available database backend or couldn't be "
            "imported. Check the above exception. To use one of the built-in "
            "backends, use 'django.db.backends.XXX', where XXX is one of:\n"
            "    'mysql', 'oracle', 'postgresql', 'sqlite3'"
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg) as cm:
            load_backend("foo")
        self.assertEqual(str(cm.exception.__cause__), "No module named 'foo'")
