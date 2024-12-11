from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase


class DbshellCommandTestCase(SimpleTestCase):
    def test_command_missing(self):
        """
        Tests the command when the required executable is missing.

        Verifies that the application correctly handles the scenario in which the executable 
        required by the command is not installed or not in the system's path, raising a 
        CommandError with the expected error message. The test checks for the presence of 
        the executable by attempting to invoke the command and confirming that the 
        predicted error occurs.

        :raises: CommandError if the executable is missing
        """
        msg = (
            "You appear not to have the %r program installed or on your path."
            % connection.client.executable_name
        )
        with self.assertRaisesMessage(CommandError, msg):
            with mock.patch("subprocess.run", side_effect=FileNotFoundError):
                call_command("dbshell")
