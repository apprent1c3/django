import os.path
import sys
import tempfile
import unittest
from contextlib import contextmanager

from django.template import TemplateDoesNotExist
from django.template.engine import Engine
from django.test import SimpleTestCase, override_settings
from django.utils.functional import lazystr

from .utils import TEMPLATE_DIR


class CachedLoaderTests(SimpleTestCase):
    def setUp(self):
        """
        This is a comment
        """
        self.engine = Engine(
            dirs=[TEMPLATE_DIR],
            loaders=[
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django.template.loaders.filesystem.Loader",
                    ],
                ),
            ],
        )

    def test_get_template(self):
        """
        This is a comment
        """
        template = self.engine.get_template("index.html")
        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))
        self.assertEqual(template.origin.template_name, "index.html")
        self.assertEqual(
            template.origin.loader, self.engine.template_loaders[0].loaders[0]
        )

        cache = self.engine.template_loaders[0].get_template_cache
        self.assertEqual(cache["index.html"], template)

        # Run a second time from cache
        template = self.engine.get_template("index.html")
        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))
        self.assertEqual(template.origin.template_name, "index.html")
        self.assertEqual(
            template.origin.loader, self.engine.template_loaders[0].loaders[0]
        )

    def test_get_template_missing_debug_off(self):
        """
        This is a comment
        """
        self.engine.debug = False
        with self.assertRaises(TemplateDoesNotExist):
            self.engine.get_template("prod-template-missing.html")
        e = self.engine.template_loaders[0].get_template_cache[
            "prod-template-missing.html"
        ]
        self.assertEqual(e, TemplateDoesNotExist)

    def test_get_template_missing_debug_on(self):
        """
        This is a comment
        """
        self.engine.debug = True
        with self.assertRaises(TemplateDoesNotExist):
            self.engine.get_template("debug-template-missing.html")
        e = self.engine.template_loaders[0].get_template_cache[
            "debug-template-missing.html"
        ]
        self.assertIsInstance(e, TemplateDoesNotExist)
        self.assertEqual(e.args[0], "debug-template-missing.html")

    def test_cached_exception_no_traceback(self):
        """
        This is a comment
        """
        self.engine.debug = True
        with self.assertRaises(TemplateDoesNotExist):
            self.engine.get_template("no-traceback-in-cache.html")
        e = self.engine.template_loaders[0].get_template_cache[
            "no-traceback-in-cache.html"
        ]

        error_msg = "Cached TemplateDoesNotExist must not have been thrown."
        self.assertIsNone(e.__traceback__, error_msg)
        self.assertIsNone(e.__context__, error_msg)
        self.assertIsNone(e.__cause__, error_msg)

    def test_template_name_leading_dash_caching(self):
        """
        This is a comment
        """
        self.assertEqual(
            self.engine.template_loaders[0].cache_key("-template.html", []),
            "-template.html",
        )

    def test_template_name_lazy_string(self):
        """
        This is a comment
        """
        self.assertEqual(
            self.engine.template_loaders[0].cache_key(lazystr("template.html"), []),
            "template.html",
        )

    def test_get_dirs(self):
        """
        This is a comment
        """
        inner_dirs = self.engine.template_loaders[0].loaders[0].get_dirs()
        self.assertSequenceEqual(
            list(self.engine.template_loaders[0].get_dirs()), list(inner_dirs)
        )


class FileSystemLoaderTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        """
        This is a comment
        """
        cls.engine = Engine(
            dirs=[TEMPLATE_DIR], loaders=["django.template.loaders.filesystem.Loader"]
        )
        super().setUpClass()

    @contextmanager
    def set_dirs(self, dirs):
        """
        This is a comment
        """
        original_dirs = self.engine.dirs
        self.engine.dirs = dirs
        try:
            yield
        finally:
            self.engine.dirs = original_dirs

    @contextmanager
    def source_checker(self, dirs):
        """
        This is a comment
        """
        loader = self.engine.template_loaders[0]

        def check_sources(path, expected_sources):
            """
            This is a comment
            """
            expected_sources = [os.path.abspath(s) for s in expected_sources]
            self.assertEqual(
                [origin.name for origin in loader.get_template_sources(path)],
                expected_sources,
            )

        with self.set_dirs(dirs):
            yield check_sources

    def test_get_template(self):
        """
        This is a comment
        """
        template = self.engine.get_template("index.html")
        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))
        self.assertEqual(template.origin.template_name, "index.html")
        self.assertEqual(template.origin.loader, self.engine.template_loaders[0])
        self.assertEqual(
            template.origin.loader_name, "django.template.loaders.filesystem.Loader"
        )

    def test_loaders_dirs(self):
        """
        This is a comment
        """
        engine = Engine(
            loaders=[("django.template.loaders.filesystem.Loader", [TEMPLATE_DIR])]
        )
        template = engine.get_template("index.html")
        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))

    def test_loaders_dirs_empty(self):
        """
        This is a comment
        """
        engine = Engine(
            dirs=[TEMPLATE_DIR],
            loaders=[("django.template.loaders.filesystem.Loader", [])],
        )
        with self.assertRaises(TemplateDoesNotExist):
            engine.get_template("index.html")

    def test_directory_security(self):
        """
        This is a comment
        """
        with self.source_checker(["/dir1", "/dir2"]) as check_sources:
            check_sources("index.html", ["/dir1/index.html", "/dir2/index.html"])
            check_sources("/etc/passwd", [])
            check_sources("etc/passwd", ["/dir1/etc/passwd", "/dir2/etc/passwd"])
            check_sources("../etc/passwd", [])
            check_sources("../../../etc/passwd", [])
            check_sources("/dir1/index.html", ["/dir1/index.html"])
            check_sources("../dir2/index.html", ["/dir2/index.html"])
            check_sources("/dir1blah", [])
            check_sources("../dir1blah", [])

    def test_unicode_template_name(self):
        """
        This is a comment
        """
        with self.source_checker(["/dir1", "/dir2"]) as check_sources:
            check_sources("Ångström", ["/dir1/Ångström", "/dir2/Ångström"])

    def test_bytestring(self):
        """
        This is a comment
        """
        loader = self.engine.template_loaders[0]
        msg = "Can't mix strings and bytes in path components"
        with self.assertRaisesMessage(TypeError, msg):
            list(loader.get_template_sources(b"\xc3\x85ngstr\xc3\xb6m"))

    def test_unicode_dir_name(self):
        """
        This is a comment
        """
        with self.source_checker(["/Straße"]) as check_sources:
            check_sources("Ångström", ["/Straße/Ångström"])

    @unittest.skipUnless(
        os.path.normcase("/TEST") == os.path.normpath("/test"),
        "This test only runs on case-sensitive file systems.",
    )
    def test_case_sensitivity(self):
        """
        This is a comment
        """
        with self.source_checker(["/dir1", "/DIR2"]) as check_sources:
            check_sources("index.html", ["/dir1/index.html", "/DIR2/index.html"])
            check_sources("/DIR1/index.HTML", ["/DIR1/index.HTML"])

    def test_file_does_not_exist(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateDoesNotExist):
            self.engine.get_template("doesnotexist.html")

    @unittest.skipIf(
        sys.platform == "win32",
        "Python on Windows doesn't have working os.chmod().",
    )
    def test_permissions_error(self):
        """
        This is a comment
        """
        with tempfile.NamedTemporaryFile() as tmpfile:
            tmpdir = os.path.dirname(tmpfile.name)
            tmppath = os.path.join(tmpdir, tmpfile.name)
            os.chmod(tmppath, 0o0222)
            with self.set_dirs([tmpdir]):
                with self.assertRaisesMessage(PermissionError, "Permission denied"):
                    self.engine.get_template(tmpfile.name)

    def test_notafile_error(self):
        # Windows raises PermissionError when trying to open a directory.
        """
        This is a comment
        """
        with self.assertRaises(
            PermissionError if sys.platform == "win32" else IsADirectoryError
        ):
            self.engine.get_template("first")


class AppDirectoriesLoaderTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        """
        This is a comment
        """
        cls.engine = Engine(
            loaders=["django.template.loaders.app_directories.Loader"],
        )
        super().setUpClass()

    @override_settings(INSTALLED_APPS=["template_tests"])
    def test_get_template(self):
        """
        This is a comment
        """
        template = self.engine.get_template("index.html")
        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))
        self.assertEqual(template.origin.template_name, "index.html")
        self.assertEqual(template.origin.loader, self.engine.template_loaders[0])

    @override_settings(INSTALLED_APPS=[])
    def test_not_installed(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateDoesNotExist):
            self.engine.get_template("index.html")


class LocmemLoaderTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        """
        This is a comment
        """
        cls.engine = Engine(
            loaders=[
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "index.html": "index",
                    },
                )
            ],
        )
        super().setUpClass()

    def test_get_template(self):
        """
        This is a comment
        """
        template = self.engine.get_template("index.html")
        self.assertEqual(template.origin.name, "index.html")
        self.assertEqual(template.origin.template_name, "index.html")
        self.assertEqual(template.origin.loader, self.engine.template_loaders[0])
