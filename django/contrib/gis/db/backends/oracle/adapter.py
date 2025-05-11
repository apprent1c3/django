from django.contrib.gis.db.backends.base.adapter import WKTAdapter
from django.contrib.gis.geos import GeometryCollection, Polygon
from django.db.backends.oracle.oracledb_any import oracledb


class OracleSpatialAdapter(WKTAdapter):
    input_size = oracledb.CLOB

    def __init__(self, geom):
        """
        Ensures the correct orientation of polygon rings in a geometric object.

        The function validates and adjusts the orientation of a polygon or geometry collection to meet Oracle's requirements.
        It checks for and fixes invalid orientations, where the outer ring must be counter-clockwise and inner rings must be clockwise.
        The result is stored as a WKT representation and spatial reference system identifier (SRID).
        """
        if isinstance(geom, Polygon):
            if self._polygon_must_be_fixed(geom):
                geom = self._fix_polygon(geom)
        elif isinstance(geom, GeometryCollection):
            if any(
                isinstance(g, Polygon) and self._polygon_must_be_fixed(g) for g in geom
            ):
                geom = self._fix_geometry_collection(geom)

        self.wkt = geom.wkt
        self.srid = geom.srid

    @staticmethod
    def _polygon_must_be_fixed(poly):
        return not poly.empty and (
            not poly.exterior_ring.is_counterclockwise
            or any(x.is_counterclockwise for x in poly)
        )

    @classmethod
    def _fix_polygon(cls, poly, clone=True):
        """
        Corrects the orientation of a polygon to ensure it conforms to the expected standard.

        If cloning is enabled, the original polygon remains unchanged and a corrected copy is returned. 
        Otherwise, the original polygon is modified in-place.

        The correction process involves reversing the order of coordinates for the exterior ring and 
        any interior rings that are currently oriented clockwise, to achieve a unified counterclockwise 
        orientation throughout the polygon.
        """
        if clone:
            poly = poly.clone()

        if not poly.exterior_ring.is_counterclockwise:
            poly.exterior_ring = list(reversed(poly.exterior_ring))

        for i in range(1, len(poly)):
            if poly[i].is_counterclockwise:
                poly[i] = list(reversed(poly[i]))

        return poly

    @classmethod
    def _fix_geometry_collection(cls, coll):
        """

        Correct the orientation of polygons within a geometry collection.

        This method ensures that all polygons in the collection have a valid orientation,
        as required by the Geometry object's initialization.

        :param coll: The geometry collection to fix.
        :rtype: The fixed geometry collection.

        """
        coll = coll.clone()
        for i, geom in enumerate(coll):
            if isinstance(geom, Polygon):
                coll[i] = cls._fix_polygon(geom, clone=False)
        return coll
