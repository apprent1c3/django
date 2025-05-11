from django.contrib.gis.db import models
from django.contrib.gis.db.backends.base.adapter import WKTAdapter
from django.contrib.gis.db.backends.base.operations import BaseSpatialOperations
from django.contrib.gis.db.backends.utils import SpatialOperator
from django.contrib.gis.geos.geometry import GEOSGeometryBase
from django.contrib.gis.geos.prototypes.io import wkb_r
from django.contrib.gis.measure import Distance
from django.db.backends.mysql.operations import DatabaseOperations
from django.utils.functional import cached_property


class MySQLOperations(BaseSpatialOperations, DatabaseOperations):
    name = "mysql"
    geom_func_prefix = "ST_"

    Adapter = WKTAdapter

    @cached_property
    def mariadb(self):
        return self.connection.mysql_is_mariadb

    @cached_property
    def mysql(self):
        return not self.connection.mysql_is_mariadb

    @cached_property
    def select(self):
        return self.geom_func_prefix + "AsBinary(%s)"

    @cached_property
    def from_text(self):
        return self.geom_func_prefix + "GeomFromText"

    @cached_property
    def collect(self):
        if self.connection.features.supports_collect_aggr:
            return self.geom_func_prefix + "Collect"

    @cached_property
    def gis_operators(self):
        operators = {
            "bbcontains": SpatialOperator(
                func="MBRContains"
            ),  # For consistency w/PostGIS API
            "bboverlaps": SpatialOperator(func="MBROverlaps"),  # ...
            "contained": SpatialOperator(func="MBRWithin"),  # ...
            "contains": SpatialOperator(func="ST_Contains"),
            "crosses": SpatialOperator(func="ST_Crosses"),
            "disjoint": SpatialOperator(func="ST_Disjoint"),
            "equals": SpatialOperator(func="ST_Equals"),
            "exact": SpatialOperator(func="ST_Equals"),
            "intersects": SpatialOperator(func="ST_Intersects"),
            "overlaps": SpatialOperator(func="ST_Overlaps"),
            "same_as": SpatialOperator(func="ST_Equals"),
            "touches": SpatialOperator(func="ST_Touches"),
            "within": SpatialOperator(func="ST_Within"),
        }
        if self.connection.mysql_is_mariadb:
            operators["relate"] = SpatialOperator(func="ST_Relate")
        return operators

    @cached_property
    def disallowed_aggregates(self):
        """
        Returns a tuple of disallowed aggregate models for the current database connection, taking into account the MySQL version and whether it's a MariaDB instance.
        """
        disallowed_aggregates = [
            models.Extent,
            models.Extent3D,
            models.MakeLine,
            models.Union,
        ]
        is_mariadb = self.connection.mysql_is_mariadb
        if is_mariadb or self.connection.mysql_version < (8, 0, 24):
            disallowed_aggregates.insert(0, models.Collect)
        return tuple(disallowed_aggregates)

    function_names = {
        "FromWKB": "ST_GeomFromWKB",
        "FromWKT": "ST_GeomFromText",
    }

    @cached_property
    def unsupported_functions(self):
        """
        Returns a set of unsupported geometric functions for the current database connection, varying depending on whether the connection is to MariaDB or another MySQL variant.
        """
        unsupported = {
            "AsGML",
            "AsKML",
            "AsSVG",
            "Azimuth",
            "BoundingCircle",
            "ClosestPoint",
            "ForcePolygonCW",
            "GeometryDistance",
            "IsEmpty",
            "LineLocatePoint",
            "MakeValid",
            "MemSize",
            "Perimeter",
            "PointOnSurface",
            "Reverse",
            "Scale",
            "SnapToGrid",
            "Transform",
            "Translate",
        }
        if self.connection.mysql_is_mariadb:
            unsupported.remove("PointOnSurface")
            unsupported.update({"GeoHash", "IsValid"})
        return unsupported

    def geo_db_type(self, f):
        return f.geom_type

    def get_distance(self, f, value, lookup_type):
        """
        Obtain a distance parameter for a query, handling both numeric values and Distance objects.

            :param f: The field associated with the distance query.
            :param value: The value to use for distance calculation (must be a numeric or Distance object).
            :param lookup_type: The type of lookup being performed.
            :return: A list containing the distance parameter to use in the query.
        """
        value = value[0]
        if isinstance(value, Distance):
            if f.geodetic(self.connection):
                raise ValueError(
                    "Only numeric values of degree units are allowed on "
                    "geodetic distance queries."
                )
            dist_param = getattr(
                value, Distance.unit_attname(f.units_name(self.connection))
            )
        else:
            dist_param = value
        return [dist_param]

    def get_geometry_converter(self, expression):
        """
        Returns a geometry converter function for the given expression.

        The converter function takes a binary geometric value, constructs a GEOSGeometry 
        object of the correct type, and sets its spatial reference system identifier (SRID) 
        if available.

        :parameter expression: The geometric expression to create a converter for
        :return: A converter function that takes a binary geometric value and returns a 
            GEOSGeometry object
        """
        read = wkb_r().read
        srid = expression.output_field.srid
        if srid == -1:
            srid = None
        geom_class = expression.output_field.geom_class

        def converter(value, expression, connection):
            """
            Convert a geometric value to a GEOSGeometry object.

            Parameters
            ----------
            value : bytes
                Geometric value to convert.
            expression : object
                Expression object (currently unused).
            connection : object
                Database connection object (currently unused).

            Returns
            -------
            GEOSGeometryBase
                Converted geometric object.

            Notes
            -----
            The conversion result is assigned the specified SRID if available.
            """
            if value is not None:
                geom = GEOSGeometryBase(read(memoryview(value)), geom_class)
                if srid:
                    geom.srid = srid
                return geom

        return converter

    def spatial_aggregate_name(self, agg_name):
        return getattr(self, agg_name.lower())
