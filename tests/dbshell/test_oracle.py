from unittest import mock, skipUnless

from django.db import connection
from django.db.backends.oracle.client import DatabaseClient
from django.test import SimpleTestCase


@skipUnless(connection.vendor == "oracle", "Requires oracledb to be installed")
class OracleDbshellTests(SimpleTestCase):
    def settings_to_cmd_args_env(self, settings_dict, parameters=None, rlwrap=False):
        """

        Generate command line arguments and environment variables for a database client.

        This function takes a dictionary of settings and a list of parameters, and returns a tuple 
        containing command line arguments and environment variables suitable for use with a database client.

        The function optionally enables rlwrap, a readline wrapper for command-line tools, by mocking 
        the shutil.which function to return the path to the rlwrap executable.

        Parameters can be passed to customize the generated command line arguments.

        :param settings_dict: Dictionary of settings for the database client
        :param parameters: List of parameters to customize the command line arguments (default: [])
        :param rlwrap: Enable rlwrap (default: False)
        :rtype: tuple

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

        Tests the conversion of connection settings to command arguments when using rlwrap.

        Verifies that the function correctly generates the expected command arguments for rlwrap, 
        including the sqlplus command and the connection client's connect string.

        The test case asserts that the generated command arguments match the expected output, 
        ensuring that the function behaves as expected when rlwrap is enabled.

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
        """
        Test the conversion of connection settings to command line arguments with additional parameters.

        This test verifies that the function correctly includes extra parameters, 
        such as the '-HELP' option, when generating the command line arguments 
        for a given set of connection settings. It checks that the resulting 
        arguments match the expected output, ensuring the function behaves 
        as intended when handling additional parameters
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
