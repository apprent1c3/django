import os
from argparse import ArgumentDefaultsHelpFormatter
from io import StringIO
from unittest import mock

from admin_scripts.tests import AdminScriptTestCase

from django.apps import apps
from django.core import management
from django.core.checks import Tags
from django.core.management import BaseCommand, CommandError, find_commands
from django.core.management.utils import (
    find_command,
    get_random_secret_key,
    is_ignored_path,
    normalize_path_patterns,
    popen_wrapper,
)
from django.db import connection
from django.test import SimpleTestCase, override_settings
from django.test.utils import captured_stderr, extend_sys_path
from django.utils import translation

from .management.commands import dance


# A minimal set of apps to avoid system checks running on all apps.
@override_settings(
    INSTALLED_APPS=[
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "user_commands",
    ],
)
class CommandTests(SimpleTestCase):
    def test_command(self):
        """
        Tests the dance command by simulating its execution and verifying the output.

        This test case checks if the dance command returns the expected message when executed.
        The message should indicate that the system does not feel like dancing Rock'n'Roll.

        :raises AssertionError: if the expected message is not found in the command output
        """
        out = StringIO()
        management.call_command("dance", stdout=out)
        self.assertIn("I don't feel like dancing Rock'n'Roll.\n", out.getvalue())

    def test_command_style(self):
        out = StringIO()
        management.call_command("dance", style="Jive", stdout=out)
        self.assertIn("I don't feel like dancing Jive.\n", out.getvalue())
        # Passing options as arguments also works (thanks argparse)
        management.call_command("dance", "--style", "Jive", stdout=out)
        self.assertIn("I don't feel like dancing Jive.\n", out.getvalue())

    def test_language_preserved(self):
        with translation.override("fr"):
            management.call_command("dance", verbosity=0)
            self.assertEqual(translation.get_language(), "fr")

    def test_explode(self):
        """An unknown command raises CommandError"""
        with self.assertRaisesMessage(CommandError, "Unknown command: 'explode'"):
            management.call_command(("explode",))

    def test_system_exit(self):
        """Exception raised in a command should raise CommandError with
        call_command, but SystemExit when run from command line
        """
        with self.assertRaises(CommandError) as cm:
            management.call_command("dance", example="raise")
        self.assertEqual(cm.exception.returncode, 3)
        dance.Command.requires_system_checks = []
        try:
            with captured_stderr() as stderr, self.assertRaises(SystemExit) as cm:
                management.ManagementUtility(
                    ["manage.py", "dance", "--example=raise"]
                ).execute()
            self.assertEqual(cm.exception.code, 3)
        finally:
            dance.Command.requires_system_checks = "__all__"
        self.assertIn("CommandError", stderr.getvalue())

    def test_no_translations_deactivate_translations(self):
        """
        When the Command handle method is decorated with @no_translations,
        translations are deactivated inside the command.
        """
        current_locale = translation.get_language()
        with translation.override("pl"):
            result = management.call_command("no_translations")
            self.assertIsNone(result)
        self.assertEqual(translation.get_language(), current_locale)

    def test_find_command_without_PATH(self):
        """
        find_command should still work when the PATH environment variable
        doesn't exist (#22256).
        """
        current_path = os.environ.pop("PATH", None)

        try:
            self.assertIsNone(find_command("_missing_"))
        finally:
            if current_path is not None:
                os.environ["PATH"] = current_path

    def test_discover_commands_in_eggs(self):
        """
        Management commands can also be loaded from Python eggs.
        """
        egg_dir = "%s/eggs" % os.path.dirname(__file__)
        egg_name = "%s/basic.egg" % egg_dir
        with extend_sys_path(egg_name):
            with self.settings(INSTALLED_APPS=["commandegg"]):
                cmds = find_commands(
                    os.path.join(apps.get_app_config("commandegg").path, "management")
                )
        self.assertEqual(cmds, ["eggcommand"])

    def test_call_command_option_parsing(self):
        """
        When passing the long option name to call_command, the available option
        key is the option dest name (#22985).
        """
        out = StringIO()
        management.call_command("dance", stdout=out, opt_3=True)
        self.assertIn("option3", out.getvalue())
        self.assertNotIn("opt_3", out.getvalue())
        self.assertNotIn("opt-3", out.getvalue())

    def test_call_command_option_parsing_non_string_arg(self):
        """
        It should be possible to pass non-string arguments to call_command.
        """
        out = StringIO()
        management.call_command("dance", 1, verbosity=0, stdout=out)
        self.assertIn("You passed 1 as a positional argument.", out.getvalue())

    def test_calling_a_command_with_only_empty_parameter_should_ends_gracefully(self):
        out = StringIO()
        management.call_command("hal", "--empty", stdout=out)
        self.assertEqual(out.getvalue(), "\nDave, I can't do that.\n")

    def test_calling_command_with_app_labels_and_parameters_should_be_ok(self):
        out = StringIO()
        management.call_command("hal", "myapp", "--verbosity", "3", stdout=out)
        self.assertIn(
            "Dave, my mind is going. I can feel it. I can feel it.\n", out.getvalue()
        )

    def test_calling_command_with_parameters_and_app_labels_at_the_end_should_be_ok(
        self,
    ):
        """
        Verifies that a command can be successfully executed with parameters and application labels provided at the end. 
        The function checks if the command's output, as captured by a string buffer, contains the expected result, 
        indicating that the command was executed correctly with the provided arguments and application labels.
        """
        out = StringIO()
        management.call_command("hal", "--verbosity", "3", "myapp", stdout=out)
        self.assertIn(
            "Dave, my mind is going. I can feel it. I can feel it.\n", out.getvalue()
        )

    def test_calling_a_command_with_no_app_labels_and_parameters_raise_command_error(
        self,
    ):
        with self.assertRaises(CommandError):
            management.call_command("hal")

    def test_output_transaction(self):
        output = management.call_command(
            "transaction", stdout=StringIO(), no_color=True
        )
        self.assertTrue(
            output.strip().startswith(connection.ops.start_transaction_sql())
        )
        self.assertTrue(output.strip().endswith(connection.ops.end_transaction_sql()))

    def test_call_command_no_checks(self):
        """
        By default, call_command should not trigger the check framework, unless
        specifically asked.
        """
        self.counter = 0

        def patched_check(self_, **kwargs):
            self.counter += 1
            self.kwargs = kwargs

        saved_check = BaseCommand.check
        BaseCommand.check = patched_check
        try:
            management.call_command("dance", verbosity=0)
            self.assertEqual(self.counter, 0)
            management.call_command("dance", verbosity=0, skip_checks=False)
            self.assertEqual(self.counter, 1)
            self.assertEqual(self.kwargs, {})
        finally:
            BaseCommand.check = saved_check

    def test_requires_system_checks_empty(self):
        with mock.patch(
            "django.core.management.base.BaseCommand.check"
        ) as mocked_check:
            management.call_command("no_system_checks")
        self.assertIs(mocked_check.called, False)

    def test_requires_system_checks_specific(self):
        with mock.patch(
            "django.core.management.base.BaseCommand.check"
        ) as mocked_check:
            management.call_command("specific_system_checks", skip_checks=False)
        mocked_check.assert_called_once_with(tags=[Tags.staticfiles, Tags.models])

    def test_requires_system_checks_invalid(self):
        class Command(BaseCommand):
            requires_system_checks = "x"

        msg = "requires_system_checks must be a list or tuple."
        with self.assertRaisesMessage(TypeError, msg):
            Command()

    def test_check_migrations(self):
        """

        Tests that the 'dance' command respects the requires_migrations_checks flag.
        Verifies that when flag is False, the command does not perform migration checks,
        and when the flag is True, it does.

        Checks the behavior of the command by calling it twice with different flag values
        and asserting the corresponding calls to the migration checking functionality.
        Ensures the original flag value is restored after the test, regardless of the outcome.

        """
        requires_migrations_checks = dance.Command.requires_migrations_checks
        self.assertIs(requires_migrations_checks, False)
        try:
            with mock.patch.object(BaseCommand, "check_migrations") as check_migrations:
                management.call_command("dance", verbosity=0)
                self.assertFalse(check_migrations.called)
                dance.Command.requires_migrations_checks = True
                management.call_command("dance", verbosity=0)
                self.assertTrue(check_migrations.called)
        finally:
            dance.Command.requires_migrations_checks = requires_migrations_checks

    def test_call_command_unrecognized_option(self):
        msg = (
            "Unknown option(s) for dance command: unrecognized. Valid options "
            "are: example, force_color, help, integer, no_color, opt_3, "
            "option3, pythonpath, settings, skip_checks, stderr, stdout, "
            "style, traceback, verbosity, version."
        )
        with self.assertRaisesMessage(TypeError, msg):
            management.call_command("dance", unrecognized=1)

        msg = (
            "Unknown option(s) for dance command: unrecognized, unrecognized2. "
            "Valid options are: example, force_color, help, integer, no_color, "
            "opt_3, option3, pythonpath, settings, skip_checks, stderr, "
            "stdout, style, traceback, verbosity, version."
        )
        with self.assertRaisesMessage(TypeError, msg):
            management.call_command("dance", unrecognized=1, unrecognized2=1)

    def test_call_command_with_required_parameters_in_options(self):
        out = StringIO()
        management.call_command(
            "required_option", need_me="foo", needme2="bar", stdout=out
        )
        self.assertIn("need_me", out.getvalue())
        self.assertIn("needme2", out.getvalue())

    def test_call_command_with_required_parameters_in_mixed_options(self):
        """

        Tests whether a management command can be successfully called with a mix of 
        optional and required parameters, verifying that the parameters are correctly 
        processed and reflected in the command's output.

        The test checks for the presence of required option values in the command's 
        stdout, ensuring that both short and long option formats are handled correctly.

        """
        out = StringIO()
        management.call_command(
            "required_option", "--need-me=foo", needme2="bar", stdout=out
        )
        self.assertIn("need_me", out.getvalue())
        self.assertIn("needme2", out.getvalue())

    def test_command_add_arguments_after_common_arguments(self):
        out = StringIO()
        management.call_command("common_args", stdout=out)
        self.assertIn("Detected that --version already exists", out.getvalue())

    def test_mutually_exclusive_group_required_options(self):
        """

        Tests that the mutually exclusive group of options in the command are handled correctly.

        The test case covers three scenarios:
        - Passing an option that is part of the mutually exclusive group and verifying its presence in the output.
        - Passing a different option from the mutually exclusive group and verifying its presence in the output.
        - Not passing any of the options from the mutually exclusive group and verifying that the correct error message is raised, indicating that at least one of the options is required.

        """
        out = StringIO()
        management.call_command("mutually_exclusive_required", foo_id=1, stdout=out)
        self.assertIn("foo_id", out.getvalue())
        management.call_command(
            "mutually_exclusive_required", foo_name="foo", stdout=out
        )
        self.assertIn("foo_name", out.getvalue())
        msg = (
            "Error: one of the arguments --foo-id --foo-name --foo-list "
            "--append_const --const --count --flag_false --flag_true is "
            "required"
        )
        with self.assertRaisesMessage(CommandError, msg):
            management.call_command("mutually_exclusive_required", stdout=out)

    def test_mutually_exclusive_group_required_const_options(self):
        """

        Tests that the mutually exclusive group required options in a management command work as expected.

        The function checks several command line arguments, each with a corresponding constant value, 
        to ensure they produce the correct output when used independently. The arguments tested are 
        append_const, const, count, flag_false, and flag_true.

        It verifies the output of the management command 'mutually_exclusive_required' when each 
        argument is provided as a command line option or as a keyword argument, confirming that 
        the expected output is generated in both scenarios.

        """
        tests = [
            ("append_const", [42]),
            ("const", 31),
            ("count", 1),
            ("flag_false", False),
            ("flag_true", True),
        ]
        for arg, value in tests:
            out = StringIO()
            expected_output = "%s=%s" % (arg, value)
            with self.subTest(arg=arg):
                management.call_command(
                    "mutually_exclusive_required",
                    "--%s" % arg,
                    stdout=out,
                )
                self.assertIn(expected_output, out.getvalue())
                out.truncate(0)
                management.call_command(
                    "mutually_exclusive_required",
                    **{arg: value, "stdout": out},
                )
                self.assertIn(expected_output, out.getvalue())

    def test_mutually_exclusive_group_required_with_same_dest_options(self):
        """
        Test that mutually exclusive options with the same destination cannot be passed together.

        Checks if attempting to pass multiple options with the same destination to the 
        'mutually_exclusive_required_with_same_dest' command raises a TypeError. The test
        covers various combinations of options to ensure that the command correctly handles
        mutually exclusive arguments with the same destination.

        Raises:
            TypeError: If options with the same destination are passed together.

        """
        tests = [
            {"until": "2"},
            {"for": "1", "until": "2"},
        ]
        msg = (
            "Cannot pass the dest 'until' that matches multiple arguments via "
            "**options."
        )
        for options in tests:
            with self.subTest(options=options):
                with self.assertRaisesMessage(TypeError, msg):
                    management.call_command(
                        "mutually_exclusive_required_with_same_dest",
                        **options,
                    )

    def test_mutually_exclusive_group_required_with_same_dest_args(self):
        tests = [
            ("--until=1",),
            ("--until", 1),
            ("--for=1",),
            ("--for", 1),
        ]
        for args in tests:
            out = StringIO()
            with self.subTest(options=args):
                management.call_command(
                    "mutually_exclusive_required_with_same_dest",
                    *args,
                    stdout=out,
                )
                output = out.getvalue()
                self.assertIn("until=1", output)

    def test_required_list_option(self):
        tests = [
            (("--foo-list", [1, 2]), {}),
            ((), {"foo_list": [1, 2]}),
        ]
        for command in ["mutually_exclusive_required", "required_list_option"]:
            for args, kwargs in tests:
                with self.subTest(command=command, args=args, kwargs=kwargs):
                    out = StringIO()
                    management.call_command(
                        command,
                        *args,
                        **kwargs,
                        stdout=out,
                    )
                    self.assertIn("foo_list=[1, 2]", out.getvalue())

    def test_required_const_options(self):
        args = {
            "append_const": [42],
            "const": 31,
            "count": 1,
            "flag_false": False,
            "flag_true": True,
        }
        expected_output = "\n".join(
            "%s=%s" % (arg, value) for arg, value in args.items()
        )
        out = StringIO()
        management.call_command(
            "required_constant_option",
            "--append_const",
            "--const",
            "--count",
            "--flag_false",
            "--flag_true",
            stdout=out,
        )
        self.assertIn(expected_output, out.getvalue())
        out.truncate(0)
        management.call_command("required_constant_option", **args, stdout=out)
        self.assertIn(expected_output, out.getvalue())

    def test_subparser(self):
        """
        Tests the subparser management command with specific arguments and verifies the expected output string is present in the result. 

        This test case invokes the 'subparser' command with 'foo' and the integer value 12, capturing the command's output. It then asserts that the output contains the substring 'bar', ensuring the command behaves as expected when executed with the provided inputs.
        """
        out = StringIO()
        management.call_command("subparser", "foo", 12, stdout=out)
        self.assertIn("bar", out.getvalue())

    def test_subparser_dest_args(self):
        out = StringIO()
        management.call_command("subparser_dest", "foo", bar=12, stdout=out)
        self.assertIn("bar", out.getvalue())

    def test_subparser_dest_required_args(self):
        """

        Tests the subparser command with destination required arguments.

        Verifies that the 'subparser_required' command correctly processes required 
        arguments and includes the 'bar' value in the output when called with 
        'foo_1', 'foo_2', and bar=12 as arguments.

        """
        out = StringIO()
        management.call_command(
            "subparser_required", "foo_1", "foo_2", bar=12, stdout=out
        )
        self.assertIn("bar", out.getvalue())

    def test_subparser_invalid_option(self):
        msg = "invalid choice: 'test' (choose from 'foo')"
        with self.assertRaisesMessage(CommandError, msg):
            management.call_command("subparser", "test", 12)
        msg = "Error: the following arguments are required: subcommand"
        with self.assertRaisesMessage(CommandError, msg):
            management.call_command("subparser_dest", subcommand="foo", bar=12)

    def test_create_parser_kwargs(self):
        """BaseCommand.create_parser() passes kwargs to CommandParser."""
        epilog = "some epilog text"
        parser = BaseCommand().create_parser(
            "prog_name",
            "subcommand",
            epilog=epilog,
            formatter_class=ArgumentDefaultsHelpFormatter,
        )
        self.assertEqual(parser.epilog, epilog)
        self.assertEqual(parser.formatter_class, ArgumentDefaultsHelpFormatter)

    def test_outputwrapper_flush(self):
        """

        Tests the output wrapper command's functionality by verifying that the expected message is written to the output stream and that the flush method is called.

        The test case checks for the presence of 'Working...' in the output and confirms that the flush operation was performed on the stdout stream, ensuring proper execution of the output wrapper command.

        """
        out = StringIO()
        with mock.patch.object(out, "flush") as mocked_flush:
            management.call_command("outputwrapper", stdout=out)
        self.assertIn("Working...", out.getvalue())
        self.assertIs(mocked_flush.called, True)


class CommandRunTests(AdminScriptTestCase):
    """
    Tests that need to run by simulating the command line, not by call_command.
    """

    def test_script_prefix_set_in_commands(self):
        """

        Tests that the script prefix is correctly set in commands.

        This function verifies that the FORCE_SCRIPT_NAME setting is applied to the generated URLs
        in management commands. It checks the output of the reverse_url management command to ensure
        that the prefix is correctly prepended to the URL.

        """
        self.write_settings(
            "settings.py",
            apps=["user_commands"],
            sdict={
                "ROOT_URLCONF": '"user_commands.urls"',
                "FORCE_SCRIPT_NAME": '"/PREFIX/"',
            },
        )
        out, err = self.run_manage(["reverse_url"])
        self.assertNoOutput(err)
        self.assertEqual(out.strip(), "/PREFIX/some/url/")

    def test_disallowed_abbreviated_options(self):
        """
        To avoid conflicts with custom options, commands don't allow
        abbreviated forms of the --setting and --pythonpath options.
        """
        self.write_settings("settings.py", apps=["user_commands"])
        out, err = self.run_manage(["set_option", "--set", "foo"])
        self.assertNoOutput(err)
        self.assertEqual(out.strip(), "Set foo")

    def test_skip_checks(self):
        """
        Tests the functionality of the set_option management command when the --skip-checks flag is provided.

        This test case ensures that the command executes successfully and produces the expected output without performing any checks.

        It verifies that the command output matches the expected string and that no error messages are generated during execution.
        """
        self.write_settings(
            "settings.py",
            apps=["django.contrib.staticfiles", "user_commands"],
            sdict={
                # (staticfiles.E001) The STATICFILES_DIRS setting is not a tuple or
                # list.
                "STATICFILES_DIRS": '"foo"',
            },
        )
        out, err = self.run_manage(["set_option", "--skip-checks", "--set", "foo"])
        self.assertNoOutput(err)
        self.assertEqual(out.strip(), "Set foo")

    def test_subparser_error_formatting(self):
        self.write_settings("settings.py", apps=["user_commands"])
        out, err = self.run_manage(["subparser", "foo", "twelve"])
        self.maxDiff = None
        self.assertNoOutput(out)
        err_lines = err.splitlines()
        self.assertEqual(len(err_lines), 2)
        self.assertEqual(
            err_lines[1],
            "manage.py subparser foo: error: argument bar: invalid int value: 'twelve'",
        )

    def test_subparser_non_django_error_formatting(self):
        """
        Tests the error formatting of the subparser when a non-Django related error occurs.

        This test case verifies that the subparser correctly handles and formats errors
        that are not specific to Django, such as invalid input values. It checks that the
        error message is properly displayed, including the command that was run and the
        specific error that occurred.

        The test uses a vanilla subparser and passes an invalid integer value to simulate
        an error. The output and error messages are then checked to ensure that they match
        the expected format and content.
        """
        self.write_settings("settings.py", apps=["user_commands"])
        out, err = self.run_manage(["subparser_vanilla", "foo", "seven"])
        self.assertNoOutput(out)
        err_lines = err.splitlines()
        self.assertEqual(len(err_lines), 2)
        self.assertEqual(
            err_lines[1],
            "manage.py subparser_vanilla foo: error: argument bar: invalid int value: "
            "'seven'",
        )


class UtilsTests(SimpleTestCase):
    def test_no_existent_external_program(self):
        """
        Tests that an error is raised when attempting to execute an external program that does not exist. 
        Verifies that the expected error message is produced when the non-existent program is invoked through the popen_wrapper function.
        """
        msg = "Error executing a_42_command_that_doesnt_exist_42"
        with self.assertRaisesMessage(CommandError, msg):
            popen_wrapper(["a_42_command_that_doesnt_exist_42"])

    def test_get_random_secret_key(self):
        """

        Tests the generation of a random secret key.

        Verifies that the generated key has a length of 50 characters and only contains alphanumeric characters and specific special characters (!, @, #, $, %, ^, &, *, -, _, =, +).

        """
        key = get_random_secret_key()
        self.assertEqual(len(key), 50)
        for char in key:
            self.assertIn(char, "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)")

    def test_is_ignored_path_true(self):
        """
        =\"\"\"Checks the function to determine if a given path is ignored based on a list of patterns.

        The function is_ignored_path takes a path and a list of ignore patterns, and returns True if the path matches any of the patterns, indicating it should be ignored.

        This test ensures the function correctly identifies ignored paths by providing various patterns, including exact matches, wildcard matches, and regex-style matches, and verifies the function returns True for each of them, confirming the path 'foo/bar/baz' is correctly identified as ignored.
        """
        patterns = (
            ["foo/bar/baz"],
            ["baz"],
            ["foo/bar/baz"],
            ["*/baz"],
            ["*"],
            ["b?z"],
            ["[abc]az"],
            ["*/ba[!z]/baz"],
        )
        for ignore_patterns in patterns:
            with self.subTest(ignore_patterns=ignore_patterns):
                self.assertIs(
                    is_ignored_path("foo/bar/baz", ignore_patterns=ignore_patterns),
                    True,
                )

    def test_is_ignored_path_false(self):
        self.assertIs(
            is_ignored_path(
                "foo/bar/baz", ignore_patterns=["foo/bar/bat", "bar", "flub/blub"]
            ),
            False,
        )

    def test_normalize_path_patterns_truncates_wildcard_base(self):
        """

        Verifies that the normalize_path_patterns function correctly truncates wildcard bases.

        This test checks if the function is able to handle path patterns with wildcards
        at the end of the path and correctly removes them, resulting in the normalized path.
        The function should return a list of paths with the wildcard base truncated, 
        and the paths normalized to the current operating system's case.

        :raises AssertionError: If the function does not correctly truncate wildcard bases.

        """
        expected = [os.path.normcase(p) for p in ["foo/bar", "bar/*/"]]
        self.assertEqual(normalize_path_patterns(["foo/bar/*", "bar/*/"]), expected)
