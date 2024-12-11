from django.contrib.gis.db.models import F, GeometryField, Value, functions
from django.contrib.gis.geos import Point, Polygon
from django.db import connection
from django.db.models import Count, Min
from django.test import TestCase, skipUnlessDBFeature

from .models import City, ManyPointModel, MultiFields


class GeoExpressionsTests(TestCase):
    fixtures = ["initial"]

    def test_geometry_value_annotation(self):
        """

        Tests annotating a database query with a geometric value.

        This test case verifies that a geometric point can be correctly annotated
        to a database query result. It checks that the annotated point matches
        the original point, ensuring that the geometric value is preserved during
        the annotation process.

        The test uses a City model instance and annotates it with a point value
        in a specific spatial reference system (SRS). The annotated point is then
        compared to the original point to ensure their equality.

        """
        p = Point(1, 1, srid=4326)
        point = City.objects.annotate(p=Value(p, GeometryField(srid=4326))).first().p
        self.assertEqual(point, p)

    @skipUnlessDBFeature("supports_transform")
    def test_geometry_value_annotation_different_srid(self):
        """

         Tests the annotation of a geometry value with a different SRID.

         This test verifies that when a geometry value is annotated with a different
         Spatial Reference System Identifier (SRID), the resulting geometry is correctly
         transformed to the target SRID. It also checks that the SRID of the resulting
         geometry matches the target SRID.

         The test uses a sample point geometry with an initial SRID and annotates it with
         a different SRID. It then checks that the transformed geometry is equal to the
         expected result and that its SRID matches the target SRID.

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
        """

        Tests the functionality of annotating the distance from a multi-field 
        object to a city and counting the number of multi-field objects 
        associated with each city.

        The test verifies that a query set can be successfully annotated with 
        the minimum distance to a specific multi-field object and the count 
        of multi-field objects, and that at least one result is returned.

        """
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
