import json
import math
import re
from decimal import Decimal

from django.contrib.gis.db.models import GeometryField, PolygonField, functions
from django.contrib.gis.geos import GEOSGeometry, LineString, Point, Polygon, fromstr
from django.contrib.gis.measure import Area
from django.db import NotSupportedError, connection
from django.db.models import IntegerField, Sum, Value
from django.test import TestCase, skipUnlessDBFeature

from ..utils import FuncTestMixin
from .models import City, Country, CountryWebMercator, ManyPointModel, State, Track


class GISFunctionsTests(FuncTestMixin, TestCase):
    """
    Testing functions from django/contrib/gis/db/models/functions.py.
    Area/Distance/Length/Perimeter are tested in distapp/tests.

    Please keep the tests in function's alphabetic order.
    """

    fixtures = ["initial"]

    def test_asgeojson(self):
        """
        Tests the AsGeoJSON database function to ensure correct GeoJSON output for Point geometries, covering various options such as CRS, bounding box, and precision.
        """
        if not connection.features.has_AsGeoJSON_function:
            with self.assertRaises(NotSupportedError):
                list(Country.objects.annotate(json=functions.AsGeoJSON("mpoly")))
            return

        pueblo_json = '{"type":"Point","coordinates":[-104.609252,38.255001]}'
        houston_json = json.loads(
            '{"type":"Point","crs":{"type":"name","properties":'
            '{"name":"EPSG:4326"}},"coordinates":[-95.363151,29.763374]}'
        )
        victoria_json = json.loads(
            '{"type":"Point",'
            '"bbox":[-123.30519600,48.46261100,-123.30519600,48.46261100],'
            '"coordinates":[-123.305196,48.462611]}'
        )
        chicago_json = json.loads(
            '{"type":"Point","crs":{"type":"name","properties":{"name":"EPSG:4326"}},'
            '"bbox":[-87.65018,41.85039,-87.65018,41.85039],'
            '"coordinates":[-87.65018,41.85039]}'
        )
        if "crs" in connection.features.unsupported_geojson_options:
            del houston_json["crs"]
            del chicago_json["crs"]
        if "bbox" in connection.features.unsupported_geojson_options:
            del chicago_json["bbox"]
            del victoria_json["bbox"]
        if "precision" in connection.features.unsupported_geojson_options:
            chicago_json["coordinates"] = [-87.650175, 41.850385]

        # Precision argument should only be an integer
        with self.assertRaises(TypeError):
            City.objects.annotate(geojson=functions.AsGeoJSON("point", precision="foo"))

        # Reference queries and values.
        # SELECT ST_AsGeoJson("geoapp_city"."point", 8, 0)
        # FROM "geoapp_city" WHERE "geoapp_city"."name" = 'Pueblo';
        self.assertJSONEqual(
            pueblo_json,
            City.objects.annotate(geojson=functions.AsGeoJSON("point"))
            .get(name="Pueblo")
            .geojson,
        )

        # SELECT ST_AsGeoJson("geoapp_city"."point", 8, 2) FROM "geoapp_city"
        # WHERE "geoapp_city"."name" = 'Houston';
        # This time we want to include the CRS by using the `crs` keyword.
        self.assertJSONEqual(
            City.objects.annotate(json=functions.AsGeoJSON("point", crs=True))
            .get(name="Houston")
            .json,
            houston_json,
        )

        # SELECT ST_AsGeoJson("geoapp_city"."point", 8, 1) FROM "geoapp_city"
        # WHERE "geoapp_city"."name" = 'Houston';
        # This time we include the bounding box by using the `bbox` keyword.
        self.assertJSONEqual(
            City.objects.annotate(geojson=functions.AsGeoJSON("point", bbox=True))
            .get(name="Victoria")
            .geojson,
            victoria_json,
        )

        # SELECT ST_AsGeoJson("geoapp_city"."point", 5, 3) FROM "geoapp_city"
        # WHERE "geoapp_city"."name" = 'Chicago';
        # Finally, we set every available keyword.
        # MariaDB doesn't limit the number of decimals in bbox.
        if connection.ops.mariadb:
            chicago_json["bbox"] = [-87.650175, 41.850385, -87.650175, 41.850385]
        try:
            self.assertJSONEqual(
                City.objects.annotate(
                    geojson=functions.AsGeoJSON(
                        "point", bbox=True, crs=True, precision=5
                    )
                )
                .get(name="Chicago")
                .geojson,
                chicago_json,
            )
        except AssertionError:
            # Give a second chance with different coords rounding.
            chicago_json["coordinates"][1] = 41.85038
            self.assertJSONEqual(
                City.objects.annotate(
                    geojson=functions.AsGeoJSON(
                        "point", bbox=True, crs=True, precision=5
                    )
                )
                .get(name="Chicago")
                .geojson,
                chicago_json,
            )

    @skipUnlessDBFeature("has_AsGeoJSON_function")
    def test_asgeojson_option_0(self):
        p1 = Point(1, 1, srid=4326)
        p2 = Point(-87.65018, 41.85039, srid=4326)
        obj = ManyPointModel.objects.create(
            point1=p1,
            point2=p2,
            point3=p2.transform(3857, clone=True),
        )
        self.assertJSONEqual(
            ManyPointModel.objects.annotate(geojson=functions.AsGeoJSON("point3"))
            .get(pk=obj.pk)
            .geojson,
            # GeoJSON without CRS.
            json.loads(
                '{"type":"Point","coordinates":[-9757173.40553877, 5138594.87034608]}'
            ),
        )

    @skipUnlessDBFeature("has_AsGML_function")
    def test_asgml(self):
        # Should throw a TypeError when trying to obtain GML from a
        # non-geometry field.
        """
        Tests the usage of the AsGML function to generate GML representations of geographic data.

        Verifies that the function raises a TypeError when used with invalid arguments and that it correctly generates GML for a City object's point field with specified precision and version parameters.
        """
        qs = City.objects.all()
        with self.assertRaises(TypeError):
            qs.annotate(gml=functions.AsGML("name"))
        ptown = City.objects.annotate(gml=functions.AsGML("point", precision=9)).get(
            name="Pueblo"
        )

        if connection.ops.oracle:
            # No precision parameter for Oracle :-/
            gml_regex = re.compile(
                r'^<gml:Point srsName="EPSG:4326" '
                r'xmlns:gml="http://www.opengis.net/gml">'
                r'<gml:coordinates decimal="\." cs="," ts=" ">'
                r"-104.60925\d+,38.25500\d+ "
                r"</gml:coordinates></gml:Point>"
            )
        else:
            gml_regex = re.compile(
                r'^<gml:Point srsName="(urn:ogc:def:crs:)?EPSG:4326"><gml:coordinates>'
                r"-104\.60925\d+,38\.255001</gml:coordinates></gml:Point>"
            )
        self.assertTrue(gml_regex.match(ptown.gml))
        self.assertIn(
            '<gml:pos srsDimension="2">',
            City.objects.annotate(gml=functions.AsGML("point", version=3))
            .get(name="Pueblo")
            .gml,
        )

    @skipUnlessDBFeature("has_AsKML_function")
    def test_askml(self):
        # Should throw a TypeError when trying to obtain KML from a
        # non-geometry field.
        with self.assertRaises(TypeError):
            City.objects.annotate(kml=functions.AsKML("name"))

        # Ensuring the KML is as expected.
        ptown = City.objects.annotate(kml=functions.AsKML("point", precision=9)).get(
            name="Pueblo"
        )
        self.assertEqual(
            "<Point><coordinates>-104.609252,38.255001</coordinates></Point>", ptown.kml
        )

    @skipUnlessDBFeature("has_AsSVG_function")
    def test_assvg(self):
        """

        Test the AsSVG function for annotating city locations with SVG data.

        This test checks that the AsSVG function raises an error when given invalid input
        and that it correctly generates SVG data for a city's coordinates.

        """
        with self.assertRaises(TypeError):
            City.objects.annotate(svg=functions.AsSVG("point", precision="foo"))
        # SELECT AsSVG(geoapp_city.point, 0, 8) FROM geoapp_city WHERE name = 'Pueblo';
        svg1 = 'cx="-104.609252" cy="-38.255001"'
        # Even though relative, only one point so it's practically the same except for
        # the 'c' letter prefix on the x,y values.
        svg2 = svg1.replace("c", "")
        self.assertEqual(
            svg1,
            City.objects.annotate(svg=functions.AsSVG("point")).get(name="Pueblo").svg,
        )
        self.assertEqual(
            svg2,
            City.objects.annotate(svg=functions.AsSVG("point", relative=5))
            .get(name="Pueblo")
            .svg,
        )

    @skipUnlessDBFeature("has_AsWKB_function")
    def test_aswkb(self):
        wkb = (
            City.objects.annotate(
                wkb=functions.AsWKB(Point(1, 2, srid=4326)),
            )
            .first()
            .wkb
        )
        # WKB is either XDR or NDR encoded.
        self.assertIn(
            bytes(wkb),
            (
                b"\x00\x00\x00\x00\x01?\xf0\x00\x00\x00\x00\x00\x00@\x00\x00"
                b"\x00\x00\x00\x00\x00",
                b"\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf0?\x00\x00"
                b"\x00\x00\x00\x00\x00@",
            ),
        )

    @skipUnlessDBFeature("has_AsWKT_function")
    def test_aswkt(self):
        wkt = (
            City.objects.annotate(
                wkt=functions.AsWKT(Point(1, 2, srid=4326)),
            )
            .first()
            .wkt
        )
        self.assertEqual(
            wkt, "POINT (1.0 2.0)" if connection.ops.oracle else "POINT(1 2)"
        )

    @skipUnlessDBFeature("has_Azimuth_function")
    def test_azimuth(self):
        # Returns the azimuth in radians.
        azimuth_expr = functions.Azimuth(Point(0, 0, srid=4326), Point(1, 1, srid=4326))
        self.assertAlmostEqual(
            City.objects.annotate(azimuth=azimuth_expr).first().azimuth,
            math.pi / 4,
            places=2,
        )
        # Returns None if the two points are coincident.
        azimuth_expr = functions.Azimuth(Point(0, 0, srid=4326), Point(0, 0, srid=4326))
        self.assertIsNone(City.objects.annotate(azimuth=azimuth_expr).first().azimuth)

    @skipUnlessDBFeature("has_BoundingCircle_function")
    def test_bounding_circle(self):
        """

        Checks the functionality of the BoundingCircle database function for geospatial operations.

        This test case verifies the calculation of the area and number of points for the bounding circle of a geometric object.
        It also checks the impact of the number of segments on the circle's characteristics.

        Supported databases with spatial functionality are tested, including PostGIS and SpatiaLite.

        """
        def circle_num_points(num_seg):
            # num_seg is the number of segments per quarter circle.
            return (4 * num_seg) + 1

        if connection.ops.postgis:
            expected_area = 169
        elif connection.ops.spatialite:
            expected_area = 168
        else:  # Oracle.
            expected_area = 171
        country = Country.objects.annotate(
            circle=functions.BoundingCircle("mpoly")
        ).order_by("name")[0]
        self.assertAlmostEqual(country.circle.area, expected_area, 0)
        if connection.ops.postgis:
            # By default num_seg=48.
            self.assertEqual(country.circle.num_points, circle_num_points(48))

        tests = [12, Value(12, output_field=IntegerField())]
        for num_seq in tests:
            with self.subTest(num_seq=num_seq):
                country = Country.objects.annotate(
                    circle=functions.BoundingCircle("mpoly", num_seg=num_seq),
                ).order_by("name")[0]
                if connection.ops.postgis:
                    self.assertGreater(country.circle.area, 168.4, 0)
                    self.assertLess(country.circle.area, 169.5, 0)
                    self.assertEqual(country.circle.num_points, circle_num_points(12))
                else:
                    self.assertAlmostEqual(country.circle.area, expected_area, 0)

    @skipUnlessDBFeature("has_Centroid_function")
    def test_centroid(self):
        """

        Tests the database's Centroid function by annotating states with their polygon centroids
        and verifying the results against the expected centroid values.

        This test checks for both correctness and proper error handling when used with an invalid
        number of arguments.

        """
        qs = State.objects.exclude(poly__isnull=True).annotate(
            centroid=functions.Centroid("poly")
        )
        tol = (
            1.8 if connection.ops.mysql else (0.1 if connection.ops.oracle else 0.00001)
        )
        for state in qs:
            self.assertTrue(state.poly.centroid.equals_exact(state.centroid, tol))

        with self.assertRaisesMessage(
            TypeError, "'Centroid' takes exactly 1 argument (2 given)"
        ):
            State.objects.annotate(centroid=functions.Centroid("poly", "poly"))

    @skipUnlessDBFeature("has_Difference_function")
    def test_difference(self):
        """
        Tests the database's Difference function by comparing the results of the function with manually computed differences, ensuring geographic annotation correctness.
        """
        geom = Point(5, 23, srid=4326)
        qs = Country.objects.annotate(diff=functions.Difference("mpoly", geom))
        # Oracle does something screwy with the Texas geometry.
        if connection.ops.oracle:
            qs = qs.exclude(name="Texas")

        for c in qs:
            self.assertTrue(c.mpoly.difference(geom).equals(c.diff))

    @skipUnlessDBFeature("has_Difference_function", "has_Transform_function")
    def test_difference_mixed_srid(self):
        """

        Tests the database's Difference function with mixed SRID, annotating Country objects 
        with the difference between their multi-polygon and a specific point geometry.

        """
        geom = Point(556597.4, 2632018.6, srid=3857)  # Spherical Mercator
        qs = Country.objects.annotate(difference=functions.Difference("mpoly", geom))
        # Oracle does something screwy with the Texas geometry.
        if connection.ops.oracle:
            qs = qs.exclude(name="Texas")
        for c in qs:
            self.assertTrue(c.mpoly.difference(geom).equals(c.difference))

    @skipUnlessDBFeature("has_Envelope_function")
    def test_envelope(self):
        countries = Country.objects.annotate(envelope=functions.Envelope("mpoly"))
        for country in countries:
            self.assertTrue(country.envelope.equals(country.mpoly.envelope))

    @skipUnlessDBFeature("has_ForcePolygonCW_function")
    def test_force_polygon_cw(self):
        """
        Tests the ForcePolygonCW function by creating a state object with a polygon, 
        annotating it with the forced clockwise polygon, and verifying the result matches the expected rings orientation
        """
        rings = (
            ((0, 0), (5, 0), (0, 5), (0, 0)),
            ((1, 1), (1, 3), (3, 1), (1, 1)),
        )
        rhr_rings = (
            ((0, 0), (0, 5), (5, 0), (0, 0)),
            ((1, 1), (3, 1), (1, 3), (1, 1)),
        )
        State.objects.create(name="Foo", poly=Polygon(*rings))
        st = State.objects.annotate(
            force_polygon_cw=functions.ForcePolygonCW("poly")
        ).get(name="Foo")
        self.assertEqual(rhr_rings, st.force_polygon_cw.coords)

    @skipUnlessDBFeature("has_FromWKB_function")
    def test_fromwkb(self):
        """
        Tests the FromWKB function for correctly converting a well-known binary (WKB) representation to a geometric object, with and without an explicit spatial reference system identifier (SRID).
        """
        g = Point(56.811078, 60.608647)
        pt1, pt2 = City.objects.values_list(
            functions.FromWKB(Value(g.wkb.tobytes())),
            functions.FromWKB(Value(g.wkb.tobytes()), srid=4326),
        )[0]
        self.assertIs(g.equals_exact(pt1, 0.00001), True)
        self.assertIsNone(pt1.srid)
        self.assertEqual(pt2.srid, 4326)

    @skipUnlessDBFeature("has_FromWKT_function")
    def test_fromwkt(self):
        """

        Tests the functionality of the database's FromWKT function, 
        which converts Well-Known Text (WKT) into a spatial object.
        It verifies the function's correctness and its behavior with and without an SRID.

        """
        g = Point(56.811078, 60.608647)
        pt1, pt2 = City.objects.values_list(
            functions.FromWKT(Value(g.wkt)),
            functions.FromWKT(Value(g.wkt), srid=4326),
        )[0]
        self.assertIs(g.equals_exact(pt1, 0.00001), True)
        self.assertIsNone(pt1.srid)
        self.assertEqual(pt2.srid, 4326)

    @skipUnlessDBFeature("has_GeoHash_function")
    def test_geohash(self):
        # Reference query:
        # SELECT ST_GeoHash(point) FROM geoapp_city WHERE name='Houston';
        # SELECT ST_GeoHash(point, 5) FROM geoapp_city WHERE name='Houston';
        """
        Tests the GeoHash function by annotating cities with their geohash values and verifying the results against a reference hash.
        """
        ref_hash = "9vk1mfq8jx0c8e0386z6"
        h1 = City.objects.annotate(geohash=functions.GeoHash("point")).get(
            name="Houston"
        )
        h2 = City.objects.annotate(geohash=functions.GeoHash("point", precision=5)).get(
            name="Houston"
        )
        self.assertEqual(ref_hash, h1.geohash[: len(ref_hash)])
        self.assertEqual(ref_hash[:5], h2.geohash)

    @skipUnlessDBFeature("has_GeometryDistance_function")
    def test_geometry_distance(self):
        """

        Checks the correctness of the GeometryDistance database function 
        by annotating City objects with their distance from a given point 
        and verifying that the resulting distances match the expected values.

        """
        point = Point(-90, 40, srid=4326)
        qs = City.objects.annotate(
            distance=functions.GeometryDistance("point", point)
        ).order_by("distance")
        distances = (
            2.99091995527296,
            5.33507274054713,
            9.33852187483721,
            9.91769193646233,
            11.556465744884,
            14.713098433352,
            34.3635252198568,
            276.987855073372,
        )
        for city, expected_distance in zip(qs, distances):
            with self.subTest(city=city):
                self.assertAlmostEqual(city.distance, expected_distance)

    @skipUnlessDBFeature("has_Intersection_function")
    def test_intersection(self):
        """
        Test the functionality of the Intersection database function in Django, specifically when a geometric intersection is empty.
        """
        geom = Point(5, 23, srid=4326)
        qs = Country.objects.annotate(inter=functions.Intersection("mpoly", geom))
        for c in qs:
            if connection.features.empty_intersection_returns_none:
                self.assertIsNone(c.inter)
            else:
                self.assertIs(c.inter.empty, True)

    @skipUnlessDBFeature("supports_empty_geometries", "has_IsEmpty_function")
    def test_isempty(self):
        empty = City.objects.create(name="Nowhere", point=Point(srid=4326))
        City.objects.create(name="Somewhere", point=Point(6.825, 47.1, srid=4326))
        self.assertSequenceEqual(
            City.objects.annotate(isempty=functions.IsEmpty("point")).filter(
                isempty=True
            ),
            [empty],
        )
        self.assertSequenceEqual(City.objects.filter(point__isempty=True), [empty])

    @skipUnlessDBFeature("has_IsValid_function")
    def test_isvalid(self):
        """
        Tests the IsValid database function by creating valid and invalid polygon geometries,
        verifying that the IsValid function correctly identifies their validity status
        """
        valid_geom = fromstr("POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))")
        invalid_geom = fromstr("POLYGON((0 0, 0 1, 1 1, 1 0, 1 1, 1 0, 0 0))")
        State.objects.create(name="valid", poly=valid_geom)
        State.objects.create(name="invalid", poly=invalid_geom)
        valid = (
            State.objects.filter(name="valid")
            .annotate(isvalid=functions.IsValid("poly"))
            .first()
        )
        invalid = (
            State.objects.filter(name="invalid")
            .annotate(isvalid=functions.IsValid("poly"))
            .first()
        )
        self.assertIs(valid.isvalid, True)
        self.assertIs(invalid.isvalid, False)

    @skipUnlessDBFeature("has_Area_function")
    def test_area_with_regular_aggregate(self):
        # Create projected country objects, for this test to work on all backends.
        """
        Tests the calculation of area for geographic objects using the PostGIS Area function, ensuring the results are accurate when projected onto a Web Mercator coordinate system.
        """
        for c in Country.objects.all():
            CountryWebMercator.objects.create(
                name=c.name, mpoly=c.mpoly.transform(3857, clone=True)
            )
        # Test in projected coordinate system
        qs = CountryWebMercator.objects.annotate(area_sum=Sum(functions.Area("mpoly")))
        # Some backends (e.g. Oracle) cannot group by multipolygon values, so
        # defer such fields in the aggregation query.
        for c in qs.defer("mpoly"):
            result = c.area_sum
            # If the result is a measure object, get value.
            if isinstance(result, Area):
                result = result.sq_m
            self.assertAlmostEqual((result - c.mpoly.area) / c.mpoly.area, 0)

    @skipUnlessDBFeature("has_Area_function")
    def test_area_lookups(self):
        # Create projected countries so the test works on all backends.
        """
        Tests area lookup functionality for spatial models, specifically the use of the Area database function to filter objects based on their area size, and ensures proper error handling for invalid area comparisons.
        """
        CountryWebMercator.objects.bulk_create(
            CountryWebMercator(name=c.name, mpoly=c.mpoly.transform(3857, clone=True))
            for c in Country.objects.all()
        )
        qs = CountryWebMercator.objects.annotate(area=functions.Area("mpoly"))
        self.assertEqual(
            qs.get(area__lt=Area(sq_km=500000)),
            CountryWebMercator.objects.get(name="New Zealand"),
        )

        with self.assertRaisesMessage(
            ValueError, "AreaField only accepts Area measurement objects."
        ):
            qs.get(area__lt=500000)

    @skipUnlessDBFeature("has_ClosestPoint_function")
    def test_closest_point(self):
        qs = Country.objects.annotate(
            closest_point=functions.ClosestPoint("mpoly", functions.Centroid("mpoly"))
        )
        for country in qs:
            self.assertIsInstance(country.closest_point, Point)
            self.assertEqual(
                country.mpoly.intersection(country.closest_point),
                country.closest_point,
            )

    @skipUnlessDBFeature("has_LineLocatePoint_function")
    def test_line_locate_point(self):
        pos_expr = functions.LineLocatePoint(
            LineString((0, 0), (0, 3), srid=4326), Point(0, 1, srid=4326)
        )
        self.assertAlmostEqual(
            State.objects.annotate(pos=pos_expr).first().pos, 0.3333333
        )

    @skipUnlessDBFeature("has_MakeValid_function")
    def test_make_valid(self):
        """
        Checks the functionality of the MakeValid database function by creating a spatial object with an invalid geometry, repairing it, and then verifying that the resulting geometry is valid and correct.
        """
        invalid_geom = fromstr("POLYGON((0 0, 0 1, 1 1, 1 0, 1 1, 1 0, 0 0))")
        State.objects.create(name="invalid", poly=invalid_geom)
        invalid = (
            State.objects.filter(name="invalid")
            .annotate(repaired=functions.MakeValid("poly"))
            .first()
        )
        self.assertIs(invalid.repaired.valid, True)
        self.assertTrue(
            invalid.repaired.equals(
                fromstr("POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))", srid=invalid.poly.srid)
            )
        )

    @skipUnlessDBFeature("has_MakeValid_function")
    def test_make_valid_multipolygon(self):
        """
        Tests the MakeValid database function for repairing invalid multipolygon geometries by creating an invalid geometry, applying the function, and verifying the result is a valid multipolygon with the expected structure.
        """
        invalid_geom = fromstr(
            "POLYGON((0 0, 0 1 , 1 1 , 1 0, 0 0), (10 0, 10 1, 11 1, 11 0, 10 0))"
        )
        State.objects.create(name="invalid", poly=invalid_geom)
        invalid = (
            State.objects.filter(name="invalid")
            .annotate(
                repaired=functions.MakeValid("poly"),
            )
            .get()
        )
        self.assertIs(invalid.repaired.valid, True)
        self.assertTrue(
            invalid.repaired.equals(
                fromstr(
                    "MULTIPOLYGON (((0 0, 0 1, 1 1, 1 0, 0 0)), "
                    "((10 0, 10 1, 11 1, 11 0, 10 0)))",
                    srid=invalid.poly.srid,
                )
            )
        )
        self.assertEqual(len(invalid.repaired), 2)

    @skipUnlessDBFeature("has_MakeValid_function")
    def test_make_valid_output_field(self):
        # output_field is GeometryField instance because different geometry
        # types can be returned.
        output_field = functions.MakeValid(
            Value(Polygon(), PolygonField(srid=42)),
        ).output_field
        self.assertIs(output_field.__class__, GeometryField)
        self.assertEqual(output_field.srid, 42)

    @skipUnlessDBFeature("has_MemSize_function")
    def test_memsize(self):
        ptown = City.objects.annotate(size=functions.MemSize("point")).get(
            name="Pueblo"
        )
        # Exact value depends on database and version.
        self.assertTrue(20 <= ptown.size <= 105)

    @skipUnlessDBFeature("has_NumGeom_function")
    def test_num_geom(self):
        # Both 'countries' only have two geometries.
        """

        Tests the functionality of the NumGeometries function in the database.

        This test checks if the function correctly calculates the number of geometries
        for a given field, verifying the annotation results for both Country and City models.
        The test accounts for differences in behavior between MySQL/MariaDB and other database systems.

        """
        for c in Country.objects.annotate(num_geom=functions.NumGeometries("mpoly")):
            self.assertEqual(2, c.num_geom)

        qs = City.objects.filter(point__isnull=False).annotate(
            num_geom=functions.NumGeometries("point")
        )
        for city in qs:
            # The results for the number of geometries on non-collections
            # depends on the database.
            if connection.ops.mysql or connection.ops.mariadb:
                self.assertIsNone(city.num_geom)
            else:
                self.assertEqual(1, city.num_geom)

    @skipUnlessDBFeature("has_NumPoint_function")
    def test_num_points(self):
        """
        Tests the functionality of the NumPoints database function.

        This test case verifies that the NumPoints function correctly calculates the number of points in a LineString, 
        MultiPolygon, and Point geometry, and checks for expected behavior when used with different geometric fields.
        """
        coords = [(-95.363151, 29.763374), (-95.448601, 29.713803)]
        Track.objects.create(name="Foo", line=LineString(coords))
        qs = Track.objects.annotate(num_points=functions.NumPoints("line"))
        self.assertEqual(qs.first().num_points, 2)
        mpoly_qs = Country.objects.annotate(num_points=functions.NumPoints("mpoly"))
        if not connection.features.supports_num_points_poly:
            for c in mpoly_qs:
                self.assertIsNone(c.num_points)
            return

        for c in mpoly_qs:
            self.assertEqual(c.mpoly.num_points, c.num_points)

        for c in City.objects.annotate(num_points=functions.NumPoints("point")):
            self.assertEqual(c.num_points, 1)

    @skipUnlessDBFeature("has_PointOnSurface_function")
    def test_point_on_surface(self):
        qs = Country.objects.annotate(
            point_on_surface=functions.PointOnSurface("mpoly")
        )
        for country in qs:
            self.assertTrue(country.mpoly.intersection(country.point_on_surface))

    @skipUnlessDBFeature("has_Reverse_function")
    def test_reverse_geom(self):
        """
        Checks if reverse geographic function is implemented correctly by annotating a track's line geometry with its reverse and comparing the result with the expected reversed coordinates.
        """
        coords = [(-95.363151, 29.763374), (-95.448601, 29.713803)]
        Track.objects.create(name="Foo", line=LineString(coords))
        track = Track.objects.annotate(reverse_geom=functions.Reverse("line")).get(
            name="Foo"
        )
        coords.reverse()
        self.assertEqual(tuple(coords), track.reverse_geom.coords)

    @skipUnlessDBFeature("has_Scale_function")
    def test_scale(self):
        """
        Tests the Scale function by applying scaling factors to geographic data.
        Verifies that coordinates are scaled correctly and checks the effect on area calculations.\"
        """
        xfac, yfac = 2, 3
        tol = 5  # The low precision tolerance is for SpatiaLite
        qs = Country.objects.annotate(scaled=functions.Scale("mpoly", xfac, yfac))
        for country in qs:
            for p1, p2 in zip(country.mpoly, country.scaled):
                for r1, r2 in zip(p1, p2):
                    for c1, c2 in zip(r1.coords, r2.coords):
                        self.assertAlmostEqual(c1[0] * xfac, c2[0], tol)
                        self.assertAlmostEqual(c1[1] * yfac, c2[1], tol)
        # Test float/Decimal values
        qs = Country.objects.annotate(
            scaled=functions.Scale("mpoly", 1.5, Decimal("2.5"))
        )
        self.assertGreater(qs[0].scaled.area, qs[0].mpoly.area)

    @skipUnlessDBFeature("has_SnapToGrid_function")
    def test_snap_to_grid(self):
        # Let's try and break snap_to_grid() with bad combinations of arguments.
        """
        Tests the functionality of the SnapToGrid database function by verifying its behavior with various input parameters and edge cases. 

        It checks that the function correctly raises exceptions when invalid arguments are provided, 
        and that it properly snaps a geographic multipolygon to a specified grid when valid arguments are used.
        """
        for bad_args in ((), range(3), range(5)):
            with self.assertRaises(ValueError):
                Country.objects.annotate(snap=functions.SnapToGrid("mpoly", *bad_args))
        for bad_args in (("1.0",), (1.0, None), tuple(map(str, range(4)))):
            with self.assertRaises(TypeError):
                Country.objects.annotate(snap=functions.SnapToGrid("mpoly", *bad_args))

        # Boundary for San Marino, courtesy of Bjorn Sandvik of thematicmapping.org
        # from the world borders dataset he provides.
        wkt = (
            "MULTIPOLYGON(((12.41580 43.95795,12.45055 43.97972,12.45389 43.98167,"
            "12.46250 43.98472,12.47167 43.98694,12.49278 43.98917,"
            "12.50555 43.98861,12.51000 43.98694,12.51028 43.98277,"
            "12.51167 43.94333,12.51056 43.93916,12.49639 43.92333,"
            "12.49500 43.91472,12.48778 43.90583,12.47444 43.89722,"
            "12.46472 43.89555,12.45917 43.89611,12.41639 43.90472,"
            "12.41222 43.90610,12.40782 43.91366,12.40389 43.92667,"
            "12.40500 43.94833,12.40889 43.95499,12.41580 43.95795)))"
        )
        Country.objects.create(name="San Marino", mpoly=fromstr(wkt))

        # Because floating-point arithmetic isn't exact, we set a tolerance
        # to pass into GEOS `equals_exact`.
        tol = 0.000000001

        # SELECT AsText(ST_SnapToGrid("geoapp_country"."mpoly", 0.1))
        # FROM "geoapp_country"
        # WHERE "geoapp_country"."name" = 'San Marino';
        ref = fromstr("MULTIPOLYGON(((12.4 44,12.5 44,12.5 43.9,12.4 43.9,12.4 44)))")
        self.assertTrue(
            ref.equals_exact(
                Country.objects.annotate(snap=functions.SnapToGrid("mpoly", 0.1))
                .get(name="San Marino")
                .snap,
                tol,
            )
        )

        # SELECT AsText(ST_SnapToGrid("geoapp_country"."mpoly", 0.05, 0.23))
        # FROM "geoapp_country"
        # WHERE "geoapp_country"."name" = 'San Marino';
        ref = fromstr(
            "MULTIPOLYGON(((12.4 43.93,12.45 43.93,12.5 43.93,12.45 43.93,12.4 43.93)))"
        )
        self.assertTrue(
            ref.equals_exact(
                Country.objects.annotate(snap=functions.SnapToGrid("mpoly", 0.05, 0.23))
                .get(name="San Marino")
                .snap,
                tol,
            )
        )

        # SELECT AsText(ST_SnapToGrid("geoapp_country"."mpoly", 0.5, 0.17, 0.05, 0.23))
        # FROM "geoapp_country"
        # WHERE "geoapp_country"."name" = 'San Marino';
        ref = fromstr(
            "MULTIPOLYGON(((12.4 43.87,12.45 43.87,12.45 44.1,12.5 44.1,12.5 43.87,"
            "12.45 43.87,12.4 43.87)))"
        )
        self.assertTrue(
            ref.equals_exact(
                Country.objects.annotate(
                    snap=functions.SnapToGrid("mpoly", 0.05, 0.23, 0.5, 0.17)
                )
                .get(name="San Marino")
                .snap,
                tol,
            )
        )

    @skipUnlessDBFeature("has_SymDifference_function")
    def test_sym_difference(self):
        """
        Tests the SymDifference database function by annotating a QuerySet of countries with their symmetric difference from a given point, and verifying the result against the expected geometric difference.
        """
        geom = Point(5, 23, srid=4326)
        qs = Country.objects.annotate(
            sym_difference=functions.SymDifference("mpoly", geom)
        )
        # Oracle does something screwy with the Texas geometry.
        if connection.ops.oracle:
            qs = qs.exclude(name="Texas")
        for country in qs:
            self.assertTrue(
                country.mpoly.sym_difference(geom).equals(country.sym_difference)
            )

    @skipUnlessDBFeature("has_Transform_function")
    def test_transform(self):
        # Pre-transformed points for Houston and Pueblo.
        """

        Tests the Transform database function, which changes the spatial reference system of a geographic object.

        This test case verifies that a point's spatial reference system can be transformed correctly,
        and checks the resulting coordinates for accuracy.

        """
        ptown = fromstr("POINT(992363.390841912 481455.395105533)", srid=2774)

        # Asserting the result of the transform operation with the values in
        #  the pre-transformed points.
        h = City.objects.annotate(pt=functions.Transform("point", ptown.srid)).get(
            name="Pueblo"
        )
        self.assertEqual(2774, h.pt.srid)
        # Precision is low due to version variations in PROJ and GDAL.
        self.assertLess(ptown.x - h.pt.x, 1)
        self.assertLess(ptown.y - h.pt.y, 1)

    @skipUnlessDBFeature("has_Translate_function")
    def test_translate(self):
        """
        Tests the database Translate function by applying a translation to a set of polygons and verifying the result.
        """
        xfac, yfac = 5, -23
        qs = Country.objects.annotate(
            translated=functions.Translate("mpoly", xfac, yfac)
        )
        for c in qs:
            for p1, p2 in zip(c.mpoly, c.translated):
                for r1, r2 in zip(p1, p2):
                    for c1, c2 in zip(r1.coords, r2.coords):
                        # The low precision is for SpatiaLite
                        self.assertAlmostEqual(c1[0] + xfac, c2[0], 5)
                        self.assertAlmostEqual(c1[1] + yfac, c2[1], 5)

    # Some combined function tests
    @skipUnlessDBFeature(
        "has_Difference_function",
        "has_Intersection_function",
        "has_SymDifference_function",
        "has_Union_function",
    )
    def test_diff_intersection_union(self):
        """

        Tests the database functions for difference, intersection, symmetric difference, and union of geometric objects.

        This test case ensures that the results of these operations match the expected outcomes, taking into account
        database-specific behaviors for empty intersection results.

        """
        geom = Point(5, 23, srid=4326)
        qs = Country.objects.annotate(
            difference=functions.Difference("mpoly", geom),
            sym_difference=functions.SymDifference("mpoly", geom),
            union=functions.Union("mpoly", geom),
            intersection=functions.Intersection("mpoly", geom),
        )

        if connection.ops.oracle:
            # Should be able to execute the queries; however, they won't be the same
            # as GEOS (because Oracle doesn't use GEOS internally like PostGIS or
            # SpatiaLite).
            return
        for c in qs:
            self.assertTrue(c.mpoly.difference(geom).equals(c.difference))
            if connection.features.empty_intersection_returns_none:
                self.assertIsNone(c.intersection)
            else:
                self.assertIs(c.intersection.empty, True)
            self.assertTrue(c.mpoly.sym_difference(geom).equals(c.sym_difference))
            self.assertTrue(c.mpoly.union(geom).equals(c.union))

    @skipUnlessDBFeature("has_Union_function")
    def test_union(self):
        """
        Union two geometries, either a geometry field and a geometry object, two geometry fields, or two geometry objects, and verify the results.
        """
        geom = Point(-95.363151, 29.763374, srid=4326)

        union = (
            City.objects.annotate(union=functions.Union("point", geom))
            .get(name="Dallas")
            .union
        )
        expected = fromstr(
            "MULTIPOINT(-96.801611 32.782057,-95.363151 29.763374)", srid=4326
        )
        self.assertTrue(expected.equals(union))

        union = (
            City.objects.annotate(union=functions.Union(geom, "point"))
            .get(name="Dallas")
            .union
        )
        self.assertTrue(expected.equals(union))

        union = (
            City.objects.annotate(union=functions.Union("point", "point"))
            .get(name="Dallas")
            .union
        )
        expected = GEOSGeometry("POINT(-96.801611 32.782057)", srid=4326)
        self.assertTrue(expected.equals(union))

        union = (
            City.objects.annotate(union=functions.Union(geom, geom))
            .get(name="Dallas")
            .union
        )
        self.assertTrue(geom.equals(union))

    @skipUnlessDBFeature("has_Union_function", "has_Transform_function")
    def test_union_mixed_srid(self):
        """
        Tests the Union function with mixed SRIDs, verifying the result SRID depends on the order of parameters.
        """
        geom = Point(61.42915, 55.15402, srid=4326)
        geom_3857 = geom.transform(3857, clone=True)
        tol = 0.001

        for city in City.objects.annotate(union=functions.Union("point", geom_3857)):
            expected = city.point | geom
            self.assertTrue(city.union.equals_exact(expected, tol))
            self.assertEqual(city.union.srid, 4326)

        for city in City.objects.annotate(union=functions.Union(geom_3857, "point")):
            expected = geom_3857 | city.point.transform(3857, clone=True)
            self.assertTrue(expected.equals_exact(city.union, tol))
            self.assertEqual(city.union.srid, 3857)

    def test_argument_validation(self):
        """
        Tests validation of arguments passed to a geometric function, specifically verifying that it raises correct errors when SRID is missing, an incorrect field type is provided, or a non-geometric argument is passed.
        """
        with self.assertRaisesMessage(
            ValueError, "SRID is required for all geometries."
        ):
            City.objects.annotate(geo=functions.GeoFunc(Point(1, 1)))

        msg = "GeoFunc function requires a GeometryField in position 1, got CharField."
        with self.assertRaisesMessage(TypeError, msg):
            City.objects.annotate(geo=functions.GeoFunc("name"))

        msg = "GeoFunc function requires a geometric argument in position 1."
        with self.assertRaisesMessage(TypeError, msg):
            City.objects.annotate(union=functions.GeoFunc(1, "point")).get(
                name="Dallas"
            )
