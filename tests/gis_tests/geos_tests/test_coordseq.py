from django.contrib.gis.geos import LineString
from django.test import SimpleTestCase


class GEOSCoordSeqTest(SimpleTestCase):
    def test_getitem(self):
        """
        Tests the indexing functionality of the CoordinateSequence object.

        Verifies that the CoordinateSequence object returns the correct 
        coordinate at a specified index and raises an IndexError with a 
        meaningful message for invalid indices.

        Specifically, this test checks that the indexing is 0-based, 
        supports positive integers, and raises an IndexError for negative 
        indices less than -1 and non-negative indices greater than or 
        equal to the length of the coordinate sequence.
        """
        coord_seq = LineString([(x, x) for x in range(2)]).coord_seq
        for i in (0, 1):
            with self.subTest(i):
                self.assertEqual(coord_seq[i], (i, i))
        for i in (-3, 10):
            msg = "invalid GEOS Geometry index: %s" % i
            with self.subTest(i):
                with self.assertRaisesMessage(IndexError, msg):
                    coord_seq[i]
