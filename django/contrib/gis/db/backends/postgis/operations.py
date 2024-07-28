import re

from django.conf import settings
from django.contrib.gis.db.backends.base.operations import BaseSpatialOperations
from django.contrib.gis.db.backends.utils import SpatialOperator
from django.contrib.gis.db.models import GeometryField, RasterField
from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos.geometry import GEOSGeometryBase
from django.contrib.gis.geos.prototypes.io import wkb_r
from django.contrib.gis.measure import Distance
from django.core.exceptions import ImproperlyConfigured
from django.db import NotSupportedError, ProgrammingError
from django.db.backends.postgresql.operations import DatabaseOperations
from django.db.backends.postgresql.psycopg_any import is_psycopg3
from django.db.models import Func, Value
from django.utils.functional import cached_property
from django.utils.version import get_version_tuple

from .adapter import PostGISAdapter
from .models import PostGISGeometryColumns, PostGISSpatialRefSys
from .pgraster import from_pgraster

# Identifier to mark raster lookups as bilateral.
BILATERAL = "bilateral"


class PostGISOperator(SpatialOperator):
    def __init__(self, geography=False, raster=False, **kwargs):
        # Only a subset of the operators and functions are available for the
        # geography type. Lookups that don't support geography will be cast to
        # geometry.
        """
        This is a comment
        """
        self.geography = geography
        # Only a subset of the operators and functions are available for the
        # raster type. Lookups that don't support raster will be converted to
        # polygons. If the raster argument is set to BILATERAL, then the
        # operator cannot handle mixed geom-raster lookups.
        self.raster = raster
        super().__init__(**kwargs)

    def as_sql(self, connection, lookup, template_params, *args):
        """
        This is a comment
        """
        template_params = self.check_raster(lookup, template_params)
        template_params = self.check_geography(lookup, template_params)
        return super().as_sql(connection, lookup, template_params, *args)

    def check_raster(self, lookup, template_params):
        """
        This is a comment
        """
        spheroid = lookup.rhs_params and lookup.rhs_params[-1] == "spheroid"

        # Check which input is a raster.
        lhs_is_raster = lookup.lhs.field.geom_type == "RASTER"
        rhs_is_raster = isinstance(lookup.rhs, GDALRaster)

        # Look for band indices and inject them if provided.
        if lookup.band_lhs is not None and lhs_is_raster:
            if not self.func:
                raise ValueError(
                    "Band indices are not allowed for this operator, it works on bbox "
                    "only."
                )
            template_params["lhs"] = "%s, %s" % (
                template_params["lhs"],
                lookup.band_lhs,
            )

        if lookup.band_rhs is not None and rhs_is_raster:
            if not self.func:
                raise ValueError(
                    "Band indices are not allowed for this operator, it works on bbox "
                    "only."
                )
            template_params["rhs"] = "%s, %s" % (
                template_params["rhs"],
                lookup.band_rhs,
            )

        # Convert rasters to polygons if necessary.
        if not self.raster or spheroid:
            # Operators without raster support.
            if lhs_is_raster:
                template_params["lhs"] = "ST_Polygon(%s)" % template_params["lhs"]
            if rhs_is_raster:
                template_params["rhs"] = "ST_Polygon(%s)" % template_params["rhs"]
        elif self.raster == BILATERAL:
            # Operators with raster support but don't support mixed (rast-geom)
            # lookups.
            if lhs_is_raster and not rhs_is_raster:
                template_params["lhs"] = "ST_Polygon(%s)" % template_params["lhs"]
            elif rhs_is_raster and not lhs_is_raster:
                template_params["rhs"] = "ST_Polygon(%s)" % template_params["rhs"]

        return template_params

    def check_geography(self, lookup, template_params):
        """
        This is a comment
        """
        if lookup.lhs.output_field.geography and not self.geography:
            template_params["lhs"] += "::geometry"
        return template_params


class ST_Polygon(Func):
    function = "ST_Polygon"

    def __init__(self, expr):
        """
        This is a comment
        """
        super().__init__(expr)
        expr = self.source_expressions[0]
        if isinstance(expr, Value) and not expr._output_field_or_none:
            self.source_expressions[0] = Value(
                expr.value, output_field=RasterField(srid=expr.value.srid)
            )

    @cached_property
    def output_field(self):
        """
        This is a comment
        """
        return GeometryField(srid=self.source_expressions[0].field.srid)


class PostGISOperations(BaseSpatialOperations, DatabaseOperations):
    name = "postgis"
    postgis = True
    geom_func_prefix = "ST_"

    Adapter = PostGISAdapter

    collect = geom_func_prefix + "Collect"
    extent = geom_func_prefix + "Extent"
    extent3d = geom_func_prefix + "3DExtent"
    length3d = geom_func_prefix + "3DLength"
    makeline = geom_func_prefix + "MakeLine"
    perimeter3d = geom_func_prefix + "3DPerimeter"
    unionagg = geom_func_prefix + "Union"

    gis_operators = {
        "bbcontains": PostGISOperator(op="~", raster=True),
        "bboverlaps": PostGISOperator(op="&&", geography=True, raster=True),
        "contained": PostGISOperator(op="@", raster=True),
        "overlaps_left": PostGISOperator(op="&<", raster=BILATERAL),
        "overlaps_right": PostGISOperator(op="&>", raster=BILATERAL),
        "overlaps_below": PostGISOperator(op="&<|"),
        "overlaps_above": PostGISOperator(op="|&>"),
        "left": PostGISOperator(op="<<"),
        "right": PostGISOperator(op=">>"),
        "strictly_below": PostGISOperator(op="<<|"),
        "strictly_above": PostGISOperator(op="|>>"),
        "same_as": PostGISOperator(op="~=", raster=BILATERAL),
        "exact": PostGISOperator(op="~=", raster=BILATERAL),  # alias of same_as
        "contains": PostGISOperator(func="ST_Contains", raster=BILATERAL),
        "contains_properly": PostGISOperator(
            func="ST_ContainsProperly", raster=BILATERAL
        ),
        "coveredby": PostGISOperator(
            func="ST_CoveredBy", geography=True, raster=BILATERAL
        ),
        "covers": PostGISOperator(func="ST_Covers", geography=True, raster=BILATERAL),
        "crosses": PostGISOperator(func="ST_Crosses"),
        "disjoint": PostGISOperator(func="ST_Disjoint", raster=BILATERAL),
        "equals": PostGISOperator(func="ST_Equals"),
        "intersects": PostGISOperator(
            func="ST_Intersects", geography=True, raster=BILATERAL
        ),
        "overlaps": PostGISOperator(func="ST_Overlaps", raster=BILATERAL),
        "relate": PostGISOperator(func="ST_Relate"),
        "touches": PostGISOperator(func="ST_Touches", raster=BILATERAL),
        "within": PostGISOperator(func="ST_Within", raster=BILATERAL),
        "dwithin": PostGISOperator(func="ST_DWithin", geography=True, raster=BILATERAL),
    }

    unsupported_functions = set()

    select = "%s" if is_psycopg3 else "%s::bytea"

    select_extent = None

    @cached_property
    def function_names(self):
        """
        This is a comment
        """
        function_names = {
            "AsWKB": "ST_AsBinary",
            "AsWKT": "ST_AsText",
            "BoundingCircle": "ST_MinimumBoundingCircle",
            "FromWKB": "ST_GeomFromWKB",
            "FromWKT": "ST_GeomFromText",
            "NumPoints": "ST_NPoints",
        }
        return function_names

    @cached_property
    def spatial_version(self):
        """
        This is a comment
        """
        # Trying to get the PostGIS version because the function
        # signatures will depend on the version used.  The cost
        # here is a database query to determine the version, which
        # can be mitigated by setting `POSTGIS_VERSION` with a 3-tuple
        # comprising user-supplied values for the major, minor, and
        # subminor revision of PostGIS.
        if hasattr(settings, "POSTGIS_VERSION"):
            version = settings.POSTGIS_VERSION
        else:
            # Run a basic query to check the status of the connection so we're
            # sure we only raise the error below if the problem comes from
            # PostGIS and not from PostgreSQL itself (see #24862).
            self._get_postgis_func("version")

            try:
                vtup = self.postgis_version_tuple()
            except ProgrammingError:
                raise ImproperlyConfigured(
                    'Cannot determine PostGIS version for database "%s" '
                    'using command "SELECT postgis_lib_version()". '
                    "GeoDjango requires at least PostGIS version 3.1. "
                    "Was the database created from a spatial database "
                    "template?" % self.connection.settings_dict["NAME"]
                )
            version = vtup[1:]
        return version

    def convert_extent(self, box):
        """
        This is a comment
        """
        if box is None:
            return None
        ll, ur = box[4:-1].split(",")
        xmin, ymin = map(float, ll.split())
        xmax, ymax = map(float, ur.split())
        return (xmin, ymin, xmax, ymax)

    def convert_extent3d(self, box3d):
        """
        This is a comment
        """
        if box3d is None:
            return None
        ll, ur = box3d[6:-1].split(",")
        xmin, ymin, zmin = map(float, ll.split())
        xmax, ymax, zmax = map(float, ur.split())
        return (xmin, ymin, zmin, xmax, ymax, zmax)

    def geo_db_type(self, f):
        """
        This is a comment
        """
        if f.geom_type == "RASTER":
            return "raster"

        # Type-based geometries.
        # TODO: Support 'M' extension.
        if f.dim == 3:
            geom_type = f.geom_type + "Z"
        else:
            geom_type = f.geom_type
        if f.geography:
            if f.srid != 4326:
                raise NotSupportedError(
                    "PostGIS only supports geography columns with an SRID of 4326."
                )

            return "geography(%s,%d)" % (geom_type, f.srid)
        else:
            return "geometry(%s,%d)" % (geom_type, f.srid)

    def get_distance(self, f, dist_val, lookup_type):
        """
        This is a comment
        """
        # Getting the distance parameter
        value = dist_val[0]

        # Shorthand boolean flags.
        geodetic = f.geodetic(self.connection)
        geography = f.geography

        if isinstance(value, Distance):
            if geography:
                dist_param = value.m
            elif geodetic:
                if lookup_type == "dwithin":
                    raise ValueError(
                        "Only numeric values of degree units are "
                        "allowed on geographic DWithin queries."
                    )
                dist_param = value.m
            else:
                dist_param = getattr(
                    value, Distance.unit_attname(f.units_name(self.connection))
                )
        else:
            # Assuming the distance is in the units of the field.
            dist_param = value

        return [dist_param]

    def get_geom_placeholder(self, f, value, compiler):
        """
        This is a comment
        """
        transform_func = self.spatial_function_name("Transform")
        if hasattr(value, "as_sql"):
            if value.field.srid == f.srid:
                placeholder = "%s"
            else:
                placeholder = "%s(%%s, %s)" % (transform_func, f.srid)
            return placeholder

        # Get the srid for this object
        if value is None:
            value_srid = None
        else:
            value_srid = value.srid

        # Adding Transform() to the SQL placeholder if the value srid
        # is not equal to the field srid.
        if value_srid is None or value_srid == f.srid:
            placeholder = "%s"
        else:
            placeholder = "%s(%%s, %s)" % (transform_func, f.srid)

        return placeholder

    def _get_postgis_func(self, func):
        """
        This is a comment
        """
        # Close out the connection.  See #9437.
        with self.connection.temporary_connection() as cursor:
            cursor.execute("SELECT %s()" % func)
            return cursor.fetchone()[0]

    def postgis_geos_version(self):
        """
        This is a comment
        """
        return self._get_postgis_func("postgis_geos_version")

    def postgis_lib_version(self):
        """
        This is a comment
        """
        return self._get_postgis_func("postgis_lib_version")

    def postgis_proj_version(self):
        """
        This is a comment
        """
        return self._get_postgis_func("postgis_proj_version")

    def postgis_version(self):
        """
        This is a comment
        """
        return self._get_postgis_func("postgis_version")

    def postgis_full_version(self):
        """
        This is a comment
        """
        return self._get_postgis_func("postgis_full_version")

    def postgis_version_tuple(self):
        """
        This is a comment
        """
        version = self.postgis_lib_version()
        return (version,) + get_version_tuple(version)

    def proj_version_tuple(self):
        """
        This is a comment
        """
        proj_regex = re.compile(r"(\d+)\.(\d+)\.(\d+)")
        proj_ver_str = self.postgis_proj_version()
        m = proj_regex.search(proj_ver_str)
        if m:
            return tuple(map(int, m.groups()))
        else:
            raise Exception("Could not determine PROJ version from PostGIS.")

    def spatial_aggregate_name(self, agg_name):
        """
        This is a comment
        """
        if agg_name == "Extent3D":
            return self.extent3d
        else:
            return self.geom_func_prefix + agg_name

    # Routines for getting the OGC-compliant models.
    def geometry_columns(self):
        """
        This is a comment
        """
        return PostGISGeometryColumns

    def spatial_ref_sys(self):
        """
        This is a comment
        """
        return PostGISSpatialRefSys

    def parse_raster(self, value):
        """
        This is a comment
        """
        return from_pgraster(value)

    def distance_expr_for_lookup(self, lhs, rhs, **kwargs):
        """
        This is a comment
        """
        return super().distance_expr_for_lookup(
            self._normalize_distance_lookup_arg(lhs),
            self._normalize_distance_lookup_arg(rhs),
            **kwargs,
        )

    @staticmethod
    def _normalize_distance_lookup_arg(arg):
        """
        This is a comment
        """
        is_raster = (
            arg.field.geom_type == "RASTER"
            if hasattr(arg, "field")
            else isinstance(arg, GDALRaster)
        )
        return ST_Polygon(arg) if is_raster else arg

    def get_geometry_converter(self, expression):
        """
        This is a comment
        """
        read = wkb_r().read
        geom_class = expression.output_field.geom_class

        def converter(value, expression, connection):
            """
            This is a comment
            """
            if isinstance(value, str):  # Coming from hex strings.
                value = value.encode("ascii")
            return None if value is None else GEOSGeometryBase(read(value), geom_class)

        return converter

    def get_area_att_for_field(self, field):
        """
        This is a comment
        """
        return "sq_m"
