from unittest import mock

from django.db import connection
from django.db.backends.base.client import BaseDatabaseClient
from django.test import SimpleTestCase


class SimpleDatabaseClientTests(SimpleTestCase):
    def setUp(self):
        self.client = BaseDatabaseClient(connection=connection)

    def test_settings_to_cmd_args_env(self):
        """

        Tests that a subclass of BaseDatabaseClient implements or overrides the settings_to_cmd_args_env method or runshell method.

        Verifies that attempting to call the settings_to_cmd_args_env method without proper implementation raises a NotImplementedError 
        with a specific error message. This ensures that users of the BaseDatabaseClient class provide the necessary functionality.

        """
        msg = (
            "subclasses of BaseDatabaseClient must provide a "
            "settings_to_cmd_args_env() method or override a runshell()."
        )
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.client.settings_to_cmd_args_env(None, None)

    def test_runshell_use_environ(self):
        """

        Tests the :meth:`BaseDatabaseClient.runshell` method to ensure it properly utilizes 
        environment variables when running the shell. 

        Two test scenarios are covered: 
        - when no environment variables are provided, 
        - when an empty dictionary of environment variables is provided.

        Verifies that the :func:`subprocess.run` function is called once with the correct environment settings.

        """
        for env in [None, {}]:
            with self.subTest(env=env):
                with mock.patch("subprocess.run") as run:
                    with mock.patch.object(
                        BaseDatabaseClient,
                        "settings_to_cmd_args_env",
                        return_value=([], env),
                    ):
                        self.client.runshell(None)
                    run.assert_called_once_with([], env=None, check=True)
