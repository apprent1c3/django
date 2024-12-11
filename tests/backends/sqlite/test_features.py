from unittest import mock, skipUnless

from django.db import OperationalError, connection
from django.test import TestCase


@skipUnless(connection.vendor == "sqlite", "SQLite tests.")
class FeaturesTests(TestCase):
    def test_supports_json_field_operational_error(self):
        """

        Tests whether an OperationalError is properly raised when checking for JSON field support.

        This test checks the scenario where a database connection error occurs while trying to check if the database supports JSON fields.
        The expected output is that an OperationalError is raised with a specific error message.

        The test covers the case where the connection to the database is not operational, simulating a situation where the database file cannot be opened.

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
