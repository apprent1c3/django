import datetime
import os
import shutil
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

from admin_scripts.tests import AdminScriptTestCase

from django.conf import STATICFILES_STORAGE_ALIAS, settings
from django.contrib.staticfiles import storage
from django.contrib.staticfiles.management.commands import collectstatic, runserver
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.core.management.base import SystemCheckError
from django.test import RequestFactory, override_settings
from django.test.utils import extend_sys_path
from django.utils._os import symlinks_supported
from django.utils.functional import empty

from .cases import CollectionTestCase, StaticFilesTestCase, TestDefaults
from .settings import TEST_ROOT, TEST_SETTINGS
from .storage import DummyStorage


class TestNoFilesCreated:
    def test_no_files_created(self):
        """
        Make sure no files were create in the destination directory.
        """
        self.assertEqual(os.listdir(settings.STATIC_ROOT), [])


class TestRunserver(StaticFilesTestCase):
    @override_settings(MIDDLEWARE=["django.middleware.common.CommonMiddleware"])
    def test_middleware_loaded_only_once(self):
        """
        Tests that the Django middleware is loaded only once during the execution of the runserver command.

        This test case ensures that the middleware initialization process is properly optimized,
        preventing unnecessary repeated loading of middlewares. It verifies the expected behavior
        by mocking the CommonMiddleware and checking its call count after the command handler is retrieved.

        The test covers the scenario where the static handler and insecure serving are enabled,
        providing assurance that the middleware loading is correct even in specific configuration settings.
        """
        command = runserver.Command()
        with mock.patch("django.middleware.common.CommonMiddleware") as mocked:
            command.get_handler(use_static_handler=True, insecure_serving=True)
            self.assertEqual(mocked.call_count, 1)

    def test_404_response(self):
        """

        Tests the HTTP response when a static file is not found.

        Verifies that a 404 status code is returned when attempting to access a non-existent static file,
        regardless of whether the application is running in debug mode or not.

        The test covers both production and development environments by toggling the DEBUG setting.

        """
        command = runserver.Command()
        handler = command.get_handler(use_static_handler=True, insecure_serving=True)
        missing_static_file = os.path.join(settings.STATIC_URL, "unknown.css")
        req = RequestFactory().get(missing_static_file)
        with override_settings(DEBUG=False):
            response = handler.get_response(req)
            self.assertEqual(response.status_code, 404)
        with override_settings(DEBUG=True):
            response = handler.get_response(req)
            self.assertEqual(response.status_code, 404)


class TestFindStatic(TestDefaults, CollectionTestCase):
    """
    Test ``findstatic`` management command.
    """

    def _get_file(self, filepath):
        path = call_command(
            "findstatic", filepath, all=False, verbosity=0, stdout=StringIO()
        )
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_all_files(self):
        """
        findstatic returns all candidate files if run without --first and -v1.
        """
        result = call_command(
            "findstatic", "test/file.txt", verbosity=1, stdout=StringIO()
        )
        lines = [line.strip() for line in result.split("\n")]
        self.assertEqual(
            len(lines), 3
        )  # three because there is also the "Found <file> here" line
        self.assertIn("project", lines[1])
        self.assertIn("apps", lines[2])

    def test_all_files_less_verbose(self):
        """
        findstatic returns all candidate files if run without --first and -v0.
        """
        result = call_command(
            "findstatic", "test/file.txt", verbosity=0, stdout=StringIO()
        )
        lines = [line.strip() for line in result.split("\n")]
        self.assertEqual(len(lines), 2)
        self.assertIn("project", lines[0])
        self.assertIn("apps", lines[1])

    def test_all_files_more_verbose(self):
        """
        findstatic returns all candidate files if run without --first and -v2.
        Also, test that findstatic returns the searched locations with -v2.
        """
        result = call_command(
            "findstatic", "test/file.txt", verbosity=2, stdout=StringIO()
        )
        lines = [line.strip() for line in result.split("\n")]
        self.assertIn("project", lines[1])
        self.assertIn("apps", lines[2])
        self.assertIn("Looking in the following locations:", lines[3])
        searched_locations = ", ".join(lines[4:])
        # AppDirectoriesFinder searched locations
        self.assertIn(
            os.path.join("staticfiles_tests", "apps", "test", "static"),
            searched_locations,
        )
        self.assertIn(
            os.path.join("staticfiles_tests", "apps", "no_label", "static"),
            searched_locations,
        )
        # FileSystemFinder searched locations
        self.assertIn(TEST_SETTINGS["STATICFILES_DIRS"][1][1], searched_locations)
        self.assertIn(TEST_SETTINGS["STATICFILES_DIRS"][0], searched_locations)
        self.assertIn(str(TEST_SETTINGS["STATICFILES_DIRS"][2]), searched_locations)
        # DefaultStorageFinder searched locations
        self.assertIn(
            os.path.join("staticfiles_tests", "project", "site_media", "media"),
            searched_locations,
        )


class TestConfiguration(StaticFilesTestCase):
    def test_location_empty(self):
        msg = "without having set the STATIC_ROOT setting to a filesystem path"
        err = StringIO()
        for root in ["", None]:
            with override_settings(STATIC_ROOT=root):
                with self.assertRaisesMessage(ImproperlyConfigured, msg):
                    call_command(
                        "collectstatic", interactive=False, verbosity=0, stderr=err
                    )

    def test_local_storage_detection_helper(self):
        staticfiles_storage = storage.staticfiles_storage
        try:
            storage.staticfiles_storage._wrapped = empty
            with self.settings(
                STORAGES={
                    **settings.STORAGES,
                    STATICFILES_STORAGE_ALIAS: {
                        "BACKEND": (
                            "django.contrib.staticfiles.storage.StaticFilesStorage"
                        )
                    },
                }
            ):
                command = collectstatic.Command()
                self.assertTrue(command.is_local_storage())

            storage.staticfiles_storage._wrapped = empty
            with self.settings(
                STORAGES={
                    **settings.STORAGES,
                    STATICFILES_STORAGE_ALIAS: {
                        "BACKEND": "staticfiles_tests.storage.DummyStorage"
                    },
                }
            ):
                command = collectstatic.Command()
                self.assertFalse(command.is_local_storage())

            collectstatic.staticfiles_storage = storage.FileSystemStorage()
            command = collectstatic.Command()
            self.assertTrue(command.is_local_storage())

            collectstatic.staticfiles_storage = DummyStorage()
            command = collectstatic.Command()
            self.assertFalse(command.is_local_storage())
        finally:
            staticfiles_storage._wrapped = empty
            collectstatic.staticfiles_storage = staticfiles_storage
            storage.staticfiles_storage = staticfiles_storage

    @override_settings(STATICFILES_DIRS=("test"))
    def test_collectstatis_check(self):
        """
        Tests that the collectstatic command raises a SystemCheckError when the STATICFILES_DIRS setting is not a tuple or list.

        This test case ensures that the command correctly checks the type of the STATICFILES_DIRS setting and raises an error if it is not a valid collection, helping to prevent potential issues during static file collection.

        :raises: SystemCheckError if the STATICFILES_DIRS setting is not a tuple or list
        """
        msg = "The STATICFILES_DIRS setting is not a tuple or list."
        with self.assertRaisesMessage(SystemCheckError, msg):
            call_command("collectstatic", skip_checks=False)


class TestCollectionHelpSubcommand(AdminScriptTestCase):
    @override_settings(STATIC_ROOT=None)
    def test_missing_settings_dont_prevent_help(self):
        """
        Even if the STATIC_ROOT setting is not set, one can still call the
        `manage.py help collectstatic` command.
        """
        self.write_settings("settings.py", apps=["django.contrib.staticfiles"])
        out, err = self.run_manage(["help", "collectstatic"])
        self.assertNoOutput(err)


class TestCollection(TestDefaults, CollectionTestCase):
    """
    Test ``collectstatic`` management command.
    """

    def test_ignore(self):
        """
        -i patterns are ignored.
        """
        self.assertFileNotFound("test/test.ignoreme")

    def test_common_ignore_patterns(self):
        """
        Common ignore patterns (*~, .*, CVS) are ignored.
        """
        self.assertFileNotFound("test/.hidden")
        self.assertFileNotFound("test/backup~")
        self.assertFileNotFound("test/CVS")

    def test_pathlib(self):
        self.assertFileContains("pathlib.txt", "pathlib")


class TestCollectionPathLib(TestCollection):
    def mkdtemp(self):
        """

             Creates a temporary directory and returns its path as a Path object.

             This method generates a unique, non-existent directory and returns a Path
             object representing its location. The directory is created in the most
             secure manner possible, and its path is returned for further use.

             The resulting directory is intended to be used as a temporary storage
             location and should be cleaned up after use to prevent clutter and
             potential security issues.

             :return: A Path object representing the created temporary directory.

        """
        tmp_dir = super().mkdtemp()
        return Path(tmp_dir)


class TestCollectionVerbosity(CollectionTestCase):
    copying_msg = "Copying "
    run_collectstatic_in_setUp = False
    post_process_msg = "Post-processed"
    staticfiles_copied_msg = "static files copied to"

    def test_verbosity_0(self):
        stdout = StringIO()
        self.run_collectstatic(verbosity=0, stdout=stdout)
        self.assertEqual(stdout.getvalue(), "")

    def test_verbosity_1(self):
        """

        Tests the verbosity level 1 of the collectstatic command.

        This test case verifies that when the verbosity level is set to 1, the 
        command outputs a message indicating the number of static files copied, 
        but does not output individual copying messages.

        The test checks for the presence of the static files copied message and 
        the absence of individual copying messages in the command output.

        """
        stdout = StringIO()
        self.run_collectstatic(verbosity=1, stdout=stdout)
        output = stdout.getvalue()
        self.assertIn(self.staticfiles_copied_msg, output)
        self.assertNotIn(self.copying_msg, output)

    def test_verbosity_2(self):
        """
        Tests that the collectstatic command displays the expected output when verbosity is set to 2.

        Verifies that both the total number of static files copied and the copying progress messages are printed to the console when the verbosity level is increased to 2, providing more detailed information about the collectstatic process.
        """
        stdout = StringIO()
        self.run_collectstatic(verbosity=2, stdout=stdout)
        output = stdout.getvalue()
        self.assertIn(self.staticfiles_copied_msg, output)
        self.assertIn(self.copying_msg, output)

    @override_settings(
        STORAGES={
            **settings.STORAGES,
            STATICFILES_STORAGE_ALIAS: {
                "BACKEND": (
                    "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
                )
            },
        }
    )
    def test_verbosity_1_with_post_process(self):
        stdout = StringIO()
        self.run_collectstatic(verbosity=1, stdout=stdout, post_process=True)
        self.assertNotIn(self.post_process_msg, stdout.getvalue())

    @override_settings(
        STORAGES={
            **settings.STORAGES,
            STATICFILES_STORAGE_ALIAS: {
                "BACKEND": (
                    "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
                )
            },
        }
    )
    def test_verbosity_2_with_post_process(self):
        """
        Tests the collectstatic command with verbosity set to 2 and post-processing enabled.

        This test case verifies that the post-processing message is correctly displayed in the output when the verbosity level is set to 2.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the post-processing message is not found in the output.
        """
        stdout = StringIO()
        self.run_collectstatic(verbosity=2, stdout=stdout, post_process=True)
        self.assertIn(self.post_process_msg, stdout.getvalue())


class TestCollectionClear(CollectionTestCase):
    """
    Test the ``--clear`` option of the ``collectstatic`` management command.
    """

    def run_collectstatic(self, **kwargs):
        """
        Runs the collectstatic management command with an additional step to clear the static files directory.

        This method creates a temporary file indicating that the static files should be cleared, then proceeds to run the collectstatic command with the clear option enabled.

        The command ensures that the static files directory is cleaned up before collecting new static files, which can help prevent stale or redundant files from being retained. 

        (args and kwargs are passed through to the parent class's run_collectstatic method)
        """
        clear_filepath = os.path.join(settings.STATIC_ROOT, "cleared.txt")
        with open(clear_filepath, "w") as f:
            f.write("should be cleared")
        super().run_collectstatic(clear=True)

    def test_cleared_not_found(self):
        self.assertFileNotFound("cleared.txt")

    def test_dir_not_exists(self, **kwargs):
        """
        Tests the collectstatic functionality when the directory does not exist.

        This test case simulates a scenario where the static root directory has been deleted.
        It removes the static root directory and then attempts to collect static files with the 'clear' option enabled.
        The purpose of this test is to verify that the collectstatic functionality can handle the absence of the target directory and recreate it as needed. 
        """
        shutil.rmtree(settings.STATIC_ROOT)
        super().run_collectstatic(clear=True)

    @override_settings(
        STORAGES={
            **settings.STORAGES,
            STATICFILES_STORAGE_ALIAS: {
                "BACKEND": "staticfiles_tests.storage.PathNotImplementedStorage"
            },
        }
    )
    def test_handle_path_notimplemented(self):
        self.run_collectstatic()
        self.assertFileNotFound("cleared.txt")


class TestInteractiveMessages(CollectionTestCase):
    overwrite_warning_msg = "This will overwrite existing files!"
    delete_warning_msg = "This will DELETE ALL FILES in this location!"
    files_copied_msg = "static files copied"

    @staticmethod
    def mock_input(stdout):
        """

        Return a mock input function for testing purposes.

        This function generates a mock input function that writes the input message to the provided stdout and returns a fixed response of 'yes'.

        Used to simulate user input in automated tests, allowing for consistent and predictable behavior.

        :param stdout: The output stream where the input message will be written.
        :return: A mock input function that can be used in place of the built-in input function.

        """
        def _input(msg):
            """
            Simulates a user input prompt by displaying a message and returning a default affirmative response.

            :param msg: The message to be displayed to the user.
            :rtype: str
            :return: A default 'yes' response.
            :note: This function does not actually wait for user input, but instead immediately returns 'yes' after displaying the message.
            """
            stdout.write(msg)
            return "yes"

        return _input

    def test_warning_when_clearing_staticdir(self):
        """

        Tests that a warning is displayed when clearing the static directory.

        This test case exercises the :func:`collectstatic` command with the ``--clear``
        option and verifies that the expected warning messages are displayed to the user.
        It confirms that the warning about overwriting files is not shown, but the warning
        about deleting files is displayed as expected. The test uses a mock input to
        simulate user interaction and captures the command's output for verification.

        """
        stdout = StringIO()
        self.run_collectstatic()
        with mock.patch("builtins.input", side_effect=self.mock_input(stdout)):
            call_command("collectstatic", interactive=True, clear=True, stdout=stdout)

        output = stdout.getvalue()
        self.assertNotIn(self.overwrite_warning_msg, output)
        self.assertIn(self.delete_warning_msg, output)

    def test_warning_when_overwriting_files_in_staticdir(self):
        stdout = StringIO()
        self.run_collectstatic()
        with mock.patch("builtins.input", side_effect=self.mock_input(stdout)):
            call_command("collectstatic", interactive=True, stdout=stdout)
        output = stdout.getvalue()
        self.assertIn(self.overwrite_warning_msg, output)
        self.assertNotIn(self.delete_warning_msg, output)

    def test_no_warning_when_staticdir_does_not_exist(self):
        """
        Tests that no warning is raised when the static directory does not exist during static file collection.

        This test case simulates a scenario where the static root directory has been deleted,
        and then attempts to collect static files using the collectstatic command.
        It verifies that the command executes without raising any warnings related to overwriting or deleting files,
        and instead reports that files have been successfully copied to the static directory.
        """
        stdout = StringIO()
        shutil.rmtree(settings.STATIC_ROOT)
        call_command("collectstatic", interactive=True, stdout=stdout)
        output = stdout.getvalue()
        self.assertNotIn(self.overwrite_warning_msg, output)
        self.assertNotIn(self.delete_warning_msg, output)
        self.assertIn(self.files_copied_msg, output)

    def test_no_warning_for_empty_staticdir(self):
        stdout = StringIO()
        with tempfile.TemporaryDirectory(
            prefix="collectstatic_empty_staticdir_test"
        ) as static_dir:
            with override_settings(STATIC_ROOT=static_dir):
                call_command("collectstatic", interactive=True, stdout=stdout)
        output = stdout.getvalue()
        self.assertNotIn(self.overwrite_warning_msg, output)
        self.assertNotIn(self.delete_warning_msg, output)
        self.assertIn(self.files_copied_msg, output)

    def test_cancelled(self):
        """
        Tests that the collectstatic command is cancelled when the user chooses not to collect static files interactively.

        Verifies that the command raises a CommandError with the expected message when the user responds 'no' to the interactive prompt.

        This test case ensures that the collectstatic command behaves as expected when run in interactive mode and the user chooses to cancel the operation.
        """
        self.run_collectstatic()
        with mock.patch("builtins.input", side_effect=lambda _: "no"):
            with self.assertRaisesMessage(
                CommandError, "Collecting static files cancelled"
            ):
                call_command("collectstatic", interactive=True)


class TestCollectionNoDefaultIgnore(TestDefaults, CollectionTestCase):
    """
    The ``--no-default-ignore`` option of the ``collectstatic`` management
    command.
    """

    def run_collectstatic(self):
        super().run_collectstatic(use_default_ignore_patterns=False)

    def test_no_common_ignore_patterns(self):
        """
        With --no-default-ignore, common ignore patterns (*~, .*, CVS)
        are not ignored.
        """
        self.assertFileContains("test/.hidden", "should be ignored")
        self.assertFileContains("test/backup~", "should be ignored")
        self.assertFileContains("test/CVS", "should be ignored")


@override_settings(
    INSTALLED_APPS=[
        "staticfiles_tests.apps.staticfiles_config.IgnorePatternsAppConfig",
        "staticfiles_tests.apps.test",
    ]
)
class TestCollectionCustomIgnorePatterns(CollectionTestCase):
    def test_custom_ignore_patterns(self):
        """
        A custom ignore_patterns list, ['*.css', '*/vendor/*.js'] in this case,
        can be specified in an AppConfig definition.
        """
        self.assertFileNotFound("test/nonascii.css")
        self.assertFileContains("test/.hidden", "should be ignored")
        self.assertFileNotFound(os.path.join("test", "vendor", "module.js"))


class TestCollectionDryRun(TestNoFilesCreated, CollectionTestCase):
    """
    Test ``--dry-run`` option for ``collectstatic`` management command.
    """

    def run_collectstatic(self):
        super().run_collectstatic(dry_run=True)


@override_settings(
    STORAGES={
        **settings.STORAGES,
        STATICFILES_STORAGE_ALIAS: {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
        },
    }
)
class TestCollectionDryRunManifestStaticFilesStorage(TestCollectionDryRun):
    pass


class TestCollectionFilesOverride(CollectionTestCase):
    """
    Test overriding duplicated files by ``collectstatic`` management command.
    Check for proper handling of apps order in installed apps even if file modification
    dates are in different order:
        'staticfiles_test_app',
        'staticfiles_tests.apps.no_label',
    """

    def setUp(self):
        """
        Sets up a temporary test environment for testing static file handling.

        Creates a temporary directory and populates it with a test application and a static file,
        mirroring the content and timestamp of a source file. The test environment is configured
        to use this temporary application, and cleanup mechanisms are established to ensure that
        the temporary directory is removed after testing.

        This setup method is intended to be used as a precursor to other tests, providing a 
        reliable and self-contained environment for testing static file functionality. 

        When the test is completed, the temporary directory and its contents are automatically 
        removed, and any modifications made to the system path are reverted.
        """
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

        # get modification and access times for no_label/static/file2.txt
        self.orig_path = os.path.join(
            TEST_ROOT, "apps", "no_label", "static", "file2.txt"
        )
        self.orig_mtime = os.path.getmtime(self.orig_path)
        self.orig_atime = os.path.getatime(self.orig_path)

        # prepare duplicate of file2.txt from a temporary app
        # this file will have modification time older than no_label/static/file2.txt
        # anyway it should be taken to STATIC_ROOT because the temporary app is before
        # 'no_label' app in installed apps
        self.temp_app_path = os.path.join(self.temp_dir, "staticfiles_test_app")
        self.testfile_path = os.path.join(self.temp_app_path, "static", "file2.txt")

        os.makedirs(self.temp_app_path)
        with open(os.path.join(self.temp_app_path, "__init__.py"), "w+"):
            pass

        os.makedirs(os.path.dirname(self.testfile_path))
        with open(self.testfile_path, "w+") as f:
            f.write("duplicate of file2.txt")

        os.utime(self.testfile_path, (self.orig_atime - 1, self.orig_mtime - 1))

        settings_with_test_app = self.modify_settings(
            INSTALLED_APPS={"prepend": "staticfiles_test_app"},
        )
        with extend_sys_path(self.temp_dir):
            settings_with_test_app.enable()
        self.addCleanup(settings_with_test_app.disable)
        super().setUp()

    def test_ordering_override(self):
        """
        Test if collectstatic takes files in proper order
        """
        self.assertFileContains("file2.txt", "duplicate of file2.txt")

        # run collectstatic again
        self.run_collectstatic()

        self.assertFileContains("file2.txt", "duplicate of file2.txt")


# The collectstatic test suite already has conflicting files since both
# project/test/file.txt and apps/test/static/test/file.txt are collected. To
# properly test for the warning not happening unless we tell it to explicitly,
# we remove the project directory and will add back a conflicting file later.
@override_settings(STATICFILES_DIRS=[])
class TestCollectionOverwriteWarning(CollectionTestCase):
    """
    Test warning in ``collectstatic`` output when a file is skipped because a
    previous file was already written to the same path.
    """

    # If this string is in the collectstatic output, it means the warning we're
    # looking for was emitted.
    warning_string = "Found another file"

    def _collectstatic_output(self, **kwargs):
        """
        Run collectstatic, and capture and return the output. We want to run
        the command at highest verbosity, which is why we can't
        just call e.g. BaseCollectionTestCase.run_collectstatic()
        """
        out = StringIO()
        call_command(
            "collectstatic", interactive=False, verbosity=3, stdout=out, **kwargs
        )
        return out.getvalue()

    def test_no_warning(self):
        """
        There isn't a warning if there isn't a duplicate destination.
        """
        output = self._collectstatic_output(clear=True)
        self.assertNotIn(self.warning_string, output)

    def test_warning(self):
        """
        There is a warning when there are duplicate destinations.
        """
        with tempfile.TemporaryDirectory() as static_dir:
            duplicate = os.path.join(static_dir, "test", "file.txt")
            os.mkdir(os.path.dirname(duplicate))
            with open(duplicate, "w+") as f:
                f.write("duplicate of file.txt")

            with self.settings(STATICFILES_DIRS=[static_dir]):
                output = self._collectstatic_output(clear=True)
            self.assertIn(self.warning_string, output)

            os.remove(duplicate)

            # Make sure the warning went away again.
            with self.settings(STATICFILES_DIRS=[static_dir]):
                output = self._collectstatic_output(clear=True)
            self.assertNotIn(self.warning_string, output)


@override_settings(
    STORAGES={
        **settings.STORAGES,
        STATICFILES_STORAGE_ALIAS: {
            "BACKEND": "staticfiles_tests.storage.DummyStorage"
        },
    }
)
class TestCollectionNonLocalStorage(TestNoFilesCreated, CollectionTestCase):
    """
    Tests for a Storage that implements get_modified_time() but not path()
    (#15035).
    """

    def test_storage_properties(self):
        # Properties of the Storage as described in the ticket.
        storage = DummyStorage()
        self.assertEqual(
            storage.get_modified_time("name"),
            datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc),
        )
        with self.assertRaisesMessage(
            NotImplementedError, "This backend doesn't support absolute paths."
        ):
            storage.path("name")


class TestCollectionNeverCopyStorage(CollectionTestCase):
    @override_settings(
        STORAGES={
            **settings.STORAGES,
            STATICFILES_STORAGE_ALIAS: {
                "BACKEND": "staticfiles_tests.storage.NeverCopyRemoteStorage"
            },
        }
    )
    def test_skips_newer_files_in_remote_storage(self):
        """
        collectstatic skips newer files in a remote storage.
        run_collectstatic() in setUp() copies the static files, then files are
        always skipped after NeverCopyRemoteStorage is activated since
        NeverCopyRemoteStorage.get_modified_time() returns a datetime in the
        future to simulate an unmodified file.
        """
        stdout = StringIO()
        self.run_collectstatic(stdout=stdout, verbosity=2)
        output = stdout.getvalue()
        self.assertIn("Skipping 'test.txt' (not modified)", output)


@unittest.skipUnless(symlinks_supported(), "Must be able to symlink to run this test.")
class TestCollectionLinks(TestDefaults, CollectionTestCase):
    """
    Test ``--link`` option for ``collectstatic`` management command.

    Note that by inheriting ``TestDefaults`` we repeat all
    the standard file resolving tests here, to make sure using
    ``--link`` does not change the file-selection semantics.
    """

    def run_collectstatic(self, clear=False, link=True, **kwargs):
        super().run_collectstatic(link=link, clear=clear, **kwargs)

    def test_links_created(self):
        """
        With ``--link``, symbolic links are created.
        """
        self.assertTrue(os.path.islink(os.path.join(settings.STATIC_ROOT, "test.txt")))

    def test_broken_symlink(self):
        """
        Test broken symlink gets deleted.
        """
        path = os.path.join(settings.STATIC_ROOT, "test.txt")
        os.unlink(path)
        self.run_collectstatic()
        self.assertTrue(os.path.islink(path))

    def test_symlinks_and_files_replaced(self):
        """
        Running collectstatic in non-symlink mode replaces symlinks with files,
        while symlink mode replaces files with symlinks.
        """
        path = os.path.join(settings.STATIC_ROOT, "test.txt")
        self.assertTrue(os.path.islink(path))
        self.run_collectstatic(link=False)
        self.assertFalse(os.path.islink(path))
        self.run_collectstatic(link=True)
        self.assertTrue(os.path.islink(path))

    def test_clear_broken_symlink(self):
        """
        With ``--clear``, broken symbolic links are deleted.
        """
        nonexistent_file_path = os.path.join(settings.STATIC_ROOT, "nonexistent.txt")
        broken_symlink_path = os.path.join(settings.STATIC_ROOT, "symlink.txt")
        os.symlink(nonexistent_file_path, broken_symlink_path)
        self.run_collectstatic(clear=True)
        self.assertFalse(os.path.lexists(broken_symlink_path))

    @override_settings(
        STORAGES={
            **settings.STORAGES,
            STATICFILES_STORAGE_ALIAS: {
                "BACKEND": "staticfiles_tests.storage.PathNotImplementedStorage"
            },
        }
    )
    def test_no_remote_link(self):
        """
        Tests that a CommandError is raised when attempting to collect static files to a remote destination.

        This test verifies that the collect static command correctly handles cases where the 
        destination is a remote link, and ensures that an error message is displayed to the user 
        informing them that symlinking to remote destinations is not supported.

        :raises: CommandError if the collect static command is run with a remote destination.

        """
        with self.assertRaisesMessage(
            CommandError, "Can't symlink to a remote destination."
        ):
            self.run_collectstatic()
