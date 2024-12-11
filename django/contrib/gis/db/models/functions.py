from decimal import Decimal

from django.contrib.gis.db.models.fields import BaseSpatialField, GeometryField
from django.contrib.gis.db.models.sql import AreaField, DistanceField
from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import FieldError
from django.db import NotSupportedError
from django.db.models import (
    BinaryField,
    BooleanField,
    FloatField,
    Func,
    IntegerField,
    TextField,
    Transform,
    Value,
)
from django.db.models.functions import Cast
from django.utils.functional import cached_property

NUMERIC_TYPES = (int, float, Decimal)


class GeoFuncMixin:
    function = None
    geom_param_pos = (0,)

    def __init__(self, *expressions, **extra):
        super().__init__(*expressions, **extra)

        # Ensure that value expressions are geometric.
        for pos in self.geom_param_pos:
            expr = self.source_expressions[pos]
            if not isinstance(expr, Value):
                continue
            try:
                output_field = expr.output_field
            except FieldError:
                output_field = None
            geom = expr.value
            if (
                not isinstance(geom, GEOSGeometry)
                or output_field
                and not isinstance(output_field, GeometryField)
            ):
                raise TypeError(
                    "%s function requires a geometric argument in position %d."
                    % (self.name, pos + 1)
                )
            if not geom.srid and not output_field:
                raise ValueError("SRID is required for all geometries.")
            if not output_field:
                self.source_expressions[pos] = Value(
                    geom, output_field=GeometryField(srid=geom.srid)
                )

    @property
    def name(self):
        return self.__class__.__name__

    @cached_property
    def geo_field(self):
        return self.source_expressions[self.geom_param_pos[0]].field

    def as_sql(self, compiler, connection, function=None, **extra_context):
        if self.function is None and function is None:
            function = connection.ops.spatial_function_name(self.name)
        return super().as_sql(compiler, connection, function=function, **extra_context)

    def resolve_expression(self, *args, **kwargs):
        res = super().resolve_expression(*args, **kwargs)
        if not self.geom_param_pos:
            return res

        # Ensure that expressions are geometric.
        source_fields = res.get_source_fields()
        for pos in self.geom_param_pos:
            field = source_fields[pos]
            if not isinstance(field, GeometryField):
                raise TypeError(
                    "%s function requires a GeometryField in position %s, got %s."
                    % (
                        self.name,
                        pos + 1,
                        type(field).__name__,
                    )
                )

        base_srid = res.geo_field.srid
        for pos in self.geom_param_pos[1:]:
            expr = res.source_expressions[pos]
            expr_srid = expr.output_field.srid
            if expr_srid != base_srid:
                # Automatic SRID conversion so objects are comparable.
                res.source_expressions[pos] = Transform(
                    expr, base_srid
                ).resolve_expression(*args, **kwargs)
        return res

    def _handle_param(self, value, param_name="", check_types=None):
        if not hasattr(value, "resolve_expression"):
            if check_types and not isinstance(value, check_types):
                raise TypeError(
                    "The %s parameter has the wrong type: should be %s."
                    % (param_name, check_types)
                )
        return value


class GeoFunc(GeoFuncMixin, Func):
    pass


class GeomOutputGeoFunc(GeoFunc):
    @cached_property
    def output_field(self):
        return GeometryField(srid=self.geo_field.srid)


class SQLiteDecimalToFloatMixin:
    """
    By default, Decimal values are converted to str by the SQLite backend, which
    is not acceptable by the GIS functions expecting numeric values.
    """

    def as_sqlite(self, compiler, connection, **extra_context):
        copy = self.copy()
        copy.set_source_expressions(
            [
                (
                    Value(float(expr.value))
                    if hasattr(expr, "value") and isinstance(expr.value, Decimal)
                    else expr
                )
                for expr in copy.get_source_expressions()
            ]
        )
        return copy.as_sql(compiler, connection, **extra_context)


class OracleToleranceMixin:
    tolerance = 0.05

    def as_oracle(self, compiler, connection, **extra_context):
        tolerance = Value(
            self._handle_param(
                self.extra.get("tolerance", self.tolerance),
                "tolerance",
                NUMERIC_TYPES,
            )
        )
        clone = self.copy()
        clone.set_source_expressions([*self.get_source_expressions(), tolerance])
        return clone.as_sql(compiler, connection, **extra_context)


class Area(OracleToleranceMixin, GeoFunc):
    arity = 1

    @cached_property
    def output_field(self):
        return AreaField(self.geo_field)

    def as_sql(self, compiler, connection, **extra_context):
        if not connection.features.supports_area_geodetic and self.geo_field.geodetic(
            connection
        ):
            raise NotSupportedError(
                "Area on geodetic coordinate systems not supported."
            )
        return super().as_sql(compiler, connection, **extra_context)

    def as_sqlite(self, compiler, connection, **extra_context):
        if self.geo_field.geodetic(connection):
            extra_context["template"] = "%(function)s(%(expressions)s, %(spheroid)d)"
            extra_context["spheroid"] = True
        return self.as_sql(compiler, connection, **extra_context)


class Azimuth(GeoFunc):
    output_field = FloatField()
    arity = 2
    geom_param_pos = (0, 1)


class AsGeoJSON(GeoFunc):
    output_field = TextField()

    def __init__(self, expression, bbox=False, crs=False, precision=8, **extra):
        """

        Initializes an object with a spatial expression and additional parameters for bounding box and coordinate reference system.

        The initialization process takes in an expression, and optional parameters for including a bounding box, a coordinate reference system, and the precision of the output.

        Parameters
        ----------
        expression : str
            The spatial expression to be evaluated.
        bbox : bool, optional
            If True, include a bounding box in the output (default is False).
        crs : bool, optional
            If True, include a coordinate reference system in the output (default is False).
        precision : int, optional
            The precision of the output (default is 8).

        Additional keyword arguments (**extra) can be passed to the parent class's initializer.

        The object is then initialized with the provided expression, precision (if specified), and a set of options that determine the inclusion of the bounding box and coordinate reference system in the output.

        """
        expressions = [expression]
        if precision is not None:
            expressions.append(self._handle_param(precision, "precision", int))
        options = 0
        if crs and bbox:
            options = 3
        elif bbox:
            options = 1
        elif crs:
            options = 2
        expressions.append(options)
        super().__init__(*expressions, **extra)

    def as_oracle(self, compiler, connection, **extra_context):
        """

        Return the SQL representation of this AsGeoJSON object, formatted as an Oracle database query.

        The function generates a SQL string by copying the current AsGeoJSON object, 
        modifying its source expressions to only include the first expression, 
        and then using the parent class's as_sql method to generate the SQL string.

        This allows the resulting SQL query to be compatible with Oracle syntax.

        """
        source_expressions = self.get_source_expressions()
        clone = self.copy()
        clone.set_source_expressions(source_expressions[:1])
        return super(AsGeoJSON, clone).as_sql(compiler, connection, **extra_context)


class AsGML(GeoFunc):
    geom_param_pos = (1,)
    output_field = TextField()

    def __init__(self, expression, version=2, precision=8, **extra):
        expressions = [version, expression]
        if precision is not None:
            expressions.append(self._handle_param(precision, "precision", int))
        super().__init__(*expressions, **extra)

    def as_oracle(self, compiler, connection, **extra_context):
        """
        .. method:: as_oracle(self, compiler, connection, **extra_context)
            :noindex:

            Compile the AsGML SQL expression for an Oracle database.

            This method adapts the AsGML expression to the Oracle database dialect, 
            specifically generating a SQL statement using the SDO_UTIL.TO_GMLGEOMETRY or 
            SDO_UTIL.TO_GML311GEOMETRY function depending on the geometry version.

            It returns the compiled SQL expression as a string, incorporating any 
            additional context provided through the **extra_context parameter.

            :param compiler: The SQL compiler to use for the compilation process.
            :param connection: The database connection to use for compilation.
            :param extra_context: Additional context to incorporate into the compilation 
                                  process.
            :return: The compiled SQL expression as a string.
        """
        source_expressions = self.get_source_expressions()
        version = source_expressions[0]
        clone = self.copy()
        clone.set_source_expressions([source_expressions[1]])
        extra_context["function"] = (
            "SDO_UTIL.TO_GML311GEOMETRY"
            if version.value == 3
            else "SDO_UTIL.TO_GMLGEOMETRY"
        )
        return super(AsGML, clone).as_sql(compiler, connection, **extra_context)


class AsKML(GeoFunc):
    output_field = TextField()

    def __init__(self, expression, precision=8, **extra):
        """

        Initializes the object with a given mathematical expression and optional precision.

        The expression is the core component that will be used by the object.
        The precision parameter (defaulting to 8) controls the level of detail or rounding applied to the expression.
        Any additional keyword arguments are passed to the parent class for further initialization.

        :param expression: The mathematical expression to be used by the object.
        :param precision: The desired level of precision, defaults to 8.

        """
        expressions = [expression]
        if precision is not None:
            expressions.append(self._handle_param(precision, "precision", int))
        super().__init__(*expressions, **extra)


class AsSVG(GeoFunc):
    output_field = TextField()

    def __init__(self, expression, relative=False, precision=8, **extra):
        """

        Initialize the object with a mathematical expression, relative comparison option, and precision setting.

        The expression is the primary input to be evaluated. The relative parameter determines whether the comparison is relative or absolute.
        If relative is provided as a boolean value, it will be converted to an integer. Alternatively, it can be an object with a resolve_expression method.

        The precision parameter sets the number of decimal places to consider during calculations, defaulting to 8 if not specified.

        Additional keyword arguments can be passed via the extra parameter to further customize the object's initialization.

        """
        relative = (
            relative if hasattr(relative, "resolve_expression") else int(relative)
        )
        expressions = [
            expression,
            relative,
            self._handle_param(precision, "precision", int),
        ]
        super().__init__(*expressions, **extra)


class AsWKB(GeoFunc):
    output_field = BinaryField()
    arity = 1


class AsWKT(GeoFunc):
    output_field = TextField()
    arity = 1


class BoundingCircle(OracleToleranceMixin, GeomOutputGeoFunc):
    def __init__(self, expression, num_seg=48, **extra):
        super().__init__(expression, num_seg, **extra)

    def as_oracle(self, compiler, connection, **extra_context):
        clone = self.copy()
        clone.set_source_expressions([self.get_source_expressions()[0]])
        return super(BoundingCircle, clone).as_oracle(
            compiler, connection, **extra_context
        )

    def as_sqlite(self, compiler, connection, **extra_context):
        clone = self.copy()
        clone.set_source_expressions([self.get_source_expressions()[0]])
        return super(BoundingCircle, clone).as_sqlite(
            compiler, connection, **extra_context
        )


class Centroid(OracleToleranceMixin, GeomOutputGeoFunc):
    arity = 1


class ClosestPoint(GeomOutputGeoFunc):
    arity = 2
    geom_param_pos = (0, 1)


class Difference(OracleToleranceMixin, GeomOutputGeoFunc):
    arity = 2
    geom_param_pos = (0, 1)


class DistanceResultMixin:
    @cached_property
    def output_field(self):
        return DistanceField(self.geo_field)

    def source_is_geography(self):
        return self.geo_field.geography and self.geo_field.srid == 4326


class Distance(DistanceResultMixin, OracleToleranceMixin, GeoFunc):
    geom_param_pos = (0, 1)
    spheroid = None

    def __init__(self, expr1, expr2, spheroid=None, **extra):
        expressions = [expr1, expr2]
        if spheroid is not None:
            self.spheroid = self._handle_param(spheroid, "spheroid", bool)
        super().__init__(*expressions, **extra)

    def as_postgresql(self, compiler, connection, **extra_context):
        clone = self.copy()
        function = None
        expr2 = clone.source_expressions[1]
        geography = self.source_is_geography()
        if expr2.output_field.geography != geography:
            if isinstance(expr2, Value):
                expr2.output_field.geography = geography
            else:
                clone.source_expressions[1] = Cast(
                    expr2,
                    GeometryField(srid=expr2.output_field.srid, geography=geography),
                )

        if not geography and self.geo_field.geodetic(connection):
            # Geometry fields with geodetic (lon/lat) coordinates need special
            # distance functions.
            if self.spheroid:
                # DistanceSpheroid is more accurate and resource intensive than
                # DistanceSphere.
                function = connection.ops.spatial_function_name("DistanceSpheroid")
                # Replace boolean param by the real spheroid of the base field
                clone.source_expressions.append(
                    Value(self.geo_field.spheroid(connection))
                )
            else:
                function = connection.ops.spatial_function_name("DistanceSphere")
        return super(Distance, clone).as_sql(
            compiler, connection, function=function, **extra_context
        )

    def as_sqlite(self, compiler, connection, **extra_context):
        """
        Converts the expression to an SQLite-compatible SQL string.

        This method takes into account the geodetic nature of the field and adjusts the SQL
        template accordingly. If the field is geodetic, it uses the COALESCE function to
        handle cases where the expression evaluates to null, and includes the spheroid
        parameter if it is specified. The generated SQL string is then passed to the
        parent class for further processing.

        :param compiler: The SQL compiler object.
        :param connection: The database connection object.
        :param extra_context: Additional context parameters.
        :return: The SQLite-compatible SQL string representation of the expression.
        """
        if self.geo_field.geodetic(connection):
            # SpatiaLite returns NULL instead of zero on geodetic coordinates
            extra_context["template"] = (
                "COALESCE(%(function)s(%(expressions)s, %(spheroid)s), 0)"
            )
            extra_context["spheroid"] = int(bool(self.spheroid))
        return super().as_sql(compiler, connection, **extra_context)


class Envelope(GeomOutputGeoFunc):
    arity = 1


class ForcePolygonCW(GeomOutputGeoFunc):
    arity = 1


class FromWKB(GeoFunc):
    arity = 2
    geom_param_pos = ()

    def __init__(self, expression, srid=0, **extra):
        expressions = [
            expression,
            self._handle_param(srid, "srid", int),
        ]
        if "output_field" not in extra:
            extra["output_field"] = GeometryField(srid=srid)
        super().__init__(*expressions, **extra)

    def as_oracle(self, compiler, connection, **extra_context):
        # Oracle doesn't support the srid parameter.
        source_expressions = self.get_source_expressions()
        clone = self.copy()
        clone.set_source_expressions(source_expressions[:1])
        return super(FromWKB, clone).as_sql(compiler, connection, **extra_context)


class FromWKT(FromWKB):
    pass


class GeoHash(GeoFunc):
    output_field = TextField()

    def __init__(self, expression, precision=None, **extra):
        """
        Initializes a new instance of the class, setting up the expression and optional precision.

        :param expression: The expression to be used by the instance.
        :param precision: The precision to be applied, defaults to None.
        :param extra: Additional keyword arguments to be passed to the parent class.

        The precision is processed and converted to an integer, if provided. The instance is then initialized with the expression and precision, using the parent class's initialization method.
        """
        expressions = [expression]
        if precision is not None:
            expressions.append(self._handle_param(precision, "precision", int))
        super().__init__(*expressions, **extra)

    def as_mysql(self, compiler, connection, **extra_context):
        clone = self.copy()
        # If no precision is provided, set it to the maximum.
        if len(clone.source_expressions) < 2:
            clone.source_expressions.append(Value(100))
        return clone.as_sql(compiler, connection, **extra_context)


class GeometryDistance(GeoFunc):
    output_field = FloatField()
    arity = 2
    function = ""
    arg_joiner = " <-> "
    geom_param_pos = (0, 1)


class Intersection(OracleToleranceMixin, GeomOutputGeoFunc):
    arity = 2
    geom_param_pos = (0, 1)


@BaseSpatialField.register_lookup
class IsEmpty(GeoFuncMixin, Transform):
    lookup_name = "isempty"
    output_field = BooleanField()


@BaseSpatialField.register_lookup
class IsValid(OracleToleranceMixin, GeoFuncMixin, Transform):
    lookup_name = "isvalid"
    output_field = BooleanField()

    def as_oracle(self, compiler, connection, **extra_context):
        sql, params = super().as_oracle(compiler, connection, **extra_context)
        return "CASE %s WHEN 'TRUE' THEN 1 ELSE 0 END" % sql, params


class Length(DistanceResultMixin, OracleToleranceMixin, GeoFunc):
    def __init__(self, expr1, spheroid=True, **extra):
        self.spheroid = spheroid
        super().__init__(expr1, **extra)

    def as_sql(self, compiler, connection, **extra_context):
        if (
            self.geo_field.geodetic(connection)
            and not connection.features.supports_length_geodetic
        ):
            raise NotSupportedError(
                "This backend doesn't support Length on geodetic fields"
            )
        return super().as_sql(compiler, connection, **extra_context)

    def as_postgresql(self, compiler, connection, **extra_context):
        clone = self.copy()
        function = None
        if self.source_is_geography():
            clone.source_expressions.append(Value(self.spheroid))
        elif self.geo_field.geodetic(connection):
            # Geometry fields with geodetic (lon/lat) coordinates need length_spheroid
            function = connection.ops.spatial_function_name("LengthSpheroid")
            clone.source_expressions.append(Value(self.geo_field.spheroid(connection)))
        else:
            dim = min(f.dim for f in self.get_source_fields() if f)
            if dim > 2:
                function = connection.ops.length3d
        return super(Length, clone).as_sql(
            compiler, connection, function=function, **extra_context
        )

    def as_sqlite(self, compiler, connection, **extra_context):
        function = None
        if self.geo_field.geodetic(connection):
            function = "GeodesicLength" if self.spheroid else "GreatCircleLength"
        return super().as_sql(compiler, connection, function=function, **extra_context)


class LineLocatePoint(GeoFunc):
    output_field = FloatField()
    arity = 2
    geom_param_pos = (0, 1)


class MakeValid(GeomOutputGeoFunc):
    pass


class MemSize(GeoFunc):
    output_field = IntegerField()
    arity = 1


class NumGeometries(GeoFunc):
    output_field = IntegerField()
    arity = 1


class NumPoints(GeoFunc):
    output_field = IntegerField()
    arity = 1


class Perimeter(DistanceResultMixin, OracleToleranceMixin, GeoFunc):
    arity = 1

    def as_postgresql(self, compiler, connection, **extra_context):
        function = None
        if self.geo_field.geodetic(connection) and not self.source_is_geography():
            raise NotSupportedError(
                "ST_Perimeter cannot use a non-projected non-geography field."
            )
        dim = min(f.dim for f in self.get_source_fields())
        if dim > 2:
            function = connection.ops.perimeter3d
        return super().as_sql(compiler, connection, function=function, **extra_context)

    def as_sqlite(self, compiler, connection, **extra_context):
        if self.geo_field.geodetic(connection):
            raise NotSupportedError("Perimeter cannot use a non-projected field.")
        return super().as_sql(compiler, connection, **extra_context)


class PointOnSurface(OracleToleranceMixin, GeomOutputGeoFunc):
    arity = 1


class Reverse(GeoFunc):
    arity = 1


class Scale(SQLiteDecimalToFloatMixin, GeomOutputGeoFunc):
    def __init__(self, expression, x, y, z=0.0, **extra):
        expressions = [
            expression,
            self._handle_param(x, "x", NUMERIC_TYPES),
            self._handle_param(y, "y", NUMERIC_TYPES),
        ]
        if z != 0.0:
            expressions.append(self._handle_param(z, "z", NUMERIC_TYPES))
        super().__init__(*expressions, **extra)


class SnapToGrid(SQLiteDecimalToFloatMixin, GeomOutputGeoFunc):
    def __init__(self, expression, *args, **extra):
        nargs = len(args)
        expressions = [expression]
        if nargs in (1, 2):
            expressions.extend(
                [self._handle_param(arg, "", NUMERIC_TYPES) for arg in args]
            )
        elif nargs == 4:
            # Reverse origin and size param ordering
            expressions += [
                *(self._handle_param(arg, "", NUMERIC_TYPES) for arg in args[2:]),
                *(self._handle_param(arg, "", NUMERIC_TYPES) for arg in args[0:2]),
            ]
        else:
            raise ValueError("Must provide 1, 2, or 4 arguments to `SnapToGrid`.")
        super().__init__(*expressions, **extra)


class SymDifference(OracleToleranceMixin, GeomOutputGeoFunc):
    arity = 2
    geom_param_pos = (0, 1)


class Transform(GeomOutputGeoFunc):
    def __init__(self, expression, srid, **extra):
        expressions = [
            expression,
            self._handle_param(srid, "srid", int),
        ]
        if "output_field" not in extra:
            extra["output_field"] = GeometryField(srid=srid)
        super().__init__(*expressions, **extra)


class Translate(Scale):
    def as_sqlite(self, compiler, connection, **extra_context):
        clone = self.copy()
        if len(self.source_expressions) < 4:
            # Always provide the z parameter for ST_Translate
            clone.source_expressions.append(Value(0))
        return super(Translate, clone).as_sqlite(compiler, connection, **extra_context)


class Union(OracleToleranceMixin, GeomOutputGeoFunc):
    arity = 2
    geom_param_pos = (0, 1)
