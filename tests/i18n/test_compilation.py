import gettext as gettext_module
import os
import stat
import unittest
from io import StringIO
from pathlib import Path
from subprocess import run
from unittest import mock

from django.core.management import CommandError, call_command, execute_from_command_line
from django.core.management.commands.makemessages import Command as MakeMessagesCommand
from django.core.management.utils import find_command
from django.test import SimpleTestCase, override_settings
from django.test.utils import captured_stderr, captured_stdout
from django.utils import translation
from django.utils.translation import gettext

from .utils import RunInTmpDirMixin, copytree

has_msgfmt = find_command("msgfmt")


@unittest.skipUnless(has_msgfmt, "msgfmt is mandatory for compilation tests")
class MessageCompilationTests(RunInTmpDirMixin, SimpleTestCase):
    work_subdir = "commands"


class PoFileTests(MessageCompilationTests):
    LOCALE = "es_AR"
    MO_FILE = "locale/%s/LC_MESSAGES/django.mo" % LOCALE
    MO_FILE_EN = "locale/en/LC_MESSAGES/django.mo"

    def test_bom_rejection(self):
        """

        Tests that a Byte Order Mark (BOM) in a file triggers an error when compiling messages.

        Verifies that when using the compilemessages command, the presence of a BOM in a file
        results in a CommandError with a descriptive error message and that the output file
        is not generated.

        """
        stderr = StringIO()
        with self.assertRaisesMessage(
            CommandError, "compilemessages generated one or more errors."
        ):
            call_command(
                "compilemessages", locale=[self.LOCALE], verbosity=0, stderr=stderr
            )
        self.assertIn("file has a BOM (Byte Order Mark)", stderr.getvalue())
        self.assertFalse(os.path.exists(self.MO_FILE))

    def test_no_write_access(self):
        """
        Tests that compilemessages command raises an error when trying to write to a non-writable location.

        This test verifies that the compilemessages command correctly handles cases where the target 
        location for compiled message files (.mo) does not have write access. It checks that a 
        CommandError is raised with a suitable error message and that the error message includes 
        details about the unwritable location. The original permissions of the location are restored 
        after the test to ensure no side effects. 
        """
        mo_file_en = Path(self.MO_FILE_EN)
        err_buffer = StringIO()
        # Put file in read-only mode.
        old_mode = mo_file_en.stat().st_mode
        mo_file_en.chmod(stat.S_IREAD)
        # Ensure .po file is more recent than .mo file.
        mo_file_en.with_suffix(".po").touch()
        try:
            with self.assertRaisesMessage(
                CommandError, "compilemessages generated one or more errors."
            ):
                call_command(
                    "compilemessages", locale=["en"], stderr=err_buffer, verbosity=0
                )
            self.assertIn("not writable location", err_buffer.getvalue())
        finally:
            mo_file_en.chmod(old_mode)

    def test_no_compile_when_unneeded(self):
        mo_file_en = Path(self.MO_FILE_EN)
        mo_file_en.touch()
        stdout = StringIO()
        call_command("compilemessages", locale=["en"], stdout=stdout, verbosity=1)
        msg = "%s” is already compiled and up to date." % mo_file_en.with_suffix(".po")
        self.assertIn(msg, stdout.getvalue())


class PoFileContentsTests(MessageCompilationTests):
    # Ticket #11240

    LOCALE = "fr"
    MO_FILE = "locale/%s/LC_MESSAGES/django.mo" % LOCALE

    def test_percent_symbol_in_po_file(self):
        call_command("compilemessages", locale=[self.LOCALE], verbosity=0)
        self.assertTrue(os.path.exists(self.MO_FILE))


class MultipleLocaleCompilationTests(MessageCompilationTests):
    MO_FILE_HR = None
    MO_FILE_FR = None

    def setUp(self):
        """
        Sets up the test environment by initializing the base test class and defining 
        MO file paths for different locales. 

        The function creates paths to MO files for Croatian (hr) and French (fr) locales 
        in the 'locale' directory within the test directory, which can be used for 
        testing language translations.

        Attributes:
            MO_FILE_HR (str): Path to the Croatian MO file.
            MO_FILE_FR (str): Path to the French MO file.

        """
        super().setUp()
        localedir = os.path.join(self.test_dir, "locale")
        self.MO_FILE_HR = os.path.join(localedir, "hr/LC_MESSAGES/django.mo")
        self.MO_FILE_FR = os.path.join(localedir, "fr/LC_MESSAGES/django.mo")

    def test_one_locale(self):
        """
        Tests the compilation of translation messages for a single locale.

        This test ensures that the locale-specific translation files can be successfully compiled.
        It overrides the locale paths to use a test directory, compiles the messages for the 'hr' locale, 
        and verifies that the compiled translation file exists.
        """
        with override_settings(LOCALE_PATHS=[os.path.join(self.test_dir, "locale")]):
            call_command("compilemessages", locale=["hr"], verbosity=0)

            self.assertTrue(os.path.exists(self.MO_FILE_HR))

    def test_multiple_locales(self):
        with override_settings(LOCALE_PATHS=[os.path.join(self.test_dir, "locale")]):
            call_command("compilemessages", locale=["hr", "fr"], verbosity=0)

            self.assertTrue(os.path.exists(self.MO_FILE_HR))
            self.assertTrue(os.path.exists(self.MO_FILE_FR))


class ExcludedLocaleCompilationTests(MessageCompilationTests):
    work_subdir = "exclude"

    MO_FILE = "locale/%s/LC_MESSAGES/django.mo"

    def setUp(self):
        super().setUp()
        copytree("canned_locale", "locale")

    def test_command_help(self):
        """
        Tests the help functionality of the compilemessages command by executing it with the --help option.

        Verifies that the command displays the correct help message when invoked with the help flag, 
        without raising any errors or exceptions.
        """
        with captured_stdout(), captured_stderr():
            # `call_command` bypasses the parser; by calling
            # `execute_from_command_line` with the help subcommand we
            # ensure that there are no issues with the parser itself.
            execute_from_command_line(["django-admin", "help", "compilemessages"])

    def test_one_locale_excluded(self):
        call_command("compilemessages", exclude=["it"], verbosity=0)
        self.assertTrue(os.path.exists(self.MO_FILE % "en"))
        self.assertTrue(os.path.exists(self.MO_FILE % "fr"))
        self.assertFalse(os.path.exists(self.MO_FILE % "it"))

    def test_multiple_locales_excluded(self):
        call_command("compilemessages", exclude=["it", "fr"], verbosity=0)
        self.assertTrue(os.path.exists(self.MO_FILE % "en"))
        self.assertFalse(os.path.exists(self.MO_FILE % "fr"))
        self.assertFalse(os.path.exists(self.MO_FILE % "it"))

    def test_one_locale_excluded_with_locale(self):
        call_command(
            "compilemessages", locale=["en", "fr"], exclude=["fr"], verbosity=0
        )
        self.assertTrue(os.path.exists(self.MO_FILE % "en"))
        self.assertFalse(os.path.exists(self.MO_FILE % "fr"))
        self.assertFalse(os.path.exists(self.MO_FILE % "it"))

    def test_multiple_locales_excluded_with_locale(self):
        """

        Tests the compilation of messages for multiple locales with excluded locales.

        This test verifies that the compilemessages command correctly compiles message files
        for the specified locales while excluding others. It checks that the compiled message
        files (.mo) exist for the included locales and do not exist for the excluded locales.

        The test uses a combination of locales to compile and exclude, ensuring that the
        command behaves as expected in different scenarios.

        """
        call_command(
            "compilemessages",
            locale=["en", "fr", "it"],
            exclude=["fr", "it"],
            verbosity=0,
        )
        self.assertTrue(os.path.exists(self.MO_FILE % "en"))
        self.assertFalse(os.path.exists(self.MO_FILE % "fr"))
        self.assertFalse(os.path.exists(self.MO_FILE % "it"))


class IgnoreDirectoryCompilationTests(MessageCompilationTests):
    # Reuse the exclude directory since it contains some locale fixtures.
    work_subdir = "exclude"
    MO_FILE = "%s/%s/LC_MESSAGES/django.mo"
    CACHE_DIR = Path("cache") / "locale"
    NESTED_DIR = Path("outdated") / "v1" / "locale"

    def setUp(self):
        """
        Sets up the test environment by copying the canned locale directory to 
        the locale, cache, and nested directories, ensuring a consistent test setup.

        This method is called before each test, allowing for a clean and isolated test 
        environment. It relies on the superclass's setUp method to perform any 
        necessary initializations before setting up the locale directories.

        The copied directories are used to provide a controlled set of locale data for 
        testing purposes, ensuring that test results are consistent and reliable.
        """
        super().setUp()
        copytree("canned_locale", "locale")
        copytree("canned_locale", self.CACHE_DIR)
        copytree("canned_locale", self.NESTED_DIR)

    def assertAllExist(self, dir, langs):
        self.assertTrue(
            all(Path(self.MO_FILE % (dir, lang)).exists() for lang in langs)
        )

    def assertNoneExist(self, dir, langs):
        self.assertTrue(
            all(Path(self.MO_FILE % (dir, lang)).exists() is False for lang in langs)
        )

    def test_one_locale_dir_ignored(self):
        call_command("compilemessages", ignore=["cache"], verbosity=0)
        self.assertAllExist("locale", ["en", "fr", "it"])
        self.assertNoneExist(self.CACHE_DIR, ["en", "fr", "it"])
        self.assertAllExist(self.NESTED_DIR, ["en", "fr", "it"])

    def test_multiple_locale_dirs_ignored(self):
        """
        Tests that multiple locale directories are ignored during the compilation of messages.

        This test case verifies that the `compilemessages` command correctly skips directories 
        marked for ignoring, and that the compiled messages are generated only in the expected 
        locale directories. The test asserts the existence of compiled messages in the locale 
        directories and their absence in the ignored directories. 

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the expected locale directories or files do not exist or if 
            the ignored directories contain compiled messages.
        """
        call_command(
            "compilemessages", ignore=["cache/locale", "outdated"], verbosity=0
        )
        self.assertAllExist("locale", ["en", "fr", "it"])
        self.assertNoneExist(self.CACHE_DIR, ["en", "fr", "it"])
        self.assertNoneExist(self.NESTED_DIR, ["en", "fr", "it"])

    def test_ignores_based_on_pattern(self):
        """
        Tests if the compilemessages command ignores files based on the provided pattern.

        This test case checks if the compilemessages command correctly excludes files from compilation 
        when a pattern is specified. It verifies that the locales 'en', 'fr', and 'it' exist in the locale 
        directory and are absent in the cache and nested directories, ensuring the pattern '*/locale' 
        is applied correctly.

        The test uses the 'compilemessages' command with the ignore option to skip the specified pattern, 
        and then asserts the existence or absence of locales in different directories to validate the 
        command's behavior. 

        Parameters: 
        None

        Returns: 
        None

        Raises: 
        AssertionError: If the compilemessages command does not correctly ignore files based on the pattern
        """
        call_command("compilemessages", ignore=["*/locale"], verbosity=0)
        self.assertAllExist("locale", ["en", "fr", "it"])
        self.assertNoneExist(self.CACHE_DIR, ["en", "fr", "it"])
        self.assertNoneExist(self.NESTED_DIR, ["en", "fr", "it"])

    def test_no_dirs_accidentally_skipped(self):
        """
        Tests that the compilemessages command does not accidentally skip directories when compiling messages. 

        The test simulates a directory structure with multiple locale directories containing message files and verifies that the command compiles messages from all expected directories. 

        Specifically, it checks that the compile_messages method is called with the correct arguments for each locale directory. The test uses mocking to isolate the test from the actual file system and ensure consistent results.
        """
        os_walk_results = [
            # To discover .po filepaths, compilemessages uses with a starting list of
            # basedirs to inspect, which in this scenario are:
            #   ["conf/locale", "locale"]
            # Then os.walk is used to discover other locale dirs, ignoring dirs matching
            # `ignore_patterns`. Mock the results to place an ignored directory directly
            # before and after a directory named "locale".
            [("somedir", ["ignore", "locale", "ignore"], [])],
            # This will result in three basedirs discovered:
            #   ["conf/locale", "locale", "somedir/locale"]
            # os.walk is called for each locale in each basedir looking for .po files.
            # In this scenario, we need to mock os.walk results for "en", "fr", and "it"
            # locales for each basedir:
            [("exclude/locale/LC_MESSAGES", [], ["en.po"])],
            [("exclude/locale/LC_MESSAGES", [], ["fr.po"])],
            [("exclude/locale/LC_MESSAGES", [], ["it.po"])],
            [("exclude/conf/locale/LC_MESSAGES", [], ["en.po"])],
            [("exclude/conf/locale/LC_MESSAGES", [], ["fr.po"])],
            [("exclude/conf/locale/LC_MESSAGES", [], ["it.po"])],
            [("exclude/somedir/locale/LC_MESSAGES", [], ["en.po"])],
            [("exclude/somedir/locale/LC_MESSAGES", [], ["fr.po"])],
            [("exclude/somedir/locale/LC_MESSAGES", [], ["it.po"])],
        ]

        module_path = "django.core.management.commands.compilemessages"
        with mock.patch(f"{module_path}.os.walk", side_effect=os_walk_results):
            with mock.patch(f"{module_path}.os.path.isdir", return_value=True):
                with mock.patch(
                    f"{module_path}.Command.compile_messages"
                ) as mock_compile_messages:
                    call_command("compilemessages", ignore=["ignore"], verbosity=4)

        expected = [
            (
                [
                    ("exclude/locale/LC_MESSAGES", "en.po"),
                    ("exclude/locale/LC_MESSAGES", "fr.po"),
                    ("exclude/locale/LC_MESSAGES", "it.po"),
                ],
            ),
            (
                [
                    ("exclude/conf/locale/LC_MESSAGES", "en.po"),
                    ("exclude/conf/locale/LC_MESSAGES", "fr.po"),
                    ("exclude/conf/locale/LC_MESSAGES", "it.po"),
                ],
            ),
            (
                [
                    ("exclude/somedir/locale/LC_MESSAGES", "en.po"),
                    ("exclude/somedir/locale/LC_MESSAGES", "fr.po"),
                    ("exclude/somedir/locale/LC_MESSAGES", "it.po"),
                ],
            ),
        ]
        self.assertEqual([c.args for c in mock_compile_messages.mock_calls], expected)


class CompilationErrorHandling(MessageCompilationTests):
    def test_error_reported_by_msgfmt(self):
        # po file contains wrong po formatting.
        with self.assertRaises(CommandError):
            call_command("compilemessages", locale=["ja"], verbosity=0)

    def test_msgfmt_error_including_non_ascii(self):
        # po file contains invalid msgstr content (triggers non-ascii error content).
        # Make sure the output of msgfmt is unaffected by the current locale.
        env = os.environ.copy()
        env.update({"LC_ALL": "C"})
        with mock.patch(
            "django.core.management.utils.run",
            lambda *args, **kwargs: run(*args, env=env, **kwargs),
        ):
            cmd = MakeMessagesCommand()
            if cmd.gettext_version < (0, 18, 3):
                self.skipTest("python-brace-format is a recent gettext addition.")
            stderr = StringIO()
            with self.assertRaisesMessage(
                CommandError, "compilemessages generated one or more errors"
            ):
                call_command(
                    "compilemessages", locale=["ko"], stdout=StringIO(), stderr=stderr
                )
            self.assertIn("' cannot start a field name", stderr.getvalue())


class ProjectAndAppTests(MessageCompilationTests):
    LOCALE = "ru"
    PROJECT_MO_FILE = "locale/%s/LC_MESSAGES/django.mo" % LOCALE
    APP_MO_FILE = "app_with_locale/locale/%s/LC_MESSAGES/django.mo" % LOCALE


class FuzzyTranslationTest(ProjectAndAppTests):
    def setUp(self):
        """
        Set up the testing environment by initializing the parent class and resetting the gettext translations cache.

        This method is used to prepare the test setup, inheriting the initialization from the parent class. It also clears the gettext translations cache to ensure a clean start for each test, preventing any previous translations from interfering with the test results.

        The purpose of this method is to provide a consistent and isolated environment for tests, allowing for reliable and reproducible test outcomes. It is typically called before each test case to reset the environment to a known state.
        """
        super().setUp()
        gettext_module._translations = {}  # flush cache or test will be useless

    def test_nofuzzy_compiling(self):
        """
        Tests the compilation of translations without fuzzy matching.

        This test ensures that the compilemessages command correctly compiles translation files
        in the specified locale directory and that the translations are applied correctly.
        It verifies that the gettext function returns the expected translated strings for a given locale.

        The test covers the following scenarios:
        - Compilation of translations using the compilemessages command
        - Application of translations for a specific locale
        - Verification of translated strings using the gettext function
        """
        with override_settings(LOCALE_PATHS=[os.path.join(self.test_dir, "locale")]):
            call_command("compilemessages", locale=[self.LOCALE], verbosity=0)
            with translation.override(self.LOCALE):
                self.assertEqual(gettext("Lenin"), "Ленин")
                self.assertEqual(gettext("Vodka"), "Vodka")

    def test_fuzzy_compiling(self):
        """
        Test compiling of fuzzy translations for a specific locale.

        This test ensures that fuzzy translations are correctly compiled and used in the application.
        It first compiles the messages for the specified locale, including fuzzy translations,
        and then verifies that the expected translations are returned for given strings.
        """
        with override_settings(LOCALE_PATHS=[os.path.join(self.test_dir, "locale")]):
            call_command(
                "compilemessages", locale=[self.LOCALE], fuzzy=True, verbosity=0
            )
            with translation.override(self.LOCALE):
                self.assertEqual(gettext("Lenin"), "Ленин")
                self.assertEqual(gettext("Vodka"), "Водка")


class AppCompilationTest(ProjectAndAppTests):
    def test_app_locale_compiled(self):
        """

        Tests that compiled locale files are generated successfully.

        Verifies that running the compilemessages command with a specified locale
        produces the expected compiled message files for the project and application.

        The test checks for the existence of the project and application.mo files
        in the locale directory after compilation.

        Attributes:
            None

        Returns:
            None

        Raises:
            AssertionError: If the expected.mo files do not exist after compilation.

        """
        call_command("compilemessages", locale=[self.LOCALE], verbosity=0)
        self.assertTrue(os.path.exists(self.PROJECT_MO_FILE))
        self.assertTrue(os.path.exists(self.APP_MO_FILE))


class PathLibLocaleCompilationTests(MessageCompilationTests):
    work_subdir = "exclude"

    def test_locale_paths_pathlib(self):
        with override_settings(LOCALE_PATHS=[Path(self.test_dir) / "canned_locale"]):
            call_command("compilemessages", locale=["fr"], verbosity=0)
            self.assertTrue(os.path.exists("canned_locale/fr/LC_MESSAGES/django.mo"))
