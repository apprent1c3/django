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

        Verifies the full version string of the Geospatial Data Abstraction Library (GDAL).

        This test checks if the full version string contains the GDAL version and 
        starts with the expected 'GDAL' prefix, ensuring that the version information 
        is correctly formatted and accessible.

        The test relies on the `gdal_full_version` and `gdal_version` functions to 
        retrieve the full and abbreviated version strings, respectively.

        """
        full_version = gdal_full_version()
        self.assertIn(gdal_version(), full_version)
        self.assertTrue(full_version.startswith(b"GDAL"))
