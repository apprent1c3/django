from collections import defaultdict, namedtuple

from django.contrib.gis import forms, gdal
from django.contrib.gis.db.models.proxy import SpatialProxy
from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.geos import (
    GeometryCollection,
    GEOSException,
    GEOSGeometry,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Field
from django.utils.translation import gettext_lazy as _

# Local cache of the spatial_ref_sys table, which holds SRID data for each
# spatial database alias. This cache exists so that the database isn't queried
# for SRID info each time a distance query is constructed.
_srid_cache = defaultdict(dict)


SRIDCacheEntry = namedtuple(
    "SRIDCacheEntry", ["units", "units_name", "spheroid", "geodetic"]
)


def get_srid_info(srid, connection):
    """
    Return spatial reference system information for a given SRID, including units, unit name, and spheroid, from the spatial database table for a specified database connection. The results are cached for efficiency.
    """
    from django.contrib.gis.gdal import SpatialReference

    global _srid_cache

    try:
        # The SpatialRefSys model for the spatial backend.
        SpatialRefSys = connection.ops.spatial_ref_sys()
    except NotImplementedError:
        SpatialRefSys = None

    alias, get_srs = (
        (
            connection.alias,
            lambda srid: SpatialRefSys.objects.using(connection.alias)
            .get(srid=srid)
            .srs,
        )
        if SpatialRefSys
        else (None, SpatialReference)
    )
    if srid not in _srid_cache[alias]:
        srs = get_srs(srid)
        units, units_name = srs.units
        _srid_cache[alias][srid] = SRIDCacheEntry(
            units=units,
            units_name=units_name,
            spheroid='SPHEROID["%s",%s,%s]'
            % (srs["spheroid"], srs.semi_major, srs.inverse_flattening),
            geodetic=srs.geographic,
        )

    return _srid_cache[alias][srid]


class BaseSpatialField(Field):
    """
    The Base GIS Field.

    It's used as a base class for GeometryField and RasterField. Defines
    properties that are common to all GIS fields such as the characteristics
    of the spatial reference system of the field.
    """

    description = _("The base GIS field.")
    empty_strings_allowed = False

    def __init__(self, verbose_name=None, srid=4326, spatial_index=True, **kwargs):
        """
        Initializes a base spatial field with a specified spatial reference system, 
        optionally creating a spatial index. Provides a foundation for geographic field 
        classes, handling spatial index creation and SRID configuration.
        """

        # Setting the index flag with the value of the `spatial_index` keyword.
        self.spatial_index = spatial_index

        # Setting the SRID and getting the units.  Unit information must be
        # easily available in the field instance for distance queries.
        self.srid = srid

        # Setting the verbose_name keyword argument with the positional
        # first parameter, so this works like normal fields.
        kwargs["verbose_name"] = verbose_name

        super().__init__(**kwargs)

    def deconstruct(self):
        """
        .. method:: deconstruct()

           Deconstructs the object into its constituent parts, including the spatial reference system identifier (SRID) and spatial index configuration, for serializing or rebuilding the object elsewhere.
        """
        name, path, args, kwargs = super().deconstruct()
        # Always include SRID for less fragility; include spatial index if it's
        # not the default value.
        kwargs["srid"] = self.srid
        if self.spatial_index is not True:
            kwargs["spatial_index"] = self.spatial_index
        return name, path, args, kwargs

    def db_type(self, connection):
        return connection.ops.geo_db_type(self)

    def spheroid(self, connection):
        return get_srid_info(self.srid, connection).spheroid

    def units(self, connection):
        return get_srid_info(self.srid, connection).units

    def units_name(self, connection):
        return get_srid_info(self.srid, connection).units_name

    def geodetic(self, connection):
        """
        Return true if this field's SRID corresponds with a coordinate
        system that uses non-projected units (e.g., latitude/longitude).
        """
        return get_srid_info(self.srid, connection).geodetic

    def get_placeholder(self, value, compiler, connection):
        """
        Return the placeholder for the spatial column for the
        given value.
        """
        return connection.ops.get_geom_placeholder(self, value, compiler)

    def get_srid(self, obj):
        """
        Determines the Spatial Reference System Identifier (SRID) for a given geometry or raster object, using the object's SRID if set, otherwise defaulting to the SRID of the field.
        """
        srid = obj.srid  # SRID of given geometry.
        if srid is None or self.srid == -1 or (srid == -1 and self.srid != -1):
            return self.srid
        else:
            return srid

    def get_db_prep_value(self, value, connection, *args, **kwargs):
        if value is None:
            return None
        return connection.ops.Adapter(
            super().get_db_prep_value(value, connection, *args, **kwargs),
            **(
                {"geography": True}
                if self.geography and connection.features.supports_geography
                else {}
            ),
        )

    def get_raster_prep_value(self, value, is_candidate):
        """
        Return a GDALRaster object if the provided value can be successfully converted, otherwise return None.
        The function accepts a value and a flag indicating whether it is a candidate for conversion, attempting to create a GDALRaster from the value if necessary.
        """
        if isinstance(value, gdal.GDALRaster):
            return value
        elif is_candidate:
            try:
                return gdal.GDALRaster(value)
            except GDALException:
                pass
        elif isinstance(value, dict):
            try:
                return gdal.GDALRaster(value)
            except GDALException:
                raise ValueError(
                    "Couldn't create spatial object from lookup value '%s'." % value
                )

    def get_prep_value(self, value):
        """
        Prepares a value for spatial lookup by converting it into a GEOSGeometry object if possible.

        The function takes an object of various types, attempts to convert it into a GEOSGeometry object,
        and returns the resulting object with the correct SRID set. If the conversion fails, it raises a ValueError.

        Supports conversion from bytes, strings, and objects with a __geo_interface__ attribute.
        """
        obj = super().get_prep_value(value)
        if obj is None:
            return None
        # When the input is not a geometry or raster, attempt to construct one
        # from the given string input.
        if isinstance(obj, GEOSGeometry):
            pass
        else:
            # Check if input is a candidate for conversion to raster or geometry.
            is_candidate = isinstance(obj, (bytes, str)) or hasattr(
                obj, "__geo_interface__"
            )
            # Try to convert the input to raster.
            raster = self.get_raster_prep_value(obj, is_candidate)

            if raster:
                obj = raster
            elif is_candidate:
                try:
                    obj = GEOSGeometry(obj)
                except (GEOSException, GDALException):
                    raise ValueError(
                        "Couldn't create spatial object from lookup value '%s'." % obj
                    )
            else:
                raise ValueError(
                    "Cannot use object with type %s for a spatial lookup parameter."
                    % type(obj).__name__
                )

        # Assigning the SRID value.
        obj.srid = self.get_srid(obj)
        return obj


class GeometryField(BaseSpatialField):
    """
    The base Geometry field -- maps to the OpenGIS Specification Geometry type.
    """

    description = _(
        "The base Geometry field — maps to the OpenGIS Specification Geometry type."
    )
    form_class = forms.GeometryField
    # The OpenGIS Geometry name.
    geom_type = "GEOMETRY"
    geom_class = None

    def __init__(
        self,
        verbose_name=None,
        dim=2,
        geography=False,
        *,
        extent=(-180.0, -90.0, 180.0, 90.0),
        tolerance=0.05,
        **kwargs,
    ):
        """
        Initializes a geometry field with customizable properties, including dimension, geographic coordinates, and tolerance, to store spatial data.
        """
        # Setting the dimension of the geometry field.
        self.dim = dim

        # Is this a geography rather than a geometry column?
        self.geography = geography

        # Oracle-specific private attributes for creating the entry in
        # `USER_SDO_GEOM_METADATA`
        self._extent = extent
        self._tolerance = tolerance

        super().__init__(verbose_name=verbose_name, **kwargs)

    def deconstruct(self):
        """
        Deconstructs the object into its constituent parts, including name, path, arguments, and keyword arguments, to support serialization or reconstruction. If the object's properties, such as dimension, geography, extent, or tolerance, differ from their default values, they are included in the keyword arguments.
        """
        name, path, args, kwargs = super().deconstruct()
        # Include kwargs if they're not the default values.
        if self.dim != 2:
            kwargs["dim"] = self.dim
        if self.geography is not False:
            kwargs["geography"] = self.geography
        if self._extent != (-180.0, -90.0, 180.0, 90.0):
            kwargs["extent"] = self._extent
        if self._tolerance != 0.05:
            kwargs["tolerance"] = self._tolerance
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, **kwargs)

        # Setup for lazy-instantiated Geometry object.
        setattr(
            cls,
            self.attname,
            SpatialProxy(self.geom_class or GEOSGeometry, self, load_func=GEOSGeometry),
        )

    def formfield(self, **kwargs):
        defaults = {
            "form_class": self.form_class,
            "geom_type": self.geom_type,
            "srid": self.srid,
            **kwargs,
        }
        if self.dim > 2 and not getattr(
            defaults["form_class"].widget, "supports_3d", False
        ):
            defaults.setdefault("widget", forms.Textarea)
        return super().formfield(**defaults)

    def select_format(self, compiler, sql, params):
        """
        Return the selection format string, depending on the requirements
        of the spatial backend. For example, Oracle and MySQL require custom
        selection formats in order to retrieve geometries in OGC WKB.
        """
        if not compiler.query.subquery:
            return compiler.connection.ops.select % sql, params
        return sql, params


# The OpenGIS Geometry Type Fields
class PointField(GeometryField):
    geom_type = "POINT"
    geom_class = Point
    form_class = forms.PointField
    description = _("Point")


class LineStringField(GeometryField):
    geom_type = "LINESTRING"
    geom_class = LineString
    form_class = forms.LineStringField
    description = _("Line string")


class PolygonField(GeometryField):
    geom_type = "POLYGON"
    geom_class = Polygon
    form_class = forms.PolygonField
    description = _("Polygon")


class MultiPointField(GeometryField):
    geom_type = "MULTIPOINT"
    geom_class = MultiPoint
    form_class = forms.MultiPointField
    description = _("Multi-point")


class MultiLineStringField(GeometryField):
    geom_type = "MULTILINESTRING"
    geom_class = MultiLineString
    form_class = forms.MultiLineStringField
    description = _("Multi-line string")


class MultiPolygonField(GeometryField):
    geom_type = "MULTIPOLYGON"
    geom_class = MultiPolygon
    form_class = forms.MultiPolygonField
    description = _("Multi polygon")


class GeometryCollectionField(GeometryField):
    geom_type = "GEOMETRYCOLLECTION"
    geom_class = GeometryCollection
    form_class = forms.GeometryCollectionField
    description = _("Geometry collection")


class ExtentField(Field):
    "Used as a return value from an extent aggregate"

    description = _("Extent Aggregate Field")

    def get_internal_type(self):
        return "ExtentField"

    def select_format(self, compiler, sql, params):
        select = compiler.connection.ops.select_extent
        return select % sql if select else sql, params


class RasterField(BaseSpatialField):
    """
    Raster field for GeoDjango -- evaluates into GDALRaster objects.
    """

    description = _("Raster Field")
    geom_type = "RASTER"
    geography = False

    def _check_connection(self, connection):
        # Make sure raster fields are used only on backends with raster support.
        if (
            not connection.features.gis_enabled
            or not connection.features.supports_raster
        ):
            raise ImproperlyConfigured(
                "Raster fields require backends with raster support."
            )

    def db_type(self, connection):
        self._check_connection(connection)
        return super().db_type(connection)

    def from_db_value(self, value, expression, connection):
        return connection.ops.parse_raster(value)

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, **kwargs)
        # Setup for lazy-instantiated Raster object. For large querysets, the
        # instantiation of all GDALRasters can potentially be expensive. This
        # delays the instantiation of the objects to the moment of evaluation
        # of the raster attribute.
        setattr(cls, self.attname, SpatialProxy(gdal.GDALRaster, self))

    def get_transform(self, name):
        """
        Returns a transformation object for a raster band, where the band can be specified by its index or name. If the provided name is an integer, a transformation for the raster band at that index is returned. Otherwise, the transformation retrieval is delegated to the parent class.
        """
        from django.contrib.gis.db.models.lookups import RasterBandTransform

        try:
            band_index = int(name)
            return type(
                "SpecificRasterBandTransform",
                (RasterBandTransform,),
                {"band_index": band_index},
            )
        except ValueError:
            pass
        return super().get_transform(name)
