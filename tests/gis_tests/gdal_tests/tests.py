import unittest

from django.contrib.gis.gdal import GDAL_VERSION, gdal_full_version, gdal_version


class GDALTest(unittest.TestCase):
    def test_gdal_version(self):
        """

        Tests the version of the Geospatial Data Abstraction Library (GDAL) against the expected version.

        Verifies that the reported GDAL version matches the version specified in GDAL_VERSION, 
        or at least contains a version number (indicated by the presence of a '.') if GDAL_VERSION is not defined.

        """
        if GDAL_VERSION:
            self.assertEqual(gdal_version(), ("%s.%s.%s" % GDAL_VERSION).encode())
        else:
            self.assertIn(b".", gdal_version())

    def test_gdal_full_version(self):
        full_version = gdal_full_version()
        self.assertIn(gdal_version(), full_version)
        self.assertTrue(full_version.startswith(b"GDAL"))
