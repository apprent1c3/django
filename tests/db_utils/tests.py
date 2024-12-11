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
        Asserts that the DATABASES setting is improperly configured.

        This test checks if the 'ENGINE' value is correctly specified in the database settings.
        It creates a ConnectionHandler instance with the provided DATABASES setting and verifies
        that an ImproperlyConfigured exception is raised when attempting to establish a connection
        to the database, indicating that the 'ENGINE' value is missing or incorrect.

        The test expects the 'ENGINE' value to be set to 'django.db.backends.dummy' for the default database alias.
        If the 'ENGINE' value is not provided, it tests for a specific error message to ensure proper error handling.

        The goal of this test is to ensure that the DATABASES setting is correctly configured before
        attempting to use the database, and to provide a clear error message when the configuration is incorrect.
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
