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
        """
        Tests the retrieval of a template by name from the template engine.

        Verifies that the correct template is returned and that it is cached correctly.
        The test checks the origin of the template, including its name, path, and loader.
        It also ensures that the template is retrieved from the cache when requested multiple times.
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
        """

        Set up the class for testing, initializing the template engine.

        This class method is called once before running any test methods in the class.
        It configures the template engine to load templates from the specified directory,
        using the Django filesystem loader. The parent class's setUpClass method is also
        called to perform any additional setup.

        """
        cls.engine = Engine(
            dirs=[TEMPLATE_DIR], loaders=["django.template.loaders.filesystem.Loader"]
        )
        super().setUpClass()

    @contextmanager
    def set_dirs(self, dirs):
        """
         Temporarily sets the engine directories for the duration of a context block.

            This context manager allows you to override the engine's directories for a specific section of code.
            On entering the context, the original directories are saved and the new directories are applied.
            On exiting the context, the original directories are restored, regardless of whether an exception was thrown or not.

            :param dirs: The new directories to use for the engine
            :yield: Control, allowing the context to be executed

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

        A context manager that provides a function to verify the source of templates.

        This context manager sets up the necessary environment for testing template sources.
        It creates a function `check_sources` that can be used to compare the expected sources of a template
        with the actual sources loaded by the template loader.

        The `check_sources` function takes two parameters: `path` (the path of the template to check)
        and `expected_sources` (a list of expected source files).

        It uses the `assertEqual` method to verify that the actual sources match the expected sources.
        The sources are compared as absolute paths.

        This context manager yields the `check_sources` function, allowing it to be used within a `with` block.

        """
        loader = self.engine.template_loaders[0]

        def check_sources(path, expected_sources):
            """
            Checks if the template sources for a given path match the expected sources.

            Args:
                path (str): The path to check template sources for.
                expected_sources (list): A list of expected template source paths.

            Verifies that the actual template sources for the given path are identical to the expected sources.
            The comparison is done by normalizing the expected source paths to absolute paths and then
            comparing them with the names of the template sources retrieved from the loader.

            Raises:
                AssertionError: If the actual template sources do not match the expected sources.
            """
            expected_sources = [os.path.abspath(s) for s in expected_sources]
            self.assertEqual(
                [origin.name for origin in loader.get_template_sources(path)],
                expected_sources,
            )

        with self.set_dirs(dirs):
            yield check_sources

    def test_get_template(self):
        template = self.engine.get_template("index.html")
        self.assertEqual(template.origin.name, os.path.join(TEMPLATE_DIR, "index.html"))
        self.assertEqual(template.origin.template_name, "index.html")
        self.assertEqual(template.origin.loader, self.engine.template_loaders[0])
        self.assertEqual(
            template.origin.loader_name, "django.template.loaders.filesystem.Loader"
        )

    def test_loaders_dirs(self):
        """
        Tests the loading of templates from the designated directories.

        This test case verifies that the template engine can correctly locate and load templates from the specified directories.
        It checks that the loaded template's origin matches the expected location in the file system, ensuring that the 
        template loader is functioning as expected.

        :raises: AssertionError if the template origin does not match the expected location
        """
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

        Tests the security of a directory by checking access to various files.

        This test function evaluates how a source checker handles different file paths,
        including absolute and relative paths, and ensures that it correctly blocks
        access to sensitive files such as /etc/passwd.

        It verifies that the source checker can:
        - Allow access to existing files within the specified directories
        - Deny access to files outside of the specified directories
        - Handle paths with '../' and other relative path components correctly
        - Block access to sensitive system files

        The test covers a range of scenarios to ensure the directory security is properly implemented.

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
        Tests that template names containing Unicode characters are handled correctly.

        Verifies that the function can properly create and check source directories with names that include non-ASCII characters, such as accented letters and non-Latin scripts.

        The test ensures that the source checker can correctly identify and validate directory paths that contain Unicode characters in the template name.

        :param none:
        :return: none
        :raises: AssertionError if the source checker fails to correctly handle Unicode template names
        """
        with self.source_checker(["/dir1", "/dir2"]) as check_sources:
            check_sources("Ångström", ["/dir1/Ångström", "/dir2/Ångström"])

    def test_bytestring(self):
        loader = self.engine.template_loaders[0]
        msg = "Can't mix strings and bytes in path components"
        with self.assertRaisesMessage(TypeError, msg):
            list(loader.get_template_sources(b"\xc3\x85ngstr\xc3\xb6m"))

    def test_unicode_dir_name(self):
        """

        Tests the handling of unicode characters in directory names.

        This test case checks that the source checker correctly handles directory names 
        containing unicode characters, ensuring that the checker can properly identify 
        and validate sources within these directories.

        """
        with self.source_checker(["/Straße"]) as check_sources:
            check_sources("Ångström", ["/Straße/Ångström"])

    @unittest.skipUnless(
        os.path.normcase("/TEST") == os.path.normpath("/test"),
        "This test only runs on case-sensitive file systems.",
    )
    def test_case_sensitivity(self):
        """

        Tests the case sensitivity of file paths on the underlying file system.

        This test ensures that the source checker correctly handles file paths with different cases
        and checks if the file system is case-sensitive or not.

        The test passes if the source checker can distinguish between identical paths with different cases,
        and fails if it cannot.

        Note: This test is only executed on case-sensitive file systems.

        """
        with self.source_checker(["/dir1", "/DIR2"]) as check_sources:
            check_sources("index.html", ["/dir1/index.html", "/DIR2/index.html"])
            check_sources("/DIR1/index.HTML", ["/DIR1/index.HTML"])

    def test_file_does_not_exist(self):
        """
        Tests that a TemplateDoesNotExist exception is raised when attempting to retrieve a non-existent template file.

        Raises a TemplateDoesNotExist exception when the template file 'doesnotexist.html' is requested from the template engine, verifying that the engine correctly handles missing templates.
        """
        with self.assertRaises(TemplateDoesNotExist):
            self.engine.get_template("doesnotexist.html")

    @unittest.skipIf(
        sys.platform == "win32",
        "Python on Windows doesn't have working os.chmod().",
    )
    def test_permissions_error(self):
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
        Test that attempting to get a template from a non-existent file raises an error.

        This test checks that the engine correctly handles the case where the template file does not exist.
        It verifies that a PermissionError is raised on Windows platforms and an IsADirectoryError is raised on other platforms.
        The test is designed to ensure that the engine provides a robust and platform-aware error handling mechanism when dealing with missing template files.
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
        """

        Tests the retrieval of a template using the template engine.

        This test case verifies that the correct template is loaded from the expected location.
        It checks that the template's origin attributes, including the template name and loader,
        match the expected values.

        """
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
