import binascii

from django.contrib.gis.geos import (
    GEOSGeometry,
    Point,
    Polygon,
    WKBReader,
    WKBWriter,
    WKTReader,
    WKTWriter,
)
from django.contrib.gis.geos.libgeos import geos_version_tuple
from django.test import SimpleTestCase


class GEOSIOTest(SimpleTestCase):
    def test01_wktreader(self):
        # Creating a WKTReader instance
        """

        Reads WKT (Well-Known Text) strings and returns geometric objects.

        This function tests the WKT reader's functionality by:

        * Reading a WKT string as both a byte-encoded and regular string
        * Comparing the results to a reference geometric object to ensure accuracy
        * Verifying that the reader raises a TypeError when given invalid input types, such as integers and memory views

        The function ensures that the WKT reader can correctly interpret WKT strings and handle different input formats, while also validating its error handling capabilities.

        """
        wkt_r = WKTReader()
        wkt = "POINT (5 23)"

        # read() should return a GEOSGeometry
        ref = GEOSGeometry(wkt)
        g1 = wkt_r.read(wkt.encode())
        g2 = wkt_r.read(wkt)

        for geom in (g1, g2):
            self.assertEqual(ref, geom)

        # Should only accept string objects.
        with self.assertRaises(TypeError):
            wkt_r.read(1)
        with self.assertRaises(TypeError):
            wkt_r.read(memoryview(b"foo"))

    def test02_wktwriter(self):
        # Creating a WKTWriter instance, testing its ptr property.
        """

        Tests the WKTWriter class by verifying its functionality and error handling.

        The test case creates a WKTWriter object and checks that it correctly raises a TypeError
        when attempting to set an invalid pointer type. It then creates a reference GEOSGeometry object
        representing a point and its expected WKT representation. The test asserts that the WKTWriter
        correctly writes the GEOSGeometry object to a WKT string, matching the expected output.

        """
        wkt_w = WKTWriter()
        with self.assertRaises(TypeError):
            wkt_w.ptr = WKTReader.ptr_type()

        ref = GEOSGeometry("POINT (5 23)")
        ref_wkt = "POINT (5.0000000000000000 23.0000000000000000)"
        self.assertEqual(ref_wkt, wkt_w.write(ref).decode())

    def test_wktwriter_constructor_arguments(self):
        """

        Tests the constructor arguments of the WKTWriter class.

        Verifies that a WKTWriter instance can be created with custom settings and 
        used to write a GEOSGeometry object to a WKT string. The test checks for 
        correct dimension, trimming, and precision settings.

        The test is version-sensitive due to differences in the WKT output between 
        GEOS versions 3.10 and above, and those below 3.10.

        """
        wkt_w = WKTWriter(dim=3, trim=True, precision=3)
        ref = GEOSGeometry("POINT (5.34562 23 1.5)")
        if geos_version_tuple() > (3, 10):
            ref_wkt = "POINT Z (5.346 23 1.5)"
        else:
            ref_wkt = "POINT Z (5.35 23 1.5)"
        self.assertEqual(ref_wkt, wkt_w.write(ref).decode())

    def test03_wkbreader(self):
        # Creating a WKBReader instance
        wkb_r = WKBReader()

        hex_bin = b"000000000140140000000000004037000000000000"
        hex_str = "000000000140140000000000004037000000000000"
        wkb = memoryview(binascii.a2b_hex(hex_bin))
        ref = GEOSGeometry(hex_bin)

        # read() should return a GEOSGeometry on either a hex string or
        # a WKB buffer.
        g1 = wkb_r.read(wkb)
        g2 = wkb_r.read(hex_bin)
        g3 = wkb_r.read(hex_str)
        for geom in (g1, g2, g3):
            self.assertEqual(ref, geom)

        bad_input = (1, 5.23, None, False)
        for bad_wkb in bad_input:
            with self.assertRaises(TypeError):
                wkb_r.read(bad_wkb)

    def test04_wkbwriter(self):
        """

        Tests the functionality of the WKBWriter class.

        The WKBWriter class is responsible for writing GEOSGeometry objects to WKB (Well-Known Binary) format.
        This test case verifies that the class correctly writes geometry objects in both hex and binary formats,
        with different byte orders and output dimensions. It also checks for error handling when invalid byte
        orders or output dimensions are provided. Additionally, it tests the inclusion of SRID (Spatial Reference
        System Identifier) information in the WKB output.

        The test covers various scenarios, including writing 2D and 3D geometry objects, with and without SRID
        information, and validates the output against expected WKB hex and binary strings.

        """
        wkb_w = WKBWriter()

        # Representations of 'POINT (5 23)' in hex -- one normal and
        # the other with the byte order changed.
        g = GEOSGeometry("POINT (5 23)")
        hex1 = b"010100000000000000000014400000000000003740"
        wkb1 = memoryview(binascii.a2b_hex(hex1))
        hex2 = b"000000000140140000000000004037000000000000"
        wkb2 = memoryview(binascii.a2b_hex(hex2))

        self.assertEqual(hex1, wkb_w.write_hex(g))
        self.assertEqual(wkb1, wkb_w.write(g))

        # Ensuring bad byteorders are not accepted.
        for bad_byteorder in (-1, 2, 523, "foo", None):
            # Equivalent of `wkb_w.byteorder = bad_byteorder`
            with self.assertRaises(ValueError):
                wkb_w._set_byteorder(bad_byteorder)

        # Setting the byteorder to 0 (for Big Endian)
        wkb_w.byteorder = 0
        self.assertEqual(hex2, wkb_w.write_hex(g))
        self.assertEqual(wkb2, wkb_w.write(g))

        # Back to Little Endian
        wkb_w.byteorder = 1

        # Now, trying out the 3D and SRID flags.
        g = GEOSGeometry("POINT (5 23 17)")
        g.srid = 4326

        hex3d = b"0101000080000000000000144000000000000037400000000000003140"
        wkb3d = memoryview(binascii.a2b_hex(hex3d))
        hex3d_srid = (
            b"01010000A0E6100000000000000000144000000000000037400000000000003140"
        )
        wkb3d_srid = memoryview(binascii.a2b_hex(hex3d_srid))

        # Ensuring bad output dimensions are not accepted
        for bad_outdim in (-1, 0, 1, 4, 423, "foo", None):
            with self.assertRaisesMessage(
                ValueError, "WKB output dimension must be 2 or 3"
            ):
                wkb_w.outdim = bad_outdim

        # Now setting the output dimensions to be 3
        wkb_w.outdim = 3

        self.assertEqual(hex3d, wkb_w.write_hex(g))
        self.assertEqual(wkb3d, wkb_w.write(g))

        # Telling the WKBWriter to include the srid in the representation.
        wkb_w.srid = True
        self.assertEqual(hex3d_srid, wkb_w.write_hex(g))
        self.assertEqual(wkb3d_srid, wkb_w.write(g))

    def test_wkt_writer_trim(self):
        """
        Tests the WKT writer's ability to trim decimal coordinates.

        Verifies that the WKT writer can be configured to remove trailing zeros from decimal coordinates.
        When trimming is enabled, the writer removes trailing zeros from decimal coordinates, resulting in a more compact WKT representation.
        When trimming is disabled, the writer includes all decimal places, resulting in a more precise WKT representation.

        """
        wkt_w = WKTWriter()
        self.assertFalse(wkt_w.trim)
        self.assertEqual(
            wkt_w.write(Point(1, 1)), b"POINT (1.0000000000000000 1.0000000000000000)"
        )

        wkt_w.trim = True
        self.assertTrue(wkt_w.trim)
        self.assertEqual(wkt_w.write(Point(1, 1)), b"POINT (1 1)")
        self.assertEqual(wkt_w.write(Point(1.1, 1)), b"POINT (1.1 1)")
        self.assertEqual(
            wkt_w.write(Point(1.0 / 3, 1)), b"POINT (0.3333333333333333 1)"
        )

        wkt_w.trim = False
        self.assertFalse(wkt_w.trim)
        self.assertEqual(
            wkt_w.write(Point(1, 1)), b"POINT (1.0000000000000000 1.0000000000000000)"
        )

    def test_wkt_writer_precision(self):
        """

        Tests the WKTWriter class's ability to control the precision of WKT output.

        Verifies that the writer's precision can be set and used to round coordinate values 
        to the specified number of decimal places during WKT serialization. The test 
        covers cases where precision is not set, set to specific integer values, and reset 
        to its default value of None, which results in maximum precision. It also checks 
        that an appropriate error is raised when attempting to set the precision to an 
        invalid value.

        """
        wkt_w = WKTWriter()
        self.assertIsNone(wkt_w.precision)
        self.assertEqual(
            wkt_w.write(Point(1.0 / 3, 2.0 / 3)),
            b"POINT (0.3333333333333333 0.6666666666666666)",
        )

        wkt_w.precision = 1
        self.assertEqual(wkt_w.precision, 1)
        self.assertEqual(wkt_w.write(Point(1.0 / 3, 2.0 / 3)), b"POINT (0.3 0.7)")

        wkt_w.precision = 0
        self.assertEqual(wkt_w.precision, 0)
        self.assertEqual(wkt_w.write(Point(1.0 / 3, 2.0 / 3)), b"POINT (0 1)")

        wkt_w.precision = None
        self.assertIsNone(wkt_w.precision)
        self.assertEqual(
            wkt_w.write(Point(1.0 / 3, 2.0 / 3)),
            b"POINT (0.3333333333333333 0.6666666666666666)",
        )

        with self.assertRaisesMessage(
            AttributeError, "WKT output rounding precision must be "
        ):
            wkt_w.precision = "potato"

    def test_empty_point_wkb(self):
        """
        Tests the behavior of writing an empty point to Well-Known Binary (WKB) format.

        This function verifies that attempting to write an empty point to WKB raises a ValueError, 
        as empty points are not representable in this format. It also checks that when the SRID 
        is included, the WKB writer correctly handles the byte order, producing the expected 
        hexadecimal and binary representations. Additionally, it ensures that the resulting 
        WKB can be successfully parsed back into a GEOSGeometry object, confirming the 
        round-trip integrity of the conversion process.
        """
        p = Point(srid=4326)
        wkb_w = WKBWriter()

        wkb_w.srid = False
        with self.assertRaisesMessage(
            ValueError, "Empty point is not representable in WKB."
        ):
            wkb_w.write(p)
        with self.assertRaisesMessage(
            ValueError, "Empty point is not representable in WKB."
        ):
            wkb_w.write_hex(p)

        wkb_w.srid = True
        for byteorder, hex in enumerate(
            [
                b"0020000001000010E67FF80000000000007FF8000000000000",
                b"0101000020E6100000000000000000F87F000000000000F87F",
            ]
        ):
            wkb_w.byteorder = byteorder
            self.assertEqual(wkb_w.write_hex(p), hex)
            self.assertEqual(GEOSGeometry(wkb_w.write_hex(p)), p)
            self.assertEqual(wkb_w.write(p), memoryview(binascii.a2b_hex(hex)))
            self.assertEqual(GEOSGeometry(wkb_w.write(p)), p)

    def test_empty_polygon_wkb(self):
        """

        Tests writing of empty polygons as WKB.

        Verifies that an empty polygon can be successfully written in WKB format with and
        without SRID information, and that the resulting WKB can be correctly
        reconstituted into a GEOSGeometry object. The test checks both big-endian and
        little-endian byte orders, and compares the written WKB against expected hex
        values.

        The test covers writing the polygon as both a hexadecimal string and as a
        memoryview (binary) object, ensuring that both formats produce the correct
        results when read back into a GEOSGeometry object.

        """
        p = Polygon(srid=4326)
        p_no_srid = Polygon()
        wkb_w = WKBWriter()
        wkb_w.srid = True
        for byteorder, hexes in enumerate(
            [
                (b"000000000300000000", b"0020000003000010E600000000"),
                (b"010300000000000000", b"0103000020E610000000000000"),
            ]
        ):
            wkb_w.byteorder = byteorder
            for srid, hex in enumerate(hexes):
                wkb_w.srid = srid
                self.assertEqual(wkb_w.write_hex(p), hex)
                self.assertEqual(
                    GEOSGeometry(wkb_w.write_hex(p)), p if srid else p_no_srid
                )
                self.assertEqual(wkb_w.write(p), memoryview(binascii.a2b_hex(hex)))
                self.assertEqual(GEOSGeometry(wkb_w.write(p)), p if srid else p_no_srid)
