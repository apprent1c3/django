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
        """
        Test the functionality of finding the first occurrence of a path.

        This test case verifies that the finder is able to correctly locate the first instance of a specified source path and match it with the expected destination path. The test checks for path equality by normalizing the case of both the found and expected paths to ensure accurate comparison across different operating systems.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the found path does not match the expected destination path.

        """
        src, dst = self.find_first
        found = self.finder.find(src)
        self.assertEqual(os.path.normcase(found), os.path.normcase(dst))

    def test_find_all(self):
        """
        Test to verify the functionality of finding all occurrences.

        This test case checks if the finder can successfully locate all 
        expected items and returns them in the correct order. The 
        test compares the found items with the expected destination 
        items after normalizing their path cases to ensure a 
        case-insensitive comparison. If the found items match the 
        expected items, the test passes; otherwise, it fails.
        """
        src, dst = self.find_all
        found = self.finder.find(src, find_all=True)
        found = [os.path.normcase(f) for f in found]
        dst = [os.path.normcase(d) for d in dst]
        self.assertEqual(found, dst)

    def test_find_all_deprecated_param(self):
        """
        Tests the finder's ability to locate all files when the deprecated 'all' parameter is used.

        This test case verifies that the finder correctly returns all expected files and 
        also raises the expected deprecation warning when the 'all' parameter is set to True.

        The test compares the found files with the expected results, ensuring their case is normalized 
        for accurate comparison.

        .. note:: This test is specifically designed to cover the deprecation of the 'all' parameter 
                  and is expected to be removed or updated when the deprecation is finalized.
        """
        src, dst = self.find_all
        with self.assertWarnsMessage(RemovedInDjango61Warning, DEPRECATION_MSG):
            found = self.finder.find(src, all=True)
            found = [os.path.normcase(f) for f in found]
            dst = [os.path.normcase(d) for d in dst]
            self.assertEqual(found, dst)

    def test_find_all_conflicting_params(self):
        """

        Tests that the find method raises a TypeError when multiple conflicting values are passed for the 'find_all' parameter.

        The test case checks for the deprecation warning and the expected error message when both 'find_all' and 'all' parameters are provided.

        """
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

        Tests that the find method of the finder object correctly raises a TypeError 
        when an unexpected keyword argument is provided.

        The test covers three scenarios, checking for an unexpected 'wrong' keyword 
        argument when 'all' is specified in different ways (as 'all', 'find_all', 
        or when neither 'all' nor 'find_all' are provided).

        Additionally, it ensures that the method also emits a RemovedInDjango61Warning 
        when 'all' is used, as expected for deprecated functionality.

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
        """

        Sets up the test environment by initializing the file system finder and defining test file paths.

        This method is responsible for preparing the necessary resources and variables for testing. It creates a file system finder instance and sets up paths for a test file, including a relative path and an absolute path.

        """
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

        Sets up the test environment for file finding operations.

        This method initializes the storage finder with a default storage instance
        pointing to the media root location. It also defines test file paths and 
        booking information for finding either the first occurrence or all occurrences 
        of a specific file ('media-file.txt') within the media root.

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

        Tests the search functionality of the finders module to retrieve locations where a searched item is found.

        This test case verifies that the searched_locations attribute of the finders module is updated correctly after a search operation.
        The test checks if the finders module successfully searches for the item 'spam' and records the correct location in the searched_locations list.

        Parameters: None
        Returns: None
        Raises: AssertionError if the searched_locations list does not match the expected location.

        """
        finders.find("spam")
        self.assertEqual(
            finders.searched_locations,
            [os.path.join(TEST_ROOT, "project", "documents")],
        )

    def test_searched_locations_find_all(self):
        """
        Tests that the searched locations are correctly identified when finding all occurrences.

        This test case verifies that the find_all functionality returns the expected 
        searched locations. It checks if the 'spam' string is found in the test project 
        documents directory and asserts that the searched_locations list contains the 
        correct path to this directory.
        """
        finders.find("spam", find_all=True)
        self.assertEqual(
            finders.searched_locations,
            [os.path.join(TEST_ROOT, "project", "documents")],
        )

    def test_searched_locations_deprecated_all(self):
        """
        Test that the 'find' function with 'all=True' emits a deprecation warning for removal in Django 6.1 and correctly updates the searched locations.
        """
        with self.assertWarnsMessage(RemovedInDjango61Warning, DEPRECATION_MSG):
            finders.find("spam", all=True)
            self.assertEqual(
                finders.searched_locations,
                [os.path.join(TEST_ROOT, "project", "documents")],
            )

    def test_searched_locations_conflicting_params(self):
        """

        Tests that the find() function raises a TypeError when both 'find_all' and 'all' parameters are provided.

        The purpose of this test is to ensure that the function behaves correctly when conflicting parameters are passed.
        It verifies that a RemovedInDjango61Warning is raised and a TypeError is raised with a message indicating that the function
        received multiple values for the 'find_all' argument.

        Args:
            None

        Returns:
            None

        Raises:
            TypeError: If both 'find_all' and 'all' parameters are provided to the find() function.
            RemovedInDjango61Warning: To notify about the deprecation.

        """
        msg = "find() got multiple values for argument 'find_all'"
        with (
            self.assertWarnsMessage(RemovedInDjango61Warning, DEPRECATION_MSG),
            self.assertRaisesMessage(TypeError, msg),
        ):
            finders.find("spam", find_all=True, all=True)

    def test_searched_locations_unexpected_params(self):
        """
        Tests that the find function raises a TypeError when provided with unexpected keyword arguments.

        The test case checks for the deprecation warning and TypeError with a specific message when using invalid parameters such as 'wrong' along with valid parameters like 'all' or 'find_all'.

        It ensures that the function behaves correctly and raises the expected errors when encountering unexpected parameters, helping prevent potential misuse and ensuring compatibility with future Django versions.
        """
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
        msg = (
            "The storage backend of the staticfiles finder "
            "<class 'django.contrib.staticfiles.finders.DefaultStorageFinder'> "
            "doesn't have a valid location."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            finders.DefaultStorageFinder()
