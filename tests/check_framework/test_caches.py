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
        Checks that the cache path is not inside the media or static files directories.

        This test ensures that the cache location is not exposed by being inside the media or static files settings, which could potentially lead to cache files being served by the web server. 

        It iterates over the MEDIA_ROOT, STATIC_ROOT, and STATICFILES_DIRS settings, and for each setting, it checks that the cache location is not inside the respective directory. 

        If the cache path is found to be inside any of these directories, it raises a Warning with the message indicating the setting that the cache path is inside.
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
        Checks that the cache path does not conflict with media, static, or static files directories.

        This test ensures that the cache location is properly isolated and does not overlap with other file system paths that may be served directly by the application, which could potentially expose sensitive data. It verifies this isolation for various settings, including media root, static root, and static files directories.
        """
        root = pathlib.Path.cwd()
        for setting in ("MEDIA_ROOT", "STATIC_ROOT", "STATICFILES_DIRS"):
            settings = self.get_settings(setting, root / "cache", root / "other")
            with self.subTest(setting=setting), self.settings(**settings):
                self.assertEqual(check_cache_location_not_exposed(None), [])

    def test_staticfiles_dirs_prefix(self):
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
        Tests that the staticfiles directory and cache prefix do not conflict.

        Verifies that when the staticfiles directory and cache prefix are set, the cache
        location is not exposed. This ensures that the cache directory does not overlap
        with the staticfiles directory, preventing potential conflicts and data loss.

        The test checks if the cache location is properly isolated from the staticfiles
        directory, ensuring a safe and functional configuration for serving static files
        and storing cache data.
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
