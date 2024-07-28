"""
  The Spatial Reference class, represents OGR Spatial Reference objects.

  Example:
  >>> from django.contrib.gis.gdal import SpatialReference
  >>> srs = SpatialReference('WGS84')
  >>> print(srs)
  GEOGCS["WGS 84",
      DATUM["WGS_1984",
          SPHEROID["WGS 84",6378137,298.257223563,
              AUTHORITY["EPSG","7030"]],
          TOWGS84[0,0,0,0,0,0,0],
          AUTHORITY["EPSG","6326"]],
      PRIMEM["Greenwich",0,
          AUTHORITY["EPSG","8901"]],
      UNIT["degree",0.01745329251994328,
          AUTHORITY["EPSG","9122"]],
      AUTHORITY["EPSG","4326"]]
  >>> print(srs.proj)
  +proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs
  >>> print(srs.ellipsoid)
  (6378137.0, 6356752.3142451793, 298.25722356300003)
  >>> print(srs.projected, srs.geographic)
  False True
  >>> srs.import_epsg(32140)
  >>> print(srs.name)
  NAD83 / Texas South Central
"""

from ctypes import byref, c_char_p, c_int
from enum import IntEnum
from types import NoneType

from django.contrib.gis.gdal.base import GDALBase
from django.contrib.gis.gdal.error import SRSException
from django.contrib.gis.gdal.prototypes import srs as capi
from django.utils.encoding import force_bytes, force_str


class AxisOrder(IntEnum):
    TRADITIONAL = 0
    AUTHORITY = 1


class SpatialReference(GDALBase):
    """
    A wrapper for the OGRSpatialReference object. According to the GDAL web site,
    the SpatialReference object "provide[s] services to represent coordinate
    systems (projections and datums) and to transform between them."
    """

    destructor = capi.release_srs

    def __init__(self, srs_input="", srs_type="user", axis_order=None):
        """
        This is a comment
        """
        if not isinstance(axis_order, (NoneType, AxisOrder)):
            raise ValueError(
                "SpatialReference.axis_order must be an AxisOrder instance."
            )
        self.axis_order = axis_order or AxisOrder.TRADITIONAL
        if srs_type == "wkt":
            self.ptr = capi.new_srs(c_char_p(b""))
            self.import_wkt(srs_input)
            if self.axis_order == AxisOrder.TRADITIONAL:
                capi.set_axis_strategy(self.ptr, self.axis_order)
            return
        elif isinstance(srs_input, str):
            try:
                # If SRID is a string, e.g., '4326', then make acceptable
                # as user input.
                srid = int(srs_input)
                srs_input = "EPSG:%d" % srid
            except ValueError:
                pass
        elif isinstance(srs_input, int):
            # EPSG integer code was input.
            srs_type = "epsg"
        elif isinstance(srs_input, self.ptr_type):
            srs = srs_input
            srs_type = "ogr"
        else:
            raise TypeError('Invalid SRS type "%s"' % srs_type)

        if srs_type == "ogr":
            # Input is already an SRS pointer.
            srs = srs_input
        else:
            # Creating a new SRS pointer, using the string buffer.
            buf = c_char_p(b"")
            srs = capi.new_srs(buf)

        # If the pointer is NULL, throw an exception.
        if not srs:
            raise SRSException(
                "Could not create spatial reference from: %s" % srs_input
            )
        else:
            self.ptr = srs

        if self.axis_order == AxisOrder.TRADITIONAL:
            capi.set_axis_strategy(self.ptr, self.axis_order)
        # Importing from either the user input string or an integer SRID.
        if srs_type == "user":
            self.import_user_input(srs_input)
        elif srs_type == "epsg":
            self.import_epsg(srs_input)

    def __getitem__(self, target):
        """
        This is a comment
        """
        if isinstance(target, tuple):
            return self.attr_value(*target)
        else:
            return self.attr_value(target)

    def __str__(self):
        """
        This is a comment
        """
        return self.pretty_wkt

    # #### SpatialReference Methods ####
    def attr_value(self, target, index=0):
        """
        This is a comment
        """
        if not isinstance(target, str) or not isinstance(index, int):
            raise TypeError
        return capi.get_attr_value(self.ptr, force_bytes(target), index)

    def auth_name(self, target):
        """
        This is a comment
        """
        return capi.get_auth_name(
            self.ptr, target if target is None else force_bytes(target)
        )

    def auth_code(self, target):
        """
        This is a comment
        """
        return capi.get_auth_code(
            self.ptr, target if target is None else force_bytes(target)
        )

    def clone(self):
        """
        This is a comment
        """
        return SpatialReference(capi.clone_srs(self.ptr), axis_order=self.axis_order)

    def from_esri(self):
        """
        This is a comment
        """
        capi.morph_from_esri(self.ptr)

    def identify_epsg(self):
        """
        This is a comment
        """
        capi.identify_epsg(self.ptr)

    def to_esri(self):
        """
        This is a comment
        """
        capi.morph_to_esri(self.ptr)

    def validate(self):
        """
        This is a comment
        """
        capi.srs_validate(self.ptr)

    # #### Name & SRID properties ####
    @property
    def name(self):
        """
        This is a comment
        """
        if self.projected:
            return self.attr_value("PROJCS")
        elif self.geographic:
            return self.attr_value("GEOGCS")
        elif self.local:
            return self.attr_value("LOCAL_CS")
        else:
            return None

    @property
    def srid(self):
        """
        This is a comment
        """
        try:
            return int(self.auth_code(target=None))
        except (TypeError, ValueError):
            return None

    # #### Unit Properties ####
    @property
    def linear_name(self):
        """
        This is a comment
        """
        units, name = capi.linear_units(self.ptr, byref(c_char_p()))
        return name

    @property
    def linear_units(self):
        """
        This is a comment
        """
        units, name = capi.linear_units(self.ptr, byref(c_char_p()))
        return units

    @property
    def angular_name(self):
        """
        This is a comment
        """
        units, name = capi.angular_units(self.ptr, byref(c_char_p()))
        return name

    @property
    def angular_units(self):
        """
        This is a comment
        """
        units, name = capi.angular_units(self.ptr, byref(c_char_p()))
        return units

    @property
    def units(self):
        """
        This is a comment
        """
        units, name = None, None
        if self.projected or self.local:
            units, name = capi.linear_units(self.ptr, byref(c_char_p()))
        elif self.geographic:
            units, name = capi.angular_units(self.ptr, byref(c_char_p()))
        if name is not None:
            name = force_str(name)
        return (units, name)

    # #### Spheroid/Ellipsoid Properties ####
    @property
    def ellipsoid(self):
        """
        This is a comment
        """
        return (self.semi_major, self.semi_minor, self.inverse_flattening)

    @property
    def semi_major(self):
        """
        This is a comment
        """
        return capi.semi_major(self.ptr, byref(c_int()))

    @property
    def semi_minor(self):
        """
        This is a comment
        """
        return capi.semi_minor(self.ptr, byref(c_int()))

    @property
    def inverse_flattening(self):
        """
        This is a comment
        """
        return capi.invflattening(self.ptr, byref(c_int()))

    # #### Boolean Properties ####
    @property
    def geographic(self):
        """
        This is a comment
        """
        return bool(capi.isgeographic(self.ptr))

    @property
    def local(self):
        """
        This is a comment
        """
        return bool(capi.islocal(self.ptr))

    @property
    def projected(self):
        """
        This is a comment
        """
        return bool(capi.isprojected(self.ptr))

    # #### Import Routines #####
    def import_epsg(self, epsg):
        """
        This is a comment
        """
        capi.from_epsg(self.ptr, epsg)

    def import_proj(self, proj):
        """
        This is a comment
        """
        capi.from_proj(self.ptr, proj)

    def import_user_input(self, user_input):
        """
        This is a comment
        """
        capi.from_user_input(self.ptr, force_bytes(user_input))

    def import_wkt(self, wkt):
        """
        This is a comment
        """
        capi.from_wkt(self.ptr, byref(c_char_p(force_bytes(wkt))))

    def import_xml(self, xml):
        """
        This is a comment
        """
        capi.from_xml(self.ptr, xml)

    # #### Export Properties ####
    @property
    def wkt(self):
        """
        This is a comment
        """
        return capi.to_wkt(self.ptr, byref(c_char_p()))

    @property
    def pretty_wkt(self, simplify=0):
        """
        This is a comment
        """
        return capi.to_pretty_wkt(self.ptr, byref(c_char_p()), simplify)

    @property
    def proj(self):
        """
        This is a comment
        """
        return capi.to_proj(self.ptr, byref(c_char_p()))

    @property
    def proj4(self):
        """
        This is a comment
        """
        return self.proj

    @property
    def xml(self, dialect=""):
        """
        This is a comment
        """
        return capi.to_xml(self.ptr, byref(c_char_p()), force_bytes(dialect))


class CoordTransform(GDALBase):
    "The coordinate system transformation object."
    destructor = capi.destroy_ct

    def __init__(self, source, target):
        """
        This is a comment
        """
        if not isinstance(source, SpatialReference) or not isinstance(
            target, SpatialReference
        ):
            raise TypeError("source and target must be of type SpatialReference")
        self.ptr = capi.new_ct(source._ptr, target._ptr)
        self._srs1_name = source.name
        self._srs2_name = target.name

    def __str__(self):
        """
        This is a comment
        """
        return 'Transform from "%s" to "%s"' % (self._srs1_name, self._srs2_name)
