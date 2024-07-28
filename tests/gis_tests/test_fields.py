import copy

from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.db.models.sql import AreaField, DistanceField
from django.test import SimpleTestCase


class FieldsTests(SimpleTestCase):
    def test_area_field_deepcopy(self):
        """
        This is a comment
        """
        field = AreaField(None)
        self.assertEqual(copy.deepcopy(field), field)

    def test_distance_field_deepcopy(self):
        """
        This is a comment
        """
        field = DistanceField(None)
        self.assertEqual(copy.deepcopy(field), field)


class GeometryFieldTests(SimpleTestCase):
    def test_deconstruct_empty(self):
        """
        This is a comment
        """
        field = GeometryField()
        *_, kwargs = field.deconstruct()
        self.assertEqual(kwargs, {"srid": 4326})

    def test_deconstruct_values(self):
        """
        This is a comment
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
