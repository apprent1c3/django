from unittest import mock

from django.db import connection
from django.db.backends.base.client import BaseDatabaseClient
from django.test import SimpleTestCase


class SimpleDatabaseClientTests(SimpleTestCase):
    def setUp(self):
        self.client = BaseDatabaseClient(connection=connection)

    def test_settings_to_cmd_args_env(self):
        """
        Tests that the settings_to_cmd_args_env method is implemented by subclasses of BaseDatabaseClient, 
        unless the runshell method is overridden. Verifies that a NotImplementedError is raised with a specific 
        error message if this method is not provided, ensuring that subclasses adhere to the required interface.
        """
        msg = (
            "subclasses of BaseDatabaseClient must provide a "
            "settings_to_cmd_args_env() method or override a runshell()."
        )
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.client.settings_to_cmd_args_env(None, None)

    def test_runshell_use_environ(self):
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
