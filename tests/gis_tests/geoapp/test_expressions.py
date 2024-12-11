from django.contrib.gis.db.models import F, GeometryField, Value, functions
from django.contrib.gis.geos import Point, Polygon
from django.db import connection
from django.db.models import Count, Min
from django.test import TestCase, skipUnlessDBFeature

from .models import City, ManyPointModel, MultiFields


class GeoExpressionsTests(TestCase):
    fixtures = ["initial"]

    def test_geometry_value_annotation(self):
        p = Point(1, 1, srid=4326)
        point = City.objects.annotate(p=Value(p, GeometryField(srid=4326))).first().p
        self.assertEqual(point, p)

    @skipUnlessDBFeature("supports_transform")
    def test_geometry_value_annotation_different_srid(self):
        """
        Tests annotation of a geometry value using a different SRID.

        This test checks if a geometry value can be correctly annotated with a
        different spatial reference system identifier (SRID). It verifies that the
        annotated geometry is transformed to the target SRID and that its spatial
        attributes are preserved within a specified tolerance.

        It covers the following key aspects:

        * Annotation of a geometry value with a different SRID
        * Transformation of the geometry value to the target SRID
        * Preservation of spatial attributes after transformation

        The test case uses a Point geometry and transforms it from SRID 32140 to
        SRID 4326, checking for exact equality within a tolerance of 10^-5 degrees.
        """
        p = Point(1, 1, srid=32140)
        point = City.objects.annotate(p=Value(p, GeometryField(srid=4326))).first().p
        self.assertTrue(point.equals_exact(p.transform(4326, clone=True), 10**-5))
        self.assertEqual(point.srid, 4326)

    @skipUnlessDBFeature("supports_geography")
    def test_geography_value(self):
        p = Polygon(((1, 1), (1, 2), (2, 2), (2, 1), (1, 1)))
        area = (
            City.objects.annotate(
                a=functions.Area(Value(p, GeometryField(srid=4326, geography=True)))
            )
            .first()
            .a
        )
        self.assertAlmostEqual(area.sq_km, 12305.1, 0)

    def test_update_from_other_field(self):
        """
        Tests the update functionality for model fields, specifically when updating 
        one field based on the value of another field. This test case verifies that 
        the update operation correctly copies the value from one field to another, 
        including when the fields have different spatial reference systems. The test 
        also checks for correct transformation of spatial data when the database 
        supports it.
        """
        p1 = Point(1, 1, srid=4326)
        p2 = Point(2, 2, srid=4326)
        obj = ManyPointModel.objects.create(
            point1=p1,
            point2=p2,
            point3=p2.transform(3857, clone=True),
        )
        # Updating a point to a point of the same SRID.
        ManyPointModel.objects.filter(pk=obj.pk).update(point2=F("point1"))
        obj.refresh_from_db()
        self.assertEqual(obj.point2, p1)
        # Updating a point to a point with a different SRID.
        if connection.features.supports_transform:
            ManyPointModel.objects.filter(pk=obj.pk).update(point3=F("point1"))
            obj.refresh_from_db()
            self.assertTrue(
                obj.point3.equals_exact(p1.transform(3857, clone=True), 0.1)
            )

    def test_multiple_annotation(self):
        multi_field = MultiFields.objects.create(
            point=Point(1, 1),
            city=City.objects.get(name="Houston"),
            poly=Polygon(((1, 1), (1, 2), (2, 2), (2, 1), (1, 1))),
        )
        qs = (
            City.objects.values("name")
            .order_by("name")
            .annotate(
                distance=Min(
                    functions.Distance("multifields__point", multi_field.city.point)
                ),
            )
            .annotate(count=Count("multifields"))
        )
        self.assertTrue(qs.first())

    @skipUnlessDBFeature("has_Translate_function")
    def test_update_with_expression(self):
        city = City.objects.create(point=Point(1, 1, srid=4326))
        City.objects.filter(pk=city.pk).update(point=functions.Translate("point", 1, 1))
        city.refresh_from_db()
        self.assertEqual(city.point, Point(2, 2, srid=4326))
