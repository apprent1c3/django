import unittest

from django.contrib.gis.gdal import GDAL_VERSION, gdal_full_version, gdal_version


class GDALTest(unittest.TestCase):
    def test_gdal_version(self):
        """
        Tests the version of the Geospatial Data Abstraction Library (GDAL) being used.

        The test checks if a valid GDAL version is available and, if so, verifies that the version
        matches the expected format. If no valid version is available, it checks that the version
        string contains at least one dot, indicating a potentially valid version number.

        This test helps ensure that the GDAL library is properly installed and configured,
        allowing the use of its geospatial data processing capabilities in the application.
        """
        if GDAL_VERSION:
            self.assertEqual(gdal_version(), ("%s.%s.%s" % GDAL_VERSION).encode())
        else:
            self.assertIn(b".", gdal_version())

    def test_gdal_full_version(self):
        """
        Tests that the full GDAL version string is correctly formatted and contains the expected version information.

        The full version string is verified to start with 'GDAL' and contain the version reported by gdal_version, ensuring consistency and accuracy in version reporting.

        This test helps to validate the integrity of the GDAL installation and configuration, providing assurance that version information is correctly retrieved and formatted.
        """
        full_version = gdal_full_version()
        self.assertIn(gdal_version(), full_version)
        self.assertTrue(full_version.startswith(b"GDAL"))
