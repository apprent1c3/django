from unittest import mock, skipUnless

from django.db import OperationalError, connection
from django.test import TestCase


@skipUnless(connection.vendor == "sqlite", "SQLite tests.")
class FeaturesTests(TestCase):
    def test_supports_json_field_operational_error(self):
        """
        Tests that the `supports_json_field` attribute of the connection features raises an OperationalError with the correct message when the database is unavailable.
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
