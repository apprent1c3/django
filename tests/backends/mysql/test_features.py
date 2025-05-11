from unittest import mock, skipUnless

from django.db import connection
from django.db.backends.mysql.features import DatabaseFeatures
from django.test import TestCase


@skipUnless(connection.vendor == "mysql", "MySQL tests")
class TestFeatures(TestCase):
    def test_supports_transactions(self):
        """
        Tests whether the current MySQL storage engine supports transactions, expecting InnoDB to support transactions and MyISAM not to.
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
        Uint tests the behavior of `allows_group_by_selected_pks` property of `DatabaseFeatures` class under different database connection settings, specifically whether MySQL or MariaDB is being used and what SQL mode is enabled.
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
