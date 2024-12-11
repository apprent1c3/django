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
        Tests that the BaseFinder class raises a NotImplementedError when its check method is invoked.

        This test case verifies that the base implementation of the check method is not implemented and is 
        intended to be overridden by subclasses to provide a custom configuration verification mechanism.

        Raises:
            AssertionError: If the NotImplementedError is not raised with the expected message.

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
            \\":\"\"\"
            Returns a list of finder objects, which can be used to identify and report errors or issues.
            Each finder object has a :meth:`check` method that, when called, returns a list of errors found.
            The finders returned by this function can be used to perform various checks and validations,
            although some may not implement the :meth:`check` method or may always return an empty list of errors.
            The purpose of each finder is not explicitly defined, but they can be instantiated and used
            to perform checks in a variety of contexts.

            :returns: A list of finder objects
            :rtype: list[Finder]

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
        Tests that the STATICFILES_DIRS setting does not contain the STATIC_ROOT setting.

        This check ensures that the static files directories and the static root directory are not conflicting, 
        as including the static root in the directories can cause issues with static file serving. 
        The test verifies that an error is raised when STATIC_ROOT is included in STATICFILES_DIRS.
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
        Tests whether the STATICFILES_DIRS setting contains the STATIC_ROOT setting when the prefix is used in a tuple.

        The test checks for a specific error condition where the STATICFILES_DIRS setting includes the STATIC_ROOT setting as part of a tuple.
        This ensures that Django's static files finders behave correctly and raises an error when the settings are misconfigured, specifically reporting an Error with id 'staticfiles.E002'.
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
        """
        Tests that the STATICFILES_DIRS setting's prefix does not end with a trailing slash.

        Verifies that the :func:`check_finders` function correctly identifies and reports an error when the 'prefix' in the STATICFILES_DIRS setting contains a trailing slash. The test checks for the presence of a specific error message in the output of :func:`check_finders`, confirming that the function behaves as expected in this scenario.

        The test uses a custom static directory path and a mocked settings object to simulate the error condition.

        Returns:
            None, but asserts that the :func:`check_finders` function returns an error indicating that the prefix must not end with a slash.

        """
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

        Tests that no errors are reported when using the staticfiles storage backend.

        Verifies that the :func:`check_storages` function returns an empty list of errors
        when the staticfiles storage is properly configured, indicating that all
        requirements for using the staticfiles storage are met.

        """
        errors = check_storages(None)
        self.assertEqual(errors, [])
