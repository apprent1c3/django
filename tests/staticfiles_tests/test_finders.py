import os

from django.conf import settings
from django.contrib.staticfiles import finders, storage
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from django.utils.deprecation import RemovedInDjango61Warning

from .cases import StaticFilesTestCase
from .settings import TEST_ROOT

DEPRECATION_MSG = (
    "Passing the `all` argument to find() is deprecated. Use `find_all` instead."
)


class TestFinders:
    """
    Base finder test mixin.

    On Windows, sometimes the case of the path we ask the finders for and the
    path(s) they find can differ. Compare them using os.path.normcase() to
    avoid false negatives.
    """

    def test_find_first(self):
        src, dst = self.find_first
        found = self.finder.find(src)
        self.assertEqual(os.path.normcase(found), os.path.normcase(dst))

    def test_find_all(self):
        """

        Tests the functionality of finding all occurrences.

        This test case verifies that the finder can locate all expected items.
        It compares the found results with the predefined expected results
        to ensure they match exactly, after normalizing the paths for consistency.

        """
        src, dst = self.find_all
        found = self.finder.find(src, find_all=True)
        found = [os.path.normcase(f) for f in found]
        dst = [os.path.normcase(d) for d in dst]
        self.assertEqual(found, dst)

    def test_find_all_deprecated_param(self):
        """

        Tests the finder's ability to locate all files or directories.

        This test case verifies that the finder can successfully retrieve all items,
        issuing a deprecation warning as expected in Django 6.1, and confirming that the
        found items match the destination items, with paths normalized for accurate comparison.

        """
        src, dst = self.find_all
        with self.assertWarnsMessage(RemovedInDjango61Warning, DEPRECATION_MSG):
            found = self.finder.find(src, all=True)
            found = [os.path.normcase(f) for f in found]
            dst = [os.path.normcase(d) for d in dst]
            self.assertEqual(found, dst)

    def test_find_all_conflicting_params(self):
        src, dst = self.find_all
        msg = (
            f"{self.finder.__class__.__qualname__}.find() got multiple values for "
            "argument 'find_all'"
        )
        with (
            self.assertWarnsMessage(RemovedInDjango61Warning, DEPRECATION_MSG),
            self.assertRaisesMessage(TypeError, msg),
        ):
            self.finder.find(src, find_all=True, all=True)

    def test_find_all_unexpected_params(self):
        """
        Tests that the find method of the finder object raises the correct exceptions when unexpected keyword arguments are passed.

        The test checks for three different combinations of keyword arguments to ensure that the method correctly handles unexpected parameters.

        :raises TypeError: If an unexpected keyword argument is provided.
        :raises RemovedInDjango61Warning: If a deprecated parameter is used.
        """
        src, dst = self.find_all
        msg = (
            f"{self.finder.__class__.__qualname__}.find() got an unexpected keyword "
            "argument 'wrong'"
        )
        with (
            self.assertWarnsMessage(RemovedInDjango61Warning, DEPRECATION_MSG),
            self.assertRaisesMessage(TypeError, msg),
        ):
            self.finder.find(src, all=True, wrong=1)

        with self.assertRaisesMessage(TypeError, msg):
            self.finder.find(src, find_all=True, wrong=1)

        with self.assertRaisesMessage(TypeError, msg):
            self.finder.find(src, wrong=1)


class TestFileSystemFinder(TestFinders, StaticFilesTestCase):
    """
    Test FileSystemFinder.
    """

    def setUp(self):
        super().setUp()
        self.finder = finders.FileSystemFinder()
        test_file_path = os.path.join(
            TEST_ROOT, "project", "documents", "test", "file.txt"
        )
        self.find_first = (os.path.join("test", "file.txt"), test_file_path)
        self.find_all = (os.path.join("test", "file.txt"), [test_file_path])


class TestAppDirectoriesFinder(TestFinders, StaticFilesTestCase):
    """
    Test AppDirectoriesFinder.
    """

    def setUp(self):
        """


        Sets up the test environment by initializing the finder and defining file paths for testing.

        This method is responsible for setting up the necessary components for the test case, including the AppDirectoriesFinder instance. It also defines two key file paths: find_first, which represents a single file path, and find_all, which represents a collection of file paths. These paths are used to test the finder's functionality in locating files.

        The file paths are constructed by joining the TEST_ROOT directory with 'apps', 'test', 'static', 'test', and 'file1.txt'. This ensures that the tests are run against a well-defined and consistent set of files.


        """
        super().setUp()
        self.finder = finders.AppDirectoriesFinder()
        test_file_path = os.path.join(
            TEST_ROOT, "apps", "test", "static", "test", "file1.txt"
        )
        self.find_first = (os.path.join("test", "file1.txt"), test_file_path)
        self.find_all = (os.path.join("test", "file1.txt"), [test_file_path])


class TestDefaultStorageFinder(TestFinders, StaticFilesTestCase):
    """
    Test DefaultStorageFinder.
    """

    def setUp(self):
        """
        Sets up the testing environment with a DefaultStorageFinder instance.

        This method initializes the base setup and then configures a finder to locate static files in the project's media root.
        It defines test file paths and finder results for use in subsequent tests, specifically a single file finding and multiple file findings.
        The finder is crucial for the tests to successfully locate and manipulate files, ensuring the accuracy of the test results.
        The setups performed here are essential for the proper execution of tests that depend on file finding and storage functionality.
        """
        super().setUp()
        self.finder = finders.DefaultStorageFinder(
            storage=storage.StaticFilesStorage(location=settings.MEDIA_ROOT)
        )
        test_file_path = os.path.join(settings.MEDIA_ROOT, "media-file.txt")
        self.find_first = ("media-file.txt", test_file_path)
        self.find_all = ("media-file.txt", [test_file_path])


@override_settings(
    STATICFILES_FINDERS=["django.contrib.staticfiles.finders.FileSystemFinder"],
    STATICFILES_DIRS=[os.path.join(TEST_ROOT, "project", "documents")],
)
class TestMiscFinder(SimpleTestCase):
    """
    A few misc finder tests.
    """

    def test_get_finder(self):
        self.assertIsInstance(
            finders.get_finder("django.contrib.staticfiles.finders.FileSystemFinder"),
            finders.FileSystemFinder,
        )

    def test_get_finder_bad_classname(self):
        with self.assertRaises(ImportError):
            finders.get_finder("django.contrib.staticfiles.finders.FooBarFinder")

    def test_get_finder_bad_module(self):
        """
        Tests that an ImportError is raised when attempting to retrieve a finder with a bad module name.

        Verifies that the finders.get_finder function handles invalid module names correctly by checking for an ImportError exception. This ensures that the function behaves as expected when encountering non-existent or improperly formatted module names.
        """
        with self.assertRaises(ImportError):
            finders.get_finder("foo.bar.FooBarFinder")

    def test_cache(self):
        finders.get_finder.cache_clear()
        for n in range(10):
            finders.get_finder("django.contrib.staticfiles.finders.FileSystemFinder")
        cache_info = finders.get_finder.cache_info()
        self.assertEqual(cache_info.hits, 9)
        self.assertEqual(cache_info.currsize, 1)

    def test_searched_locations(self):
        """
        Tests the locations searched by the finders module.

        Checks that the searched locations are correctly updated after a search
        is performed, verifying that the expected project directory is included
        in the list of searched locations.

        The test case specifically asserts that searching for 'spam' results
        in the 'documents' subdirectory of the test project root being searched.
        """
        finders.find("spam")
        self.assertEqual(
            finders.searched_locations,
            [os.path.join(TEST_ROOT, "project", "documents")],
        )

    def test_searched_locations_find_all(self):
        finders.find("spam", find_all=True)
        self.assertEqual(
            finders.searched_locations,
            [os.path.join(TEST_ROOT, "project", "documents")],
        )

    def test_searched_locations_deprecated_all(self):
        """
        Test that the find function with the all parameter raises a deprecation warning and searches in the correct location.

        The function checks that the find function, which is being deprecated, still behaves as expected when the all parameter is set to True. 
        It verifies that a warning is raised with the correct deprecation message and that the searched locations are limited to the project documents directory.
        """
        with self.assertWarnsMessage(RemovedInDjango61Warning, DEPRECATION_MSG):
            finders.find("spam", all=True)
            self.assertEqual(
                finders.searched_locations,
                [os.path.join(TEST_ROOT, "project", "documents")],
            )

    def test_searched_locations_conflicting_params(self):
        """
        Tests that the find() function correctly raises a TypeError when conflicting parameters are provided.

        Verifies that passing both 'find_all' and 'all' parameters results in a TypeError with a message indicating multiple values for the 'find_all' argument, and also triggers a RemovedInDjango61Warning with a deprecation message.

        This test ensures the function handles conflicting input parameters as expected and provides informative error messages for deprecated usage.
        """
        msg = "find() got multiple values for argument 'find_all'"
        with (
            self.assertWarnsMessage(RemovedInDjango61Warning, DEPRECATION_MSG),
            self.assertRaisesMessage(TypeError, msg),
        ):
            finders.find("spam", find_all=True, all=True)

    def test_searched_locations_unexpected_params(self):
        msg = "find() got an unexpected keyword argument 'wrong'"
        with (
            self.assertWarnsMessage(RemovedInDjango61Warning, DEPRECATION_MSG),
            self.assertRaisesMessage(TypeError, msg),
        ):
            finders.find("spam", all=True, wrong=1)

        with self.assertRaisesMessage(TypeError, msg):
            finders.find("spam", find_all=True, wrong=1)

        with self.assertRaisesMessage(TypeError, msg):
            finders.find("spam", wrong=1)

    @override_settings(MEDIA_ROOT="")
    def test_location_empty(self):
        """
        Tests that a DefaultStorageFinder raises an ImproperlyConfigured exception when the MEDIA_ROOT setting is empty, as the storage backend requires a valid location to function correctly.
        """
        msg = (
            "The storage backend of the staticfiles finder "
            "<class 'django.contrib.staticfiles.finders.DefaultStorageFinder'> "
            "doesn't have a valid location."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            finders.DefaultStorageFinder()
