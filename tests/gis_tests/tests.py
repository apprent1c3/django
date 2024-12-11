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
            self.version = version
            self.connection = FakeConnection()

        def _get_postgis_func(self, func):
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
        Tests the postgis_version_tuple method of the PostGIS operations class to ensure it correctly parses the PostGIS version.

        The test verifies that the version is returned as a tuple containing the version string and major, minor, and micro version numbers.

        This test case specifically checks the version in the classic format, where the version string matches the major, minor, and micro version numbers.  

        Args: None

        Returns: None

        Raises: AssertionError if the expected and actual version tuples do not match.
        """
        expect = ("1.2.3", 1, 2, 3)
        ops = FakePostGISOperations(expect[0])
        actual = ops.postgis_version_tuple()
        self.assertEqual(expect, actual)

    def test_version_dev_tuple(self):
        """
        Tests the postgis_version_tuple function by comparing its output with an expected version tuple for a development version of PostGIS.

         The expected version is in the format (version_string, major, minor, micro), where version_string is a string representing the version, and major, minor, and micro are integers representing the major, minor, and micro version numbers respectively.

         This test ensures that the postgis_version_tuple function correctly parses the version string and returns the expected tuple.
        """
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
        """

        Tests that the spatial version is correctly extracted from valid PostGIS version numbers.

        The function checks a range of version numbers to ensure that the major, minor and micro versions are accurately parsed and returned.

        """
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
