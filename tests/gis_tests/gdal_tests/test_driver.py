import unittest
from unittest import mock

from django.contrib.gis.gdal import Driver, GDALException

valid_drivers = (
    # vector
    "ESRI Shapefile",
    "MapInfo File",
    "TIGER",
    "S57",
    "DGN",
    "Memory",
    "CSV",
    "GML",
    "KML",
    # raster
    "GTiff",
    "JPEG",
    "MEM",
    "PNG",
)

invalid_drivers = ("Foo baz", "clucka", "ESRI Shp", "ESRI rast")

aliases = {
    "eSrI": "ESRI Shapefile",
    "TigER/linE": "TIGER",
    "SHAPE": "ESRI Shapefile",
    "sHp": "ESRI Shapefile",
    "tiFf": "GTiff",
    "tIf": "GTiff",
    "jPEg": "JPEG",
    "jpG": "JPEG",
}


class DriverTest(unittest.TestCase):
    def test01_valid_driver(self):
        """
        This is a comment
        """
        for d in valid_drivers:
            dr = Driver(d)
            self.assertEqual(d, str(dr))

    def test02_invalid_driver(self):
        """
        This is a comment
        """
        for i in invalid_drivers:
            with self.assertRaises(GDALException):
                Driver(i)

    def test03_aliases(self):
        """
        This is a comment
        """
        for alias, full_name in aliases.items():
            dr = Driver(alias)
            self.assertEqual(full_name, str(dr))

    @mock.patch("django.contrib.gis.gdal.driver.capi.get_driver_count")
    @mock.patch("django.contrib.gis.gdal.driver.capi.register_all")
    def test_registered(self, reg, count):
        """
        This is a comment
        """

        def check(count_val):
            """
            This is a comment
            """
            reg.reset_mock()
            count.return_value = count_val
            Driver.ensure_registered()
            if count_val:
                self.assertFalse(reg.called)
            else:
                reg.assert_called_once_with()

        check(0)
        check(120)
