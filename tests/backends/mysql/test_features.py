from unittest import mock, skipUnless

from django.db import connection
from django.db.backends.mysql.features import DatabaseFeatures
from django.test import TestCase


@skipUnless(connection.vendor == "mysql", "MySQL tests")
class TestFeatures(TestCase):
    def test_supports_transactions(self):
        """
        All storage engines except MyISAM support transactions.
        """
        del connection.features.supports_transactions
        with mock.patch(
            "django.db.connection.features._mysql_storage_engine", "InnoDB"
        ):
            self.assertTrue(connection.features.supports_transactions)
        del connection.features.supports_transactions
        with mock.patch(
            "django.db.connection.features._mysql_storage_engine", "MyISAM"
        ):
            self.assertFalse(connection.features.supports_transactions)
        del connection.features.supports_transactions

    def test_allows_auto_pk_0(self):
        with mock.MagicMock() as _connection:
            _connection.sql_mode = {"NO_AUTO_VALUE_ON_ZERO"}
            database_features = DatabaseFeatures(_connection)
            self.assertIs(database_features.allows_auto_pk_0, True)

    def test_allows_group_by_selected_pks(self):
        """
        Tests the DatabaseFeatures.allows_group_by_selected_pks property.

        This test case verifies the behavior of the allows_group_by_selected_pks property 
        under different database configurations. It checks whether the property correctly 
        detects when a database allows grouping by primary keys that are selected in the query.

        The test covers various database scenarios, including MySQL and MariaDB, 
        with different SQL modes enabled. The results of this test ensure that the 
        DatabaseFeatures class accurately reflects the capabilities of the underlying database system.

        The test passes if the allows_group_by_selected_pks property is correctly set to 
        True for MySQL databases and False for MariaDB databases with the ONLY_FULL_GROUP_BY 
        SQL mode enabled, among other scenarios.
        """
        with mock.MagicMock() as _connection:
            _connection.mysql_is_mariadb = False
            database_features = DatabaseFeatures(_connection)
            self.assertIs(database_features.allows_group_by_selected_pks, True)

        with mock.MagicMock() as _connection:
            _connection.mysql_is_mariadb = False
            _connection.sql_mode = {}
            database_features = DatabaseFeatures(_connection)
            self.assertIs(database_features.allows_group_by_selected_pks, True)

        with mock.MagicMock() as _connection:
            _connection.mysql_is_mariadb = True
            _connection.sql_mode = {"ONLY_FULL_GROUP_BY"}
            database_features = DatabaseFeatures(_connection)
            self.assertIs(database_features.allows_group_by_selected_pks, False)
