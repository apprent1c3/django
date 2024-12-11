import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest import mock, skipUnless

from django.db import connection
from django.db.backends.postgresql.client import DatabaseClient
from django.test import SimpleTestCase


class PostgreSqlDbshellCommandTestCase(SimpleTestCase):
    def settings_to_cmd_args_env(self, settings_dict, parameters=None):
        """

        Converts a dictionary of database settings into command line arguments and environment variables.

        This function takes a dictionary of database settings and an optional list of parameters.
        It prepares the settings for use with a database client by converting them into command line arguments and environment variables.
        The function also ensures that the 'OPTIONS' key is present in the settings dictionary, creating it if necessary.

        The resulting command line arguments and environment variables can be used to configure a database client.

        :param settings_dict: A dictionary of database settings.
        :param parameters: An optional list of parameters to consider when converting settings.
        :return: A representation of the settings as command line arguments and environment variables.

        """
        if parameters is None:
            parameters = []
        settings_dict.setdefault("OPTIONS", {})
        return DatabaseClient.settings_to_cmd_args_env(settings_dict, parameters)

    def test_basic(self):
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "NAME": "dbname",
                    "USER": "someuser",
                    "PASSWORD": "somepassword",
                    "HOST": "somehost",
                    "PORT": "444",
                }
            ),
            (
                ["psql", "-U", "someuser", "-h", "somehost", "-p", "444", "dbname"],
                {"PGPASSWORD": "somepassword"},
            ),
        )

    def test_nopass(self):
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "NAME": "dbname",
                    "USER": "someuser",
                    "HOST": "somehost",
                    "PORT": "444",
                }
            ),
            (
                ["psql", "-U", "someuser", "-h", "somehost", "-p", "444", "dbname"],
                None,
            ),
        )

    def test_ssl_certificate(self):
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "NAME": "dbname",
                    "USER": "someuser",
                    "HOST": "somehost",
                    "PORT": "444",
                    "OPTIONS": {
                        "sslmode": "verify-ca",
                        "sslrootcert": "root.crt",
                        "sslcert": "client.crt",
                        "sslkey": "client.key",
                    },
                }
            ),
            (
                ["psql", "-U", "someuser", "-h", "somehost", "-p", "444", "dbname"],
                {
                    "PGSSLCERT": "client.crt",
                    "PGSSLKEY": "client.key",
                    "PGSSLMODE": "verify-ca",
                    "PGSSLROOTCERT": "root.crt",
                },
            ),
        )

    def test_service(self):
        self.assertEqual(
            self.settings_to_cmd_args_env({"OPTIONS": {"service": "django_test"}}),
            (["psql"], {"PGSERVICE": "django_test"}),
        )

    def test_passfile(self):
        """

        Tests the conversion of database settings to command line arguments and environment variables when a passfile is specified.

        The function checks that the settings are correctly translated into command line arguments for the `psql` command and environment variables, specifically the `PGPASSFILE` variable.

        It covers two scenarios: 
        - when a complete set of database connection settings (including name, user, host, port, and passfile) are provided, 
        - and when only the passfile and a service name are specified.

        """
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "NAME": "dbname",
                    "USER": "someuser",
                    "HOST": "somehost",
                    "PORT": "444",
                    "OPTIONS": {
                        "passfile": "~/.custompgpass",
                    },
                }
            ),
            (
                ["psql", "-U", "someuser", "-h", "somehost", "-p", "444", "dbname"],
                {"PGPASSFILE": "~/.custompgpass"},
            ),
        )
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "OPTIONS": {
                        "service": "django_test",
                        "passfile": "~/.custompgpass",
                    },
                }
            ),
            (
                ["psql"],
                {"PGSERVICE": "django_test", "PGPASSFILE": "~/.custompgpass"},
            ),
        )

    def test_column(self):
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "NAME": "dbname",
                    "USER": "some:user",
                    "PASSWORD": "some:password",
                    "HOST": "::1",
                    "PORT": "444",
                }
            ),
            (
                ["psql", "-U", "some:user", "-h", "::1", "-p", "444", "dbname"],
                {"PGPASSWORD": "some:password"},
            ),
        )

    def test_accent(self):
        username = "rôle"
        password = "sésame"
        self.assertEqual(
            self.settings_to_cmd_args_env(
                {
                    "NAME": "dbname",
                    "USER": username,
                    "PASSWORD": password,
                    "HOST": "somehost",
                    "PORT": "444",
                }
            ),
            (
                ["psql", "-U", username, "-h", "somehost", "-p", "444", "dbname"],
                {"PGPASSWORD": password},
            ),
        )

    def test_parameters(self):
        self.assertEqual(
            self.settings_to_cmd_args_env({"NAME": "dbname"}, ["--help"]),
            (["psql", "--help", "dbname"], None),
        )

    @skipUnless(connection.vendor == "postgresql", "Requires a PostgreSQL connection")
    def test_sigint_handler(self):
        """SIGINT is ignored in Python and passed to psql to abort queries."""

        def _mock_subprocess_run(*args, **kwargs):
            """
            ..: 
                Verify that the signal handler for SIGINT is set to SIG_IGN.

                This function checks the current signal handler for the SIGINT signal, 
                which is typically generated by the user pressing Ctrl+C. It asserts 
                that the signal handler is set to SIG_IGN, indicating that the signal 
                is being ignored. 

                :raises AssertionError: If the signal handler for SIGINT is not SIG_IGN.
            """
            handler = signal.getsignal(signal.SIGINT)
            self.assertEqual(handler, signal.SIG_IGN)

        sigint_handler = signal.getsignal(signal.SIGINT)
        # The default handler isn't SIG_IGN.
        self.assertNotEqual(sigint_handler, signal.SIG_IGN)
        with mock.patch("subprocess.run", new=_mock_subprocess_run):
            connection.client.runshell([])
        # dbshell restores the original handler.
        self.assertEqual(sigint_handler, signal.getsignal(signal.SIGINT))

    def test_crash_password_does_not_leak(self):
        # The password doesn't leak in an exception that results from a client
        # crash.
        """
        Tests that a crash password is not leaked in the output when the client crashes. 
        This test simulates a client crash by running a fake client with a known password, 
        then validates that the password is not present in the error message.
        """
        args, env = self.settings_to_cmd_args_env({"PASSWORD": "somepassword"}, [])
        if env:
            env = {**os.environ, **env}
        fake_client = Path(__file__).with_name("fake_client.py")
        args[0:1] = [sys.executable, str(fake_client)]
        with self.assertRaises(subprocess.CalledProcessError) as ctx:
            subprocess.run(args, check=True, env=env)
        self.assertNotIn("somepassword", str(ctx.exception))
