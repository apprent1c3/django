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

            Initializes a new instance of the class.

            :param version: The version to be associated with the instance. Defaults to None if not provided.
            :ivar version: The version associated with the instance.
            :ivar connection: A fake connection object, initialized upon instance creation.

            This constructor sets up the basic attributes of the class, including the version and a fake connection.

            """
            self.version = version
            self.connection = FakeConnection()

        def _get_postgis_func(self, func):
            """

            Retrieve the PostGIS library information or version.

            This method returns information about the PostGIS library, specifically the version.
            It supports the following PostGIS functions:
                - postgis_lib_version: Returns the version of the PostGIS library.
                - version: Currently not implemented.

            Args:
                func (str): The name of the PostGIS function to retrieve information for.

            Returns:
                str: The version of the PostGIS library if the requested function is postgis_lib_version.

            Raises:
                ProgrammingError: If the PostGIS version is not available and the postgis_lib_version function is requested.
                NotImplementedError: If an unsupported function is requested.

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
        expect = "1.0.0"
        ops = FakePostGISOperations(expect)
        actual = ops.postgis_lib_version()
        self.assertEqual(expect, actual)

    def test_version_classic_tuple(self):
        """
        Test the postgis_version_tuple method of the FakePostGISOperations class.

        Verifies that the method correctly returns a tuple containing the PostGIS version
        as a string, followed by the major, minor, and micro version numbers.

        The test checks that the returned tuple matches the expected format and values,
        ensuring that the version information is correctly parsed and extracted.

        This test is used to validate the functionality of the postgis_version_tuple method
        in the context of the FakePostGISOperations class, ensuring it behaves as expected
        when working with the PostGIS version string.
        """
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
