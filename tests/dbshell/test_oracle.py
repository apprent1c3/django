from unittest import mock, skipUnless

from django.db import connection
from django.db.backends.oracle.client import DatabaseClient
from django.test import SimpleTestCase


@skipUnless(connection.vendor == "oracle", "Requires oracledb to be installed")
class OracleDbshellTests(SimpleTestCase):
    def settings_to_cmd_args_env(self, settings_dict, parameters=None, rlwrap=False):
        """
        Converts database settings into command arguments and environment variables.

        :param settings_dict: Dictionary containing database connection settings.
        :param parameters: Optional list of additional command-line parameters.
        :param rlwrap: Optional boolean flag to enable support for rlwrap.
        :return: A dictionary containing command arguments and environment variables for a database client.
        :note: The function simulates the presence or absence of rlwrap, depending on the `rlwrap` parameter, to ensure consistent behavior across different environments.
        """
        if parameters is None:
            parameters = []
        with mock.patch(
            "shutil.which", return_value="/usr/bin/rlwrap" if rlwrap else None
        ):
            return DatabaseClient.settings_to_cmd_args_env(settings_dict, parameters)

    def test_without_rlwrap(self):
        expected_args = [
            "sqlplus",
            "-L",
            connection.client.connect_string(connection.settings_dict),
        ]
        self.assertEqual(
            self.settings_to_cmd_args_env(connection.settings_dict, rlwrap=False),
            (expected_args, None),
        )

    def test_with_rlwrap(self):
        expected_args = [
            "/usr/bin/rlwrap",
            "sqlplus",
            "-L",
            connection.client.connect_string(connection.settings_dict),
        ]
        self.assertEqual(
            self.settings_to_cmd_args_env(connection.settings_dict, rlwrap=True),
            (expected_args, None),
        )

    def test_parameters(self):
        """
        Tests that the function correctly converts connection settings to command line arguments when requesting help.

        Verifies that the function returns the expected command line arguments and no environment variables when the '-HELP' parameter is specified.

        The function is expected to handle the conversion of connection settings to command line arguments, including the proper formatting of the connect string and the inclusion of the requested help parameter.
        """
        expected_args = [
            "sqlplus",
            "-L",
            connection.client.connect_string(connection.settings_dict),
            "-HELP",
        ]
        self.assertEqual(
            self.settings_to_cmd_args_env(
                connection.settings_dict,
                parameters=["-HELP"],
            ),
            (expected_args, None),
        )
