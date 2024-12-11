import copy

from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.db.models.sql import AreaField, DistanceField
from django.test import SimpleTestCase


class FieldsTests(SimpleTestCase):
    def test_area_field_deepcopy(self):
        field = AreaField(None)
        self.assertEqual(copy.deepcopy(field), field)

    def test_distance_field_deepcopy(self):
        field = DistanceField(None)
        self.assertEqual(copy.deepcopy(field), field)


class GeometryFieldTests(SimpleTestCase):
    def test_deconstruct_empty(self):
        field = GeometryField()
        *_, kwargs = field.deconstruct()
        self.assertEqual(kwargs, {"srid": 4326})

    def test_deconstruct_values(self):
        """

        Tests the deconstruction of a GeometryField into its constituent keyword arguments.

        The deconstruct method is expected to return a tuple containing the field's
        constructor arguments, which are then unpacked and compared against the
        original field's attributes.

        This ensures that the field can be properly reconstructed from its deconstructed
        values, verifying the correctness of the deconstruction process.

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
