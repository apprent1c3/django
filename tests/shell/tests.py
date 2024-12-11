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
        """
        Tests the command option functionality by executing a shell command that imports Django 
        and logs its version. The test verifies that the logged message matches the expected 
        Django version. This ensures that the command option is correctly configured and 
        executing the specified command as expected.
        """
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
        """
        :param self: Instance of the test class
        :raises AssertionError: If the test fails
        :returns: None

        Tests whether the given script globals are properly set as command options when running the shell command.

        Verifies that the script globals are successfully executed and produce the expected output, confirming that the option is correctly processed by the command.
        """
        with captured_stdout() as stdout:
            call_command("shell", command=self.script_globals)
        self.assertEqual(stdout.getvalue().strip(), "True")

    def test_command_option_inline_function_call(self):
        """
        Tests that the command option can handle inline function calls.

        Verifies that the :func:`call_command` successfully executes a command that includes
        an inline function call and that the output matches the expected version number.\"\"\"
        ```
        """
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
        """

        Tests if the Django management shell command can correctly handle inline function calls 
        from standard input, ensuring it produces the expected output.

        The test emulates user input through stdin, providing a script that includes an inline 
        function call. It then verifies that the command's output matches the expected result.

        Note: This test is skipped on Windows platforms due to limitations in the select() 
        function when dealing with file descriptors.

        """
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
        Tests the shell command when attempting to use the IPython interface without IPython being installed.

        The test simulates a scenario where IPython is not available and verifies that the command raises a CommandError with a message indicating that the IPython interface could not be imported.
        """
        select.return_value = ([], [], [])
        with self.assertRaisesMessage(
            CommandError, "Couldn't import ipython interface."
        ):
            call_command("shell", interface="ipython")

    def test_bpython(self):
        """

        Tests the integration of the bpython interpreter with the command interface.
        Verifies that the bpython embed function is called when the bpython command is executed.
        This test ensures that the command interface correctly dispatches the bpython command
        to the bpython interpreter for execution.

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
        Tests that the Django shell command raises an error when the bpython interface is requested but the bpython library is not installed. This test case simulates the absence of the bpython module by patching the sys.modules dictionary and verifies that a CommandError is raised with the expected error message when attempting to use the bpython interface.
        """
        select.return_value = ([], [], [])
        with self.assertRaisesMessage(
            CommandError, "Couldn't import bpython interface."
        ):
            call_command("shell", interface="bpython")

    def test_python(self):
        """
        Tests the python command functionality.

        Verifies that the command correctly interacts with the code module by
        mocking the code module and asserting the expected interaction.

        Specifically, this test checks that when the 'no_startup' option is enabled,
        the command calls the interact method of the code module with an empty local
        namespace.

        This ensures that the command behaves as expected under these specific
        conditions, providing a foundation for further testing and validation of the
        command's functionality.
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
