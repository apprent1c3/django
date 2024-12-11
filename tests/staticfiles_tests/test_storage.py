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
    взаимODEction
    Hashed File Path
    ----------------

    This function generates a hashed version of a given file path by applying a template rendering process.

    The function takes two parameters, `test` and `path`, and returns the resulting hashed file path as a string. The hashing process involves rendering the provided `path` using a template snippet, and then removing a specified static URL prefix from the result.

    The hashed file path can be used in scenarios where a unique, versioned reference to a file is required, such as in web applications where static files need to be updated without affecting the overall application functionality.
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
        """
        Tests that a file path with a query string is correctly hashed and stored.

        The function verifies that the query string is preserved in the hashed file path, 
        and checks that the resulting file contents are as expected. Specifically, it 
        ensures that the contents do not include a reference to an unrelated cached file, 
        and do include a reference to another file that has been correctly hashed. 

        Finally, it checks that any necessary post-conditions have been met after 
        the storage operation is complete.
        """
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

        Tests the functionality of a template tag when used with relative file paths.

        Verifies that the template tag correctly resolves relative paths in CSS files,
        replacing them with hashed versions of the files. Specifically, it checks that:

        * Relative CSS imports are rewritten to use hashed versions of the imported files.
        * Relative image URLs are rewritten to use hashed versions of the image files.
        * The resulting CSS file does not contain any references to unhashed files.

        Ensures that the post-condition of the test is met, indicating that the test has
        not introduced any unintended side effects.

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
        Tests the rendering of a template tag with deep relative URLs.

        Verifies that a static CSS file is correctly generated with hashed filenames,
        and that the file contains the expected relative URLs to other static assets.
        The test checks for the absence of non-hashed URLs and the presence of hashed
        URLs, ensuring that the template tag correctly resolves and generates relative
        paths for static files.

        Ensures that the post-condition of the test is met after verifying the template
        tag's behavior.

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
        Tests a template tag's ability to generate a URL for a static file by checking the following conditions:

         * The generated relative path to the static file has been correctly hashed.
         * The contents of the generated file contain an absolute URL, specifically one starting with 'https://'.

         Verifies the post condition after the test execution.
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
        """

        Checks that CSS imports are handled in a case-insensitive manner.

        This test verifies that the styles file is correctly hashed and stored,
        and that its contents are as expected. The test specifically checks 
        that the file imports another file with a hashed filename, 
        regardless of the original filename's case, and that the original 
        filename is not used in the import statement.

        The test covers the following scenarios:
        - The hashed filename of the styles file is correct.
        - The contents of the styles file do not include the original filename of the imported file.
        - The contents of the styles file include the hashed filename of the imported file.

        """
        relpath = self.hashed_file_path("cached/styles_insensitive.css")
        self.assertEqual(relpath, "cached/styles_insensitive.3fa427592a53.css")
        with storage.staticfiles_storage.open(relpath) as relfile:
            content = relfile.read()
            self.assertNotIn(b"cached/other.css", content)
            self.assertIn(b"other.d41d8cd98f00.css", content)
        self.assertPostCondition()

    def test_css_source_map(self):
        """
        Tests that the CSS source map is correctly generated and referenced.

        Verifies that the hashed file path for the source map CSS file is correctly generated,
        and that the contents of the file do not contain the original source map reference,
        but instead contain the correct hashed source map reference.

        Ensures that the test post condition is met after the test execution.
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
        Tests that CSS source maps are correctly handled when tabs are present.

        Verifies that the source mapping URL comment in the CSS file does not contain tabs
        and that the correct mapping file path is included. The test case also checks the 
        file path of the hashed CSS file. 

        The test ensures that the storage mechanism for static files is correctly 
        configuring source maps for CSS files and that the post-conditions for the test 
        are met after the source map has been processed.
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
        """
        Tests the CSS source map functionality with sensitivity to file names, verifying that the source mapping URL is correctly included in the generated CSS file and that the file name is properly hashed. The test checks for the presence of a specific source map comment and ensures that an incorrect comment is not present, confirming the integrity of the source map generation process.
        """
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
        Tests that the JavaScript source map file path is correctly generated and the trailing whitespace is removed.

        Verifies that the hashed file path for a given JavaScript file is as expected and that
        the source map URL in the resulting file does not contain trailing whitespace and
        has been correctly replaced with the hashed source map file path.

        Ensures the correct behavior of source map handling in the context of static file storage.
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
        """

        Tests the sensitivity of JavaScript source maps.

        Verifies that the correct source map file is generated and included in the JavaScript file,
        with the correct path and file name. The test checks for the presence of the expected
        source mapping URL in the file contents and ensures that an incorrect source mapping URL
        is not present.

        The test also validates that the post-condition is met after executing the test.

        """
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

        Tests the post-processing functionality when dealing with static files that contain non-UTF8 encoded characters.

        This test case simulates a scenario where a static file (nonutf8.css) contains non-UTF8 encoded characters.
        It verifies that a UnicodeDecodeError is raised when attempting to collect static files using the 'collectstatic' command.
        Additionally, it checks that the error message generated during post-processing is as expected.

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
        Sets up the test environment by clearing the static files cache.

        This method is called before each test to ensure a clean slate. It removes any
        hashed files from the static files storage, allowing tests to run independently
        without interference from previous test runs. It then calls the parent class's
        setUp method to perform any additional setup required by the testing framework.
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
        """
        Cleans up after a test by removing a temporary file and resetting a manifest setting.

        Resets the state of the test environment to ensure consistency across tests. This includes
        deleting a specific file if it exists and reverting a manifest strictness setting to its
        original value. The superclass's tear down method is also called to perform any additional
        necessary cleanup operations.
        """
        if os.path.exists(self._clear_filename):
            os.unlink(self._clear_filename)

        storage.staticfiles_storage.manifest_strict = self._manifest_strict
        super().tearDown()

    def assertPostCondition(self):
        hashed_files = storage.staticfiles_storage.hashed_files
        # The in-memory version of the manifest matches the one on disk
        # since a properly created manifest should cover all filenames.
        if hashed_files:
            manifest, _ = storage.staticfiles_storage.load_manifest()
            self.assertEqual(hashed_files, manifest)

    def test_manifest_exists(self):
        """
        Verifies the existence of the static files manifest.

        Checks if a manifest file, as determined by the static files storage backend,
        is present on the file system. The test ensures that the manifest file, which
        maps static file names to unique hashed versions, can be found at the expected
        location.

        Raises:
            AssertionError: If the manifest file does not exist.

        """
        filename = storage.staticfiles_storage.manifest_name
        path = storage.staticfiles_storage.path(filename)
        self.assertTrue(os.path.exists(path))

    def test_manifest_does_not_exist(self):
        storage.staticfiles_storage.manifest_name = "does.not.exist.json"
        self.assertIsNone(storage.staticfiles_storage.read_manifest())

    def test_manifest_does_not_ignore_permission_error(self):
        """
        Tests that reading the manifest file raises a PermissionError when the file cannot be opened due to a permissions issue.

        This test case ensures that the storage system properly propagates permission errors when attempting to read the manifest file, rather than ignoring or masking them.

        Args: None

        Raises: PermissionError if the manifest file cannot be opened due to a permissions issue

        Returns: None
        """
        with mock.patch("builtins.open", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                storage.staticfiles_storage.read_manifest()

    def test_loaded_cache(self):
        """
        Tests the integrity of the loaded cache by verifying that it is not empty and that the manifest file contains the expected manifest version.
        """
        self.assertNotEqual(storage.staticfiles_storage.hashed_files, {})
        manifest_content = storage.staticfiles_storage.read_manifest()
        self.assertIn(
            '"version": "%s"' % storage.staticfiles_storage.manifest_version,
            manifest_content,
        )

    def test_parse_cache(self):
        hashed_files = storage.staticfiles_storage.hashed_files
        manifest, _ = storage.staticfiles_storage.load_manifest()
        self.assertEqual(hashed_files, manifest)

    def test_clear_empties_manifest(self):
        """
        Tests that the collectstatic process correctly clears and empties the manifest when the clear option is enabled. Verifies that a file is properly added to the manifest and stored, then checks that the file and its reference are removed from the manifest and storage after clearing.
        """
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
        Tests that a protocol-relative URL is ignored during static file collection.

        This test case verifies that a protocol-relative URL (i.e., a URL starting with//
        without a protocol specified) within a static file is preserved and not modified
        during the static file collection process. The test checks that the collected file
        has the expected hashed filename and that its content remains unchanged, including
        the protocol-relative URL.

        The test utilizes Django's static file collection mechanism and uses a custom
        static file finder to locate the files. It also checks the resulting collected file
        for the expected content, ensuring that the protocol-relative URL is not modified
        during the collection process.
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

        Tests that the hashed_file_path method returns the expected relative path for a given file.

        This test case verifies that the hashed version of a file path is identical to the original path when the hash is not modified.

        The test is performed on a specific CSS file ('cached/styles.css') and ensures that the relative path returned by hashed_file_path matches the original file path.

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
        """
        Sets up the test environment by clearing the cached hashed files in the static files storage and then calls the superclass's setUp method to perform any additional setup tasks.
        """
        storage.staticfiles_storage.hashed_files.clear()  # avoid cache interference
        super().setUp()

    def test_template_tag_return(self):
        """
        Tests the functionality of the template tag for returning static content.

        This function checks the behavior of the template tag in various scenarios, 
        including when the requested file does not exist, and when the file does exist 
        with and without versioning. It also tests the handling of directories and queries.

        The test cases cover the following situations:
        - Raise an error when the requested file is not found.
        - Render the correct path for a non-versioned file.
        - Render the correct path for a versioned file.
        - Render the correct path for a directory.
        - Render the correct path for a file with a query string.

        These test cases ensure that the template tag behaves correctly in different 
        situations, providing a robust and reliable way to serve static content.
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
        Tests the rendering of a simple template tag.

        This function verifies that the template tag correctly generates a hashed file path 
        and that the file's content is updated accordingly. It checks that the hashed file path 
        is correctly formatted and that the file's content includes the expected hashed references 
        to other files, while excluding the non-hashed references.

        The test covers the basic functionality of the template tag, ensuring that it produces 
        the expected output without any unexpected inclusions or omissions. The test outcome 
        confirms whether the template tag behaves as expected in a simple scenario.
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
        """

        Tests the aggregation of modules in the caching process.

        Verifies that the relative path of a hashed file is correctly generated and 
        that the content of the cached file contains the expected module imports.

        The function checks for the presence of various import statements within the 
        cached file content, including default exports, named exports, and aliased exports.

        """
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
        Initializes the instance.

        This constructor takes variable arguments and keyword arguments. 
        It creates a StaticFilesStorage instance using the provided manifest_location 
        and uses it to call the superclass's constructor, effectively setting up the 
        manifest storage for the instance.

        :param manifest_location: The location to store manifests.
        :param args: Variable arguments to be passed to the superclass.
        :param kwargs: Keyword arguments to be passed to the superclass.

        """
        manifest_storage = storage.StaticFilesStorage(
            location=kwargs.pop("manifest_location"),
        )
        super().__init__(*args, manifest_storage=manifest_storage, **kwargs)


class TestCustomManifestStorage(SimpleTestCase):
    def setUp(self):
        """

        Setup method for creating a temporary environment for testing CustomManifestStorage.

        This method prepares a temporary directory to store manifest files, sets up a CustomManifestStorage instance with the temporary directory,
        and creates a basic manifest file with the current version number.

        The temporary directory is automatically removed after the test is completed.

        Attributes set by this method:
            - staticfiles_storage: An instance of CustomManifestStorage.
            - manifest_file: The path to the manifest file.
            - manifest: A dictionary representing the initial manifest data.

        """
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

        Tests the behavior of read_manifest when the manifest file does not exist.

        Verifies that the function returns None when the manifest file is missing,
        ensuring proper handling of this edge case.

        """
        os.remove(self.manifest_file)
        self.assertIsNone(self.staticfiles_storage.read_manifest())

    def test_save_manifest_override(self):
        """
        Tests that saving a manifest file using the static files storage correctly overrides the existing manifest.

        Verifies that the manifest file exists both before and after saving, and that the resulting manifest contains the expected 'paths' key and differs from the original manifest.

        Ensures that the save_manifest method updates the manifest file as expected, and that the changes are reflected in the file's contents.
        """
        self.assertIs(self.manifest_file.exists(), True)
        self.staticfiles_storage.save_manifest()
        self.assertIs(self.manifest_file.exists(), True)
        new_manifest = json.loads(self.staticfiles_storage.read_manifest())
        self.assertIn("paths", new_manifest)
        self.assertNotEqual(new_manifest, self.manifest)

    def test_save_manifest_create(self):
        """
        Tests the creation of a new manifest file through the save_manifest method.

        Verifies that the manifest file is generated, contains the required 'paths' key, 
        and has different contents than the original manifest.

        Ensures that the save_manifest method correctly creates a new manifest when the 
        existing one is removed, which is a crucial step in managing static files.

        """
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
        """
        Sets up the test environment by setting the umask to a specific value.

        This function configures the umask, which controls the default permissions for new files and directories,
        to a value of 23. It also saves the original umask value and schedules it to be restored after the test
        has completed, ensuring that the test environment is cleaned up properly.

        The parent class's setUp method is then called to perform any additional setup required by the test framework.

        """
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
        Tests the permissions of static files and directories after running the collectstatic command.

        Verifies that the collected static files have the correct file permissions and that the
        directories containing these files have the correct directory permissions. The test checks
        the permissions of the static root directory's contents, including subdirectories and files.

        The test verifies that:

        - The permissions of the static files match the value specified in FILE_UPLOAD_PERMISSIONS.
        - The permissions of the directories containing the static files match the value specified
          in FILE_UPLOAD_DIRECTORY_PERMISSIONS.

        This test ensures that the collectstatic command is correctly applying the specified
        permissions to the static files and directories, which is important for security and
        access control in a production environment.
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

        Tests the default permissions set on files and directories when collecting static files using the collectstatic command.

        This test verifies that the permissions of the collected files and directories are correctly applied, taking into account the system's umask setting.

        The test checks the permissions of a test file, as well as several directories and subdirectories within the static root directory, to ensure they match the expected values.

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
