import pathlib

from django.core.checks import Warning
from django.core.checks.caches import (
    E001,
    check_cache_location_not_exposed,
    check_default_cache_is_configured,
    check_file_based_cache_is_absolute,
)
from django.test import SimpleTestCase
from django.test.utils import override_settings


class CheckCacheSettingsAppDirsTest(SimpleTestCase):
    VALID_CACHES_CONFIGURATION = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        },
    }
    INVALID_CACHES_CONFIGURATION = {
        "other": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        },
    }

    @override_settings(CACHES=VALID_CACHES_CONFIGURATION)
    def test_default_cache_included(self):
        """
        Don't error if 'default' is present in CACHES setting.
        """
        self.assertEqual(check_default_cache_is_configured(None), [])

    @override_settings(CACHES=INVALID_CACHES_CONFIGURATION)
    def test_default_cache_not_included(self):
        """
        Error if 'default' not present in CACHES setting.
        """
        self.assertEqual(check_default_cache_is_configured(None), [E001])


class CheckCacheLocationTest(SimpleTestCase):
    warning_message = (
        "Your 'default' cache configuration might expose your cache or lead "
        "to corruption of your data because its LOCATION %s %s."
    )

    @staticmethod
    def get_settings(setting, cache_path, setting_path):
        return {
            "CACHES": {
                "default": {
                    "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
                    "LOCATION": cache_path,
                },
            },
            setting: [setting_path] if setting == "STATICFILES_DIRS" else setting_path,
        }

    def test_cache_path_matches_media_static_setting(self):
        """
        Checks if the cache path is not exposed through Django's MEDIA_ROOT, STATIC_ROOT, or STATICFILES_DIRS settings.

        This test verifies that the cache location does not overlap with any of the specified media and static file settings to prevent unintended exposure. It iterates over each setting, generates a warning message, and asserts that the warning is raised with the correct message and identifier. This ensures that the cache path is properly configured to maintain security and prevent information disclosure.
        """
        root = pathlib.Path.cwd()
        for setting in ("MEDIA_ROOT", "STATIC_ROOT", "STATICFILES_DIRS"):
            settings = self.get_settings(setting, root, root)
            with self.subTest(setting=setting), self.settings(**settings):
                msg = self.warning_message % ("matches", setting)
                self.assertEqual(
                    check_cache_location_not_exposed(None),
                    [
                        Warning(msg, id="caches.W002"),
                    ],
                )

    def test_cache_path_inside_media_static_setting(self):
        """
        Tests whether a cache path set inside a media or static setting raises the expected warning.

        This test case iterates over various Django settings (MEDIA_ROOT, STATIC_ROOT, STATICFILES_DIRS) 
        and checks if the check_cache_location_not_exposed function correctly identifies 
        when a cache path is located inside one of these settings, which could expose sensitive data.
        The test verifies that a warning with the appropriate message and ID is raised in such cases.
        """
        root = pathlib.Path.cwd()
        for setting in ("MEDIA_ROOT", "STATIC_ROOT", "STATICFILES_DIRS"):
            settings = self.get_settings(setting, root / "cache", root)
            with self.subTest(setting=setting), self.settings(**settings):
                msg = self.warning_message % ("is inside", setting)
                self.assertEqual(
                    check_cache_location_not_exposed(None),
                    [
                        Warning(msg, id="caches.W002"),
                    ],
                )

    def test_cache_path_contains_media_static_setting(self):
        root = pathlib.Path.cwd()
        for setting in ("MEDIA_ROOT", "STATIC_ROOT", "STATICFILES_DIRS"):
            settings = self.get_settings(setting, root, root / "other")
            with self.subTest(setting=setting), self.settings(**settings):
                msg = self.warning_message % ("contains", setting)
                self.assertEqual(
                    check_cache_location_not_exposed(None),
                    [
                        Warning(msg, id="caches.W002"),
                    ],
                )

    def test_cache_path_not_conflict(self):
        """

        Tests that the cache path does not conflict with significant project settings.

        This test ensures that the cache location is not exposed in the project's 
        MEDIA_ROOT, STATIC_ROOT, or STATICFILES_DIRS settings, which could potentially
        lead to security issues or conflicts. It iterates over these project settings, 
        checks the cache location, and verifies that no conflicts are found.

        """
        root = pathlib.Path.cwd()
        for setting in ("MEDIA_ROOT", "STATIC_ROOT", "STATICFILES_DIRS"):
            settings = self.get_settings(setting, root / "cache", root / "other")
            with self.subTest(setting=setting), self.settings(**settings):
                self.assertEqual(check_cache_location_not_exposed(None), [])

    def test_staticfiles_dirs_prefix(self):
        """

        Test the prefix setting in STATICFILES_DIRS to ensure cache locations are not exposed.

        This test case verifies that the cache directory is correctly checked against the
        STATICFILES_DIRS setting to prevent exposure of cache locations. It checks three
        different scenarios: when the cache directory matches the STATICFILES_DIRS prefix,
        when the cache directory is inside the STATICFILES_DIRS prefix, and when the
        STATICFILES_DIRS prefix contains the cache directory. In each case, it expects a
        warning to be raised when the cache location is exposed.

        """
        root = pathlib.Path.cwd()
        tests = [
            (root, root, "matches"),
            (root / "cache", root, "is inside"),
            (root, root / "other", "contains"),
        ]
        for cache_path, setting_path, msg in tests:
            settings = self.get_settings(
                "STATICFILES_DIRS",
                cache_path,
                ("prefix", setting_path),
            )
            with self.subTest(path=setting_path), self.settings(**settings):
                msg = self.warning_message % (msg, "STATICFILES_DIRS")
                self.assertEqual(
                    check_cache_location_not_exposed(None),
                    [
                        Warning(msg, id="caches.W002"),
                    ],
                )

    def test_staticfiles_dirs_prefix_not_conflict(self):
        """

        Verifies that the 'STATICFILES_DIRS' setting does not conflict with the cache directory when a prefix is specified.
        Checks that the cache location is not exposed when the static files directories and cache directory have overlapping paths.
        Ensures the integrity of the cache system by testing for potential directory conflicts.

        """
        root = pathlib.Path.cwd()
        settings = self.get_settings(
            "STATICFILES_DIRS",
            root / "cache",
            ("prefix", root / "other"),
        )
        with self.settings(**settings):
            self.assertEqual(check_cache_location_not_exposed(None), [])


class CheckCacheAbsolutePath(SimpleTestCase):
    def test_absolute_path(self):
        """

        Tests that the absolute path validation for file-based cache returns an empty list when the cache location is absolute.

        This test verifies the correctness of the check_file_based_cache_is_absolute function when it receives a None value, 
        which triggers the function to check the default cache location.
        The test ensures that the function behaves as expected when the cache location is set to an absolute path, 
        in this case, the current working directory.

        """
        with self.settings(
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
                    "LOCATION": pathlib.Path.cwd() / "cache",
                },
            }
        ):
            self.assertEqual(check_file_based_cache_is_absolute(None), [])

    def test_relative_path(self):
        """
        Tests that a relative path in the default cache location triggers a warning.

        This test case ensures that when the default cache location is set to a relative path,
        a suitable warning is raised to encourage the use of an absolute path instead.
        The test verifies that the check for absolute paths in the cache location settings correctly identifies
        relative paths and issues the expected warning message.

        Returns:
            A list containing a warning indicating that the cache location path is relative.

        """
        with self.settings(
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
                    "LOCATION": "cache",
                },
            }
        ):
            self.assertEqual(
                check_file_based_cache_is_absolute(None),
                [
                    Warning(
                        "Your 'default' cache LOCATION path is relative. Use an "
                        "absolute path instead.",
                        id="caches.W003",
                    ),
                ],
            )
