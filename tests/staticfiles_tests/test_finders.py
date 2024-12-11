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
        src, dst = self.find_all
        found = self.finder.find(src, find_all=True)
        found = [os.path.normcase(f) for f in found]
        dst = [os.path.normcase(d) for d in dst]
        self.assertEqual(found, dst)

    def test_find_all_deprecated_param(self):
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

        Tests that the finder's find method raises a TypeError when unexpected keyword arguments are provided.

        The test checks that the find method correctly identifies and reports unexpected keyword arguments, including 
        when 'all' or 'find_all' are specified. This ensures that invalid usage of the find method results in a 
        meaningful error, helping to prevent bugs and improve code maintainability.

        A RemovedInDjango61Warning is also expected to be raised when using the 'all' keyword argument, as per the 
        deprecation policy.

        The test includes multiple scenarios to cover different invalid usage patterns, ensuring robust error handling 
        in the find method.

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
        Sets up the test environment by initializing the necessary storage finder and test data.

        This method is used to prepare the test setup, creating a DefaultStorageFinder instance with a StaticFilesStorage
        configured to use the MEDIA_ROOT location defined in the project settings. It also creates a test file path
        and assigns test data attributes, including a tuple representing a single file find and another tuple representing
        a collection of files to find, both referencing the 'media-file.txt' in the MEDIA_ROOT directory.

        The test data attributes set in this method can be used in tests to verify the functionality of file finding operations.
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
        """
        Tests that the get_finder function raises an ImportError when given a non-existent finder class name. 

        This test case ensures that the expected error is triggered when trying to retrieve a finder class that does not exist.
        """
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

        Test that the searched locations are correctly updated after invoking the finder.

        This test case verifies that upon searching for a specific item, the finder
        updates the list of searched locations accordingly. In this scenario, the
        finder is expected to search within a specific project directory and update
        the searched locations list with the corresponding path.

        The test assertion checks that the searched locations list contains the
        expected path after the finder has completed its search.

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

        Tests that the find method from the finders module correctly handles the deprecated all parameter.

        The test checks that using the all parameter raises a RemovedInDjango61Warning with the expected message.
        It also verifies that the search locations are correctly identified, specifically the 'documents' directory within the test project root.

        The purpose of this test is to ensure backwards compatibility and graceful deprecation of the all parameter.

        """
        with self.assertWarnsMessage(RemovedInDjango61Warning, DEPRECATION_MSG):
            finders.find("spam", all=True)
            self.assertEqual(
                finders.searched_locations,
                [os.path.join(TEST_ROOT, "project", "documents")],
            )

    def test_searched_locations_conflicting_params(self):
        """
        Tests that calling the find function with conflicting parameters 'find_all' and 'all' raises a TypeError and a RemovedInDjango61Warning.

         The conflicting parameters are 'find_all' and 'all' which shouldn't be used simultaneously. 
         The expected exception message for TypeError is 'find() got multiple values for argument 'find_all''. 
         The DEPRECATION_MSG is also expected to be raised as a RemovedInDjango61Warning.
        """
        msg = "find() got multiple values for argument 'find_all'"
        with (
            self.assertWarnsMessage(RemovedInDjango61Warning, DEPRECATION_MSG),
            self.assertRaisesMessage(TypeError, msg),
        ):
            finders.find("spam", find_all=True, all=True)

    def test_searched_locations_unexpected_params(self):
        """

        Tests that the find function raises a TypeError when unexpected keyword arguments are provided.

        This test case checks that the function behaves correctly when given unknown parameters,
        ensuring that it raises an exception with a suitable error message instead of silently ignoring them.
        It also verifies that this behavior is consistent across different combinations of valid and invalid arguments,
        including deprecated and removed parameters, and covers various scenarios to ensure robust functionality.

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
        """

        Test that an ImproperlyConfigured exception is raised when the DefaultStorageFinder 
        is instantiated without a valid location set.

        This test case checks that the storage backend of the staticfiles finder does not 
        allow an empty location. It verifies that a specific error message is displayed 
        when the location is not properly configured.

        """
        msg = (
            "The storage backend of the staticfiles finder "
            "<class 'django.contrib.staticfiles.finders.DefaultStorageFinder'> "
            "doesn't have a valid location."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            finders.DefaultStorageFinder()
