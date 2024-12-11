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
        """
        Sets up the test environment by defining the path to a raster dataset and creating a GDALRaster object.

        This method initializes the raster dataset path to a specific file (raster.tif) located in the '../data/rasters/' directory
        relative to the current script. It then creates a GDALRaster object from this file, making it available for further processing.

        The raster dataset is used as a reference for subsequent tests, providing a consistent input for validation and verification purposes.

        :attribute rs_path: Path to the raster dataset file
        :attribute rs: GDALRaster object created from the raster dataset file
        """
        self.rs_path = os.path.join(
            os.path.dirname(__file__), "../data/rasters/raster.tif"
        )
        self.rs = GDALRaster(self.rs_path)

    def test_gdalraster_input_as_path(self):
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

        Verifies that the size of the render surface (rs) matches the expected dimensions.

        The function checks that the width of the rs is 163 pixels and the height is 174 pixels,
        ensuring that the render surface has been correctly initialized or configured.

        """
        self.assertEqual(self.rs.width, 163)
        self.assertEqual(self.rs.height, 174)

    def test_rs_srs(self):
        """
        Tests the Spatial Reference System (SRS) settings of the Raster Source (RS).

        Verifies that the SRS identifier (SRID) and unit of measurement are correctly set.

        Specifically, checks that the SRID is 3086 (indicating the use of a specific coordinate system) 
        and that the units of measurement are in meters.
        """
        self.assertEqual(self.rs.srs.srid, 3086)
        self.assertEqual(self.rs.srs.units, (1.0, "metre"))

    def test_rs_srid(self):
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
        """
        Tests the validation of geotransform inputs for a raster object, specifically checking for cases with incorrect or invalid input formats.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the geotransform input does not consist of exactly 6 numeric values.

        Notes
        -----
        This test case covers various error scenarios, including geotransform inputs with the wrong number of elements or containing non-numeric values. It verifies that the expected error message is raised in each of these scenarios.
        """
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
        Tests the bands of the RasterSource (RS) object.

        Verifies that the RS object contains exactly one band and checks that the band is an instance of GDALBand, ensuring compatibility with Geospatial Data Abstraction Library (GDAL) standards.
        """
        self.assertEqual(len(self.rs.bands), 1)
        self.assertIsInstance(self.rs.bands[0], GDALBand)

    def test_memory_based_raster_creation(self):
        # Create uint8 raster with full pixel data range (0-255)
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

        This test function verifies that a raster object can be successfully created from a temporary TIFF file.
        It checks that the spatial reference system (SRS), geotransform, and band data are correctly restored from the file.
        The test uses a temporary file to store the raster data and then reads the data back to compare it with the original raster.
        The comparison includes the SRS, geotransform, and band data, ensuring that the raster is accurately recreated from the file.
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
        """
        Tests the error handling of the GDALRaster class when attempting to read a non-existent raster file. Verifies that a GDALException is raised with a specific error message indicating the inability to read the specified input file.
        """
        msg = 'Unable to read raster source input "nonexistent.tif".'
        with self.assertRaisesMessage(GDALException, msg):
            GDALRaster("nonexistent.tif")

    def test_vsi_raster_creation(self):
        # Open a raster as a file object.
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
        """
        Tests that creating a VSI raster from an invalid buffer raises a GDALException.

        Verifies that an error message is correctly propagated when attempting to create a
        VSI raster from a buffer that does not contain valid raster data. The expected
        error message indicates that the buffer failed to be parsed as a raster.

        Raises:
            GDALException: If the buffer is not a valid raster.

        """
        msg = "Failed creating VSI raster from the input buffer."
        with self.assertRaisesMessage(GDALException, msg):
            GDALRaster(b"not-a-raster-buffer")

    def test_vsi_buffer_property(self):
        # Create a vsi-based raster from scratch.
        """
        Tests the property of a GDAL Raster object's VSI buffer.

        The test case creates a new GDAL Raster object with a small in-memory TIFF image,
        then checks that the raster's VSI buffer can be successfully read and written.
        It verifies that the data is correctly retrieved from the VSI buffer and that
        it matches the original data.

        Additionally, the test checks that the VSI buffer property of another raster
        object is correctly initialized as None, to ensure proper behavior in cases
        where no VSI buffer is set.

        This test ensures that the VSI buffer property of GDAL Raster objects functions
        correctly, providing a reliable way to access and manipulate raster data in memory.
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
        Tests the functionality of reading a raster file from a vsizip archive.

        This test creates a temporary zip file containing a raster file, then attempts 
        to read the raster file from the zip archive using the vsizip filesystem. The 
        test verifies that the raster file is read correctly and that its properties, 
        such as the driver name and path, are as expected. Additionally, it checks that 
        the raster file is identified as being vsi-based and that it does not have a 
        vsi buffer.

        The purpose of this test is to ensure that the vsizip filesystem is properly 
        supported and that raster files can be successfully read from zip archives.
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
        """

        Tests that the creation of a raster object correctly handles offset, size, and shape parameters.

        This test case verifies that when creating a raster with a single band, having a specific offset, size, and shape, 
        the resulting raster data is correctly populated and can be read back accurately. 

        The test checks the data value of the raster to ensure it matches the expected output, taking into account the 
        specified nodata value and the shape and offset of the data within the band. 

        It also handles the conversion of the result to a flattened list when the numpy library is available.

        """
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

        Tests that the nodata value is correctly set when creating a raster.

        This test case verifies that the specified nodata value is applied to all cells in the raster
        when it is created with a given set of parameters, including datatype, width, height, SRID, and band information.
        The test checks that the resulting raster data matches the expected nodata value for all cells.

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
        """
        Tests the metadata property of a raster object.

        This test case verifies that the metadata of a raster object can be accessed and modified correctly.
        It checks that the default metadata values are correctly set and updated, and that metadata values are
        properly propagated to the raster's bands. The test also ensures that metadata keys with None values are
        removed from the metadata dictionary.

        The test covers various scenarios, including setting and updating metadata at the raster and band levels,
        and checks that the expected metadata values are returned in each case.
        """
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

        Tests the raster information accessor to verify that it returns the expected metadata.

        The function checks that the returned information contains the correct driver, file path, size, origin, pixel size, and other key metadata.
        It also verifies that the information includes specific lines and patterns to ensure accuracy and completeness.
        Additionally, it checks for the presence of a specific spatial reference system (NAD83 / Florida GDL Albers) to ensure correct georeferencing.

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
        """

        Tests the :meth:`GDALRaster.warp` method for warping a raster.

        The test creates a sample raster with a specified data type, size, and spatial reference system,
        and then applies the warping method with different output parameters, such as scale, width, height, and data type.

        The test verifies that the resulting warped raster has the expected properties, including size, scale, data type, and name.
        It also checks the data values of the warped raster to ensure that the warping process is correct.

        Two test cases are covered:

        * Warping with a specified scale, width, and height, and verifying the resulting raster's properties and data values.
        * Warping with a specified file path and data type, and verifying the resulting raster's properties and data values.

        """
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

        Tests the raster warp operation with a no-data zone.

        The test creates a raster with a specified set of properties, including a no-data value, 
        and then applies a warp operation to it. The result is compared to an expected output 
        to ensure that the no-data value is correctly propagated to the target raster.

        This test case checks that the warp operation preserves the no-data value when the 
        source raster is warped to a new location, and that the resulting raster has the 
        correct no-data value in all cells.

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

        Test the clone method of a GDAL Raster object.

        This function creates a GDAL Raster object with different drivers (in-memory and file-based) 
        and tests that cloning the object produces a new, independent object with the same properties.
        The test checks that the cloned object has a different name, but shares the same spatial reference system,
        dimensions, origin, scale, and skew as the original object.

        The test also verifies that the cloned object is not the same object as the original, 
        but rather a new object that can be modified independently.

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
        """
        Tests the transformation of a raster from one spatial reference system to another.

        The test checks the correctness of the transformation by comparing the resulting
        raster's spatial reference system, dimensions, data type, origin, scale, and skew
        with the expected values. It also verifies that the data is correctly transformed
        and that the nodata value is preserved.

        The test uses different inputs to specify the target spatial reference system,
        including an integer code, a string representation, and a SpatialReference object.

        The test is performed using a temporary raster file with a known set of data and
        parameters, and the result is checked against a predefined set of expected values.


        """
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
        """

        Tests the cloning of a GDALRaster object when transforming its CRS.

        Verifies that the clone method is called once when the transform method is invoked,
        ensuring that the original raster remains unchanged and a new transformed raster is created.

        """
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

        Tests the data of a raster band to ensure its properties and values are correct.

        This test case verifies the following properties of the raster band:
            - Dimensions (width and height)
            - Description
            - Data type (as an integer and a string)
            - Color interpretation (as an integer and a string)
            - No data value

        Additionally, if the numpy library is available, it checks the actual data values in the band
        against a reference array loaded from a text file, ensuring that the data matches the expected values
        and has the correct shape.

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
        """
        Tests that setting the nodata value of a raster band in read mode raises an exception.

        This test case verifies that attempting to modify a raster band's nodata value when the raster is opened in read-only mode results in a GDALException being raised, as expected.

        :raises: GDALException when attempting to set the nodata value in read mode
        """
        rs = GDALRaster(self.rs_path, write=False)
        band = rs.bands[0]
        self.addCleanup(self._remove_aux_file)

        # Setting attributes in write mode raises exception in the _flush method
        with self.assertRaises(GDALException):
            setattr(band, "nodata_value", 10)

    def test_band_data_setters(self):
        # Create in-memory raster and get band
        """
        Tests the data setter functionality of a raster band.

        This test case checks the ability to set and retrieve data from a raster band using various data types, including raw bytes, numpy arrays, and Python lists. It tests the functionality of setting a single value, setting data for a band, and retrieving data from a band with and without specifying an offset and size.

        The test case covers the following scenarios:
        - Setting and retrieving the nodata value of a band
        - Setting and retrieving data for a band with and without using numpy
        - Setting and retrieving data for a band using different data types (raw bytes, numpy arrays, Python lists, bytearray, bytes, and memoryview)
        - Testing the data setter functionality with different data types and numpy arrays
        - Verifying the data setter functionality works correctly when using a JSON raster source

        The test case uses assertions to verify that the set and retrieved data match, and that the data is correctly stored and retrieved from the raster band.
        """
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

        Tests the automatic refresh of band statistics after modifying the band data.

        This test case validates that the statistics (minimum, maximum, mean, and standard deviation) of a band are correctly updated 
        when the band's data or nodata value is changed. It covers scenarios with default and custom nodata values.

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
        """
        Tests the statistics of an empty raster band.

        This test case verifies the behavior of the :meth:`.statistics` method when applied to a band with no valid data. The expected outcome is that the method should return a tuple of four :obj:`None` values, indicating that the minimum, maximum, mean, and standard deviation of the band are undefined due to the absence of data.
        """
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
