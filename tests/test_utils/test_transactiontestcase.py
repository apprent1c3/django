from unittest import mock

from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.testcases import DatabaseOperationForbidden

from .models import Car


class TestSerializedRollbackInhibitsPostMigrate(TransactionTestCase):
    """
    TransactionTestCase._fixture_teardown() inhibits the post_migrate signal
    for test classes with serialized_rollback=True.
    """

    available_apps = ["test_utils"]
    serialized_rollback = True

    def setUp(self):
        # self.available_apps must be None to test the serialized_rollback
        # condition.
        self.available_apps = None

    def tearDown(self):
        self.available_apps = ["test_utils"]

    @mock.patch("django.test.testcases.call_command")
    def test(self, call_command):
        # with a mocked call_command(), this doesn't have any effect.
        """

        Tests that the database command 'flush' is called with the correct parameters.

        The test case verifies that the command is executed with the following settings:
        - interactive mode disabled
        - allow cascade disabled
        - reset sequences disabled
        - inhibit post migrate enabled
        - using the default database
        - verbosity level set to 0 (minimal output)

        This ensures that the database is properly reset to a known state, while minimizing output and avoiding unnecessary post-migration operations.

        """
        self._fixture_teardown()
        call_command.assert_called_with(
            "flush",
            interactive=False,
            allow_cascade=False,
            reset_sequences=False,
            inhibit_post_migrate=True,
            database="default",
            verbosity=0,
        )


@override_settings(DEBUG=True)  # Enable query logging for test_queries_cleared
class TransactionTestCaseDatabasesTests(TestCase):
    available_apps = []
    databases = {"default", "other"}

    def test_queries_cleared(self):
        """
        TransactionTestCase._pre_setup() clears the connections' queries_log
        so that it's less likely to overflow. An overflow causes
        assertNumQueries() to fail.
        """
        for alias in self.databases:
            self.assertEqual(
                len(connections[alias].queries_log), 0, "Failed for alias %s" % alias
            )


class DisallowedDatabaseQueriesTests(TransactionTestCase):
    available_apps = ["test_utils"]

    def test_disallowed_database_queries(self):
        """

        Tests if database queries to the 'other' database are properly disallowed.

        This test case verifies that attempts to query the 'other' database are met with a DatabaseOperationForbidden exception,
        ensuring test isolation. To allow queries to this database for testing purposes, 'other' must be added to the list of 
        disallowed databases in test_utils.test_transactiontestcase.DisallowedDatabaseQueriesTests.databases.

        """
        message = (
            "Database queries to 'other' are not allowed in this test. "
            "Add 'other' to test_utils.test_transactiontestcase."
            "DisallowedDatabaseQueriesTests.databases to ensure proper test "
            "isolation and silence this failure."
        )
        with self.assertRaisesMessage(DatabaseOperationForbidden, message):
            Car.objects.using("other").get()
