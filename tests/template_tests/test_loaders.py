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
        With template debugging disabled, the raw TemplateDoesNotExist class
        should be cached when a template is missing. See ticket #26306 and
        docstrings in the cached loader for details.
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
        With template debugging enabled, a TemplateDoesNotExist instance
        should be cached when a template is missing.
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
        When a TemplateDoesNotExist instance is cached, the cached instance
        should not contain the __traceback__, __context__, or __cause__
        attributes that Python sets when raising exceptions.
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
        #26536 -- A leading dash in a template name shouldn't be stripped
        from its cache key.
        """
        self.assertEqual(
            self.engine.template_loaders[0].cache_key("-template.html", []),
            "-template.html",
        )

    def test_template_name_lazy_string(self):
        """
        #26603 -- A template name specified as a lazy string should be forced
        to text before computing its cache key.
        """
        self.assertEqual(
            self.engine.template_loaders[0].cache_key(lazystr("template.html"), []),
            "template.html",
        )

    def test_get_dirs(self):
        inner_dirs = self.engine.template_loaders[0].loaders[0].get_dirs()
        self.assertSequenceEqual(
            list(self.engine.template_loaders[0].get_dirs()), list(inner_dirs)
        )


class FileSystemLoaderTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Engine(
            dirs=[TEMPLATE_DIR], loaders=["django.template.loaders.filesystem.Loader"]
        )
        super().setUpClass()

    @contextmanager
    def set_dirs(self, dirs):
        original_dirs = self.engine.dirs
        self.engine.dirs = dirs
        try:
            yield
        finally:
            self.engine.dirs = original_dirs

    @contextmanager
    def source_checker(self, dirs):
        """
        Context manager to check the sources of templates loaded by the template loader.

        Within the context, it yields a function `check_sources` which compares the expected sources of a template with the actual sources obtained from the template loader.

        The `check_sources` function takes two parameters: `path` (the template path to check) and `expected_sources` (a list of expected source paths).

        It ensures that the actual sources match the expected sources, allowing for validation of template loading behavior.

        Args:
            path (str): The template path to check.
            expected_sources (list): A list of expected source paths.

        Example:
            with source_checker(dirs=['/path/to/templates']):
                check_sources('template.html', ['/path/to/templates/template.html'])

        """
        loader = self.engine.template_loaders[0]

        def check_sources(path, expected_sources):
            """

            Verifies that the template sources for a given path match the expected sources.

            Checks that the names of the template sources loaded from the specified path
            are identical to the provided list of expected sources. The expected sources
            are first converted to absolute paths to ensure accurate comparison.

            Args:
                path (str): The path to check for template sources.
                expected_sources (list): A list of paths representing the expected template sources.

            Returns:
                None: This function does not return any value. It raises an AssertionError if the
                actual template sources do not match the expected sources.

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
        Tests the retrieval of a template from the template engine.

        Verifies that the correct template is loaded from the expected location and
        that its origin attributes are correctly set. This includes checking the
        template's name, loader, and loader name to ensure they match the expected
        values.

        The test case covers the basic functionality of the template engine's get
        template method, providing assurance that templates are properly resolved and
        loaded from the file system.

        """
        template = self.engine.get_template("index.html")
        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))
        self.assertEqual(template.origin.template_name, "index.html")
        self.assertEqual(template.origin.loader, self.engine.template_loaders[0])
        self.assertEqual(
            template.origin.loader_name, "django.template.loaders.filesystem.Loader"
        )

    def test_loaders_dirs(self):
        engine = Engine(
            loaders=[("django.template.loaders.filesystem.Loader", [TEMPLATE_DIR])]
        )
        template = engine.get_template("index.html")
        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))

    def test_loaders_dirs_empty(self):
        """An empty dirs list in loaders overrides top level dirs."""
        engine = Engine(
            dirs=[TEMPLATE_DIR],
            loaders=[("django.template.loaders.filesystem.Loader", [])],
        )
        with self.assertRaises(TemplateDoesNotExist):
            engine.get_template("index.html")

    def test_directory_security(self):
        """

        Tests the security of directory traversal functionality.

        This function checks how the system handles various file paths to ensure that
        it does not allow access to sensitive files or directories outside the intended
        root directories.

        It verifies that the system correctly handles absolute paths, relative paths,
        and paths that attempt to traverse outside the root directories using \"..\" or
        \"../\" notation.

        The test cases cover a range of scenarios, including:

        * Accessing files within the intended root directories
        * Attempting to access sensitive system files (e.g. /etc/passwd)
        * Using relative paths to access files within the root directories
        * Trying to traverse outside the root directories using \"..\" or \"../\" notation
        * Requesting non-existent files within and outside the root directories

        By passing these test cases, the system demonstrates its ability to securely
        handle directory traversal and prevent potential security vulnerabilities.

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
        with self.source_checker(["/dir1", "/dir2"]) as check_sources:
            check_sources("Ångström", ["/dir1/Ångström", "/dir2/Ångström"])

    def test_bytestring(self):
        """
        Test that a TypeError is raised when a bytestring is passed as a path component to the template loader.

        This test case verifies that the loader correctly handles bytestrings and raises an error when it encounters one,
        preventing the mixing of strings and bytes in path components. The error message should match the expected message
        \"Can't mix strings and bytes in path components\".

        :param None:
        :return: None
        :raises TypeError: when a bytestring is passed as a path component to the template loader
        """
        loader = self.engine.template_loaders[0]
        msg = "Can't mix strings and bytes in path components"
        with self.assertRaisesMessage(TypeError, msg):
            list(loader.get_template_sources(b"\xc3\x85ngstr\xc3\xb6m"))

    def test_unicode_dir_name(self):
        with self.source_checker(["/Straße"]) as check_sources:
            check_sources("Ångström", ["/Straße/Ångström"])

    @unittest.skipUnless(
        os.path.normcase("/TEST") == os.path.normpath("/test"),
        "This test only runs on case-sensitive file systems.",
    )
    def test_case_sensitivity(self):
        with self.source_checker(["/dir1", "/DIR2"]) as check_sources:
            check_sources("index.html", ["/dir1/index.html", "/DIR2/index.html"])
            check_sources("/DIR1/index.HTML", ["/DIR1/index.HTML"])

    def test_file_does_not_exist(self):
        """
        Tests that the template engine correctly raises an error when attempting to retrieve a template that does not exist.

        This test verifies that the engine's get_template method behaves as expected when given a template name that is not found, ensuring that the TemplateDoesNotExist exception is properly raised in such cases.
        """
        with self.assertRaises(TemplateDoesNotExist):
            self.engine.get_template("doesnotexist.html")

    @unittest.skipIf(
        sys.platform == "win32",
        "Python on Windows doesn't have working os.chmod().",
    )
    def test_permissions_error(self):
        """

        Tests that the engine raises a PermissionError when attempting to access a template file with insufficient permissions.

        This test case creates a temporary file with restricted permissions, then attempts to retrieve the template using the engine. 
        It verifies that the expected PermissionError is raised with the correct error message.

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
        Raises an error when attempting to load a non-existent or inaccessible template.

        Tests that a suitable exception is raised when the template 'first' cannot be loaded, 
        detecting platform-specific differences between Windows and other operating systems. 
        On Windows, a PermissionError is expected, whereas on other platforms, an IsADirectoryError is anticipated.
        """
        with self.assertRaises(
            PermissionError if sys.platform == "win32" else IsADirectoryError
        ):
            self.engine.get_template("first")


class AppDirectoriesLoaderTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Engine(
            loaders=["django.template.loaders.app_directories.Loader"],
        )
        super().setUpClass()

    @override_settings(INSTALLED_APPS=["template_tests"])
    def test_get_template(self):
        template = self.engine.get_template("index.html")
        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))
        self.assertEqual(template.origin.template_name, "index.html")
        self.assertEqual(template.origin.loader, self.engine.template_loaders[0])

    @override_settings(INSTALLED_APPS=[])
    def test_not_installed(self):
        with self.assertRaises(TemplateDoesNotExist):
            self.engine.get_template("index.html")


class LocmemLoaderTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
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
        template = self.engine.get_template("index.html")
        self.assertEqual(template.origin.name, "index.html")
        self.assertEqual(template.origin.template_name, "index.html")
        self.assertEqual(template.origin.loader, self.engine.template_loaders[0])
