from django.contrib.gis.geos import LineString
from django.test import SimpleTestCase


class GEOSCoordSeqTest(SimpleTestCase):
    def test_getitem(self):
        """
        Tests the functionality of the __getitem__ method for coordinate sequences.

        This test checks that the method returns the correct coordinates for valid 
        indices and raises an IndexError with a descriptive message for invalid indices.

        The test covers both positive and negative indices that are within and outside 
        the valid range, ensuring that the method behaves correctly in all scenarios.
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
