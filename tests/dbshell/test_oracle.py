from unittest import mock, skipUnless

from django.db import connection
from django.db.backends.oracle.client import DatabaseClient
from django.test import SimpleTestCase


@skipUnless(connection.vendor == "oracle", "Requires oracledb to be installed")
class OracleDbshellTests(SimpleTestCase):
    def settings_to_cmd_args_env(self, settings_dict, parameters=None, rlwrap=False):
        """

        Generates command line arguments and environment variables from the provided settings dictionary.

        This function takes a dictionary of settings and an optional list of parameters, 
        then returns the equivalent command line arguments and environment variables.
        It also supports optional rlwrap functionality, which can be enabled by setting the rlwrap parameter to True.

        :param settings_dict: A dictionary containing the settings to be converted to command line arguments and environment variables.
        :param parameters: An optional list of parameters to be included in the command line arguments. Defaults to an empty list if not provided.
        :param rlwrap: An optional boolean flag to enable or disable rlwrap functionality. Defaults to False.
        :return: The generated command line arguments and environment variables based on the provided settings and parameters.

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
        """

        Tests the settings_to_cmd_args_env method to ensure it correctly generates 
        command line arguments for sqlplus when using rlwrap. 

        The function verifies that the generated command arguments include the rlwrap 
        binary, sqlplus command, and the required connection string. 

        """
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
