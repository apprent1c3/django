import copy

from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.db.models.sql import AreaField, DistanceField
from django.test import SimpleTestCase


class FieldsTests(SimpleTestCase):
    def test_area_field_deepcopy(self):
        field = AreaField(None)
        self.assertEqual(copy.deepcopy(field), field)

    def test_distance_field_deepcopy(self):
        """
        Tests that a deep copy of a DistanceField object is equal to the original object.

        This test verifies that the deepcopy operation correctly creates a new independent copy
        of the DistanceField instance, ensuring that modifications to the copy do not affect
        the original object. It checks for equality between the original and copied objects,
        confirming that the deepcopy operation preserves the object's state and attributes.
        """
        field = DistanceField(None)
        self.assertEqual(copy.deepcopy(field), field)


class GeometryFieldTests(SimpleTestCase):
    def test_deconstruct_empty(self):
        field = GeometryField()
        *_, kwargs = field.deconstruct()
        self.assertEqual(kwargs, {"srid": 4326})

    def test_deconstruct_values(self):
        """

        Tests the deconstruction of GeometryField values.

        Verifies that the :meth:`deconstruct` method of a GeometryField instance returns the correct keyword arguments, including 
        SRID, dimension, geography, extent, and tolerance. This ensures that the field's attributes are properly broken down into 
        a dictionary for potential reuse.

        """
        field = GeometryField(
            srid=4067,
            dim=3,
            geography=True,
            extent=(
                50199.4814,
                6582464.0358,
                -50000.0,
                761274.6247,
                7799839.8902,
                50000.0,
            ),
            tolerance=0.01,
        )
        *_, kwargs = field.deconstruct()
        self.assertEqual(
            kwargs,
            {
                "srid": 4067,
                "dim": 3,
                "geography": True,
                "extent": (
                    50199.4814,
                    6582464.0358,
                    -50000.0,
                    761274.6247,
                    7799839.8902,
                    50000.0,
                ),
                "tolerance": 0.01,
            },
        )
