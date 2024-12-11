import unittest
from contextlib import contextmanager
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.db import NotSupportedError, connection
from django.test import TestCase, override_settings


@contextmanager
def get_connection():
    new_connection = connection.copy()
    yield new_connection
    new_connection.close()


@override_settings(DEBUG=True)
@unittest.skipUnless(connection.vendor == "mysql", "MySQL tests")
class IsolationLevelTests(TestCase):
    read_committed = "read committed"
    repeatable_read = "repeatable read"
    isolation_values = {
        level: level.upper() for level in (read_committed, repeatable_read)
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        configured_isolation_level = (
            connection.isolation_level or cls.isolation_values[cls.repeatable_read]
        )
        cls.configured_isolation_level = configured_isolation_level.upper()
        cls.other_isolation_level = (
            cls.read_committed
            if configured_isolation_level != cls.isolation_values[cls.read_committed]
            else cls.repeatable_read
        )

    @staticmethod
    def get_isolation_level(connection):
        """
        .. staticmethod:: get_isolation_level(connection)
           Retrieves the current isolation level of a given database connection.

           :param connection: A database connection object.
           :return: The current isolation level as a string, with hyphens replaced by spaces for readability.
           :rtype: str

           This method queries the database to determine the current isolation level, providing information on how the database handles concurrent transactions. The returned isolation level can be used to understand the consistency and visibility of data across different database sessions.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SHOW VARIABLES "
                "WHERE variable_name IN ('transaction_isolation', 'tx_isolation')"
            )
            return cursor.fetchone()[1].replace("-", " ")

    def test_auto_is_null_auto_config(self):
        """
        Tests the automatic configuration of SQL auto-is-null setting.

        Verifies that the 'sql_auto_is_null' setting is properly handled during connection initialization.
        If the database feature 'sql_auto_is_null' is enabled, checks that the corresponding SQL query is executed.
        Otherwise, checks that the query is not executed.

        This test ensures that the connection state is properly initialized and configured according to the database features.
        """
        query = "set sql_auto_is_null = 0"
        connection.init_connection_state()
        last_query = connection.queries[-1]["sql"].lower()
        if connection.features.is_sql_auto_is_null_enabled:
            self.assertIn(query, last_query)
        else:
            self.assertNotIn(query, last_query)

    def test_connect_isolation_level(self):
        self.assertEqual(
            self.get_isolation_level(connection), self.configured_isolation_level
        )

    def test_setting_isolation_level(self):
        """
        Tests setting the isolation level of a database connection.

        Verifies that setting the isolation level in the connection settings dictionary
        successfully changes the isolation level of the database connection.

        Checks that the isolation level retrieved from the connection matches the expected
        value after setting it to a different level.

        """
        with get_connection() as new_connection:
            new_connection.settings_dict["OPTIONS"][
                "isolation_level"
            ] = self.other_isolation_level
            self.assertEqual(
                self.get_isolation_level(new_connection),
                self.isolation_values[self.other_isolation_level],
            )

    def test_uppercase_isolation_level(self):
        # Upper case values are also accepted in 'isolation_level'.
        with get_connection() as new_connection:
            new_connection.settings_dict["OPTIONS"][
                "isolation_level"
            ] = self.other_isolation_level.upper()
            self.assertEqual(
                self.get_isolation_level(new_connection),
                self.isolation_values[self.other_isolation_level],
            )

    def test_default_isolation_level(self):
        # If not specified in settings, the default is read committed.
        """

        Tests that the default isolation level is correctly set when no isolation level is specified.

        This test case verifies that when the 'isolation_level' option is not provided in the 
        database connection settings, the default isolation level is 'READ COMMITTED'. It 
        checks the current isolation level of the database connection and compares it to the 
        expected default isolation level.

        The test relies on the get_connection and get_isolation_level functions to establish 
        a database connection and retrieve its isolation level, respectively.

        """
        with get_connection() as new_connection:
            new_connection.settings_dict["OPTIONS"].pop("isolation_level", None)
            self.assertEqual(
                self.get_isolation_level(new_connection),
                self.isolation_values[self.read_committed],
            )

    def test_isolation_level_validation(self):
        """

        Tests validation of the transaction isolation level setting.

        Verifies that an Invalid transaction isolation level raises an ImproperlyConfigured exception,
        ensuring that only valid isolation levels ('read committed', 'read uncommitted', 'repeatable read', 'serializable', or None) are accepted.

        """
        new_connection = connection.copy()
        new_connection.settings_dict["OPTIONS"]["isolation_level"] = "xxx"
        msg = (
            "Invalid transaction isolation level 'xxx' specified.\n"
            "Use one of 'read committed', 'read uncommitted', "
            "'repeatable read', 'serializable', or None."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            new_connection.cursor()


@unittest.skipUnless(connection.vendor == "mysql", "MySQL tests")
class Tests(TestCase):
    @mock.patch.object(connection, "get_database_version")
    def test_check_database_version_supported(self, mocked_get_database_version):
        """

        Checks if the version of the connected database is supported.

        This function verifies that the version of MySQL or MariaDB meets the minimum requirements.
        For MySQL, it checks for version 8.0.11 or later, and for MariaDB, it checks for version 10.5 or later.

        If the database version is not supported, it raises a NotSupportedError with a message
        indicating the required version and the version found.

        Note: This function requires an established database connection to function correctly.

        """
        if connection.mysql_is_mariadb:
            mocked_get_database_version.return_value = (10, 4)
            msg = "MariaDB 10.5 or later is required (found 10.4)."
        else:
            mocked_get_database_version.return_value = (8, 0, 4)
            msg = "MySQL 8.0.11 or later is required (found 8.0.4)."

        with self.assertRaisesMessage(NotSupportedError, msg):
            connection.check_database_version_supported()
        self.assertTrue(mocked_get_database_version.called)
