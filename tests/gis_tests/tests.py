import unittest

from django.core.exceptions import ImproperlyConfigured
from django.db import ProgrammingError
from django.db.backends.base.base import NO_DB_ALIAS

try:
    from django.contrib.gis.db.backends.postgis.operations import PostGISOperations

    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False


if HAS_POSTGRES:

    class FakeConnection:
        def __init__(self):
            self.settings_dict = {
                "NAME": "test",
            }

    class FakePostGISOperations(PostGISOperations):
        def __init__(self, version=None):
            """
            Initializes the object with an optional version parameter.

            The version can be specified to identify or track different states or configurations.
            A connection object is also created during initialization, allowing for further operations or interactions.
            If no version is provided, it defaults to None.

            :param version: Optional version identifier
            :raises: No exceptions are explicitly raised in this method
            :returns: None
            """
            self.version = version
            self.connection = FakeConnection()

        def _get_postgis_func(self, func):
            """

            Gets the version of the PostGIS library.

            This method retrieves the version of the PostGIS library, or raises an exception if it is not available.

            Parameters
            ----------
            func : str
                The name of the function to call. Currently, only 'postgis_lib_version' is supported.

            Returns
            -------
            str
                The version of the PostGIS library.

            Raises
            ------
            ProgrammingError
                If the library version is not available.
            NotImplementedError
                If an unsupported function is requested.

            """
            if func == "postgis_lib_version":
                if self.version is None:
                    raise ProgrammingError
                else:
                    return self.version
            elif func == "version":
                pass
            else:
                raise NotImplementedError("This function was not expected to be called")


@unittest.skipUnless(HAS_POSTGRES, "The psycopg driver is needed for these tests")
class TestPostGISVersionCheck(unittest.TestCase):
    """
    The PostGIS version check parses correctly the version numbers
    """

    def test_get_version(self):
        """
        #: 
            Tests the retrieval of the PostGIS library version.

            Verifies that the version number returned by the :meth:`postgis_lib_version` 
            method matches the expected version.

            :return: None
        """
        expect = "1.0.0"
        ops = FakePostGISOperations(expect)
        actual = ops.postgis_lib_version()
        self.assertEqual(expect, actual)

    def test_version_classic_tuple(self):
        expect = ("1.2.3", 1, 2, 3)
        ops = FakePostGISOperations(expect[0])
        actual = ops.postgis_version_tuple()
        self.assertEqual(expect, actual)

    def test_version_dev_tuple(self):
        expect = ("1.2.3dev", 1, 2, 3)
        ops = FakePostGISOperations(expect[0])
        actual = ops.postgis_version_tuple()
        self.assertEqual(expect, actual)

    def test_version_loose_tuple(self):
        """
        Test that the postgis_version_tuple method returns the expected version information.

        The postgis_version_tuple method is expected to return a tuple containing the PostGIS version string and its individual components.
        This test case verifies that the method behaves correctly by comparing its output with an expected result.
        """
        expect = ("1.2.3b1.dev0", 1, 2, 3)
        ops = FakePostGISOperations(expect[0])
        actual = ops.postgis_version_tuple()
        self.assertEqual(expect, actual)

    def test_valid_version_numbers(self):
        versions = [
            ("1.3.0", 1, 3, 0),
            ("2.1.1", 2, 1, 1),
            ("2.2.0dev", 2, 2, 0),
        ]

        for version in versions:
            with self.subTest(version=version):
                ops = FakePostGISOperations(version[0])
                actual = ops.spatial_version
                self.assertEqual(version[1:], actual)

    def test_no_version_number(self):
        """
        Tests that a ProperlyConfigured exception is raised when no spatial version number is provided.

        This test case checks the behavior of the PostGIS operations when no version number is
        configured. It verifies that the expected exception is raised, ensuring that the system
        handles this scenario correctly.

        Raises:
            ImproperlyConfigured: When no spatial version number is available.

        """
        ops = FakePostGISOperations()
        with self.assertRaises(ImproperlyConfigured):
            ops.spatial_version


@unittest.skipUnless(HAS_POSTGRES, "PostGIS-specific tests.")
class TestPostGISBackend(unittest.TestCase):
    def test_non_db_connection_classes(self):
        from django.contrib.gis.db.backends.postgis.base import DatabaseWrapper
        from django.db.backends.postgresql.features import DatabaseFeatures
        from django.db.backends.postgresql.introspection import DatabaseIntrospection
        from django.db.backends.postgresql.operations import DatabaseOperations

        wrapper = DatabaseWrapper(settings_dict={}, alias=NO_DB_ALIAS)
        # PostGIS-specific stuff is not initialized for non-db connections.
        self.assertIs(wrapper.features_class, DatabaseFeatures)
        self.assertIs(wrapper.ops_class, DatabaseOperations)
        self.assertIs(wrapper.introspection_class, DatabaseIntrospection)
