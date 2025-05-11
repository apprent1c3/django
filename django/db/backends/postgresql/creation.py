import sys

from django.core.exceptions import ImproperlyConfigured
from django.db.backends.base.creation import BaseDatabaseCreation
from django.db.backends.postgresql.psycopg_any import errors
from django.db.backends.utils import strip_quotes


class DatabaseCreation(BaseDatabaseCreation):
    def _quote_name(self, name):
        return self.connection.ops.quote_name(name)

    def _get_database_create_suffix(self, encoding=None, template=None):
        """
        Returns a SQL suffix string for a CREATE DATABASE statement.

        The suffix includes ENCODING and TEMPLATE specifications if provided, 
        prefixed with the 'WITH' keyword if any specifications are present.
        """
        suffix = ""
        if encoding:
            suffix += " ENCODING '{}'".format(encoding)
        if template:
            suffix += " TEMPLATE {}".format(self._quote_name(template))
        return suffix and "WITH" + suffix

    def sql_table_creation_suffix(self):
        test_settings = self.connection.settings_dict["TEST"]
        if test_settings.get("COLLATION") is not None:
            raise ImproperlyConfigured(
                "PostgreSQL does not support collation setting at database "
                "creation time."
            )
        return self._get_database_create_suffix(
            encoding=test_settings["CHARSET"],
            template=test_settings.get("TEMPLATE"),
        )

    def _database_exists(self, cursor, database_name):
        cursor.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            [strip_quotes(database_name)],
        )
        return cursor.fetchone() is not None

    def _execute_create_test_db(self, cursor, parameters, keepdb=False):
        """
        Creates a test database, optionally reusing an existing one if keepdb is enabled.

        Parameters
        ----------
        cursor : object
            Database cursor.
        parameters : dict
            Dictionary containing test database parameters, including 'dbname'.
        keepdb : bool, optional
            If True, the test database will not be recreated if it already exists (default is False).

        Raises
        ------
        Exception
            If an error occurs during test database creation and the error is not a DuplicateDatabase exception.

        Notes
        -----
        If keepdb is False and a DuplicateDatabase error occurs, the exception is re-raised. Otherwise, the exception is caught and logged, and the program exits with a non-zero status code if the error is not a DuplicateDatabase exception.””
        """
        try:
            if keepdb and self._database_exists(cursor, parameters["dbname"]):
                # If the database should be kept and it already exists, don't
                # try to create a new one.
                return
            super()._execute_create_test_db(cursor, parameters, keepdb)
        except Exception as e:
            if not isinstance(e.__cause__, errors.DuplicateDatabase):
                # All errors except "database already exists" cancel tests.
                self.log("Got an error creating the test database: %s" % e)
                sys.exit(2)
            elif not keepdb:
                # If the database should be kept, ignore "database already
                # exists".
                raise

    def _clone_test_db(self, suffix, verbosity, keepdb=False):
        # CREATE DATABASE ... WITH TEMPLATE ... requires closing connections
        # to the template database.
        """
        Clone the test database with the given suffix, verbosity, and database retention policy.

            :param str suffix: The suffix to append to the test database name.
            :param int verbosity: The verbosity level of the operation.
            :param bool keepdb: Whether to retain the test database after use. Defaults to False.

        """
        self.connection.close()
        self.connection.close_pool()

        source_database_name = self.connection.settings_dict["NAME"]
        target_database_name = self.get_test_db_clone_settings(suffix)["NAME"]
        test_db_params = {
            "dbname": self._quote_name(target_database_name),
            "suffix": self._get_database_create_suffix(template=source_database_name),
        }
        with self._nodb_cursor() as cursor:
            try:
                self._execute_create_test_db(cursor, test_db_params, keepdb)
            except Exception:
                try:
                    if verbosity >= 1:
                        self.log(
                            "Destroying old test database for alias %s..."
                            % (
                                self._get_database_display_str(
                                    verbosity, target_database_name
                                ),
                            )
                        )
                    cursor.execute("DROP DATABASE %(dbname)s" % test_db_params)
                    self._execute_create_test_db(cursor, test_db_params, keepdb)
                except Exception as e:
                    self.log("Got an error cloning the test database: %s" % e)
                    sys.exit(2)

    def _destroy_test_db(self, test_database_name, verbosity):
        self.connection.close_pool()
        return super()._destroy_test_db(test_database_name, verbosity)
