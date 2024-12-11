from pathlib import Path
from unittest import mock

from django.conf import DEFAULT_STORAGE_ALIAS, STATICFILES_STORAGE_ALIAS, settings
from django.contrib.staticfiles.checks import E005, check_finders, check_storages
from django.contrib.staticfiles.finders import BaseFinder, get_finder
from django.core.checks import Error, Warning
from django.test import SimpleTestCase, override_settings

from .cases import CollectionTestCase
from .settings import TEST_ROOT


class FindersCheckTests(CollectionTestCase):
    run_collectstatic_in_setUp = False

    def test_base_finder_check_not_implemented(self):
        """
        Tests that the BaseFinder class correctly raises a NotImplementedError when its check method is called.

        This test case verifies that the check method, which is intended to be implemented by subclasses to validate the finder's configuration, is not implemented in the base class and therefore raises an exception as expected.

        The expected error message is also checked to ensure that it provides a clear indication of the need for subclasses to implement this method.

        This test ensures that any subclasses of BaseFinder will be forced to implement the check method, providing a way to verify that the finder is properly configured before use.
        """
        finder = BaseFinder()
        msg = (
            "subclasses may provide a check() method to verify the finder is "
            "configured correctly."
        )
        with self.assertRaisesMessage(NotImplementedError, msg):
            finder.check()

    def test_check_finders(self):
        """check_finders() concatenates all errors."""
        error1 = Error("1")
        error2 = Error("2")
        error3 = Error("3")

        def get_finders():
            """
            Returns a list of finder objects, each responsible for identifying specific errors or issues.

            The returned finders are instances of classes that inherit from BaseFinder and implement the check method, which evaluates certain conditions and returns a list of errors found. 

            The finders in the returned list are:
                * Finder1: Checks for error1 and returns it if found.
                * Finder2: Does not check for any errors and returns an empty list.
                * Finder3: Checks for multiple errors (error2 and error3) and returns them if found.
                * Finder4: An empty finder that does not implement the check method.

            These finders can be used to perform various checks and validations, and the returned errors can be further processed or handled as needed.

            :rtype: list[BaseFinder]
            :return: A list of finder objects
            """
            class Finder1(BaseFinder):
                def check(self, **kwargs):
                    return [error1]

            class Finder2(BaseFinder):
                def check(self, **kwargs):
                    return []

            class Finder3(BaseFinder):
                def check(self, **kwargs):
                    return [error2, error3]

            class Finder4(BaseFinder):
                pass

            return [Finder1(), Finder2(), Finder3(), Finder4()]

        with mock.patch("django.contrib.staticfiles.checks.get_finders", get_finders):
            errors = check_finders(None)
            self.assertEqual(errors, [error1, error2, error3])

    def test_no_errors_with_test_settings(self):
        self.assertEqual(check_finders(None), [])

    @override_settings(STATICFILES_DIRS="a string")
    def test_dirs_not_tuple_or_list(self):
        self.assertEqual(
            check_finders(None),
            [
                Error(
                    "The STATICFILES_DIRS setting is not a tuple or list.",
                    hint="Perhaps you forgot a trailing comma?",
                    id="staticfiles.E001",
                )
            ],
        )

    def test_dirs_contains_static_root(self):
        """

        Verifies that the STATICFILES_DIRS setting does not contain the STATIC_ROOT directory.

        This test checks for a common configuration mistake where the STATIC_ROOT directory
        is inadvertently included in the STATICFILES_DIRS setting. This can cause issues with
        static file collection and serving. The test ensures that the check_finders function
        correctly identifies and reports this error.

        """
        with self.settings(STATICFILES_DIRS=[settings.STATIC_ROOT]):
            self.assertEqual(
                check_finders(None),
                [
                    Error(
                        "The STATICFILES_DIRS setting should not contain the "
                        "STATIC_ROOT setting.",
                        id="staticfiles.E002",
                    )
                ],
            )

    def test_dirs_contains_static_root_in_tuple(self):
        """

        Tests that the STATICFILES_DIRS setting does not contain the STATIC_ROOT setting.

        This test checks for a specific error case where the STATICFILES_DIRS setting is
        configured to include the STATIC_ROOT setting, which is not allowed. It verifies
        that the check_finders function correctly identifies and reports this configuration
        issue, returning an Error object with a specific error message and ID.

        """
        with self.settings(STATICFILES_DIRS=[("prefix", settings.STATIC_ROOT)]):
            self.assertEqual(
                check_finders(None),
                [
                    Error(
                        "The STATICFILES_DIRS setting should not contain the "
                        "STATIC_ROOT setting.",
                        id="staticfiles.E002",
                    )
                ],
            )

    def test_prefix_contains_trailing_slash(self):
        static_dir = Path(TEST_ROOT) / "project" / "documents"
        with self.settings(STATICFILES_DIRS=[("prefix/", static_dir)]):
            self.assertEqual(
                check_finders(None),
                [
                    Error(
                        "The prefix 'prefix/' in the STATICFILES_DIRS setting must "
                        "not end with a slash.",
                        id="staticfiles.E003",
                    ),
                ],
            )

    def test_nonexistent_directories(self):
        with self.settings(
            STATICFILES_DIRS=[
                "/fake/path",
                ("prefix", "/fake/prefixed/path"),
            ]
        ):
            self.assertEqual(
                check_finders(None),
                [
                    Warning(
                        "The directory '/fake/path' in the STATICFILES_DIRS "
                        "setting does not exist.",
                        id="staticfiles.W004",
                    ),
                    Warning(
                        "The directory '/fake/prefixed/path' in the "
                        "STATICFILES_DIRS setting does not exist.",
                        id="staticfiles.W004",
                    ),
                ],
            )
            # Nonexistent directories are skipped.
            finder = get_finder("django.contrib.staticfiles.finders.FileSystemFinder")
            self.assertEqual(list(finder.list(None)), [])


class StoragesCheckTests(SimpleTestCase):
    @override_settings(STORAGES={})
    def test_error_empty_storages(self):
        errors = check_storages(None)
        self.assertEqual(errors, [E005])

    @override_settings(
        STORAGES={
            DEFAULT_STORAGE_ALIAS: {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
            },
            "example": {
                "BACKEND": "ignore.me",
            },
        }
    )
    def test_error_missing_staticfiles(self):
        """
        Tests that an error is raised when a storage configuration is missing static files settings.

        This test case checks that the :func:`check_storages` function correctly identifies and reports
        a configuration error when a storage backend is defined without the required static files settings.
        The expected result is an error code of E005, indicating that the storage configuration is invalid.

        Args:
            None

        Returns:
            An assertion that the check_storages function returns the expected error code [E005].
        """
        errors = check_storages(None)
        self.assertEqual(errors, [E005])

    @override_settings(
        STORAGES={
            STATICFILES_STORAGE_ALIAS: {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }
    )
    def test_staticfiles_no_errors(self):
        """

        Checks if the static files storage is correctly configured.

        This test ensures that the static files storage does not produce any errors.
        It utilizes the check_storages function to verify the configuration and
        asserts that no errors are returned, confirming proper setup of the static files storage.

        :returns: None

        """
        errors = check_storages(None)
        self.assertEqual(errors, [])
