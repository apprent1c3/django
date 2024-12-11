from unittest import mock, skipUnless

from django.db import OperationalError, connection
from django.test import TestCase


@skipUnless(connection.vendor == "sqlite", "SQLite tests.")
class FeaturesTests(TestCase):
    def test_supports_json_field_operational_error(self):
        """

        Tests that the 'supports_json_field' attribute of the database connection features raises an OperationalError when 
        the database is unavailable. This check ensures that the application correctly handles a situation where it cannot 
        open the database file, providing a meaningful error message instead of failing silently or producing an unexpected 
        result.

        The test verifies that the OperationalError is propagated to the caller when an attempt to access the database fails, 
        indicated by the 'unable to open database file' error message.

        """
        if hasattr(connection.features, "supports_json_field"):
            del connection.features.supports_json_field
        msg = "unable to open database file"
        with mock.patch.object(
            connection,
            "cursor",
            side_effect=OperationalError(msg),
        ):
            with self.assertRaisesMessage(OperationalError, msg):
                connection.features.supports_json_field
