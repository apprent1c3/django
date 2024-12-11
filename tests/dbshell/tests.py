from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase


class DbshellCommandTestCase(SimpleTestCase):
    def test_command_missing(self):
        """
        Tests that a CommandError is raised when the command to start a database shell is executed but the required executable is missing from the system's PATH.

        This test simulates the scenario where the executable required to start the database shell is not installed or not available on the system, and checks that the expected error message is raised as a result.

        Args:
            None

        Returns:
            None

        Raises:
            CommandError: If the executable required to start the database shell is not found on the system's PATH. The error message will indicate that the executable appears not to be installed or on the path.
        """
        msg = (
            "You appear not to have the %r program installed or on your path."
            % connection.client.executable_name
        )
        with self.assertRaisesMessage(CommandError, msg):
            with mock.patch("subprocess.run", side_effect=FileNotFoundError):
                call_command("dbshell")
