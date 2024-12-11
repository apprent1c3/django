import sys
import unittest
from unittest import mock

from django import __version__
from django.core.management import CommandError, call_command
from django.core.management.commands import shell
from django.test import SimpleTestCase
from django.test.utils import captured_stdin, captured_stdout


class ShellCommandTestCase(SimpleTestCase):
    script_globals = 'print("__name__" in globals())'
    script_with_inline_function = (
        "import django\ndef f():\n    print(django.__version__)\nf()"
    )

    def test_command_option(self):
        with self.assertLogs("test", "INFO") as cm:
            call_command(
                "shell",
                command=(
                    "import django; from logging import getLogger; "
                    'getLogger("test").info(django.__version__)'
                ),
            )
        self.assertEqual(cm.records[0].getMessage(), __version__)

    def test_command_option_globals(self):
        with captured_stdout() as stdout:
            call_command("shell", command=self.script_globals)
        self.assertEqual(stdout.getvalue().strip(), "True")

    def test_command_option_inline_function_call(self):
        with captured_stdout() as stdout:
            call_command("shell", command=self.script_with_inline_function)
        self.assertEqual(stdout.getvalue().strip(), __version__)

    @unittest.skipIf(
        sys.platform == "win32", "Windows select() doesn't support file descriptors."
    )
    @mock.patch("django.core.management.commands.shell.select")
    def test_stdin_read(self, select):
        with captured_stdin() as stdin, captured_stdout() as stdout:
            stdin.write("print(100)\n")
            stdin.seek(0)
            call_command("shell")
        self.assertEqual(stdout.getvalue().strip(), "100")

    @unittest.skipIf(
        sys.platform == "win32",
        "Windows select() doesn't support file descriptors.",
    )
    @mock.patch("django.core.management.commands.shell.select")  # [1]
    def test_stdin_read_globals(self, select):
        with captured_stdin() as stdin, captured_stdout() as stdout:
            stdin.write(self.script_globals)
            stdin.seek(0)
            call_command("shell")
        self.assertEqual(stdout.getvalue().strip(), "True")

    @unittest.skipIf(
        sys.platform == "win32",
        "Windows select() doesn't support file descriptors.",
    )
    @mock.patch("django.core.management.commands.shell.select")  # [1]
    def test_stdin_read_inline_function_call(self, select):
        with captured_stdin() as stdin, captured_stdout() as stdout:
            stdin.write(self.script_with_inline_function)
            stdin.seek(0)
            call_command("shell")
        self.assertEqual(stdout.getvalue().strip(), __version__)

    def test_ipython(self):
        cmd = shell.Command()
        mock_ipython = mock.Mock(start_ipython=mock.MagicMock())

        with mock.patch.dict(sys.modules, {"IPython": mock_ipython}):
            cmd.ipython({})

        self.assertEqual(mock_ipython.start_ipython.mock_calls, [mock.call(argv=[])])

    @mock.patch("django.core.management.commands.shell.select.select")  # [1]
    @mock.patch.dict("sys.modules", {"IPython": None})
    def test_shell_with_ipython_not_installed(self, select):
        """
        Tests the Django shell command when IPython interface is not installed.

        This test case simulates the scenario where IPython is not available, 
        and verifies that the 'shell' command raises a CommandError with an appropriate message when attempting to use the IPython interface.

        The test mocks the 'select' function and sets 'IPython' to None in sys.modules to emulate the absence of IPython, 
        then checks for the expected error message when calling the 'shell' command with the 'ipython' interface specified.
        """
        select.return_value = ([], [], [])
        with self.assertRaisesMessage(
            CommandError, "Couldn't import ipython interface."
        ):
            call_command("shell", interface="ipython")

    def test_bpython(self):
        """

        Tests the functionality of the bpython command.

        This test case verifies that the bpython command is executed correctly by mocking the bpython module and checking if the embed function is called as expected.

        The test scenario simulates the execution of the bpython command and confirms that it invokes the embed function from the bpython module, ensuring the correct interaction between the command and the bpython interpreter.

        """
        cmd = shell.Command()
        mock_bpython = mock.Mock(embed=mock.MagicMock())

        with mock.patch.dict(sys.modules, {"bpython": mock_bpython}):
            cmd.bpython({})

        self.assertEqual(mock_bpython.embed.mock_calls, [mock.call()])

    @mock.patch("django.core.management.commands.shell.select.select")  # [1]
    @mock.patch.dict("sys.modules", {"bpython": None})
    def test_shell_with_bpython_not_installed(self, select):
        """
        Tests the shell command when bpython is specified as the interface but is not installed.

        Verifies that the command raises a CommandError with a message indicating that the bpython interface could not be imported, when attempting to use it without having bpython installed.

        This test ensures that the shell command behaves correctly and provides a meaningful error message when the selected interface is unavailable due to missing dependencies.
        """
        select.return_value = ([], [], [])
        with self.assertRaisesMessage(
            CommandError, "Couldn't import bpython interface."
        ):
            call_command("shell", interface="bpython")

    def test_python(self):
        cmd = shell.Command()
        mock_code = mock.Mock(interact=mock.MagicMock())

        with mock.patch.dict(sys.modules, {"code": mock_code}):
            cmd.python({"no_startup": True})

        self.assertEqual(mock_code.interact.mock_calls, [mock.call(local={})])

    # [1] Patch select to prevent tests failing when the test suite is run
    # in parallel mode. The tests are run in a subprocess and the subprocess's
    # stdin is closed and replaced by /dev/null. Reading from /dev/null always
    # returns EOF and so select always shows that sys.stdin is ready to read.
    # This causes problems because of the call to select.select() toward the
    # end of shell's handle() method.
