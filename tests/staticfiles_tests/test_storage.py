import json
import os
import shutil
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import STATICFILES_STORAGE_ALIAS, settings
from django.contrib.staticfiles import finders, storage
from django.contrib.staticfiles.management.commands.collectstatic import (
    Command as CollectstaticCommand,
)
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from .cases import CollectionTestCase
from .settings import TEST_ROOT


def hashed_file_path(test, path):
    """
    Args:
        test: The test object used to render the template.
        path: The path to be rendered as a static file.

    Returns:
        str: The path of a static file with the static URL prefix removed.

    Notes:
        This function takes a test object and a path, renders the path as a static template snippet, 
        and returns the resulting path with the static URL prefix removed.
    """
    fullpath = test.render_template(test.static_template_snippet(path))
    return fullpath.removeprefix(settings.STATIC_URL)


class TestHashedFiles:
    hashed_file_path = hashed_file_path

    def tearDown(self):
        # Clear hashed files to avoid side effects among tests.
        storage.staticfiles_storage.hashed_files.clear()

    def assertPostCondition(self):
        """
        Assert post conditions for a test are met. Must be manually called at
        the end of each test.
        """
        pass

    def test_template_tag_return(self):
        """
        Tests template tag functionality for handling static files.

        This function verifies the behavior of the static template tag under various scenarios, 
        including non-existent files, static file rendering, and cached files. It checks 
        if the tag correctly raises an exception for non-existent files and if it 
        properly renders the static files with and without caching. Additionally, it tests 
        the tag's handling of file paths with query parameters and ensures that the 
        post-conditions are met after the tests are executed.

        The test cases cover a range of file types and paths to ensure the template tag 
        is working as expected in different situations. By checking the tag's behavior 
        in these scenarios, this function helps ensure that the static template tag is 
        reliable and functions correctly in a variety of contexts.
        """
        self.assertStaticRaises(
            ValueError, "does/not/exist.png", "/static/does/not/exist.png"
        )
        self.assertStaticRenders("test/file.txt", "/static/test/file.dad0999e4f8f.txt")
        self.assertStaticRenders(
            "test/file.txt", "/static/test/file.dad0999e4f8f.txt", asvar=True
        )
        self.assertStaticRenders(
            "cached/styles.css", "/static/cached/styles.5e0040571e1a.css"
        )
        self.assertStaticRenders("path/", "/static/path/")
        self.assertStaticRenders("path/?query", "/static/path/?query")
        self.assertPostCondition()

    def test_template_tag_simple_content(self):
        relpath = self.hashed_file_path("cached/styles.css")
        self.assertEqual(relpath, "cached/styles.5e0040571e1a.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertNotIn(b"cached/other.css", content)
            self.assertIn(b"other.d41d8cd98f00.css", content)
        self.assertPostCondition()

    def test_path_ignored_completely(self):
        relpath = self.hashed_file_path("cached/css/ignored.css")
        self.assertEqual(relpath, "cached/css/ignored.55e7c226dda1.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertIn(b"#foobar", content)
            self.assertIn(b"http:foobar", content)
            self.assertIn(b"https:foobar", content)
            self.assertIn(b"data:foobar", content)
            self.assertIn(b"chrome:foobar", content)
            self.assertIn(b"//foobar", content)
            self.assertIn(b"url()", content)
        self.assertPostCondition()

    def test_path_with_querystring(self):
        relpath = self.hashed_file_path("cached/styles.css?spam=eggs")
        self.assertEqual(relpath, "cached/styles.5e0040571e1a.css?spam=eggs")
        with storage.staticfiles_storage.open(
            "cached/styles.5e0040571e1a.css"
        ) as relfile:
            content = relfile.read()
            self.assertNotIn(b"cached/other.css", content)
            self.assertIn(b"other.d41d8cd98f00.css", content)
        self.assertPostCondition()

    def test_path_with_fragment(self):
        """
        Tests that a file path with a fragment is correctly handled.

        Verifies that a relative path to a hashed file with a fragment (e.g. a CSS file with an anchor) 
        is correctly computed and that the corresponding file content does not include references to 
        other hashed files with different fragments, but does include references to other hashed files 
        with the same fragment. 

        Ensures that post-conditions are met after the test execution.
        """
        relpath = self.hashed_file_path("cached/styles.css#eggs")
        self.assertEqual(relpath, "cached/styles.5e0040571e1a.css#eggs")
        with storage.staticfiles_storage.open(
            "cached/styles.5e0040571e1a.css"
        ) as relfile:
            content = relfile.read()
            self.assertNotIn(b"cached/other.css", content)
            self.assertIn(b"other.d41d8cd98f00.css", content)
        self.assertPostCondition()

    def test_path_with_querystring_and_fragment(self):
        relpath = self.hashed_file_path("cached/css/fragments.css")
        self.assertEqual(relpath, "cached/css/fragments.7fe344dee895.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertIn(b"fonts/font.b9b105392eb8.eot?#iefix", content)
            self.assertIn(b"fonts/font.b8d603e42714.svg#webfontIyfZbseF", content)
            self.assertIn(
                b"fonts/font.b8d603e42714.svg#path/to/../../fonts/font.svg", content
            )
            self.assertIn(
                b"data:font/woff;charset=utf-8;"
                b"base64,d09GRgABAAAAADJoAA0AAAAAR2QAAQAAAAAAAAAAAAA",
                content,
            )
            self.assertIn(b"#default#VML", content)
        self.assertPostCondition()

    def test_template_tag_absolute(self):
        """

        Tests the functionality of the template tag when serving absolute files.

        This test case validates that the absolute file paths are correctly generated
        and that the content of the served file contains the expected hashed URLs.

        Specifically, it checks that the content does not contain original URLs, but
        instead includes the hashed versions of the files, including CSS and image files.

        """
        relpath = self.hashed_file_path("cached/absolute.css")
        self.assertEqual(relpath, "cached/absolute.eb04def9f9a4.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertNotIn(b"/static/cached/styles.css", content)
            self.assertIn(b"/static/cached/styles.5e0040571e1a.css", content)
            self.assertNotIn(b"/static/styles_root.css", content)
            self.assertIn(b"/static/styles_root.401f2509a628.css", content)
            self.assertIn(b"/static/cached/img/relative.acae32e4532b.png", content)
        self.assertPostCondition()

    def test_template_tag_absolute_root(self):
        """
        Like test_template_tag_absolute, but for a file in STATIC_ROOT (#26249).
        """
        relpath = self.hashed_file_path("absolute_root.css")
        self.assertEqual(relpath, "absolute_root.f821df1b64f7.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertNotIn(b"/static/styles_root.css", content)
            self.assertIn(b"/static/styles_root.401f2509a628.css", content)
        self.assertPostCondition()

    def test_template_tag_relative(self):
        """
        Tests the template tag for rendering relative URLs in CSS files.

        This test case verifies that the template tag correctly rewrites URLs in CSS files
        to use relative paths, ensuring that the resulting URLs are correctly hashed
        and point to the correct locations. Specifically, it checks that:

        * Relative paths are correctly rewritten
        * Absolute paths are converted to relative paths
        * Imported files are correctly referenced
        * URLs in the CSS content are correctly rewritten to use hashed filenames

        The test case uses a cached CSS file as input and checks the resulting content
        to ensure that it meets the expected output criteria.
        """
        relpath = self.hashed_file_path("cached/relative.css")
        self.assertEqual(relpath, "cached/relative.c3e9e1ea6f2e.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertNotIn(b"../cached/styles.css", content)
            self.assertNotIn(b'@import "styles.css"', content)
            self.assertNotIn(b"url(img/relative.png)", content)
            self.assertIn(b'url("img/relative.acae32e4532b.png")', content)
            self.assertIn(b"../cached/styles.5e0040571e1a.css", content)
        self.assertPostCondition()

    def test_import_replacement(self):
        "See #18050"
        relpath = self.hashed_file_path("cached/import.css")
        self.assertEqual(relpath, "cached/import.f53576679e5a.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            self.assertIn(b"""import url("styles.5e0040571e1a.css")""", relfile.read())
        self.assertPostCondition()

    def test_template_tag_deep_relative(self):
        """

        Tests the deep relative functionality of a template tag.

        This test case verifies that a template tag can correctly resolve and replace 
        relative URLs with hashed versions of the file paths, ensuring that cached files 
        are properly referenced. The test checks for the presence of the expected hashed 
        URL in the file content and the absence of the non-hashed URL.

        The test validates the file 'window.css' in the 'cached/css' directory, 
        confirming that the 'url' references within the file have been correctly replaced 
        with their hashed equivalents, such as 'window.acae32e4532b.png'.

        """
        relpath = self.hashed_file_path("cached/css/window.css")
        self.assertEqual(relpath, "cached/css/window.5d5c10836967.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertNotIn(b"url(img/window.png)", content)
            self.assertIn(b'url("img/window.acae32e4532b.png")', content)
        self.assertPostCondition()

    def test_template_tag_url(self):
        """
        Tests the functionality of a template tag for generating URL paths.

        Verifies that the hashed file path generated by the template tag matches the expected path.
        Additionally, checks that the contents of the file at the generated path contain a specific URL scheme.

        This test ensures that the template tag correctly handles URL generation and file storage.

        """
        relpath = self.hashed_file_path("cached/url.css")
        self.assertEqual(relpath, "cached/url.902310b73412.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            self.assertIn(b"https://", relfile.read())
        self.assertPostCondition()

    @override_settings(
        STATICFILES_DIRS=[os.path.join(TEST_ROOT, "project", "loop")],
        STATICFILES_FINDERS=["django.contrib.staticfiles.finders.FileSystemFinder"],
    )
    def test_import_loop(self):
        """

        Tests the behavior of the collectstatic command when encountering a post-processing loop.

        This test simulates a scenario where the post-processing of static files enters an
        infinite loop. It verifies that the command raises a RuntimeError and provides
        the expected error messages when the maximum number of post-processing passes is exceeded.

        """
        finders.get_finder.cache_clear()
        err = StringIO()
        with self.assertRaisesMessage(RuntimeError, "Max post-process passes exceeded"):
            call_command("collectstatic", interactive=False, verbosity=0, stderr=err)
        self.assertEqual("Post-processing 'All' failed!\n\n", err.getvalue())
        self.assertPostCondition()

    def test_post_processing(self):
        """
        post_processing behaves correctly.

        Files that are alterable should always be post-processed; files that
        aren't should be skipped.

        collectstatic has already been called once in setUp() for this testcase,
        therefore we check by verifying behavior on a second run.
        """
        collectstatic_args = {
            "interactive": False,
            "verbosity": 0,
            "link": False,
            "clear": False,
            "dry_run": False,
            "post_process": True,
            "use_default_ignore_patterns": True,
            "ignore_patterns": ["*.ignoreme"],
        }

        collectstatic_cmd = CollectstaticCommand()
        collectstatic_cmd.set_options(**collectstatic_args)
        stats = collectstatic_cmd.collect()
        self.assertIn(
            os.path.join("cached", "css", "window.css"), stats["post_processed"]
        )
        self.assertIn(
            os.path.join("cached", "css", "img", "window.png"), stats["unmodified"]
        )
        self.assertIn(os.path.join("test", "nonascii.css"), stats["post_processed"])
        # No file should be yielded twice.
        self.assertCountEqual(stats["post_processed"], set(stats["post_processed"]))
        self.assertPostCondition()

    def test_css_import_case_insensitive(self):
        relpath = self.hashed_file_path("cached/styles_insensitive.css")
        self.assertEqual(relpath, "cached/styles_insensitive.3fa427592a53.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertNotIn(b"cached/other.css", content)
            self.assertIn(b"other.d41d8cd98f00.css", content)
        self.assertPostCondition()

    def test_css_source_map(self):
        """
        Tests the CSS source map file to ensure it is correctly formatted and linked.

        This test verifies that the source map file is properly generated and referenced
        in the CSS file. It checks that the relative path to the CSS file is correctly
        hashed and that the source map URL in the CSS file points to the hashed source
        map file. Additionally, it confirms that the post-condition checks pass after
        reading and verifying the CSS file content.

        The test ensures that the CSS source map is properly integrated and can be used
        for debugging purposes. It also validates that the `storage.staticfiles_storage`
        is correctly configured to open and read the CSS file.
        """
        relpath = self.hashed_file_path("cached/source_map.css")
        self.assertEqual(relpath, "cached/source_map.b2fceaf426aa.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertNotIn(b"/*# sourceMappingURL=source_map.css.map*/", content)
            self.assertIn(
                b"/*# sourceMappingURL=source_map.css.99914b932bd3.map */",
                content,
            )
        self.assertPostCondition()

    def test_css_source_map_tabs(self):
        """

         Tests the CSS source map functionality with tabs.

        This test verifies that the CSS source map is correctly generated and referenced
        in the CSS file. It checks that the source map URL is correctly formatted and
        included in the CSS file, and that the incorrect source map URL with a tab 
        character is not present. The test also ensures that the post-condition is met 
        after the test execution.

        """
        relpath = self.hashed_file_path("cached/source_map_tabs.css")
        self.assertEqual(relpath, "cached/source_map_tabs.b2fceaf426aa.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertNotIn(b"/*#\tsourceMappingURL=source_map.css.map\t*/", content)
            self.assertIn(
                b"/*# sourceMappingURL=source_map.css.99914b932bd3.map */",
                content,
            )
        self.assertPostCondition()

    def test_css_source_map_sensitive(self):
        relpath = self.hashed_file_path("cached/source_map_sensitive.css")
        self.assertEqual(relpath, "cached/source_map_sensitive.456683f2106f.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertIn(b"/*# sOuRcEMaPpInGURL=source_map.css.map */", content)
            self.assertNotIn(
                b"/*# sourceMappingURL=source_map.css.99914b932bd3.map */",
                content,
            )
        self.assertPostCondition()

    def test_css_source_map_data_uri(self):
        """
        Tests that the source map data URI is correctly included in the CSS file.

        Verifies that the CSS file path is correctly hashed and that the file contents
        include the expected source map data URI. This ensures that the CSS file is
        properly generated and includes the necessary information for sourcemaps.

        The test checks for the presence of a specific base64-encoded source map data URI
        in the CSS file contents, which is expected to be included when the file is
        generated. If the data URI is not found, the test will fail.

        This test case covers the functionality of generating CSS files with source maps
        and ensures that the resulting files contain the required data URIs for correct
        operation.
        """
        relpath = self.hashed_file_path("cached/source_map_data_uri.css")
        self.assertEqual(relpath, "cached/source_map_data_uri.3166be10260d.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            source_map_data_uri = (
                b"/*# sourceMappingURL=data:application/json;charset=utf8;base64,"
                b"eyJ2ZXJzaW9uIjozLCJzb3VyY2VzIjpbIl9zcmMv*/"
            )
            self.assertIn(source_map_data_uri, content)
        self.assertPostCondition()

    def test_js_source_map(self):
        relpath = self.hashed_file_path("cached/source_map.js")
        self.assertEqual(relpath, "cached/source_map.cd45b8534a87.js")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertNotIn(b"//# sourceMappingURL=source_map.js.map", content)
            self.assertIn(
                b"//# sourceMappingURL=source_map.js.99914b932bd3.map",
                content,
            )
        self.assertPostCondition()

    def test_js_source_map_trailing_whitespace(self):
        """

        Tests the functionality of handling JavaScript source maps with trailing whitespace.

        Verifies that the file is correctly hashed and stored, and that the source map URL is 
        properly updated to reference the hashed file without any trailing whitespace.

        Ensures that the resulting file content meets the expected format and contains the 
        correct source map reference.

        """
        relpath = self.hashed_file_path("cached/source_map_trailing_whitespace.js")
        self.assertEqual(
            relpath, "cached/source_map_trailing_whitespace.cd45b8534a87.js"
        )
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertNotIn(b"//# sourceMappingURL=source_map.js.map\t ", content)
            self.assertIn(
                b"//# sourceMappingURL=source_map.js.99914b932bd3.map",
                content,
            )
        self.assertPostCondition()

    def test_js_source_map_sensitive(self):
        relpath = self.hashed_file_path("cached/source_map_sensitive.js")
        self.assertEqual(relpath, "cached/source_map_sensitive.5da96fdd3cb3.js")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertIn(b"//# sOuRcEMaPpInGURL=source_map.js.map", content)
            self.assertNotIn(
                b"//# sourceMappingURL=source_map.js.99914b932bd3.map",
                content,
            )
        self.assertPostCondition()

    def test_js_source_map_data_uri(self):
        """
        Tests that the source map data is correctly embedded as a data URI in the generated JavaScript file.

        Verifies that the expected source map data URI prefix is present in the file contents, 
        indicating that the source map data has been successfully encoded and included in the file.

        Checks the file path and contents to ensure they match the expected output, 
        specifically that the source map data URI starts with the correct header and contains the expected base64 encoded data.
        """
        relpath = self.hashed_file_path("cached/source_map_data_uri.js")
        self.assertEqual(relpath, "cached/source_map_data_uri.a68d23cbf6dd.js")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            source_map_data_uri = (
                b"//# sourceMappingURL=data:application/json;charset=utf8;base64,"
                b"eyJ2ZXJzaW9uIjozLCJzb3VyY2VzIjpbIl9zcmMv"
            )
            self.assertIn(source_map_data_uri, content)
        self.assertPostCondition()

    @override_settings(
        STATICFILES_DIRS=[os.path.join(TEST_ROOT, "project", "faulty")],
        STATICFILES_FINDERS=["django.contrib.staticfiles.finders.FileSystemFinder"],
    )
    def test_post_processing_failure(self):
        """
        post_processing indicates the origin of the error when it fails.
        """
        finders.get_finder.cache_clear()
        err = StringIO()
        with self.assertRaises(Exception):
            call_command("collectstatic", interactive=False, verbosity=0, stderr=err)
        self.assertEqual("Post-processing 'faulty.css' failed!\n\n", err.getvalue())
        self.assertPostCondition()

    @override_settings(
        STATICFILES_DIRS=[os.path.join(TEST_ROOT, "project", "nonutf8")],
        STATICFILES_FINDERS=["django.contrib.staticfiles.finders.FileSystemFinder"],
    )
    def test_post_processing_nonutf8(self):
        """
        Tests post-processing of static files with non-UTF8 encoding.

        This test case verifies that the collectstatic command correctly handles static files
        that contain non-UTF8 encoded characters. It checks that the post-processing step
        detects the encoding error and raises a UnicodeDecodeError exception.

        The test scenario simulates a setup where the static files directory contains a file
        with non-UTF8 encoding, and then runs the collectstatic command to test its
        behavior. The test asserts that the command raises an exception with the expected
        error message, indicating that the post-processing step failed due to the encoding
        issue. Additionally, the test checks the post-condition to ensure that the system is
        in a correct state after the error occurred.
        """
        finders.get_finder.cache_clear()
        err = StringIO()
        with self.assertRaises(UnicodeDecodeError):
            call_command("collectstatic", interactive=False, verbosity=0, stderr=err)
        self.assertEqual("Post-processing 'nonutf8.css' failed!\n\n", err.getvalue())
        self.assertPostCondition()


@override_settings(
    STORAGES={
        **settings.STORAGES,
        STATICFILES_STORAGE_ALIAS: {
            "BACKEND": "staticfiles_tests.storage.ExtraPatternsStorage",
        },
    }
)
class TestExtraPatternsStorage(CollectionTestCase):
    def setUp(self):
        """
        Sets up the test environment by clearing the static files storage and 
        calling the parent class's setup method to initialize any additional 
        necessary resources.

        This method ensures a clean state for static files before each test, 
        allowing for consistent and reliable testing of static file handling 
        functionality.

        It should be called at the beginning of each test to prevent interference 
        from previous test runs and ensure predictable test outcomes.
        """
        storage.staticfiles_storage.hashed_files.clear()  # avoid cache interference
        super().setUp()

    def cached_file_path(self, path):
        fullpath = self.render_template(self.static_template_snippet(path))
        return fullpath.replace(settings.STATIC_URL, "")

    def test_multi_extension_patterns(self):
        """
        With storage classes having several file extension patterns, only the
        files matching a specific file pattern should be affected by the
        substitution (#19670).
        """
        # CSS files shouldn't be touched by JS patterns.
        relpath = self.cached_file_path("cached/import.css")
        self.assertEqual(relpath, "cached/import.f53576679e5a.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            self.assertIn(b'import url("styles.5e0040571e1a.css")', relfile.read())

        # Confirm JS patterns have been applied to JS files.
        relpath = self.cached_file_path("cached/test.js")
        self.assertEqual(relpath, "cached/test.388d7a790d46.js")
        with storage.staticfiles_storage.open(relpath) as relfile:
            self.assertIn(b'JS_URL("import.f53576679e5a.css")', relfile.read())


@override_settings(
    STORAGES={
        **settings.STORAGES,
        STATICFILES_STORAGE_ALIAS: {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
        },
    }
)
class TestCollectionManifestStorage(TestHashedFiles, CollectionTestCase):
    """
    Tests for the Cache busting storage
    """

    def setUp(self):
        """

        Set up the test environment by creating a temporary directory and a file within it.
        The temporary directory is used to mimic the STATICFILES_DIRS setting and the file is used for testing purposes.
        The function also patches the settings to include the temporary directory and enables the manifest strict mode for static files.
        After the test, the temporary directory and its contents are cleaned up to ensure a clean environment for subsequent tests.

        """
        super().setUp()

        temp_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(temp_dir, "test"))
        self._clear_filename = os.path.join(temp_dir, "test", "cleared.txt")
        with open(self._clear_filename, "w") as f:
            f.write("to be deleted in one test")

        patched_settings = self.settings(
            STATICFILES_DIRS=settings.STATICFILES_DIRS + [temp_dir],
        )
        patched_settings.enable()
        self.addCleanup(patched_settings.disable)
        self.addCleanup(shutil.rmtree, temp_dir)
        self._manifest_strict = storage.staticfiles_storage.manifest_strict

    def tearDown(self):
        if os.path.exists(self._clear_filename):
            os.unlink(self._clear_filename)

        storage.staticfiles_storage.manifest_strict = self._manifest_strict
        super().tearDown()

    def assertPostCondition(self):
        """

        Checks if the hashed files match the manifest after static file collection.

        This method verifies that the hashed files stored in the static files storage
        match the manifest loaded from the storage. It ensures that the files collected
        and hashed are consistent with the manifest, which is crucial for maintaining
        data integrity and preventing inconsistencies in the application.

        :raises AssertionError: If the hashed files do not match the manifest.

        """
        hashed_files = storage.staticfiles_storage.hashed_files
        # The in-memory version of the manifest matches the one on disk
        # since a properly created manifest should cover all filenames.
        if hashed_files:
            manifest, _ = storage.staticfiles_storage.load_manifest()
            self.assertEqual(hashed_files, manifest)

    def test_manifest_exists(self):
        """
        Tests whether the static files manifest exists in the specified storage location.

        This test verifies the presence of a manifest file, which maps static file names to their hashed versions, in the configured static files storage. It checks for the existence of the manifest file at the expected path, ensuring that it is properly generated and accessible.
        """
        filename = storage.staticfiles_storage.manifest_name
        path = storage.staticfiles_storage.path(filename)
        self.assertTrue(os.path.exists(path))

    def test_manifest_does_not_exist(self):
        storage.staticfiles_storage.manifest_name = "does.not.exist.json"
        self.assertIsNone(storage.staticfiles_storage.read_manifest())

    def test_manifest_does_not_ignore_permission_error(self):
        with mock.patch("builtins.open", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                storage.staticfiles_storage.read_manifest()

    def test_loaded_cache(self):
        self.assertNotEqual(storage.staticfiles_storage.hashed_files, {})
        manifest_content = storage.staticfiles_storage.read_manifest()
        self.assertIn(
            '"version": "%s"' % storage.staticfiles_storage.manifest_version,
            manifest_content,
        )

    def test_parse_cache(self):
        """
        Tests if the hashed files storage matches the files listed in the staticfiles manifest, ensuring data consistency and integrity. This test is crucial for verifying that the cache is properly updated when static files are modified, added, or removed.
        """
        hashed_files = storage.staticfiles_storage.hashed_files
        manifest, _ = storage.staticfiles_storage.load_manifest()
        self.assertEqual(hashed_files, manifest)

    def test_clear_empties_manifest(self):
        cleared_file_name = storage.staticfiles_storage.clean_name(
            os.path.join("test", "cleared.txt")
        )
        # collect the additional file
        self.run_collectstatic()

        hashed_files = storage.staticfiles_storage.hashed_files
        self.assertIn(cleared_file_name, hashed_files)

        manifest_content, _ = storage.staticfiles_storage.load_manifest()
        self.assertIn(cleared_file_name, manifest_content)

        original_path = storage.staticfiles_storage.path(cleared_file_name)
        self.assertTrue(os.path.exists(original_path))

        # delete the original file form the app, collect with clear
        os.unlink(self._clear_filename)
        self.run_collectstatic(clear=True)

        self.assertFileNotFound(original_path)

        hashed_files = storage.staticfiles_storage.hashed_files
        self.assertNotIn(cleared_file_name, hashed_files)

        manifest_content, _ = storage.staticfiles_storage.load_manifest()
        self.assertNotIn(cleared_file_name, manifest_content)

    def test_missing_entry(self):
        missing_file_name = "cached/missing.css"
        configured_storage = storage.staticfiles_storage
        self.assertNotIn(missing_file_name, configured_storage.hashed_files)

        # File name not found in manifest
        with self.assertRaisesMessage(
            ValueError,
            "Missing staticfiles manifest entry for '%s'" % missing_file_name,
        ):
            self.hashed_file_path(missing_file_name)

        configured_storage.manifest_strict = False
        # File doesn't exist on disk
        err_msg = "The file '%s' could not be found with %r." % (
            missing_file_name,
            configured_storage._wrapped,
        )
        with self.assertRaisesMessage(ValueError, err_msg):
            self.hashed_file_path(missing_file_name)

        content = StringIO()
        content.write("Found")
        configured_storage.save(missing_file_name, content)
        # File exists on disk
        self.hashed_file_path(missing_file_name)

    def test_intermediate_files(self):
        """
        Test that the correct number of intermediate files are generated.

        Verifies that exactly two cached files with names starting with 'relative.' exist in the STATIC_ROOT directory after processing.

        This test ensures the proper creation of intermediate files with the expected naming convention, confirming the correct functioning of the caching mechanism.

        :raises AssertionError: If the number of matching cached files does not match the expected count
        """
        cached_files = os.listdir(os.path.join(settings.STATIC_ROOT, "cached"))
        # Intermediate files shouldn't be created for reference.
        self.assertEqual(
            len(
                [
                    cached_file
                    for cached_file in cached_files
                    if cached_file.startswith("relative.")
                ]
            ),
            2,
        )

    def test_manifest_hash(self):
        # Collect the additional file.
        """

        Tests the generation and validation of the manifest hash in the static files storage.

        This test case checks the following scenarios:
        - That an initial manifest hash is generated after collecting static files.
        - That the manifest hash is correctly saved and loaded.
        - That clearing the static files and re-collecting them generates a new manifest hash.
        - That the new manifest hash differs from the original one.

        Verifies the integrity of the manifest hash generation process to ensure that
        changes to static files result in a new hash being generated, allowing for
        efficient caching and invalidation of static assets.

        """
        self.run_collectstatic()

        _, manifest_hash_orig = storage.staticfiles_storage.load_manifest()
        self.assertNotEqual(manifest_hash_orig, "")
        self.assertEqual(storage.staticfiles_storage.manifest_hash, manifest_hash_orig)
        # Saving doesn't change the hash.
        storage.staticfiles_storage.save_manifest()
        self.assertEqual(storage.staticfiles_storage.manifest_hash, manifest_hash_orig)
        # Delete the original file from the app, collect with clear.
        os.unlink(self._clear_filename)
        self.run_collectstatic(clear=True)
        # Hash is changed.
        _, manifest_hash = storage.staticfiles_storage.load_manifest()
        self.assertNotEqual(manifest_hash, manifest_hash_orig)

    def test_manifest_hash_v1(self):
        storage.staticfiles_storage.manifest_name = "staticfiles_v1.json"
        manifest_content, manifest_hash = storage.staticfiles_storage.load_manifest()
        self.assertEqual(manifest_hash, "")
        self.assertEqual(manifest_content, {"dummy.txt": "dummy.txt"})


@override_settings(
    STATIC_URL="/",
    STORAGES={
        **settings.STORAGES,
        STATICFILES_STORAGE_ALIAS: {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
        },
    },
)
class TestCollectionManifestStorageStaticUrlSlash(CollectionTestCase):
    run_collectstatic_in_setUp = False
    hashed_file_path = hashed_file_path

    def test_protocol_relative_url_ignored(self):
        """

        Tests that a protocol-relative URL in a static file is preserved during collection.

        This test ensures that when a static file contains a URL that starts with '//',
        it is not modified or rewritten during the collection process. The test checks
        that the collected file has the correct hashed filename and that its content
        still contains the original protocol-relative URL.

        """
        with override_settings(
            STATICFILES_DIRS=[os.path.join(TEST_ROOT, "project", "static_url_slash")],
            STATICFILES_FINDERS=["django.contrib.staticfiles.finders.FileSystemFinder"],
        ):
            self.run_collectstatic()
        relpath = self.hashed_file_path("ignored.css")
        self.assertEqual(relpath, "ignored.61707f5f4942.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertIn(b"//foobar", content)


@override_settings(
    STORAGES={
        **settings.STORAGES,
        STATICFILES_STORAGE_ALIAS: {
            "BACKEND": "staticfiles_tests.storage.NoneHashStorage",
        },
    }
)
class TestCollectionNoneHashStorage(CollectionTestCase):
    hashed_file_path = hashed_file_path

    def test_hashed_name(self):
        """
        Tests that a hashed name of a file path returns the original relative path when the file's hash is not required.

        This test case verifies that the hashed_file_path function correctly handles files for which hashing is not necessary, 
        returning the original relative path instead of a hashed version.

        The test uses 'cached/styles.css' as a sample file path, checking that the function behaves as expected for this scenario.
        """
        relpath = self.hashed_file_path("cached/styles.css")
        self.assertEqual(relpath, "cached/styles.css")


@override_settings(
    STORAGES={
        **settings.STORAGES,
        STATICFILES_STORAGE_ALIAS: {
            "BACKEND": "staticfiles_tests.storage.NoPostProcessReplacedPathStorage",
        },
    }
)
class TestCollectionNoPostProcessReplacedPaths(CollectionTestCase):
    run_collectstatic_in_setUp = False

    def test_collectstatistic_no_post_process_replaced_paths(self):
        """
        Tests the collectstatic functionality to ensure post-processing is correctly replaced with the expected paths.

        This test case verifies that during the collection of static files, the post-processing step is correctly handled and the expected paths are used instead, with the test passing if the phrase 'post-processed' is found in the standard output.

        The purpose of this test is to ensure the integrity and correctness of the static file collection process, particularly in scenarios where post-processing is involved, by checking for the presence of specific indicators in the output, thus validating the overall flow of the collectstatic operation.
        """
        stdout = StringIO()
        self.run_collectstatic(verbosity=1, stdout=stdout)
        self.assertIn("post-processed", stdout.getvalue())


@override_settings(
    STORAGES={
        **settings.STORAGES,
        STATICFILES_STORAGE_ALIAS: {
            "BACKEND": "staticfiles_tests.storage.SimpleStorage",
        },
    }
)
class TestCollectionSimpleStorage(CollectionTestCase):
    hashed_file_path = hashed_file_path

    def setUp(self):
        storage.staticfiles_storage.hashed_files.clear()  # avoid cache interference
        super().setUp()

    def test_template_tag_return(self):
        """

        Tests the functionality of a template tag related to static file handling.

        This function checks various scenarios to ensure the template tag behaves as expected.
        It verifies that the tag correctly handles cases where a file does not exist, 
        and that it properly renders files with and without cache busting versions.
        Additionally, it checks that the tag handles files in different paths, 
        including those with query parameters.

        The function raises an assertion error if any of the test cases fail.

        """
        self.assertStaticRaises(
            ValueError, "does/not/exist.png", "/static/does/not/exist.png"
        )
        self.assertStaticRenders("test/file.txt", "/static/test/file.deploy12345.txt")
        self.assertStaticRenders(
            "cached/styles.css", "/static/cached/styles.deploy12345.css"
        )
        self.assertStaticRenders("path/", "/static/path/")
        self.assertStaticRenders("path/?query", "/static/path/?query")

    def test_template_tag_simple_content(self):
        """

        Tests the rendering of a template tag with simple content.

        Verifies that the template tag correctly generates a relative path for a hashed file,
        and that the file's content is correctly replaced with the hashed version of the referenced files.

        """
        relpath = self.hashed_file_path("cached/styles.css")
        self.assertEqual(relpath, "cached/styles.deploy12345.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertNotIn(b"cached/other.css", content)
            self.assertIn(b"other.deploy12345.css", content)


class JSModuleImportAggregationManifestStorage(storage.ManifestStaticFilesStorage):
    support_js_module_import_aggregation = True


@override_settings(
    STORAGES={
        **settings.STORAGES,
        STATICFILES_STORAGE_ALIAS: {
            "BACKEND": (
                "staticfiles_tests.test_storage."
                "JSModuleImportAggregationManifestStorage"
            ),
        },
    }
)
class TestCollectionJSModuleImportAggregationManifestStorage(CollectionTestCase):
    hashed_file_path = hashed_file_path

    def test_module_import(self):
        """

        Tests the import statements in a module file after it has been processed and saved to storage.

        The test verifies that various types of import statements are correctly included in the module file.
        These include default imports, relative imports, named imports, absolute imports, dynamic imports, 
        and namespace imports. The test also checks for correct aliasing of imported variables.

        The module file is identified by its hashed file path, and the test ensures that the expected import 
        statements are present in the file's contents.

        """
        relpath = self.hashed_file_path("cached/module.js")
        self.assertEqual(relpath, "cached/module.55fd6938fbc5.js")
        tests = [
            # Relative imports.
            b'import testConst from "./module_test.477bbebe77f0.js";',
            b'import relativeModule from "../nested/js/nested.866475c46bb4.js";',
            b'import { firstConst, secondConst } from "./module_test.477bbebe77f0.js";',
            # Absolute import.
            b'import rootConst from "/static/absolute_root.5586327fe78c.js";',
            # Dynamic import.
            b'const dynamicModule = import("./module_test.477bbebe77f0.js");',
            # Creating a module object.
            b'import * as NewModule from "./module_test.477bbebe77f0.js";',
            # Aliases.
            b'import { testConst as alias } from "./module_test.477bbebe77f0.js";',
            b"import {\n"
            b"    firstVar1 as firstVarAlias,\n"
            b"    $second_var_2 as secondVarAlias\n"
            b'} from "./module_test.477bbebe77f0.js";',
        ]
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            for module_import in tests:
                with self.subTest(module_import=module_import):
                    self.assertIn(module_import, content)

    def test_aggregating_modules(self):
        relpath = self.hashed_file_path("cached/module.js")
        self.assertEqual(relpath, "cached/module.55fd6938fbc5.js")
        tests = [
            b'export * from "./module_test.477bbebe77f0.js";',
            b'export { testConst } from "./module_test.477bbebe77f0.js";',
            b"export {\n"
            b"    firstVar as firstVarAlias,\n"
            b"    secondVar as secondVarAlias\n"
            b'} from "./module_test.477bbebe77f0.js";',
        ]
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            for module_import in tests:
                with self.subTest(module_import=module_import):
                    self.assertIn(module_import, content)


class CustomManifestStorage(storage.ManifestStaticFilesStorage):
    def __init__(self, *args, manifest_storage=None, **kwargs):
        """
        Initializes the object with the given arguments and keyword arguments, setting up a static files storage for manifests. 

        The `manifest_storage` parameter determines where manifests are stored, defaults to a static files storage if not provided. 
        The `manifest_location` keyword argument further configures this storage by specifying the location where manifests are stored.
        Other keyword arguments are forwarded to the superclass's initializer.
        """
        manifest_storage = storage.StaticFilesStorage(
            location=kwargs.pop("manifest_location"),
        )
        super().__init__(*args, manifest_storage=manifest_storage, **kwargs)


class TestCustomManifestStorage(SimpleTestCase):
    def setUp(self):
        manifest_path = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, manifest_path)

        self.staticfiles_storage = CustomManifestStorage(
            manifest_location=manifest_path,
        )
        self.manifest_file = manifest_path / self.staticfiles_storage.manifest_name
        # Manifest without paths.
        self.manifest = {"version": self.staticfiles_storage.manifest_version}
        with self.manifest_file.open("w") as manifest_file:
            json.dump(self.manifest, manifest_file)

    def test_read_manifest(self):
        self.assertEqual(
            self.staticfiles_storage.read_manifest(),
            json.dumps(self.manifest),
        )

    def test_read_manifest_nonexistent(self):
        """
        Tests the behavior of reading a manifest file when it does not exist.

        Verifies that the read_manifest method returns None when the expected manifest file is not found on the file system.
        """
        os.remove(self.manifest_file)
        self.assertIsNone(self.staticfiles_storage.read_manifest())

    def test_save_manifest_override(self):
        """

        Tests the saving of the manifest file with overridden content.

        This test checks that the manifest file exists before and after saving the manifest,
        and verifies that the saved manifest contains the expected 'paths' key and differs
        from the original manifest.

        """
        self.assertIs(self.manifest_file.exists(), True)
        self.staticfiles_storage.save_manifest()
        self.assertIs(self.manifest_file.exists(), True)
        new_manifest = json.loads(self.staticfiles_storage.read_manifest())
        self.assertIn("paths", new_manifest)
        self.assertNotEqual(new_manifest, self.manifest)

    def test_save_manifest_create(self):
        os.remove(self.manifest_file)
        self.staticfiles_storage.save_manifest()
        self.assertIs(self.manifest_file.exists(), True)
        new_manifest = json.loads(self.staticfiles_storage.read_manifest())
        self.assertIn("paths", new_manifest)
        self.assertNotEqual(new_manifest, self.manifest)


class CustomStaticFilesStorage(storage.StaticFilesStorage):
    """
    Used in TestStaticFilePermissions
    """

    def __init__(self, *args, **kwargs):
        kwargs["file_permissions_mode"] = 0o640
        kwargs["directory_permissions_mode"] = 0o740
        super().__init__(*args, **kwargs)


@unittest.skipIf(sys.platform == "win32", "Windows only partially supports chmod.")
class TestStaticFilePermissions(CollectionTestCase):
    command_params = {
        "interactive": False,
        "verbosity": 0,
        "ignore_patterns": ["*.ignoreme"],
    }

    def setUp(self):
        self.umask = 0o027
        old_umask = os.umask(self.umask)
        self.addCleanup(os.umask, old_umask)
        super().setUp()

    # Don't run collectstatic command in this test class.
    def run_collectstatic(self, **kwargs):
        pass

    @override_settings(
        FILE_UPLOAD_PERMISSIONS=0o655,
        FILE_UPLOAD_DIRECTORY_PERMISSIONS=0o765,
    )
    def test_collect_static_files_permissions(self):
        """

        Tests the file permissions of static files collected by the 'collectstatic' command.

        Verifies that the permissions of the static files match the settings defined in
        FILE_UPLOAD_PERMISSIONS, and the permissions of the directories containing these
        files match the settings defined in FILE_UPLOAD_DIRECTORY_PERMISSIONS.

        The test checks the permissions of a sample test file and multiple directories,
        including nested directories, to ensure they conform to the expected settings.

        """
        call_command("collectstatic", **self.command_params)
        static_root = Path(settings.STATIC_ROOT)
        test_file = static_root / "test.txt"
        file_mode = test_file.stat().st_mode & 0o777
        self.assertEqual(file_mode, 0o655)
        tests = [
            static_root / "subdir",
            static_root / "nested",
            static_root / "nested" / "css",
        ]
        for directory in tests:
            with self.subTest(directory=directory):
                dir_mode = directory.stat().st_mode & 0o777
                self.assertEqual(dir_mode, 0o765)

    @override_settings(
        FILE_UPLOAD_PERMISSIONS=None,
        FILE_UPLOAD_DIRECTORY_PERMISSIONS=None,
    )
    def test_collect_static_files_default_permissions(self):
        """
        Test the default file permissions set by the collectstatic command.

        This test checks the permissions of the files and directories created when running 
        the collectstatic management command with default settings. It verifies that the 
        permissions of the collected files and directories match the expected values, 
        taking into account the system's umask.

        The test covers both the top-level static directory and nested subdirectories, 
        ensuring that the permissions are correctly applied in all cases.

        Validation includes checking the permissions of a test file and multiple 
        subdirectories, confirming that the collectstatic command produces the expected 
        results without explicitly setting file or directory permissions.
        """
        call_command("collectstatic", **self.command_params)
        static_root = Path(settings.STATIC_ROOT)
        test_file = static_root / "test.txt"
        file_mode = test_file.stat().st_mode & 0o777
        self.assertEqual(file_mode, 0o666 & ~self.umask)
        tests = [
            static_root / "subdir",
            static_root / "nested",
            static_root / "nested" / "css",
        ]
        for directory in tests:
            with self.subTest(directory=directory):
                dir_mode = directory.stat().st_mode & 0o777
                self.assertEqual(dir_mode, 0o777 & ~self.umask)

    @override_settings(
        FILE_UPLOAD_PERMISSIONS=0o655,
        FILE_UPLOAD_DIRECTORY_PERMISSIONS=0o765,
        STORAGES={
            **settings.STORAGES,
            STATICFILES_STORAGE_ALIAS: {
                "BACKEND": "staticfiles_tests.test_storage.CustomStaticFilesStorage",
            },
        },
    )
    def test_collect_static_files_subclass_of_static_storage(self):
        call_command("collectstatic", **self.command_params)
        static_root = Path(settings.STATIC_ROOT)
        test_file = static_root / "test.txt"
        file_mode = test_file.stat().st_mode & 0o777
        self.assertEqual(file_mode, 0o640)
        tests = [
            static_root / "subdir",
            static_root / "nested",
            static_root / "nested" / "css",
        ]
        for directory in tests:
            with self.subTest(directory=directory):
                dir_mode = directory.stat().st_mode & 0o777
                self.assertEqual(dir_mode, 0o740)


@override_settings(
    STORAGES={
        **settings.STORAGES,
        STATICFILES_STORAGE_ALIAS: {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
        },
    }
)
class TestCollectionHashedFilesCache(CollectionTestCase):
    """
    Files referenced from CSS use the correct final hashed name regardless of
    the order in which the files are post-processed.
    """

    hashed_file_path = hashed_file_path

    def setUp(self):
        """
        Sets up the test environment by creating a temporary directory and a subdirectory named 'test' within it.

        The temporary directory is created using the tempfile module and its path is stored in the '_temp_dir' attribute. 
        A cleanup method is also registered to ensure that the temporary directory is removed after the test is completed, 
        regardless of the test outcome. 

        This method should be called at the beginning of each test to provide a clean and isolated environment for testing.
        """
        super().setUp()
        self._temp_dir = temp_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(temp_dir, "test"))
        self.addCleanup(shutil.rmtree, temp_dir)

    def _get_filename_path(self, filename):
        return os.path.join(self._temp_dir, "test", filename)

    def test_file_change_after_collectstatic(self):
        # Create initial static files.
        file_contents = (
            ("foo.png", "foo"),
            ("bar.css", 'url("foo.png")\nurl("xyz.png")'),
            ("xyz.png", "xyz"),
        )
        for filename, content in file_contents:
            with open(self._get_filename_path(filename), "w") as f:
                f.write(content)

        with self.modify_settings(STATICFILES_DIRS={"append": self._temp_dir}):
            finders.get_finder.cache_clear()
            err = StringIO()
            # First collectstatic run.
            call_command("collectstatic", interactive=False, verbosity=0, stderr=err)
            relpath = self.hashed_file_path("test/bar.css")
            with storage.staticfiles_storage.open(relpath) as relfile:
                content = relfile.read()
                self.assertIn(b"foo.acbd18db4cc2.png", content)
                self.assertIn(b"xyz.d16fb36f0911.png", content)

            # Change the contents of the png files.
            for filename in ("foo.png", "xyz.png"):
                with open(self._get_filename_path(filename), "w+b") as f:
                    f.write(b"new content of file to change its hash")

            # The hashes of the png files in the CSS file are updated after
            # a second collectstatic.
            call_command("collectstatic", interactive=False, verbosity=0, stderr=err)
            relpath = self.hashed_file_path("test/bar.css")
            with storage.staticfiles_storage.open(relpath) as relfile:
                content = relfile.read()
                self.assertIn(b"foo.57a5cb9ba68d.png", content)
                self.assertIn(b"xyz.57a5cb9ba68d.png", content)
