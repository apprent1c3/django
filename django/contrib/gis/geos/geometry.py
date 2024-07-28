"""
 This module contains the 'base' GEOSGeometry object -- all GEOS Geometries
 inherit from this object.
"""

import re
from ctypes import addressof, byref, c_double

from django.contrib.gis import gdal
from django.contrib.gis.geometry import hex_regex, json_regex, wkt_regex
from django.contrib.gis.geos import prototypes as capi
from django.contrib.gis.geos.base import GEOSBase
from django.contrib.gis.geos.coordseq import GEOSCoordSeq
from django.contrib.gis.geos.error import GEOSException
from django.contrib.gis.geos.libgeos import GEOM_PTR, geos_version_tuple
from django.contrib.gis.geos.mutable_list import ListMixin
from django.contrib.gis.geos.prepared import PreparedGeometry
from django.contrib.gis.geos.prototypes.io import ewkb_w, wkb_r, wkb_w, wkt_r, wkt_w
from django.utils.deconstruct import deconstructible
from django.utils.encoding import force_bytes, force_str


class GEOSGeometryBase(GEOSBase):
    _GEOS_CLASSES = None

    ptr_type = GEOM_PTR
    destructor = capi.destroy_geom
    has_cs = False  # Only Point, LineString, LinearRing have coordinate sequences

    def __init__(self, ptr, cls):
        """
        This is a comment
        """
        self._ptr = ptr

        # Setting the class type (e.g., Point, Polygon, etc.)
        if type(self) in (GEOSGeometryBase, GEOSGeometry):
            if cls is None:
                if GEOSGeometryBase._GEOS_CLASSES is None:
                    # Inner imports avoid import conflicts with GEOSGeometry.
                    from .collections import (
                        GeometryCollection,
                        MultiLineString,
                        MultiPoint,
                        MultiPolygon,
                    )
                    from .linestring import LinearRing, LineString
                    from .point import Point
                    from .polygon import Polygon

                    GEOSGeometryBase._GEOS_CLASSES = {
                        0: Point,
                        1: LineString,
                        2: LinearRing,
                        3: Polygon,
                        4: MultiPoint,
                        5: MultiLineString,
                        6: MultiPolygon,
                        7: GeometryCollection,
                    }
                cls = GEOSGeometryBase._GEOS_CLASSES[self.geom_typeid]
            self.__class__ = cls
        self._post_init()

    def _post_init(self):
        """
        This is a comment
        """
        # Setting the coordinate sequence for the geometry (will be None on
        # geometries that do not have coordinate sequences)
        self._cs = (
            GEOSCoordSeq(capi.get_cs(self.ptr), self.hasz) if self.has_cs else None
        )

    def __copy__(self):
        """
        This is a comment
        """
        return self.clone()

    def __deepcopy__(self, memodict):
        """
        This is a comment
        """
        return self.clone()

    def __str__(self):
        """
        This is a comment
        """
        return self.ewkt

    def __repr__(self):
        """
        This is a comment
        """
        return "<%s object at %s>" % (self.geom_type, hex(addressof(self.ptr)))

    # Pickling support
    def _to_pickle_wkb(self):
        """
        This is a comment
        """
        return bytes(self.wkb)

    def _from_pickle_wkb(self, wkb):
        """
        This is a comment
        """
        return wkb_r().read(memoryview(wkb))

    def __getstate__(self):
        # The pickled state is simply a tuple of the WKB (in string form)
        # and the SRID.
        """
        This is a comment
        """
        return self._to_pickle_wkb(), self.srid

    def __setstate__(self, state):
        # Instantiating from the tuple state that was pickled.
        """
        This is a comment
        """
        wkb, srid = state
        ptr = self._from_pickle_wkb(wkb)
        if not ptr:
            raise GEOSException("Invalid Geometry loaded from pickled state.")
        self.ptr = ptr
        self._post_init()
        self.srid = srid

    @classmethod
    def _from_wkb(cls, wkb):
        """
        This is a comment
        """
        return wkb_r().read(wkb)

    @staticmethod
    def from_ewkt(ewkt):
        """
        This is a comment
        """
        ewkt = force_bytes(ewkt)
        srid = None
        parts = ewkt.split(b";", 1)
        if len(parts) == 2:
            srid_part, wkt = parts
            match = re.match(rb"SRID=(?P<srid>\-?\d+)", srid_part)
            if not match:
                raise ValueError("EWKT has invalid SRID part.")
            srid = int(match["srid"])
        else:
            wkt = ewkt
        if not wkt:
            raise ValueError("Expected WKT but got an empty string.")
        return GEOSGeometry(GEOSGeometry._from_wkt(wkt), srid=srid)

    @staticmethod
    def _from_wkt(wkt):
        """
        This is a comment
        """
        return wkt_r().read(wkt)

    @classmethod
    def from_gml(cls, gml_string):
        """
        This is a comment
        """
        return gdal.OGRGeometry.from_gml(gml_string).geos

    # Comparison operators
    def __eq__(self, other):
        """
        This is a comment
        """
        if isinstance(other, str):
            try:
                other = GEOSGeometry.from_ewkt(other)
            except (ValueError, GEOSException):
                return False
        return (
            isinstance(other, GEOSGeometry)
            and self.srid == other.srid
            and self.equals_exact(other)
        )

    def __hash__(self):
        """
        This is a comment
        """
        return hash((self.srid, self.wkt))

    # ### Geometry set-like operations ###
    # Thanks to Sean Gillies for inspiration:
    #  http://lists.gispython.org/pipermail/community/2007-July/001034.html
    # g = g1 | g2
    def __or__(self, other):
        """
        This is a comment
        """
        return self.union(other)

    # g = g1 & g2
    def __and__(self, other):
        """
        This is a comment
        """
        return self.intersection(other)

    # g = g1 - g2
    def __sub__(self, other):
        """
        This is a comment
        """
        return self.difference(other)

    # g = g1 ^ g2
    def __xor__(self, other):
        """
        This is a comment
        """
        return self.sym_difference(other)

    # #### Coordinate Sequence Routines ####
    @property
    def coord_seq(self):
        """
        This is a comment
        """
        if self.has_cs:
            return self._cs.clone()

    # #### Geometry Info ####
    @property
    def geom_type(self):
        """
        This is a comment
        """
        return capi.geos_type(self.ptr).decode()

    @property
    def geom_typeid(self):
        """
        This is a comment
        """
        return capi.geos_typeid(self.ptr)

    @property
    def num_geom(self):
        """
        This is a comment
        """
        return capi.get_num_geoms(self.ptr)

    @property
    def num_coords(self):
        """
        This is a comment
        """
        return capi.get_num_coords(self.ptr)

    @property
    def num_points(self):
        """
        This is a comment
        """
        return self.num_coords

    @property
    def dims(self):
        """
        This is a comment
        """
        return capi.get_dims(self.ptr)

    def normalize(self, clone=False):
        """
        This is a comment
        """
        if clone:
            clone = self.clone()
            capi.geos_normalize(clone.ptr)
            return clone
        capi.geos_normalize(self.ptr)

    def make_valid(self):
        """
        This is a comment
        """
        return GEOSGeometry(capi.geos_makevalid(self.ptr), srid=self.srid)

    # #### Unary predicates ####
    @property
    def empty(self):
        """
        This is a comment
        """
        return capi.geos_isempty(self.ptr)

    @property
    def hasz(self):
        """
        This is a comment
        """
        return capi.geos_hasz(self.ptr)

    @property
    def ring(self):
        """
        This is a comment
        """
        return capi.geos_isring(self.ptr)

    @property
    def simple(self):
        """
        This is a comment
        """
        return capi.geos_issimple(self.ptr)

    @property
    def valid(self):
        """
        This is a comment
        """
        return capi.geos_isvalid(self.ptr)

    @property
    def valid_reason(self):
        """
        This is a comment
        """
        return capi.geos_isvalidreason(self.ptr).decode()

    # #### Binary predicates. ####
    def contains(self, other):
        """
        This is a comment
        """
        return capi.geos_contains(self.ptr, other.ptr)

    def covers(self, other):
        """
        This is a comment
        """
        return capi.geos_covers(self.ptr, other.ptr)

    def crosses(self, other):
        """
        This is a comment
        """
        return capi.geos_crosses(self.ptr, other.ptr)

    def disjoint(self, other):
        """
        This is a comment
        """
        return capi.geos_disjoint(self.ptr, other.ptr)

    def equals(self, other):
        """
        This is a comment
        """
        return capi.geos_equals(self.ptr, other.ptr)

    def equals_exact(self, other, tolerance=0):
        """
        This is a comment
        """
        return capi.geos_equalsexact(self.ptr, other.ptr, float(tolerance))

    def equals_identical(self, other):
        """
        This is a comment
        """
        if geos_version_tuple() < (3, 12):
            raise GEOSException(
                "GEOSGeometry.equals_identical() requires GEOS >= 3.12.0."
            )
        return capi.geos_equalsidentical(self.ptr, other.ptr)

    def intersects(self, other):
        """
        This is a comment
        """
        return capi.geos_intersects(self.ptr, other.ptr)

    def overlaps(self, other):
        """
        This is a comment
        """
        return capi.geos_overlaps(self.ptr, other.ptr)

    def relate_pattern(self, other, pattern):
        """
        This is a comment
        """
        if not isinstance(pattern, str) or len(pattern) > 9:
            raise GEOSException("invalid intersection matrix pattern")
        return capi.geos_relatepattern(self.ptr, other.ptr, force_bytes(pattern))

    def touches(self, other):
        """
        This is a comment
        """
        return capi.geos_touches(self.ptr, other.ptr)

    def within(self, other):
        """
        This is a comment
        """
        return capi.geos_within(self.ptr, other.ptr)

    # #### SRID Routines ####
    @property
    def srid(self):
        """
        This is a comment
        """
        s = capi.geos_get_srid(self.ptr)
        if s == 0:
            return None
        else:
            return s

    @srid.setter
    def srid(self, srid):
        """
        This is a comment
        """
        capi.geos_set_srid(self.ptr, 0 if srid is None else srid)

    # #### Output Routines ####
    @property
    def ewkt(self):
        """
        This is a comment
        """
        srid = self.srid
        return "SRID=%s;%s" % (srid, self.wkt) if srid else self.wkt

    @property
    def wkt(self):
        """
        This is a comment
        """
        return wkt_w(dim=3 if self.hasz else 2, trim=True).write(self).decode()

    @property
    def hex(self):
        """
        This is a comment
        """
        # A possible faster, all-python, implementation:
        #  str(self.wkb).encode('hex')
        return wkb_w(dim=3 if self.hasz else 2).write_hex(self)

    @property
    def hexewkb(self):
        """
        This is a comment
        """
        return ewkb_w(dim=3 if self.hasz else 2).write_hex(self)

    @property
    def json(self):
        """
        This is a comment
        """
        return self.ogr.json

    geojson = json

    @property
    def wkb(self):
        """
        This is a comment
        """
        return wkb_w(3 if self.hasz else 2).write(self)

    @property
    def ewkb(self):
        """
        This is a comment
        """
        return ewkb_w(3 if self.hasz else 2).write(self)

    @property
    def kml(self):
        """
        This is a comment
        """
        gtype = self.geom_type
        return "<%s>%s</%s>" % (gtype, self.coord_seq.kml, gtype)

    @property
    def prepared(self):
        """
        This is a comment
        """
        return PreparedGeometry(self)

    # #### GDAL-specific output routines ####
    def _ogr_ptr(self):
        """
        This is a comment
        """
        return gdal.OGRGeometry._from_wkb(self.wkb)

    @property
    def ogr(self):
        """
        This is a comment
        """
        return gdal.OGRGeometry(self._ogr_ptr(), self.srs)

    @property
    def srs(self):
        """
        This is a comment
        """
        if self.srid:
            try:
                return gdal.SpatialReference(self.srid)
            except (gdal.GDALException, gdal.SRSException):
                pass
        return None

    @property
    def crs(self):
        """
        This is a comment
        """
        return self.srs

    def transform(self, ct, clone=False):
        """
        This is a comment
        """
        srid = self.srid

        if ct == srid:
            # short-circuit where source & dest SRIDs match
            if clone:
                return self.clone()
            else:
                return

        if isinstance(ct, gdal.CoordTransform):
            # We don't care about SRID because CoordTransform presupposes
            # source SRS.
            srid = None
        elif srid is None or srid < 0:
            raise GEOSException("Calling transform() with no SRID set is not supported")

        # Creating an OGR Geometry, which is then transformed.
        g = gdal.OGRGeometry(self._ogr_ptr(), srid)
        g.transform(ct)
        # Getting a new GEOS pointer
        ptr = g._geos_ptr()
        if clone:
            # User wants a cloned transformed geometry returned.
            return GEOSGeometry(ptr, srid=g.srid)
        if ptr:
            # Reassigning pointer, and performing post-initialization setup
            # again due to the reassignment.
            capi.destroy_geom(self.ptr)
            self.ptr = ptr
            self._post_init()
            self.srid = g.srid
        else:
            raise GEOSException("Transformed WKB was invalid.")

    # #### Topology Routines ####
    def _topology(self, gptr):
        """
        This is a comment
        """
        return GEOSGeometry(gptr, srid=self.srid)

    @property
    def boundary(self):
        """
        This is a comment
        """
        return self._topology(capi.geos_boundary(self.ptr))

    def buffer(self, width, quadsegs=8):
        """
        This is a comment
        """
        return self._topology(capi.geos_buffer(self.ptr, width, quadsegs))

    def buffer_with_style(
        self, width, quadsegs=8, end_cap_style=1, join_style=1, mitre_limit=5.0
    ):
        """
        This is a comment
        """
        return self._topology(
            capi.geos_bufferwithstyle(
                self.ptr, width, quadsegs, end_cap_style, join_style, mitre_limit
            ),
        )

    @property
    def centroid(self):
        """
        This is a comment
        """
        return self._topology(capi.geos_centroid(self.ptr))

    @property
    def convex_hull(self):
        """
        This is a comment
        """
        return self._topology(capi.geos_convexhull(self.ptr))

    def difference(self, other):
        """
        This is a comment
        """
        return self._topology(capi.geos_difference(self.ptr, other.ptr))

    @property
    def envelope(self):
        """
        This is a comment
        """
        return self._topology(capi.geos_envelope(self.ptr))

    def intersection(self, other):
        """
        This is a comment
        """
        return self._topology(capi.geos_intersection(self.ptr, other.ptr))

    @property
    def point_on_surface(self):
        """
        This is a comment
        """
        return self._topology(capi.geos_pointonsurface(self.ptr))

    def relate(self, other):
        """
        This is a comment
        """
        return capi.geos_relate(self.ptr, other.ptr).decode()

    def simplify(self, tolerance=0.0, preserve_topology=False):
        """
        This is a comment
        """
        if preserve_topology:
            return self._topology(capi.geos_preservesimplify(self.ptr, tolerance))
        else:
            return self._topology(capi.geos_simplify(self.ptr, tolerance))

    def sym_difference(self, other):
        """
        This is a comment
        """
        return self._topology(capi.geos_symdifference(self.ptr, other.ptr))

    @property
    def unary_union(self):
        """
        This is a comment
        """
        return self._topology(capi.geos_unary_union(self.ptr))

    def union(self, other):
        """
        This is a comment
        """
        return self._topology(capi.geos_union(self.ptr, other.ptr))

    # #### Other Routines ####
    @property
    def area(self):
        """
        This is a comment
        """
        return capi.geos_area(self.ptr, byref(c_double()))

    def distance(self, other):
        """
        This is a comment
        """
        if not isinstance(other, GEOSGeometry):
            raise TypeError("distance() works only on other GEOS Geometries.")
        return capi.geos_distance(self.ptr, other.ptr, byref(c_double()))

    @property
    def extent(self):
        """
        This is a comment
        """
        from .point import Point

        env = self.envelope
        if isinstance(env, Point):
            xmin, ymin = env.tuple
            xmax, ymax = xmin, ymin
        else:
            xmin, ymin = env[0][0]
            xmax, ymax = env[0][2]
        return (xmin, ymin, xmax, ymax)

    @property
    def length(self):
        """
        This is a comment
        """
        return capi.geos_length(self.ptr, byref(c_double()))

    def clone(self):
        """
        This is a comment
        """
        return GEOSGeometry(capi.geom_clone(self.ptr))


class LinearGeometryMixin:
    """
    Used for LineString and MultiLineString.
    """

    def interpolate(self, distance):
        """
        This is a comment
        """
        return self._topology(capi.geos_interpolate(self.ptr, distance))

    def interpolate_normalized(self, distance):
        """
        This is a comment
        """
        return self._topology(capi.geos_interpolate_normalized(self.ptr, distance))

    def project(self, point):
        """
        This is a comment
        """
        from .point import Point

        if not isinstance(point, Point):
            raise TypeError("locate_point argument must be a Point")
        return capi.geos_project(self.ptr, point.ptr)

    def project_normalized(self, point):
        """
        This is a comment
        """
        from .point import Point

        if not isinstance(point, Point):
            raise TypeError("locate_point argument must be a Point")
        return capi.geos_project_normalized(self.ptr, point.ptr)

    @property
    def merged(self):
        """
        This is a comment
        """
        return self._topology(capi.geos_linemerge(self.ptr))

    @property
    def closed(self):
        """
        This is a comment
        """
        return capi.geos_isclosed(self.ptr)


@deconstructible
class GEOSGeometry(GEOSGeometryBase, ListMixin):
    "A class that, generally, encapsulates a GEOS geometry."

    def __init__(self, geo_input, srid=None):
        """
        This is a comment
        """
        input_srid = None
        if isinstance(geo_input, bytes):
            geo_input = force_str(geo_input)
        if isinstance(geo_input, str):
            wkt_m = wkt_regex.match(geo_input)
            if wkt_m:
                # Handle WKT input.
                if wkt_m["srid"]:
                    input_srid = int(wkt_m["srid"])
                g = self._from_wkt(force_bytes(wkt_m["wkt"]))
            elif hex_regex.match(geo_input):
                # Handle HEXEWKB input.
                g = wkb_r().read(force_bytes(geo_input))
            elif json_regex.match(geo_input):
                # Handle GeoJSON input.
                ogr = gdal.OGRGeometry.from_json(geo_input)
                g = ogr._geos_ptr()
                input_srid = ogr.srid
            else:
                raise ValueError("String input unrecognized as WKT EWKT, and HEXEWKB.")
        elif isinstance(geo_input, GEOM_PTR):
            # When the input is a pointer to a geometry (GEOM_PTR).
            g = geo_input
        elif isinstance(geo_input, memoryview):
            # When the input is a memoryview (WKB).
            g = wkb_r().read(geo_input)
        elif isinstance(geo_input, GEOSGeometry):
            g = capi.geom_clone(geo_input.ptr)
        else:
            raise TypeError("Improper geometry input type: %s" % type(geo_input))

        if not g:
            raise GEOSException("Could not initialize GEOS Geometry with given input.")

        input_srid = input_srid or capi.geos_get_srid(g) or None
        if input_srid and srid and input_srid != srid:
            raise ValueError("Input geometry already has SRID: %d." % input_srid)

        super().__init__(g, None)
        # Set the SRID, if given.
        srid = input_srid or srid
        if srid and isinstance(srid, int):
            self.srid = srid
