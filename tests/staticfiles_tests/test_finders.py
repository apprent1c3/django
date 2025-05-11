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
        Verifies that the finder can locate all expected items, comparing the discovered results to a predefined set of expected destinations.
        """
        src, dst = self.find_all
        found = self.finder.find(src, find_all=True)
        found = [os.path.normcase(f) for f in found]
        dst = [os.path.normcase(d) for d in dst]
        self.assertEqual(found, dst)

    def test_find_all_deprecated_param(self):
        """
        Tests finding all files using the deprecated 'all' parameter, verifying a warning is raised and the results are correct.
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
        Tests that the finder's find method raises a TypeError when given an unexpected keyword argument, 
        ensuring that deprecation warnings are also raised for removed 'all' and 'find_all' arguments in Django 6.1.
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
        Initializes the test environment, setting up a file system finder and test file paths for subsequent tests
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
        """
        Sets up the test environment by initializing the app directories finder and defining test file paths.
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

        Set up the test environment with a default storage finder.

        Initializes the storage finder with static files storage located at MEDIA_ROOT,
        and defines test file paths for finding individual and multiple media files.

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
        """
        Tests the caching behavior of the get_finder function, verifying that repeated lookups 
        for the same finder result in cache hits and that the cache size remains as expected.
        """
        finders.get_finder.cache_clear()
        for n in range(10):
            finders.get_finder("django.contrib.staticfiles.finders.FileSystemFinder")
        cache_info = finders.get_finder.cache_info()
        self.assertEqual(cache_info.hits, 9)
        self.assertEqual(cache_info.currsize, 1)

    def test_searched_locations(self):
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
        with self.assertWarnsMessage(RemovedInDjango61Warning, DEPRECATION_MSG):
            finders.find("spam", all=True)
            self.assertEqual(
                finders.searched_locations,
                [os.path.join(TEST_ROOT, "project", "documents")],
            )

    def test_searched_locations_conflicting_params(self):
        msg = "find() got multiple values for argument 'find_all'"
        with (
            self.assertWarnsMessage(RemovedInDjango61Warning, DEPRECATION_MSG),
            self.assertRaisesMessage(TypeError, msg),
        ):
            finders.find("spam", find_all=True, all=True)

    def test_searched_locations_unexpected_params(self):
        """
        Tests that the finders.find function raises a TypeError when unexpected keyword arguments are passed, ensuring deprecated function signatures are properly handled and raising correct warnings and errors.
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
