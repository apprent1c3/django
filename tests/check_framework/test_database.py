import unittest
from unittest import mock

from django.core.checks.database import check_database_backends
from django.db import connection, connections
from django.test import TestCase


class DatabaseCheckTests(TestCase):
    databases = {"default", "other"}

    @mock.patch("django.db.backends.base.validation.BaseDatabaseValidation.check")
    def test_database_checks_called(self, mocked_check):
        """

        Tests whether database checks are called when the function check_database_backends is invoked.

        The test checks two scenarios:
            - When the function is called without specifying any databases, it verifies that no database checks are performed.
            - When the function is called with a list of databases, it verifies that the checks are indeed performed.

        This test case ensures that the check_database_backends function behaves as expected in both cases, 
        providing confidence in its ability to handle database checks correctly.

        """
        check_database_backends()
        self.assertFalse(mocked_check.called)
        check_database_backends(databases=self.databases)
        self.assertTrue(mocked_check.called)

    @unittest.skipUnless(connection.vendor == "mysql", "Test only for MySQL")
    def test_mysql_strict_mode(self):
        def _clean_sql_mode():
            for alias in self.databases:
                if hasattr(connections[alias], "sql_mode"):
                    del connections[alias].sql_mode

        _clean_sql_mode()
        good_sql_modes = [
            "STRICT_TRANS_TABLES,STRICT_ALL_TABLES",
            "STRICT_TRANS_TABLES",
            "STRICT_ALL_TABLES",
        ]
        for sql_mode in good_sql_modes:
            with mock.patch.object(
                connection,
                "mysql_server_data",
                {"sql_mode": sql_mode},
            ):
                self.assertEqual(check_database_backends(databases=self.databases), [])
            _clean_sql_mode()

        bad_sql_modes = ["", "WHATEVER"]
        for sql_mode in bad_sql_modes:
            mocker_default = mock.patch.object(
                connection,
                "mysql_server_data",
                {"sql_mode": sql_mode},
            )
            mocker_other = mock.patch.object(
                connections["other"],
                "mysql_server_data",
                {"sql_mode": sql_mode},
            )
            with mocker_default, mocker_other:
                # One warning for each database alias
                result = check_database_backends(databases=self.databases)
                self.assertEqual(len(result), 2)
                self.assertEqual([r.id for r in result], ["mysql.W002", "mysql.W002"])
            _clean_sql_mode()
