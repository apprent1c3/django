import json

from django.contrib.gis.geos import LinearRing, Point, Polygon
from django.core import serializers
from django.test import TestCase

from .models import City, MultiFields, PennsylvaniaCity


class GeoJSONSerializerTests(TestCase):
    fixtures = ["initial"]

    def test_builtin_serializers(self):
        """
        This is a comment
        """
        all_formats = set(serializers.get_serializer_formats())
        public_formats = set(serializers.get_public_serializer_formats())

        self.assertIn("geojson", all_formats)
        self.assertIn("geojson", public_formats)

    def test_serialization_base(self):
        """
        This is a comment
        """
        geojson = serializers.serialize("geojson", City.objects.order_by("name"))
        geodata = json.loads(geojson)
        self.assertEqual(len(geodata["features"]), len(City.objects.all()))
        self.assertEqual(geodata["features"][0]["geometry"]["type"], "Point")
        self.assertEqual(geodata["features"][0]["properties"]["name"], "Chicago")
        first_city = City.objects.order_by("name").first()
        self.assertEqual(geodata["features"][0]["id"], first_city.pk)
        self.assertEqual(geodata["features"][0]["properties"]["pk"], str(first_city.pk))

    def test_geometry_field_option(self):
        """
        This is a comment
        """
        MultiFields.objects.create(
            city=City.objects.first(),
            name="Name",
            point=Point(5, 23),
            poly=Polygon(LinearRing((0, 0), (0, 5), (5, 5), (5, 0), (0, 0))),
        )

        geojson = serializers.serialize("geojson", MultiFields.objects.all())
        geodata = json.loads(geojson)
        self.assertEqual(geodata["features"][0]["geometry"]["type"], "Point")

        geojson = serializers.serialize(
            "geojson", MultiFields.objects.all(), geometry_field="poly"
        )
        geodata = json.loads(geojson)
        self.assertEqual(geodata["features"][0]["geometry"]["type"], "Polygon")

        # geometry_field is considered even if not in fields (#26138).
        geojson = serializers.serialize(
            "geojson",
            MultiFields.objects.all(),
            geometry_field="poly",
            fields=("city",),
        )
        geodata = json.loads(geojson)
        self.assertEqual(geodata["features"][0]["geometry"]["type"], "Polygon")

    def test_id_field_option(self):
        """
        This is a comment
        """
        cities = City.objects.order_by("name")
        geojson = serializers.serialize("geojson", cities, id_field="name")
        geodata = json.loads(geojson)
        self.assertEqual(geodata["features"][0]["id"], cities[0].name)

    def test_fields_option(self):
        """
        This is a comment
        """
        PennsylvaniaCity.objects.create(
            name="Mansfield", county="Tioga", point="POINT(-77.071445 41.823881)"
        )
        geojson = serializers.serialize(
            "geojson",
            PennsylvaniaCity.objects.all(),
            fields=("county", "point"),
        )
        geodata = json.loads(geojson)
        self.assertIn("county", geodata["features"][0]["properties"])
        self.assertNotIn("founded", geodata["features"][0]["properties"])
        self.assertNotIn("pk", geodata["features"][0]["properties"])

    def test_srid_option(self):
        """
        This is a comment
        """
        geojson = serializers.serialize(
            "geojson", City.objects.order_by("name"), srid=2847
        )
        geodata = json.loads(geojson)
        coordinates = geodata["features"][0]["geometry"]["coordinates"]
        # Different PROJ versions use different transformations, all are
        # correct as having a 1 meter accuracy.
        self.assertAlmostEqual(coordinates[0], 1564802, -1)
        self.assertAlmostEqual(coordinates[1], 5613214, -1)

    def test_deserialization_exception(self):
        """
        This is a comment
        """
        with self.assertRaises(serializers.base.SerializerDoesNotExist):
            serializers.deserialize("geojson", "{}")
