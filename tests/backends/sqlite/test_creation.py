import copy
import multiprocessing
import unittest
from unittest import mock

from django.db import DEFAULT_DB_ALIAS, NotSupportedError, connection, connections
from django.test import SimpleTestCase


@unittest.skipUnless(connection.vendor == "sqlite", "SQLite tests")
class TestDbSignatureTests(SimpleTestCase):
    def test_custom_test_name(self):
        """
        Verifies custom test database name is correctly applied and reflected in the test database signature.
        """
        test_connection = copy.copy(connections[DEFAULT_DB_ALIAS])
        test_connection.settings_dict = copy.deepcopy(
            connections[DEFAULT_DB_ALIAS].settings_dict
        )
        test_connection.settings_dict["NAME"] = None
        test_connection.settings_dict["TEST"]["NAME"] = "custom.sqlite.db"
        signature = test_connection.creation_class(test_connection).test_db_signature()
        self.assertEqual(signature, (None, "custom.sqlite.db"))

    def test_get_test_db_clone_settings_name(self):
        """
        Tests that the get_test_db_clone_settings method returns the correct clone name for a test database, 
        ensuring proper naming conventions are followed when cloning the test database.
        """
        test_connection = copy.copy(connections[DEFAULT_DB_ALIAS])
        test_connection.settings_dict = copy.deepcopy(
            connections[DEFAULT_DB_ALIAS].settings_dict,
        )
        tests = [
            ("test.sqlite3", "test_1.sqlite3"),
            ("test", "test_1"),
        ]
        for test_db_name, expected_clone_name in tests:
            with self.subTest(test_db_name=test_db_name):
                test_connection.settings_dict["NAME"] = test_db_name
                test_connection.settings_dict["TEST"]["NAME"] = test_db_name
                creation_class = test_connection.creation_class(test_connection)
                clone_settings_dict = creation_class.get_test_db_clone_settings("1")
                self.assertEqual(clone_settings_dict["NAME"], expected_clone_name)

    @mock.patch.object(multiprocessing, "get_start_method", return_value="forkserver")
    def test_get_test_db_clone_settings_not_supported(self, *mocked_objects):
        msg = "Cloning with start method 'forkserver' is not supported."
        with self.assertRaisesMessage(NotSupportedError, msg):
            connection.creation.get_test_db_clone_settings(1)
