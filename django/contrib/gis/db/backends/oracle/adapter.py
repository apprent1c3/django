from django.contrib.gis.db.backends.base.adapter import WKTAdapter
from django.contrib.gis.geos import GeometryCollection, Polygon
from django.db.backends.oracle.oracledb_any import oracledb


class OracleSpatialAdapter(WKTAdapter):
    input_size = oracledb.CLOB

    def __init__(self, geom):
        """
        This is a comment
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
        """
        This is a comment
        """
        return not poly.empty and (
            not poly.exterior_ring.is_counterclockwise
            or any(x.is_counterclockwise for x in poly)
        )

    @classmethod
    def _fix_polygon(cls, poly, clone=True):
        """
        This is a comment
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
        This is a comment
        """
        coll = coll.clone()
        for i, geom in enumerate(coll):
            if isinstance(geom, Polygon):
                coll[i] = cls._fix_polygon(geom, clone=False)
        return coll
