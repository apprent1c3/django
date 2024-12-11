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
        """

        Tests the ability to read globals from standard input when running the Django shell command.

        This test case checks that when the Django shell command is executed, it correctly reads
        globals from standard input and makes them available in the shell environment.

        The test simulates user input by writing a script containing globals to standard input,
        then checks that the output of the shell command reflects the expected result of executing
        those globals.

        By verifying that the shell command produces the expected output, this test ensures that
        the command correctly integrates with standard input and provides a functional shell
        environment.

        """
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
        """
        Tests the Django shell command when an inline function call is read from standard input.

        This test ensures that when the Django shell is invoked and an inline function call
        is provided as input, the function is executed correctly and its output is displayed.

        The test specifically checks the output of the inline function call to verify that it
        matches the expected result. It uses mocking to isolate the test from the underlying
        system's select functionality, allowing the test to focus on the Django shell's behavior.

        Note that this test is skipped on Windows platforms due to limitations in the Windows
        implementation of the select function.
        """
        with captured_stdin() as stdin, captured_stdout() as stdout:
            stdin.write(self.script_with_inline_function)
            stdin.seek(0)
            call_command("shell")
        self.assertEqual(stdout.getvalue().strip(), __version__)

    def test_ipython(self):
        """
        Tests the ipython command functionality by simulating an IPython environment.

        This test case verifies that the ipython command is properly invoked when 
        called. It checks that the command correctly imports the IPython module and 
        calls the start_ipython method with the expected arguments.

        The test uses mocking to isolate the IPython module and ensure that the test 
        results are consistent and reliable. The mock IPython module is used to 
        validate the calls made to the start_ipython method.

        The test asserts that the start_ipython method is called once with an empty 
        argv list, indicating that the ipython command was successfully executed.


        """
        cmd = shell.Command()
        mock_ipython = mock.Mock(start_ipython=mock.MagicMock())

        with mock.patch.dict(sys.modules, {"IPython": mock_ipython}):
            cmd.ipython({})

        self.assertEqual(mock_ipython.start_ipython.mock_calls, [mock.call(argv=[])])

    @mock.patch("django.core.management.commands.shell.select.select")  # [1]
    @mock.patch.dict("sys.modules", {"IPython": None})
    def test_shell_with_ipython_not_installed(self, select):
        select.return_value = ([], [], [])
        with self.assertRaisesMessage(
            CommandError, "Couldn't import ipython interface."
        ):
            call_command("shell", interface="ipython")

    def test_bpython(self):
        cmd = shell.Command()
        mock_bpython = mock.Mock(embed=mock.MagicMock())

        with mock.patch.dict(sys.modules, {"bpython": mock_bpython}):
            cmd.bpython({})

        self.assertEqual(mock_bpython.embed.mock_calls, [mock.call()])

    @mock.patch("django.core.management.commands.shell.select.select")  # [1]
    @mock.patch.dict("sys.modules", {"bpython": None})
    def test_shell_with_bpython_not_installed(self, select):
        select.return_value = ([], [], [])
        with self.assertRaisesMessage(
            CommandError, "Couldn't import bpython interface."
        ):
            call_command("shell", interface="bpython")

    def test_python(self):
        """

        Tests that the python command correctly invokes the code module with the given options.

        This test ensures that the code module's interact function is called with an empty local scope when the
        'no_startup' option is enabled. This option prevents the execution of any startup scripts, providing a
        clean environment for testing or interactive use. The test verifies that the code module is properly
        mocked and that the expected call to interact is made, confirming the correct behavior of the python
        command in this scenario.

        """
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
