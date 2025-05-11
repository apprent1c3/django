"""
 This object provides quoting for GEOS geometries into PostgreSQL/PostGIS.
"""

from django.contrib.gis.db.backends.postgis.pgraster import to_pgraster
from django.contrib.gis.geos import GEOSGeometry
from django.db.backends.postgresql.psycopg_any import sql


class PostGISAdapter:
    def __init__(self, obj, geography=False):
        """
        Initializes the spatial object, determining its geometry type and setting its EWKB representation and SRID, with optional geography mode.
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
        Checks if a given protocol conforms to the Psycopg2 SQL quote protocol, returning the object if it does, and raising an exception otherwise, typically indicating that Psycopg2 is not installed.
        """
        from psycopg2.extensions import ISQLQuote

        if proto == ISQLQuote:
            return self
        else:
            raise Exception(
                "Error implementing psycopg2 protocol. Is psycopg2 installed?"
            )

    def __eq__(self, other):
        return isinstance(other, PostGISAdapter) and self.ewkb == other.ewkb

    def __hash__(self):
        return hash(self.ewkb)

    def __str__(self):
        return self.getquoted().decode()

    @classmethod
    def _fix_polygon(cls, poly):
        return poly

    def getquoted(self):
        """
        Return a properly quoted string representation of the object for use in PostgreSQL/PostGIS, handling both geometric and raster data types.
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
