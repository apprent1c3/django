import unittest
from contextlib import contextmanager
from io import StringIO
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connection
from django.db.backends.base.creation import BaseDatabaseCreation
from django.test import SimpleTestCase

try:
    from django.db.backends.postgresql.psycopg_any import errors
except ImportError:
    pass
else:
    from django.db.backends.postgresql.creation import DatabaseCreation


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL tests")
class DatabaseCreationTests(SimpleTestCase):
    @contextmanager
    def changed_test_settings(self, **kwargs):
        settings = connection.settings_dict["TEST"]
        saved_values = {}
        for name in kwargs:
            if name in settings:
                saved_values[name] = settings[name]

        for name, value in kwargs.items():
            settings[name] = value
        try:
            yield
        finally:
            for name in kwargs:
                if name in saved_values:
                    settings[name] = saved_values[name]
                else:
                    del settings[name]

    def check_sql_table_creation_suffix(self, settings, expected):
        with self.changed_test_settings(**settings):
            creation = DatabaseCreation(connection)
            suffix = creation.sql_table_creation_suffix()
            self.assertEqual(suffix, expected)

    def test_sql_table_creation_suffix_with_none_settings(self):
        settings = {"CHARSET": None, "TEMPLATE": None}
        self.check_sql_table_creation_suffix(settings, "")

    def test_sql_table_creation_suffix_with_encoding(self):
        settings = {"CHARSET": "UTF8"}
        self.check_sql_table_creation_suffix(settings, "WITH ENCODING 'UTF8'")

    def test_sql_table_creation_suffix_with_template(self):
        settings = {"TEMPLATE": "template0"}
        self.check_sql_table_creation_suffix(settings, 'WITH TEMPLATE "template0"')

    def test_sql_table_creation_suffix_with_encoding_and_template(self):
        """
        Tests the SQL table creation suffix when the ' CHARSET' setting is specified with a value and the 'TEMPLATE' setting is provided. 
        Verifies that the generated suffix includes the correct encoding and template values, 
        resulting in a suffix of the form 'WITH ENCODING \'ENCODING_VALUE\' TEMPLATE \"TEMPLATE_VALUE\"'.
        """
        settings = {"CHARSET": "UTF8", "TEMPLATE": "template0"}
        self.check_sql_table_creation_suffix(
            settings, '''WITH ENCODING 'UTF8' TEMPLATE "template0"'''
        )

    def test_sql_table_creation_raises_with_collation(self):
        """
        Tests that creating a SQL table raises an error when a collation is specified.

        This test case checks that attempting to create a SQL table with a collation setting
        raises an ImproperlyConfigured exception. This is because PostgreSQL does not support
        setting collation at database creation time.

        :param None:
        :raises ImproperlyConfigured: if a collation is specified in the database settings
        """
        settings = {"COLLATION": "test"}
        msg = (
            "PostgreSQL does not support collation setting at database "
            "creation time."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.check_sql_table_creation_suffix(settings, None)

    def _execute_raise_database_already_exists(self, cursor, parameters, keepdb=False):
        """

        Raises a DatabaseError when a database with the same name already exists.

        This function handles the case where a database creation attempt is made, 
        but a database with the same name is already present in the system.

        :param cursor: A database cursor object.
        :param parameters: A dictionary containing database creation parameters.
        :param keepdb: A flag indicating whether to keep the database if it already exists.
        :raises DatabaseError: If the database with the given name already exists.

        """
        error = errors.DuplicateDatabase(
            "database %s already exists" % parameters["dbname"]
        )
        raise DatabaseError() from error

    def _execute_raise_permission_denied(self, cursor, parameters, keepdb=False):
        error = errors.InsufficientPrivilege("permission denied to create database")
        raise DatabaseError() from error

    def patch_test_db_creation(self, execute_create_test_db):
        return mock.patch.object(
            BaseDatabaseCreation, "_execute_create_test_db", execute_create_test_db
        )

    @mock.patch("sys.stdout", new_callable=StringIO)
    @mock.patch("sys.stderr", new_callable=StringIO)
    def test_create_test_db(self, *mocked_objects):
        """
        Tests the creation of a test database.

        This test function verifies the behavior of the DatabaseCreation class when creating
        a test database under various conditions, including when the database already exists,
        when permission is denied, and when the user chooses to keep the database.

        It checks that the correct exceptions are raised and that the database is created
        or not created as expected, based on the provided verbosity, autoclobber, and keepdb
        parameters. The function also tests the handling of user input when prompted to
        overwrite an existing database.

        The test cases cover different scenarios to ensure that the DatabaseCreation class
        behaves as expected in various situations, providing a robust test of its functionality.
        """
        creation = DatabaseCreation(connection)
        # Simulate test database creation raising "database already exists"
        with self.patch_test_db_creation(self._execute_raise_database_already_exists):
            with mock.patch("builtins.input", return_value="no"):
                with self.assertRaises(SystemExit):
                    # SystemExit is raised if the user answers "no" to the
                    # prompt asking if it's okay to delete the test database.
                    creation._create_test_db(
                        verbosity=0, autoclobber=False, keepdb=False
                    )
            # "Database already exists" error is ignored when keepdb is on
            creation._create_test_db(verbosity=0, autoclobber=False, keepdb=True)
        # Simulate test database creation raising unexpected error
        with self.patch_test_db_creation(self._execute_raise_permission_denied):
            with mock.patch.object(
                DatabaseCreation, "_database_exists", return_value=False
            ):
                with self.assertRaises(SystemExit):
                    creation._create_test_db(
                        verbosity=0, autoclobber=False, keepdb=False
                    )
                with self.assertRaises(SystemExit):
                    creation._create_test_db(
                        verbosity=0, autoclobber=False, keepdb=True
                    )
        # Simulate test database creation raising "insufficient privileges".
        # An error shouldn't appear when keepdb is on and the database already
        # exists.
        with self.patch_test_db_creation(self._execute_raise_permission_denied):
            with mock.patch.object(
                DatabaseCreation, "_database_exists", return_value=True
            ):
                creation._create_test_db(verbosity=0, autoclobber=False, keepdb=True)
