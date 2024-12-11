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
    Return the units, unit name, and spheroid WKT associated with the
    given SRID from the `spatial_ref_sys` (or equivalent) spatial database
    table for the given database connection.  These results are cached.
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
        The initialization function for base spatial fields. Takes the following
        as keyword arguments:

        srid:
         The spatial reference system identifier, an OGC standard.
         Defaults to 4326 (WGS84).

        spatial_index:
         Indicates whether to create a spatial index.  Defaults to True.
         Set this instead of 'db_index' for geographic fields since index
         creation is different for geometry columns.
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
        Return the default SRID for the given geometry or raster, taking into
        account the SRID set for the field. For example, if the input geometry
        or raster doesn't have an SRID, then the SRID of the field will be
        returned.
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
        Return a GDALRaster if conversion is successful, otherwise return None.
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
        Get the prepared geometric value for a given object, converting it to a standard format if necessary.

        This method takes an input value and checks if it can be used for spatial lookups.
        It supports various input types, including GEOSGeometry objects, strings, bytes, and objects that implement the __geo_interface__.
        If the input is not already in the correct format, it attempts to convert it to a GEOSGeometry object.
        The method also ensures that the resulting object has a valid spatial reference system (SRS) identifier.
        If the conversion fails, a ValueError is raised with a descriptive error message.

        The returned object is guaranteed to be a valid geometric object with a specified SRS identifier, or None if the input was None.
        The method is intended for use in spatial database operations and provides a convenient way to prepare input data for geographic queries.
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
        The initialization function for geometry fields. In addition to the
        parameters from BaseSpatialField, it takes the following as keyword
        arguments:

        dim:
         The number of dimensions for this geometry.  Defaults to 2.

        extent:
         Customize the extent, in a 4-tuple of WGS 84 coordinates, for the
         geometry field entry in the `USER_SDO_GEOM_METADATA` table.  Defaults
         to (-180.0, -90.0, 180.0, 90.0).

        tolerance:
         Define the tolerance, in meters, to use for the geometry field
         entry in the `USER_SDO_GEOM_METADATA` table.  Defaults to 0.05.
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
        Deconstructs the object into its constituent parts to facilitate serialization or other forms of reconstruction.

        The deconstruction process involves breaking down the object into its name, path, arguments, and keyword arguments. Specifically, it captures and includes any non-default values for the object's dimensionality, geographic settings, spatial extent, and tolerance.

        Returns a tuple containing the object's name, path, positional arguments, and keyword arguments, which can be used to recreate the object or store its configuration.
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
        """
        Contributes the spatial field to the model class, providing a proxy object for accessing and manipulating geometric data.

        The proxy object, accessible via the attribute name specified by :attr:`attname`, allows for loading and manipulation of geometric data using the :class:`GEOSGeometry` class.

        Bydefault, the :class:`GEOSGeometry` class is used for loading geometric data. However, a custom geometry class can be specified via the :attr:`geom_class` attribute.

        Parameters
        ----------
        cls : class
            The model class being contributed to.
        name : str
            The name of the field being contributed.
        **kwargs
            Additional keyword arguments passed to the superclass's contribute_to_class method.

        Returns
        -------
        None
            The proxy object is set as an attribute on the model class.
        """
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
        """

        Returns a formatted SQL query string with optional extent specification.

        This function takes a database compiler, an SQL query, and query parameters as input.
        It checks if the database connection supports extent specification, and if so,
        it appends the extent to the SQL query. The formatted query string and the original
        parameters are then returned as a tuple.

        The extent specification is typically used to define the scope of the query,
        such as the table or database to query. If the database connection does not
        support extent specification, the original SQL query is returned unchanged.

        :return: A tuple containing the formatted SQL query string and the query parameters.

        """
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
        """

        Registers the spatial field with the given model class.

        This method integrates the spatial field with the specified class, 
        enabling spatial functionality. It sets up a proxy object to manage 
        the spatial data, utilizing the GDALRaster type from the GDAL library.

        :param cls: The model class to integrate the spatial field with.
        :param name: The name of the spatial field.
        :param kwargs: Additional keyword arguments.

        """
        super().contribute_to_class(cls, name, **kwargs)
        # Setup for lazy-instantiated Raster object. For large querysets, the
        # instantiation of all GDALRasters can potentially be expensive. This
        # delays the instantiation of the objects to the moment of evaluation
        # of the raster attribute.
        setattr(cls, self.attname, SpatialProxy(gdal.GDALRaster, self))

    def get_transform(self, name):
        """

        Returns a transform object for a given raster band.

        The transform object is created based on the provided name. If the name can be
        converted to an integer, it is treated as a band index and a new transform object
        with that band index is returned. Otherwise, the parent class's get_transform
        method is called to handle the name.

        This allows for easy transformation of raster bands by their index, and also
        falls back to the default behavior for other types of transforms.

        :param name: The name of the transform, which can be either an integer band index
                     or another type of transform name.
        :rtype: A transform object, specifically a RasterBandTransform subclass or the
                result of the parent class's get_transform method.

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
