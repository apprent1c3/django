"""
 This object provides quoting for GEOS geometries into PostgreSQL/PostGIS.
"""

from django.contrib.gis.db.backends.postgis.pgraster import to_pgraster
from django.contrib.gis.geos import GEOSGeometry
from django.db.backends.postgresql.psycopg_any import sql


class PostGISAdapter:
    def __init__(self, obj, geography=False):
        """
        This is a comment
        """
        self.is_geometry = isinstance(obj, (GEOSGeometry, PostGISAdapter))

        # Getting the WKB (in string form, to allow easy pickling of
        # the adaptor) and the SRID from the geometry or raster.
        if self.is_geometry:
            self.ewkb = bytes(obj.ewkb)
        else:
            self.ewkb = to_pgraster(obj)

        self.srid = obj.srid
        self.geography = geography

    def __conform__(self, proto):
        """
        This is a comment
        """
        from psycopg2.extensions import ISQLQuote

        if proto == ISQLQuote:
            return self
        else:
            raise Exception(
                "Error implementing psycopg2 protocol. Is psycopg2 installed?"
            )

    def __eq__(self, other):
        """
        This is a comment
        """
        return isinstance(other, PostGISAdapter) and self.ewkb == other.ewkb

    def __hash__(self):
        """
        This is a comment
        """
        return hash(self.ewkb)

    def __str__(self):
        """
        This is a comment
        """
        return self.getquoted().decode()

    @classmethod
    def _fix_polygon(cls, poly):
        """
        This is a comment
        """
        return poly

    def getquoted(self):
        """
        This is a comment
        """
        if self.is_geometry:
            # Psycopg will figure out whether to use E'\\000' or '\000'.
            return b"%s(%s)" % (
                b"ST_GeogFromWKB" if self.geography else b"ST_GeomFromEWKB",
                sql.quote(self.ewkb).encode(),
            )
        else:
            # For rasters, add explicit type cast to WKB string.
            return b"'%s'::raster" % self.ewkb.hex().encode()
