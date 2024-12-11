import os
import shutil
import struct
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

from django.contrib.gis.gdal import GDAL_VERSION, GDALRaster, SpatialReference
from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.gdal.raster.band import GDALBand
from django.contrib.gis.shortcuts import numpy
from django.core.files.temp import NamedTemporaryFile
from django.test import SimpleTestCase

from ..data.rasters.textrasters import JSON_RASTER


class GDALRasterTests(SimpleTestCase):
    """
    Test a GDALRaster instance created from a file (GeoTiff).
    """

    def setUp(self):
        self.rs_path = os.path.join(
            os.path.dirname(__file__), "../data/rasters/raster.tif"
        )
        self.rs = GDALRaster(self.rs_path)

    def test_gdalraster_input_as_path(self):
        """
        Tests that a GDALRaster object can be initialized from a file path.

        Verifies that the name attribute of the GDALRaster object matches the file path used to create it.

        Ensures correct functionality when working with raster data stored in files, by checking that the object accurately reflects the source file's location.

        Args: None

        Returns: None

        Raises: AssertionError if the name attribute does not match the file path used to create the GDALRaster object.
        """
        rs_path = Path(__file__).parent.parent / "data" / "rasters" / "raster.tif"
        rs = GDALRaster(rs_path)
        self.assertEqual(str(rs_path), rs.name)

    def test_rs_name_repr(self):
        self.assertEqual(self.rs_path, self.rs.name)
        self.assertRegex(repr(self.rs), r"<Raster object at 0x\w+>")

    def test_rs_driver(self):
        self.assertEqual(self.rs.driver.name, "GTiff")

    def test_rs_size(self):
        """
        Verifies the size of the raster (rs) object.

        Checks that the width and height of the rs object match the expected values.
        The test ensures that the rs object has been correctly initialized or updated with the correct dimensions.

        Expected dimensions:
            - Width: 163
            - Height: 174

        Raises an AssertionError if the dimensions do not match the expected values.
        """
        self.assertEqual(self.rs.width, 163)
        self.assertEqual(self.rs.height, 174)

    def test_rs_srs(self):
        """

        Tests the Spatial Reference System (SRS) of the RasterSource object.

        Verifies that the SRS has the expected Spatial Reference System Identifier (SRID) and units.

        """
        self.assertEqual(self.rs.srs.srid, 3086)
        self.assertEqual(self.rs.srs.units, (1.0, "metre"))

    def test_rs_srid(self):
        """
        Tests the Spatial Reference System Identifier (SRID) of a raster object.

        The function creates a GDAL raster object with a predefined width, height, and SRID, 
        then verifies that the SRID is correctly set and can be updated. This ensures that 
        the raster object's spatial reference system is properly handled.
        """
        rast = GDALRaster(
            {
                "width": 16,
                "height": 16,
                "srid": 4326,
            }
        )
        self.assertEqual(rast.srid, 4326)
        rast.srid = 3086
        self.assertEqual(rast.srid, 3086)

    def test_geotransform_and_friends(self):
        # Assert correct values for file based raster
        self.assertEqual(
            self.rs.geotransform,
            [511700.4680706557, 100.0, 0.0, 435103.3771231986, 0.0, -100.0],
        )
        self.assertEqual(self.rs.origin, [511700.4680706557, 435103.3771231986])
        self.assertEqual(self.rs.origin.x, 511700.4680706557)
        self.assertEqual(self.rs.origin.y, 435103.3771231986)
        self.assertEqual(self.rs.scale, [100.0, -100.0])
        self.assertEqual(self.rs.scale.x, 100.0)
        self.assertEqual(self.rs.scale.y, -100.0)
        self.assertEqual(self.rs.skew, [0, 0])
        self.assertEqual(self.rs.skew.x, 0)
        self.assertEqual(self.rs.skew.y, 0)
        # Create in-memory rasters and change gtvalues
        rsmem = GDALRaster(JSON_RASTER)
        # geotransform accepts both floats and ints
        rsmem.geotransform = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertEqual(rsmem.geotransform, [0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        rsmem.geotransform = range(6)
        self.assertEqual(rsmem.geotransform, [float(x) for x in range(6)])
        self.assertEqual(rsmem.origin, [0, 3])
        self.assertEqual(rsmem.origin.x, 0)
        self.assertEqual(rsmem.origin.y, 3)
        self.assertEqual(rsmem.scale, [1, 5])
        self.assertEqual(rsmem.scale.x, 1)
        self.assertEqual(rsmem.scale.y, 5)
        self.assertEqual(rsmem.skew, [2, 4])
        self.assertEqual(rsmem.skew.x, 2)
        self.assertEqual(rsmem.skew.y, 4)
        self.assertEqual(rsmem.width, 5)
        self.assertEqual(rsmem.height, 5)

    def test_geotransform_bad_inputs(self):
        rsmem = GDALRaster(JSON_RASTER)
        error_geotransforms = [
            [1, 2],
            [1, 2, 3, 4, 5, "foo"],
            [1, 2, 3, 4, 5, 6, "foo"],
        ]
        msg = "Geotransform must consist of 6 numeric values."
        for geotransform in error_geotransforms:
            with (
                self.subTest(i=geotransform),
                self.assertRaisesMessage(ValueError, msg),
            ):
                rsmem.geotransform = geotransform

    def test_rs_extent(self):
        self.assertEqual(
            self.rs.extent,
            (
                511700.4680706557,
                417703.3771231986,
                528000.4680706557,
                435103.3771231986,
            ),
        )

    def test_rs_bands(self):
        """

        Tests the number and type of bands in the raster source.

        Checks that the raster source contains exactly one band and verifies that the band is an instance of GDALBand, ensuring compatibility with the Geospatial Data Abstraction Library (GDAL) standards.

        """
        self.assertEqual(len(self.rs.bands), 1)
        self.assertIsInstance(self.rs.bands[0], GDALBand)

    def test_memory_based_raster_creation(self):
        # Create uint8 raster with full pixel data range (0-255)
        """

        Tests the creation of a memory-based raster.

        This test verifies that a raster object can be successfully created in memory
        and that its data can be correctly retrieved. The raster is created with a
        specific set of parameters, including a single band with a range of values from
        0 to 255, and a nodata value of 255. The test then checks that the retrieved
        data matches the expected values, ensuring that the raster creation process is
        working as expected.

        """
        rast = GDALRaster(
            {
                "datatype": 1,
                "width": 16,
                "height": 16,
                "srid": 4326,
                "bands": [
                    {
                        "data": range(256),
                        "nodata_value": 255,
                    }
                ],
            }
        )

        # Get array from raster
        result = rast.bands[0].data()
        if numpy:
            result = result.flatten().tolist()

        # Assert data is same as original input
        self.assertEqual(result, list(range(256)))

    def test_file_based_raster_creation(self):
        # Prepare tempfile
        """

        Tests the creation of a raster from a file.

        This test creates a temporary GeoTIFF file containing a single band of raster data,
        writes it to disk using the GDALRaster class, and then reads it back to verify that
        the data and spatial reference system (SRS) are correctly preserved.

        The test checks that the restored raster has the same spatial reference system,
        geotransform, and band data as the original raster.

        """
        rstfile = NamedTemporaryFile(suffix=".tif")

        # Create file-based raster from scratch
        GDALRaster(
            {
                "datatype": self.rs.bands[0].datatype(),
                "driver": "tif",
                "name": rstfile.name,
                "width": 163,
                "height": 174,
                "nr_of_bands": 1,
                "srid": self.rs.srs.wkt,
                "origin": (self.rs.origin.x, self.rs.origin.y),
                "scale": (self.rs.scale.x, self.rs.scale.y),
                "skew": (self.rs.skew.x, self.rs.skew.y),
                "bands": [
                    {
                        "data": self.rs.bands[0].data(),
                        "nodata_value": self.rs.bands[0].nodata_value,
                    }
                ],
            }
        )

        # Reload newly created raster from file
        restored_raster = GDALRaster(rstfile.name)
        # Presence of TOWGS84 depend on GDAL/Proj versions.
        self.assertEqual(
            restored_raster.srs.wkt.replace("TOWGS84[0,0,0,0,0,0,0],", ""),
            self.rs.srs.wkt.replace("TOWGS84[0,0,0,0,0,0,0],", ""),
        )
        self.assertEqual(restored_raster.geotransform, self.rs.geotransform)
        if numpy:
            numpy.testing.assert_equal(
                restored_raster.bands[0].data(), self.rs.bands[0].data()
            )
        else:
            self.assertEqual(restored_raster.bands[0].data(), self.rs.bands[0].data())

    def test_nonexistent_file(self):
        msg = 'Unable to read raster source input "nonexistent.tif".'
        with self.assertRaisesMessage(GDALException, msg):
            GDALRaster("nonexistent.tif")

    def test_vsi_raster_creation(self):
        # Open a raster as a file object.
        """
        Tests the creation of a VSI raster by comparing its data with a target raster.

            This test case reads the data from a raster file, creates a VSI raster from it,
            and then compares the data of the VSI raster with the data of a target raster.
            The test passes if the data of the two rasters are equal.

            The test utilizes the GDAL library to create the VSI raster and the numpy library
            to flatten the data for comparison. If numpy is available, the test flattens the
            data into a list before comparison; otherwise, it compares the data in its original form.

            Args:
                None

            Returns:
                None

            Raises:
                AssertionError: If the data of the VSI raster and the target raster do not match.

        """
        with open(self.rs_path, "rb") as dat:
            # Instantiate a raster from the file binary buffer.
            vsimem = GDALRaster(dat.read())
        # The data of the in-memory file is equal to the source file.
        result = vsimem.bands[0].data()
        target = self.rs.bands[0].data()
        if numpy:
            result = result.flatten().tolist()
            target = target.flatten().tolist()
        self.assertEqual(result, target)

    def test_vsi_raster_deletion(self):
        """

        Tests the deletion of a raster from /vsimem by creating a temporary raster,
        verifying its properties, deleting the raster, and then attempting to reopen
        it to confirm that it has been successfully removed.

        This test case covers the following scenarios:

        * Creating a new raster in /vsimem
        * Verifying the properties of the created raster
        * Deleting the raster
        * Verifying that the raster can no longer be opened after deletion

        """
        path = "/vsimem/raster.tif"
        # Create a vsi-based raster from scratch.
        vsimem = GDALRaster(
            {
                "name": path,
                "driver": "tif",
                "width": 4,
                "height": 4,
                "srid": 4326,
                "bands": [
                    {
                        "data": range(16),
                    }
                ],
            }
        )
        # The virtual file exists.
        rst = GDALRaster(path)
        self.assertEqual(rst.width, 4)
        # Delete GDALRaster.
        del vsimem
        del rst
        # The virtual file has been removed.
        msg = 'Could not open the datasource at "/vsimem/raster.tif"'
        with self.assertRaisesMessage(GDALException, msg):
            GDALRaster(path)

    def test_vsi_invalid_buffer_error(self):
        msg = "Failed creating VSI raster from the input buffer."
        with self.assertRaisesMessage(GDALException, msg):
            GDALRaster(b"not-a-raster-buffer")

    def test_vsi_buffer_property(self):
        # Create a vsi-based raster from scratch.
        """

        Tests the VSI buffer property of a GDALRaster object.

        This test case verifies that the VSI buffer property correctly returns the binary data of a raster object.
        It also checks that an empty VSI buffer is returned for a raster object that does not have a VSI buffer.

        The test creates a temporary in-memory raster object, retrieves its VSI buffer, and compares the resulting data with the original data.
        It ensures that the data is correctly retrieved and that an empty VSI buffer is returned when expected.

        The test is performed using the GDALRaster class and utilizes the numpy library for data manipulation, if available.

        """
        rast = GDALRaster(
            {
                "name": "/vsimem/raster.tif",
                "driver": "tif",
                "width": 4,
                "height": 4,
                "srid": 4326,
                "bands": [
                    {
                        "data": range(16),
                    }
                ],
            }
        )
        # Do a round trip from raster to buffer to raster.
        result = GDALRaster(rast.vsi_buffer).bands[0].data()
        if numpy:
            result = result.flatten().tolist()
        # Band data is equal to nodata value except on input block of ones.
        self.assertEqual(result, list(range(16)))
        # The vsi buffer is None for rasters that are not vsi based.
        self.assertIsNone(self.rs.vsi_buffer)

    def test_vsi_vsizip_filesystem(self):
        """
        Tests the handling of a VSI-based vsizip filesystem by creating a temporary zip file containing a raster TIFF image, then opening it through the VSI interface and verifying its properties, including the driver name, raster name, and the fact that it is VSI-based with no VSI buffer.
        """
        rst_zipfile = NamedTemporaryFile(suffix=".zip")
        with zipfile.ZipFile(rst_zipfile, mode="w") as zf:
            zf.write(self.rs_path, "raster.tif")
        rst_path = "/vsizip/" + os.path.join(rst_zipfile.name, "raster.tif")
        rst = GDALRaster(rst_path)
        self.assertEqual(rst.driver.name, self.rs.driver.name)
        self.assertEqual(rst.name, rst_path)
        self.assertIs(rst.is_vsi_based, True)
        self.assertIsNone(rst.vsi_buffer)

    def test_offset_size_and_shape_on_raster_creation(self):
        rast = GDALRaster(
            {
                "datatype": 1,
                "width": 4,
                "height": 4,
                "srid": 4326,
                "bands": [
                    {
                        "data": (1,),
                        "offset": (1, 1),
                        "size": (2, 2),
                        "shape": (1, 1),
                        "nodata_value": 2,
                    }
                ],
            }
        )
        # Get array from raster.
        result = rast.bands[0].data()
        if numpy:
            result = result.flatten().tolist()
        # Band data is equal to nodata value except on input block of ones.
        self.assertEqual(result, [2, 2, 2, 2, 2, 1, 1, 2, 2, 1, 1, 2, 2, 2, 2, 2])

    def test_set_nodata_value_on_raster_creation(self):
        # Create raster filled with nodata values.
        """

        Tests the setting of a no-data value when creating a GDAL raster.

        This function verifies that a raster is initialized correctly with a specified no-data value.
        It creates a sample raster with a defined no-data value and checks that the resulting raster data matches the expected no-data value.
        The test ensures that the no-data value is correctly applied to all pixels in the raster.

        """
        rast = GDALRaster(
            {
                "datatype": 1,
                "width": 2,
                "height": 2,
                "srid": 4326,
                "bands": [{"nodata_value": 23}],
            }
        )
        # Get array from raster.
        result = rast.bands[0].data()
        if numpy:
            result = result.flatten().tolist()
        # All band data is equal to nodata value.
        self.assertEqual(result, [23] * 4)

    def test_set_nodata_none_on_raster_creation(self):
        # Create raster without data and without nodata value.
        rast = GDALRaster(
            {
                "datatype": 1,
                "width": 2,
                "height": 2,
                "srid": 4326,
                "bands": [{"nodata_value": None}],
            }
        )
        # Get array from raster.
        result = rast.bands[0].data()
        if numpy:
            result = result.flatten().tolist()
        # Band data is equal to zero because no nodata value has been specified.
        self.assertEqual(result, [0] * 4)

    def test_raster_metadata_property(self):
        data = self.rs.metadata
        self.assertEqual(data["DEFAULT"], {"AREA_OR_POINT": "Area"})
        self.assertEqual(data["IMAGE_STRUCTURE"], {"INTERLEAVE": "BAND"})

        # Create file-based raster from scratch
        source = GDALRaster(
            {
                "datatype": 1,
                "width": 2,
                "height": 2,
                "srid": 4326,
                "bands": [{"data": range(4), "nodata_value": 99}],
            }
        )
        # Set metadata on raster and on a band.
        metadata = {
            "DEFAULT": {"OWNER": "Django", "VERSION": "1.0", "AREA_OR_POINT": "Point"},
        }
        source.metadata = metadata
        source.bands[0].metadata = metadata
        self.assertEqual(source.metadata["DEFAULT"], metadata["DEFAULT"])
        self.assertEqual(source.bands[0].metadata["DEFAULT"], metadata["DEFAULT"])
        # Update metadata on raster.
        metadata = {
            "DEFAULT": {"VERSION": "2.0"},
        }
        source.metadata = metadata
        self.assertEqual(source.metadata["DEFAULT"]["VERSION"], "2.0")
        # Remove metadata on raster.
        metadata = {
            "DEFAULT": {"OWNER": None},
        }
        source.metadata = metadata
        self.assertNotIn("OWNER", source.metadata["DEFAULT"])

    def test_raster_info_accessor(self):
        """
        Tests the raster info accessor to ensure it provides accurate and complete metadata.

        This test checks that the info attribute contains the expected lines, including
        the driver, file path, size, origin, and pixel size. It also verifies that the
        metadata, image structure metadata, and band information are as expected.

        Additionally, this test checks for specific lines containing the upper left, lower
        left, upper right, lower right, and center coordinates, as well as the spatial
        reference system (SRS) using regular expressions to account for formatting
        variations.

        The expected output includes lines indicating the area or point, interleave, band
        type, color interpretation, and no data value, as well as the SRS name, which
        should be 'NAD83 / Florida GDL Albers' in this case. The goal of this test is to
        ensure that the raster info accessor provides a reliable and comprehensive view
        of the underlying raster data.
        """
        infos = self.rs.info
        # Data
        info_lines = [line.strip() for line in infos.split("\n") if line.strip() != ""]
        for line in [
            "Driver: GTiff/GeoTIFF",
            "Files: {}".format(self.rs_path),
            "Size is 163, 174",
            "Origin = (511700.468070655711927,435103.377123198588379)",
            "Pixel Size = (100.000000000000000,-100.000000000000000)",
            "Metadata:",
            "AREA_OR_POINT=Area",
            "Image Structure Metadata:",
            "INTERLEAVE=BAND",
            "Band 1 Block=163x50 Type=Byte, ColorInterp=Gray",
            "NoData Value=15",
        ]:
            self.assertIn(line, info_lines)
        for line in [
            r"Upper Left  \(  511700.468,  435103.377\) "
            r'\( 82d51\'46.1\d"W, 27d55\' 1.5\d"N\)',
            r"Lower Left  \(  511700.468,  417703.377\) "
            r'\( 82d51\'52.0\d"W, 27d45\'37.5\d"N\)',
            r"Upper Right \(  528000.468,  435103.377\) "
            r'\( 82d41\'48.8\d"W, 27d54\'56.3\d"N\)',
            r"Lower Right \(  528000.468,  417703.377\) "
            r'\( 82d41\'55.5\d"W, 27d45\'32.2\d"N\)',
            r"Center      \(  519850.468,  426403.377\) "
            r'\( 82d46\'50.6\d"W, 27d50\'16.9\d"N\)',
        ]:
            self.assertRegex(infos, line)
        # CRS (skip the name because string depends on the GDAL/Proj versions).
        self.assertIn("NAD83 / Florida GDL Albers", infos)

    def test_compressed_file_based_raster_creation(self):
        rstfile = NamedTemporaryFile(suffix=".tif")
        # Make a compressed copy of an existing raster.
        compressed = self.rs.warp(
            {"papsz_options": {"compress": "packbits"}, "name": rstfile.name}
        )
        # Check physically if compression worked.
        self.assertLess(os.path.getsize(compressed.name), os.path.getsize(self.rs.name))
        # Create file-based raster with options from scratch.
        papsz_options = {
            "compress": "packbits",
            "blockxsize": 23,
            "blockysize": 23,
        }
        if GDAL_VERSION < (3, 7):
            datatype = 1
            papsz_options["pixeltype"] = "signedbyte"
        else:
            datatype = 14
        compressed = GDALRaster(
            {
                "datatype": datatype,
                "driver": "tif",
                "name": rstfile.name,
                "width": 40,
                "height": 40,
                "srid": 3086,
                "origin": (500000, 400000),
                "scale": (100, -100),
                "skew": (0, 0),
                "bands": [
                    {
                        "data": range(40 ^ 2),
                        "nodata_value": 255,
                    }
                ],
                "papsz_options": papsz_options,
            }
        )
        # Check if options used on creation are stored in metadata.
        # Reopening the raster ensures that all metadata has been written
        # to the file.
        compressed = GDALRaster(compressed.name)
        self.assertEqual(
            compressed.metadata["IMAGE_STRUCTURE"]["COMPRESSION"],
            "PACKBITS",
        )
        self.assertEqual(compressed.bands[0].datatype(), datatype)
        if GDAL_VERSION < (3, 7):
            self.assertEqual(
                compressed.bands[0].metadata["IMAGE_STRUCTURE"]["PIXELTYPE"],
                "SIGNEDBYTE",
            )
        self.assertIn("Block=40x23", compressed.info)

    def test_raster_warp(self):
        # Create in memory raster
        source = GDALRaster(
            {
                "datatype": 1,
                "driver": "MEM",
                "name": "sourceraster",
                "width": 4,
                "height": 4,
                "nr_of_bands": 1,
                "srid": 3086,
                "origin": (500000, 400000),
                "scale": (100, -100),
                "skew": (0, 0),
                "bands": [
                    {
                        "data": range(16),
                        "nodata_value": 255,
                    }
                ],
            }
        )

        # Test altering the scale, width, and height of a raster
        data = {
            "scale": [200, -200],
            "width": 2,
            "height": 2,
        }
        target = source.warp(data)
        self.assertEqual(target.width, data["width"])
        self.assertEqual(target.height, data["height"])
        self.assertEqual(target.scale, data["scale"])
        self.assertEqual(target.bands[0].datatype(), source.bands[0].datatype())
        self.assertEqual(target.name, "sourceraster_copy.MEM")
        result = target.bands[0].data()
        if numpy:
            result = result.flatten().tolist()
        self.assertEqual(result, [5, 7, 13, 15])

        # Test altering the name and datatype (to float)
        data = {
            "name": "/path/to/targetraster.tif",
            "datatype": 6,
        }
        target = source.warp(data)
        self.assertEqual(target.bands[0].datatype(), 6)
        self.assertEqual(target.name, "/path/to/targetraster.tif")
        self.assertEqual(target.driver.name, "MEM")
        result = target.bands[0].data()
        if numpy:
            result = result.flatten().tolist()
        self.assertEqual(
            result,
            [
                0.0,
                1.0,
                2.0,
                3.0,
                4.0,
                5.0,
                6.0,
                7.0,
                8.0,
                9.0,
                10.0,
                11.0,
                12.0,
                13.0,
                14.0,
                15.0,
            ],
        )

    def test_raster_warp_nodata_zone(self):
        # Create in memory raster.
        """

        Tests the warping of a raster with a nodata zone.

        This test creates a sample raster with a specified data type, size, spatial reference system,
        and nodata value, then warps it to a new origin. The resulting raster data is compared
        to the expected output, which should be filled with the nodata value due to the warp operation.

        The test verifies that the warping process correctly handles nodata zones and produces
        the expected output, which is a raster filled with the specified nodata value.

        """
        source = GDALRaster(
            {
                "datatype": 1,
                "driver": "MEM",
                "width": 4,
                "height": 4,
                "srid": 3086,
                "origin": (500000, 400000),
                "scale": (100, -100),
                "skew": (0, 0),
                "bands": [
                    {
                        "data": range(16),
                        "nodata_value": 23,
                    }
                ],
            }
        )
        # Warp raster onto a location that does not cover any pixels of the original.
        result = source.warp({"origin": (200000, 200000)}).bands[0].data()
        if numpy:
            result = result.flatten().tolist()
        # The result is an empty raster filled with the correct nodata value.
        self.assertEqual(result, [23] * 16)

    def test_raster_clone(self):
        """

        Test the ability to clone a raster object.

        This function creates test cases with different drivers and raster data, 
        then clones the raster and verifies that the cloned object has the same 
        metadata as the original, such as SRID, width, height, origin, scale, and skew.
        It also checks that the cloned object has a different name and is not the same object as the original.

        """
        rstfile = NamedTemporaryFile(suffix=".tif")
        tests = [
            ("MEM", "", 23),  # In memory raster.
            ("tif", rstfile.name, 99),  # In file based raster.
        ]
        for driver, name, nodata_value in tests:
            with self.subTest(driver=driver):
                source = GDALRaster(
                    {
                        "datatype": 1,
                        "driver": driver,
                        "name": name,
                        "width": 4,
                        "height": 4,
                        "srid": 3086,
                        "origin": (500000, 400000),
                        "scale": (100, -100),
                        "skew": (0, 0),
                        "bands": [
                            {
                                "data": range(16),
                                "nodata_value": nodata_value,
                            }
                        ],
                    }
                )
                clone = source.clone()
                self.assertNotEqual(clone.name, source.name)
                self.assertEqual(clone._write, source._write)
                self.assertEqual(clone.srs.srid, source.srs.srid)
                self.assertEqual(clone.width, source.width)
                self.assertEqual(clone.height, source.height)
                self.assertEqual(clone.origin, source.origin)
                self.assertEqual(clone.scale, source.scale)
                self.assertEqual(clone.skew, source.skew)
                self.assertIsNot(clone, source)

    def test_raster_transform(self):
        tests = [
            3086,
            "3086",
            SpatialReference(3086),
        ]
        for srs in tests:
            with self.subTest(srs=srs):
                # Prepare tempfile and nodata value.
                rstfile = NamedTemporaryFile(suffix=".tif")
                ndv = 99
                # Create in file based raster.
                source = GDALRaster(
                    {
                        "datatype": 1,
                        "driver": "tif",
                        "name": rstfile.name,
                        "width": 5,
                        "height": 5,
                        "nr_of_bands": 1,
                        "srid": 4326,
                        "origin": (-5, 5),
                        "scale": (2, -2),
                        "skew": (0, 0),
                        "bands": [
                            {
                                "data": range(25),
                                "nodata_value": ndv,
                            }
                        ],
                    }
                )

                target = source.transform(srs)

                # Reload data from disk.
                target = GDALRaster(target.name)
                self.assertEqual(target.srs.srid, 3086)
                self.assertEqual(target.width, 7)
                self.assertEqual(target.height, 7)
                self.assertEqual(target.bands[0].datatype(), source.bands[0].datatype())
                self.assertAlmostEqual(target.origin[0], 9124842.791079799, 3)
                self.assertAlmostEqual(target.origin[1], 1589911.6476407414, 3)
                self.assertAlmostEqual(target.scale[0], 223824.82664250192, 3)
                self.assertAlmostEqual(target.scale[1], -223824.82664250192, 3)
                self.assertEqual(target.skew, [0, 0])

                result = target.bands[0].data()
                if numpy:
                    result = result.flatten().tolist()
                # The reprojection of a raster that spans over a large area
                # skews the data matrix and might introduce nodata values.
                self.assertEqual(
                    result,
                    [
                        ndv,
                        ndv,
                        ndv,
                        ndv,
                        4,
                        ndv,
                        ndv,
                        ndv,
                        ndv,
                        2,
                        3,
                        9,
                        ndv,
                        ndv,
                        ndv,
                        1,
                        2,
                        8,
                        13,
                        19,
                        ndv,
                        0,
                        6,
                        6,
                        12,
                        18,
                        18,
                        24,
                        ndv,
                        10,
                        11,
                        16,
                        22,
                        23,
                        ndv,
                        ndv,
                        ndv,
                        15,
                        21,
                        22,
                        ndv,
                        ndv,
                        ndv,
                        ndv,
                        20,
                        ndv,
                        ndv,
                        ndv,
                        ndv,
                    ],
                )

    def test_raster_transform_clone(self):
        with mock.patch.object(GDALRaster, "clone") as mocked_clone:
            # Create in file based raster.
            rstfile = NamedTemporaryFile(suffix=".tif")
            source = GDALRaster(
                {
                    "datatype": 1,
                    "driver": "tif",
                    "name": rstfile.name,
                    "width": 5,
                    "height": 5,
                    "nr_of_bands": 1,
                    "srid": 4326,
                    "origin": (-5, 5),
                    "scale": (2, -2),
                    "skew": (0, 0),
                    "bands": [
                        {
                            "data": range(25),
                            "nodata_value": 99,
                        }
                    ],
                }
            )
            # transform() returns a clone because it is the same SRID and
            # driver.
            source.transform(4326)
            self.assertEqual(mocked_clone.call_count, 1)

    def test_raster_transform_clone_name(self):
        # Create in file based raster.
        """

        Translates the test for cloning a raster with a specific name post transformation.

        This function tests if a raster object can be transformed into the same projection (in this case, SRID 4326) 
        and saved with a specified name. The new name must include the specified name suffix. 

        The transformation is performed with a GDAL Raster object, and the test checks if the resulting 
        transformed raster object's name matches the specified clone name.

        Parameters: None

        Returns: None

        Raises: AssertionError if the transformed raster's name does not match the specified clone name.

        """
        rstfile = NamedTemporaryFile(suffix=".tif")
        source = GDALRaster(
            {
                "datatype": 1,
                "driver": "tif",
                "name": rstfile.name,
                "width": 5,
                "height": 5,
                "nr_of_bands": 1,
                "srid": 4326,
                "origin": (-5, 5),
                "scale": (2, -2),
                "skew": (0, 0),
                "bands": [
                    {
                        "data": range(25),
                        "nodata_value": 99,
                    }
                ],
            }
        )
        clone_name = rstfile.name + "_respect_name.GTiff"
        target = source.transform(4326, name=clone_name)
        self.assertEqual(target.name, clone_name)


class GDALBandTests(SimpleTestCase):
    rs_path = os.path.join(os.path.dirname(__file__), "../data/rasters/raster.tif")

    def test_band_data(self):
        """

        Test the properties and data of a raster band.

        This test case verifies that the band's width, height, description, data type,
        color interpretation, and no-data value match the expected values. If numpy is
        available, it also checks that the band's data matches a reference array loaded
        from a file and that the data shape corresponds to the band's dimensions.

        """
        rs = GDALRaster(self.rs_path)
        band = rs.bands[0]
        self.assertEqual(band.width, 163)
        self.assertEqual(band.height, 174)
        self.assertEqual(band.description, "")
        self.assertEqual(band.datatype(), 1)
        self.assertEqual(band.datatype(as_string=True), "GDT_Byte")
        self.assertEqual(band.color_interp(), 1)
        self.assertEqual(band.color_interp(as_string=True), "GCI_GrayIndex")
        self.assertEqual(band.nodata_value, 15)
        if numpy:
            data = band.data()
            assert_array = numpy.loadtxt(
                os.path.join(
                    os.path.dirname(__file__), "../data/rasters/raster.numpy.txt"
                )
            )
            numpy.testing.assert_equal(data, assert_array)
            self.assertEqual(data.shape, (band.height, band.width))

    def test_band_statistics(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            rs_path = os.path.join(tmp_dir, "raster.tif")
            shutil.copyfile(self.rs_path, rs_path)
            rs = GDALRaster(rs_path)
            band = rs.bands[0]
            pam_file = rs_path + ".aux.xml"
            smin, smax, smean, sstd = band.statistics(approximate=True)
            self.assertEqual(smin, 0)
            self.assertEqual(smax, 9)
            self.assertAlmostEqual(smean, 2.842331288343558)
            self.assertAlmostEqual(sstd, 2.3965567248965356)

            smin, smax, smean, sstd = band.statistics(approximate=False, refresh=True)
            self.assertEqual(smin, 0)
            self.assertEqual(smax, 9)
            self.assertAlmostEqual(smean, 2.828326634228898)
            self.assertAlmostEqual(sstd, 2.4260526986669095)

            self.assertEqual(band.min, 0)
            self.assertEqual(band.max, 9)
            self.assertAlmostEqual(band.mean, 2.828326634228898)
            self.assertAlmostEqual(band.std, 2.4260526986669095)

            # Statistics are persisted into PAM file on band close
            rs = band = None
            self.assertTrue(os.path.isfile(pam_file))

    def _remove_aux_file(self):
        pam_file = self.rs_path + ".aux.xml"
        if os.path.isfile(pam_file):
            os.remove(pam_file)

    def test_read_mode_error(self):
        # Open raster in read mode
        rs = GDALRaster(self.rs_path, write=False)
        band = rs.bands[0]
        self.addCleanup(self._remove_aux_file)

        # Setting attributes in write mode raises exception in the _flush method
        with self.assertRaises(GDALException):
            setattr(band, "nodata_value", 10)

    def test_band_data_setters(self):
        # Create in-memory raster and get band
        rsmem = GDALRaster(
            {
                "datatype": 1,
                "driver": "MEM",
                "name": "mem_rst",
                "width": 10,
                "height": 10,
                "nr_of_bands": 1,
                "srid": 4326,
            }
        )
        bandmem = rsmem.bands[0]

        # Set nodata value
        bandmem.nodata_value = 99
        self.assertEqual(bandmem.nodata_value, 99)

        # Set data for entire dataset
        bandmem.data(range(100))
        if numpy:
            numpy.testing.assert_equal(
                bandmem.data(), numpy.arange(100).reshape(10, 10)
            )
        else:
            self.assertEqual(bandmem.data(), list(range(100)))

        # Prepare data for setting values in subsequent tests
        block = list(range(100, 104))
        packed_block = struct.pack("<" + "B B B B", *block)

        # Set data from list
        bandmem.data(block, (1, 1), (2, 2))
        result = bandmem.data(offset=(1, 1), size=(2, 2))
        if numpy:
            numpy.testing.assert_equal(result, numpy.array(block).reshape(2, 2))
        else:
            self.assertEqual(result, block)

        # Set data from packed block
        bandmem.data(packed_block, (1, 1), (2, 2))
        result = bandmem.data(offset=(1, 1), size=(2, 2))
        if numpy:
            numpy.testing.assert_equal(result, numpy.array(block).reshape(2, 2))
        else:
            self.assertEqual(result, block)

        # Set data from bytes
        bandmem.data(bytes(packed_block), (1, 1), (2, 2))
        result = bandmem.data(offset=(1, 1), size=(2, 2))
        if numpy:
            numpy.testing.assert_equal(result, numpy.array(block).reshape(2, 2))
        else:
            self.assertEqual(result, block)

        # Set data from bytearray
        bandmem.data(bytearray(packed_block), (1, 1), (2, 2))
        result = bandmem.data(offset=(1, 1), size=(2, 2))
        if numpy:
            numpy.testing.assert_equal(result, numpy.array(block).reshape(2, 2))
        else:
            self.assertEqual(result, block)

        # Set data from memoryview
        bandmem.data(memoryview(packed_block), (1, 1), (2, 2))
        result = bandmem.data(offset=(1, 1), size=(2, 2))
        if numpy:
            numpy.testing.assert_equal(result, numpy.array(block).reshape(2, 2))
        else:
            self.assertEqual(result, block)

        # Set data from numpy array
        if numpy:
            bandmem.data(numpy.array(block, dtype="int8").reshape(2, 2), (1, 1), (2, 2))
            numpy.testing.assert_equal(
                bandmem.data(offset=(1, 1), size=(2, 2)),
                numpy.array(block).reshape(2, 2),
            )

        # Test json input data
        rsmemjson = GDALRaster(JSON_RASTER)
        bandmemjson = rsmemjson.bands[0]
        if numpy:
            numpy.testing.assert_equal(
                bandmemjson.data(), numpy.array(range(25)).reshape(5, 5)
            )
        else:
            self.assertEqual(bandmemjson.data(), list(range(25)))

    def test_band_statistics_automatic_refresh(self):
        """

        Tests the automatic refresh of band statistics in a GDALRaster object.

        This test case verifies that the statistics of a raster band are correctly updated when 
        the band's data or nodata value is changed. The band's statistics include the minimum, 
        maximum, mean, and standard deviation of the band's data.

        The test starts with a raster band containing all zeros and no nodata value, then updates 
        the data to include non-zero values and checks that the statistics are correctly updated. 
        Finally, it sets the nodata value to zero and verifies that the statistics are recalculated 
        without including the nodata value.

        The expected results are verified using assertions, ensuring that the band statistics are 
        accurate after each change.

        """
        rsmem = GDALRaster(
            {
                "srid": 4326,
                "width": 2,
                "height": 2,
                "bands": [{"data": [0] * 4, "nodata_value": 99}],
            }
        )
        band = rsmem.bands[0]
        # Populate statistics cache
        self.assertEqual(band.statistics(), (0, 0, 0, 0))
        # Change data
        band.data([1, 1, 0, 0])
        # Statistics are properly updated
        self.assertEqual(band.statistics(), (0.0, 1.0, 0.5, 0.5))
        # Change nodata_value
        band.nodata_value = 0
        # Statistics are properly updated
        self.assertEqual(band.statistics(), (1.0, 1.0, 1.0, 0.0))

    def test_band_statistics_empty_band(self):
        rsmem = GDALRaster(
            {
                "srid": 4326,
                "width": 1,
                "height": 1,
                "bands": [{"data": [0], "nodata_value": 0}],
            }
        )
        self.assertEqual(rsmem.bands[0].statistics(), (None, None, None, None))

    def test_band_delete_nodata(self):
        rsmem = GDALRaster(
            {
                "srid": 4326,
                "width": 1,
                "height": 1,
                "bands": [{"data": [0], "nodata_value": 1}],
            }
        )
        rsmem.bands[0].nodata_value = None
        self.assertIsNone(rsmem.bands[0].nodata_value)

    def test_band_data_replication(self):
        """

        Tests the replication of band data in a raster object.

        This function checks that the data in a raster band can be correctly replicated when
        accessed with different block sizes and buffer lengths. It uses a sample raster band
        with a 3x3 grid of data and tests various combinations of block sizes and buffer
        sizes to ensure that the data is correctly replicated.

        The test checks that the data in the band can be read back correctly after replication,
        either using NumPy arrays if available or as a list. The test covers different cases
        of data replication, including replication with varying block sizes and buffer lengths.

        """
        band = GDALRaster(
            {
                "srid": 4326,
                "width": 3,
                "height": 3,
                "bands": [{"data": range(10, 19), "nodata_value": 0}],
            }
        ).bands[0]

        # Variations for input (data, shape, expected result).
        combos = (
            ([1], (1, 1), [1] * 9),
            (range(3), (1, 3), [0, 0, 0, 1, 1, 1, 2, 2, 2]),
            (range(3), (3, 1), [0, 1, 2, 0, 1, 2, 0, 1, 2]),
        )
        for combo in combos:
            band.data(combo[0], shape=combo[1])
            if numpy:
                numpy.testing.assert_equal(
                    band.data(), numpy.array(combo[2]).reshape(3, 3)
                )
            else:
                self.assertEqual(band.data(), list(combo[2]))
