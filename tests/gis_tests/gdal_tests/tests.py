import unittest

from django.contrib.gis.gdal import GDAL_VERSION, gdal_full_version, gdal_version


class GDALTest(unittest.TestCase):
    def test_gdal_version(self):
        if GDAL_VERSION:
            self.assertEqual(gdal_version(), ("%s.%s.%s" % GDAL_VERSION).encode())
        else:
            self.assertIn(b".", gdal_version())

    def test_gdal_full_version(self):
        """
        Tests that the full version string of the Geospatial Data Abstraction Library (GDAL) 
        contains the expected version information and prefix.

        This function verifies that the full version string, which includes detailed version 
        information, starts with the 'GDAL' prefix and contains the version number obtained 
        from :func:`gdal_version`. This ensures that the library version can be correctly 
        identified and verified within the application.

        Returns:
            None

        Raises:
            AssertionError: If the full version string does not contain the expected version 
            information or prefix.
        """
        full_version = gdal_full_version()
        self.assertIn(gdal_version(), full_version)
        self.assertTrue(full_version.startswith(b"GDAL"))
