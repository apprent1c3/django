import json

from django import forms
from django.core import checks, exceptions
from django.db import NotSupportedError, connections, router
from django.db.models import expressions, lookups
from django.db.models.constants import LOOKUP_SEP
from django.db.models.fields import TextField
from django.db.models.lookups import (
    FieldGetDbPrepValueMixin,
    PostgresOperatorLookup,
    Transform,
)
from django.utils.translation import gettext_lazy as _

from . import Field
from .mixins import CheckFieldDefaultMixin

__all__ = ["JSONField"]


class JSONField(CheckFieldDefaultMixin, Field):
    empty_strings_allowed = False
    description = _("A JSON object")
    default_error_messages = {
        "invalid": _("Value must be valid JSON."),
    }
    _default_hint = ("dict", "{}")

    def __init__(
        self,
        verbose_name=None,
        name=None,
        encoder=None,
        decoder=None,
        **kwargs,
    ):
        """
        Initializes an instance with optional encoder and decoder functions, as well as a verbose name and internal name, providing a foundation for further processing or transformation.
        """
        if encoder and not callable(encoder):
            raise ValueError("The encoder parameter must be a callable object.")
        if decoder and not callable(decoder):
            raise ValueError("The decoder parameter must be a callable object.")
        self.encoder = encoder
        self.decoder = decoder
        super().__init__(verbose_name, name, **kwargs)

    def check(self, **kwargs):
        errors = super().check(**kwargs)
        databases = kwargs.get("databases") or []
        errors.extend(self._check_supported(databases))
        return errors

    def _check_supported(self, databases):
        """
        Checks a list of databases for compatibility with the model's required features.

        Verifies that each database supports the model's fields, specifically JSONFields, and
        returns a list of errors if any database does not meet the requirements.
        """
        errors = []
        for db in databases:
            if not router.allow_migrate_model(db, self.model):
                continue
            connection = connections[db]
            if (
                self.model._meta.required_db_vendor
                and self.model._meta.required_db_vendor != connection.vendor
            ):
                continue
            if not (
                "supports_json_field" in self.model._meta.required_db_features
                or connection.features.supports_json_field
            ):
                errors.append(
                    checks.Error(
                        "%s does not support JSONFields." % connection.display_name,
                        obj=self.model,
                        id="fields.E180",
                    )
                )
        return errors

    def deconstruct(self):
        """
        Augments the deconstruction process of the parent class by including the optional encoder and decoder if they have been configured. Returns the deconstructed representation of the object, including any custom encoders and decoders.
        """
        name, path, args, kwargs = super().deconstruct()
        if self.encoder is not None:
            kwargs["encoder"] = self.encoder
        if self.decoder is not None:
            kwargs["decoder"] = self.decoder
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection):
        """
        Deserializes a JSON value from the database into a Python object.

        :param value: The value from the database
        :param expression: The database expression that yielded the value
        :param connection: The database connection
        :return: The deserialized Python object, or the original value if deserialization fails or is not applicable.
        """
        if value is None:
            return value
        # Some backends (SQLite at least) extract non-string values in their
        # SQL datatypes.
        if isinstance(expression, KeyTransform) and not isinstance(value, str):
            return value
        try:
            return json.loads(value, cls=self.decoder)
        except json.JSONDecodeError:
            return value

    def get_internal_type(self):
        return "JSONField"

    def get_db_prep_value(self, value, connection, prepared=False):
        """
        Returns the database preparation value for a given value.

        This method prepares a value to be used in a database operation, handling
        JSON values and other special cases, and adapts it according to the database
        connection being used.
        """
        if not prepared:
            value = self.get_prep_value(value)
        if isinstance(value, expressions.Value) and isinstance(
            value.output_field, JSONField
        ):
            value = value.value
        elif hasattr(value, "as_sql"):
            return value
        return connection.ops.adapt_json_value(value, self.encoder)

    def get_db_prep_save(self, value, connection):
        if value is None:
            return value
        return self.get_db_prep_value(value, connection)

    def get_transform(self, name):
        transform = super().get_transform(name)
        if transform:
            return transform
        return KeyTransformFactory(name)

    def validate(self, value, model_instance):
        """
        Validate a value to ensure it can be serialized to JSON. If the value cannot be serialized, a ValidationError is raised with a message indicating that the value is invalid.
        """
        super().validate(value, model_instance)
        try:
            json.dumps(value, cls=self.encoder)
        except TypeError:
            raise exceptions.ValidationError(
                self.error_messages["invalid"],
                code="invalid",
                params={"value": value},
            )

    def value_to_string(self, obj):
        return self.value_from_object(obj)

    def formfield(self, **kwargs):
        return super().formfield(
            **{
                "form_class": forms.JSONField,
                "encoder": self.encoder,
                "decoder": self.decoder,
                **kwargs,
            }
        )


def compile_json_path(key_transforms, include_root=True):
    """
    :param list key_transforms: A list of key transformations to apply to the JSON path
    :param bool include_root: Whether to include the root ($) in the generated JSON path
    :return: A compiled JSON path as a string,
             combining key transformations with dot notation and array indexing.
    """
    path = ["$"] if include_root else []
    for key_transform in key_transforms:
        try:
            num = int(key_transform)
        except ValueError:  # non-integer
            path.append(".")
            path.append(json.dumps(key_transform))
        else:
            path.append("[%s]" % num)
    return "".join(path)


class DataContains(FieldGetDbPrepValueMixin, PostgresOperatorLookup):
    lookup_name = "contains"
    postgres_operator = "@>"

    def as_sql(self, compiler, connection):
        """
        Generates the SQL representation of a JSON field contains lookup, raising an error if the database backend does not support this operation.
        """
        if not connection.features.supports_json_field_contains:
            raise NotSupportedError(
                "contains lookup is not supported on this database backend."
            )
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = tuple(lhs_params) + tuple(rhs_params)
        return "JSON_CONTAINS(%s, %s)" % (lhs, rhs), params


class ContainedBy(FieldGetDbPrepValueMixin, PostgresOperatorLookup):
    lookup_name = "contained_by"
    postgres_operator = "<@"

    def as_sql(self, compiler, connection):
        """
        Generates the SQL for the JSON_CONTAINS lookup. 
        Checks if the database backend supports the `contained_by` lookup, 
        raising an error if not supported. Returns a SQL string and parameters 
        to be used in the query.
        """
        if not connection.features.supports_json_field_contains:
            raise NotSupportedError(
                "contained_by lookup is not supported on this database backend."
            )
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = tuple(rhs_params) + tuple(lhs_params)
        return "JSON_CONTAINS(%s, %s)" % (rhs, lhs), params


class HasKeyLookup(PostgresOperatorLookup):
    logical_operator = None

    def compile_json_path_final_key(self, key_transform):
        # Compile the final key without interpreting ints as array elements.
        return ".%s" % json.dumps(key_transform)

    def as_sql(self, compiler, connection, template=None):
        # Process JSON path from the left-hand side.
        """
        Generates SQL for a database operation involving JSON data.
        This function takes a template and, based on the left-hand side (LHS) and right-hand side (RHS) of the operation,
        constructs the necessary SQL string and parameters to query JSON data.
        It handles both simple and complex JSON paths, including those that involve nested keys.
        """
        if isinstance(self.lhs, KeyTransform):
            lhs, lhs_params, lhs_key_transforms = self.lhs.preprocess_lhs(
                compiler, connection
            )
            lhs_json_path = compile_json_path(lhs_key_transforms)
        else:
            lhs, lhs_params = self.process_lhs(compiler, connection)
            lhs_json_path = "$"
        sql = template % lhs
        # Process JSON path from the right-hand side.
        rhs = self.rhs
        rhs_params = []
        if not isinstance(rhs, (list, tuple)):
            rhs = [rhs]
        for key in rhs:
            if isinstance(key, KeyTransform):
                *_, rhs_key_transforms = key.preprocess_lhs(compiler, connection)
            else:
                rhs_key_transforms = [key]
            *rhs_key_transforms, final_key = rhs_key_transforms
            rhs_json_path = compile_json_path(rhs_key_transforms, include_root=False)
            rhs_json_path += self.compile_json_path_final_key(final_key)
            rhs_params.append(lhs_json_path + rhs_json_path)
        # Add condition for each key.
        if self.logical_operator:
            sql = "(%s)" % self.logical_operator.join([sql] * len(rhs_params))
        return sql, tuple(lhs_params) + tuple(rhs_params)

    def as_mysql(self, compiler, connection):
        return self.as_sql(
            compiler, connection, template="JSON_CONTAINS_PATH(%s, 'one', %%s)"
        )

    def as_oracle(self, compiler, connection):
        sql, params = self.as_sql(
            compiler, connection, template="JSON_EXISTS(%s, '%%s')"
        )
        # Add paths directly into SQL because path expressions cannot be passed
        # as bind variables on Oracle.
        return sql % tuple(params), []

    def as_postgresql(self, compiler, connection):
        """
        Adapts the given expression for use with PostgreSQL, handling KeyTransform instances on the right-hand side by applying any necessary key transformations to the left-hand side.
        """
        if isinstance(self.rhs, KeyTransform):
            *_, rhs_key_transforms = self.rhs.preprocess_lhs(compiler, connection)
            for key in rhs_key_transforms[:-1]:
                self.lhs = KeyTransform(key, self.lhs)
            self.rhs = rhs_key_transforms[-1]
        return super().as_postgresql(compiler, connection)

    def as_sqlite(self, compiler, connection):
        return self.as_sql(
            compiler, connection, template="JSON_TYPE(%s, %%s) IS NOT NULL"
        )


class HasKey(HasKeyLookup):
    lookup_name = "has_key"
    postgres_operator = "?"
    prepare_rhs = False


class HasKeys(HasKeyLookup):
    lookup_name = "has_keys"
    postgres_operator = "?&"
    logical_operator = " AND "

    def get_prep_lookup(self):
        return [str(item) for item in self.rhs]


class HasAnyKeys(HasKeys):
    lookup_name = "has_any_keys"
    postgres_operator = "?|"
    logical_operator = " OR "


class HasKeyOrArrayIndex(HasKey):
    def compile_json_path_final_key(self, key_transform):
        return compile_json_path([key_transform], include_root=False)


class CaseInsensitiveMixin:
    """
    Mixin to allow case-insensitive comparison of JSON values on MySQL.
    MySQL handles strings used in JSON context using the utf8mb4_bin collation.
    Because utf8mb4_bin is a binary collation, comparison of JSON values is
    case-sensitive.
    """

    def process_lhs(self, compiler, connection):
        lhs, lhs_params = super().process_lhs(compiler, connection)
        if connection.vendor == "mysql":
            return "LOWER(%s)" % lhs, lhs_params
        return lhs, lhs_params

    def process_rhs(self, compiler, connection):
        rhs, rhs_params = super().process_rhs(compiler, connection)
        if connection.vendor == "mysql":
            return "LOWER(%s)" % rhs, rhs_params
        return rhs, rhs_params


class JSONExact(lookups.Exact):
    can_use_none_as_rhs = True

    def process_rhs(self, compiler, connection):
        """
        Processes the right-hand side of a database query, adapting it to the specific database connection being used. 
        Specifically, handles conversion of null values and applies MySQL-specific JSON extraction transformations.
        """
        rhs, rhs_params = super().process_rhs(compiler, connection)
        # Treat None lookup values as null.
        if rhs == "%s" and rhs_params == [None]:
            rhs_params = ["null"]
        if connection.vendor == "mysql":
            func = ["JSON_EXTRACT(%s, '$')"] * len(rhs_params)
            rhs %= tuple(func)
        return rhs, rhs_params

    def as_oracle(self, compiler, connection):
        """
        Renders an Oracle-compatible JSON equality check operation.

        This function processes the left-hand side (LHS) and right-hand side (RHS) of a comparison,
        wraps them in Oracle's JSON equality check function if the database supports primitives in JSON fields,
        and returns the resulting expression along with its parameters.
        """
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        if connection.features.supports_primitives_in_json_field:
            lhs = f"JSON({lhs})"
            rhs = f"JSON({rhs})"
        return f"JSON_EQUAL({lhs}, {rhs} ERROR ON ERROR)", (*lhs_params, *rhs_params)


class JSONIContains(CaseInsensitiveMixin, lookups.IContains):
    pass


JSONField.register_lookup(DataContains)
JSONField.register_lookup(ContainedBy)
JSONField.register_lookup(HasKey)
JSONField.register_lookup(HasKeys)
JSONField.register_lookup(HasAnyKeys)
JSONField.register_lookup(JSONExact)
JSONField.register_lookup(JSONIContains)


class KeyTransform(Transform):
    postgres_operator = "->"
    postgres_nested_operator = "#>"

    def __init__(self, key_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.key_name = str(key_name)

    def preprocess_lhs(self, compiler, connection):
        """
        Preprocesses the left-hand side of a query by compiling it and extracting key transformations.

        :arg compiler: The compiler object used for compilation.
        :arg connection: The database connection object.
        :return: A tuple containing the compiled left-hand side, parameters, and key transformations.
        :note: The key transformations are escaped for Oracle databases by replacing '%' with '%%'.
        """
        key_transforms = [self.key_name]
        previous = self.lhs
        while isinstance(previous, KeyTransform):
            key_transforms.insert(0, previous.key_name)
            previous = previous.lhs
        lhs, params = compiler.compile(previous)
        if connection.vendor == "oracle":
            # Escape string-formatting.
            key_transforms = [key.replace("%", "%%") for key in key_transforms]
        return lhs, params, key_transforms

    def as_mysql(self, compiler, connection):
        lhs, params, key_transforms = self.preprocess_lhs(compiler, connection)
        json_path = compile_json_path(key_transforms)
        return "JSON_EXTRACT(%s, %%s)" % lhs, tuple(params) + (json_path,)

    def as_oracle(self, compiler, connection):
        """
        Generates an Oracle-compatible SQL expression to extract a JSON value from a field, handling both primitive and non-primitive JSON values.
        """
        lhs, params, key_transforms = self.preprocess_lhs(compiler, connection)
        json_path = compile_json_path(key_transforms)
        if connection.features.supports_primitives_in_json_field:
            sql = (
                "COALESCE(JSON_VALUE(%s, '%s'), JSON_QUERY(%s, '%s' DISALLOW SCALARS))"
            )
        else:
            sql = "COALESCE(JSON_QUERY(%s, '%s'), JSON_VALUE(%s, '%s'))"
        return sql % ((lhs, json_path) * 2), tuple(params) * 2

    def as_postgresql(self, compiler, connection):
        """
        Translates the query lookup to PostgreSQL syntax.

        Generates SQL and parameters for the given lookup type, handling both
        nested and simple lookups, and returning them as a tuple. The resulting
        SQL string is formatted with a placeholder for the lookup value, which
        is included in the parameters tuple.

        :param compiler: The compiler instance to use for preprocessing.
        :param connection: The database connection to use for the query.
        :returns: A tuple containing the formatted SQL string and the parameters.

        """
        lhs, params, key_transforms = self.preprocess_lhs(compiler, connection)
        if len(key_transforms) > 1:
            sql = "(%s %s %%s)" % (lhs, self.postgres_nested_operator)
            return sql, tuple(params) + (key_transforms,)
        try:
            lookup = int(self.key_name)
        except ValueError:
            lookup = self.key_name
        return "(%s %s %%s)" % (lhs, self.postgres_operator), tuple(params) + (lookup,)

    def as_sqlite(self, compiler, connection):
        lhs, params, key_transforms = self.preprocess_lhs(compiler, connection)
        json_path = compile_json_path(key_transforms)
        datatype_values = ",".join(
            [repr(datatype) for datatype in connection.ops.jsonfield_datatype_values]
        )
        return (
            "(CASE WHEN JSON_TYPE(%s, %%s) IN (%s) "
            "THEN JSON_TYPE(%s, %%s) ELSE JSON_EXTRACT(%s, %%s) END)"
        ) % (lhs, datatype_values, lhs, lhs), (tuple(params) + (json_path,)) * 3


class KeyTextTransform(KeyTransform):
    postgres_operator = "->>"
    postgres_nested_operator = "#>>"
    output_field = TextField()

    def as_mysql(self, compiler, connection):
        """
        Generates a MySQL SQL expression for a JSON path operation, handling both MySQL and MariaDB variants.

        Returns a tuple containing the SQL expression and the required parameters. For MariaDB, the SQL expression is wrapped in a JSON_UNQUOTE call. For MySQL, the SQL expression is constructed using the ->> operator. The resulting SQL expression can be used to extract a JSON value from a column.

        :param compiler: The SQL compiler used to generate the expression.
        :param connection: The database connection, which provides information about the MySQL variant being used.
        :rtype: tuple[str, tuple]
        """
        if connection.mysql_is_mariadb:
            # MariaDB doesn't support -> and ->> operators (see MDEV-13594).
            sql, params = super().as_mysql(compiler, connection)
            return "JSON_UNQUOTE(%s)" % sql, params
        else:
            lhs, params, key_transforms = self.preprocess_lhs(compiler, connection)
            json_path = compile_json_path(key_transforms)
            return "(%s ->> %%s)" % lhs, tuple(params) + (json_path,)

    @classmethod
    def from_lookup(cls, lookup):
        """
        ).. 
            Builds a chain of transformations from a string-based lookup specification.

            :param lookup: A string containing the lookup specification, with transformations and keys/indexes separated by ``LOOKUP_SEP``.
            :return: The constructed transformation chain.
            :raises ValueError: If the lookup string does not contain any keys or indexes.
        """
        transform, *keys = lookup.split(LOOKUP_SEP)
        if not keys:
            raise ValueError("Lookup must contain key or index transforms.")
        for key in keys:
            transform = cls(key, transform)
        return transform


KT = KeyTextTransform.from_lookup


class KeyTransformTextLookupMixin:
    """
    Mixin for combining with a lookup expecting a text lhs from a JSONField
    key lookup. On PostgreSQL, make use of the ->> operator instead of casting
    key values to text and performing the lookup on the resulting
    representation.
    """

    def __init__(self, key_transform, *args, **kwargs):
        if not isinstance(key_transform, KeyTransform):
            raise TypeError(
                "Transform should be an instance of KeyTransform in order to "
                "use this lookup."
            )
        key_text_transform = KeyTextTransform(
            key_transform.key_name,
            *key_transform.source_expressions,
            **key_transform.extra,
        )
        super().__init__(key_text_transform, *args, **kwargs)


class KeyTransformIsNull(lookups.IsNull):
    # key__isnull=False is the same as has_key='key'
    def as_oracle(self, compiler, connection):
        """
        Generates Oracle SQL representation for a NOT IN or NOT EXISTS condition.

        Handles cases where the right-hand side (RHS) is empty or non-empty, 
        and combines the left-hand side (LHS) preprocessing with the Oracle SQL 
        generated from the condition's key or array index.

        Returns the constructed Oracle SQL query and its parameters.
        """
        sql, params = HasKeyOrArrayIndex(
            self.lhs.lhs,
            self.lhs.key_name,
        ).as_oracle(compiler, connection)
        if not self.rhs:
            return sql, params
        # Column doesn't have a key or IS NULL.
        lhs, lhs_params, _ = self.lhs.preprocess_lhs(compiler, connection)
        return "(NOT %s OR %s IS NULL)" % (sql, lhs), tuple(params) + tuple(lhs_params)

    def as_sqlite(self, compiler, connection):
        template = "JSON_TYPE(%s, %%s) IS NULL"
        if not self.rhs:
            template = "JSON_TYPE(%s, %%s) IS NOT NULL"
        return HasKeyOrArrayIndex(self.lhs.lhs, self.lhs.key_name).as_sql(
            compiler,
            connection,
            template=template,
        )


class KeyTransformIn(lookups.In):
    def resolve_expression_parameter(self, compiler, connection, sql, param):
        """

        Resolves an expression parameter for use in SQL queries, handling JSON field support for various database vendors.

        This method extends the base implementation to provide vendor-specific handling for Oracle, MySQL, and SQLite databases.
        It converts JSON parameters to the correct SQL syntax for each vendor, ensuring compatibility and correct data representation.

        """
        sql, params = super().resolve_expression_parameter(
            compiler,
            connection,
            sql,
            param,
        )
        if (
            not hasattr(param, "as_sql")
            and not connection.features.has_native_json_field
        ):
            if connection.vendor == "oracle":
                value = json.loads(param)
                sql = "%s(JSON_OBJECT('value' VALUE %%s FORMAT JSON), '$.value')"
                if isinstance(value, (list, dict)):
                    sql %= "JSON_QUERY"
                else:
                    sql %= "JSON_VALUE"
            elif connection.vendor == "mysql" or (
                connection.vendor == "sqlite"
                and params[0] not in connection.ops.jsonfield_datatype_values
            ):
                sql = "JSON_EXTRACT(%s, '$')"
        if connection.vendor == "mysql" and connection.mysql_is_mariadb:
            sql = "JSON_UNQUOTE(%s)" % sql
        return sql, params


class KeyTransformExact(JSONExact):
    def process_rhs(self, compiler, connection):
        """
        Handle the right-hand side of a database query, adapting the SQL syntax 
        for JSON operations dependent on the vendor (Oracle or SQLite).
        """
        if isinstance(self.rhs, KeyTransform):
            return super(lookups.Exact, self).process_rhs(compiler, connection)
        rhs, rhs_params = super().process_rhs(compiler, connection)
        if connection.vendor == "oracle":
            func = []
            sql = "%s(JSON_OBJECT('value' VALUE %%s FORMAT JSON), '$.value')"
            for value in rhs_params:
                value = json.loads(value)
                if isinstance(value, (list, dict)):
                    func.append(sql % "JSON_QUERY")
                else:
                    func.append(sql % "JSON_VALUE")
            rhs %= tuple(func)
        elif connection.vendor == "sqlite":
            func = []
            for value in rhs_params:
                if value in connection.ops.jsonfield_datatype_values:
                    func.append("%s")
                else:
                    func.append("JSON_EXTRACT(%s, '$')")
            rhs %= tuple(func)
        return rhs, rhs_params

    def as_oracle(self, compiler, connection):
        """

        Generates Oracle-specific SQL for the current database operation, handling 
        special cases when the right-hand side is null. This ensures proper translation 
        of Python expressions into Oracle-compatible queries.

        """
        rhs, rhs_params = super().process_rhs(compiler, connection)
        if rhs_params == ["null"]:
            # Field has key and it's NULL.
            has_key_expr = HasKeyOrArrayIndex(self.lhs.lhs, self.lhs.key_name)
            has_key_sql, has_key_params = has_key_expr.as_oracle(compiler, connection)
            is_null_expr = self.lhs.get_lookup("isnull")(self.lhs, True)
            is_null_sql, is_null_params = is_null_expr.as_sql(compiler, connection)
            return (
                "%s AND %s" % (has_key_sql, is_null_sql),
                tuple(has_key_params) + tuple(is_null_params),
            )
        return super().as_sql(compiler, connection)


class KeyTransformIExact(
    CaseInsensitiveMixin, KeyTransformTextLookupMixin, lookups.IExact
):
    pass


class KeyTransformIContains(
    CaseInsensitiveMixin, KeyTransformTextLookupMixin, lookups.IContains
):
    pass


class KeyTransformStartsWith(KeyTransformTextLookupMixin, lookups.StartsWith):
    pass


class KeyTransformIStartsWith(
    CaseInsensitiveMixin, KeyTransformTextLookupMixin, lookups.IStartsWith
):
    pass


class KeyTransformEndsWith(KeyTransformTextLookupMixin, lookups.EndsWith):
    pass


class KeyTransformIEndsWith(
    CaseInsensitiveMixin, KeyTransformTextLookupMixin, lookups.IEndsWith
):
    pass


class KeyTransformRegex(KeyTransformTextLookupMixin, lookups.Regex):
    pass


class KeyTransformIRegex(
    CaseInsensitiveMixin, KeyTransformTextLookupMixin, lookups.IRegex
):
    pass


class KeyTransformNumericLookupMixin:
    def process_rhs(self, compiler, connection):
        rhs, rhs_params = super().process_rhs(compiler, connection)
        if not connection.features.has_native_json_field:
            rhs_params = [json.loads(value) for value in rhs_params]
        return rhs, rhs_params


class KeyTransformLt(KeyTransformNumericLookupMixin, lookups.LessThan):
    pass


class KeyTransformLte(KeyTransformNumericLookupMixin, lookups.LessThanOrEqual):
    pass


class KeyTransformGt(KeyTransformNumericLookupMixin, lookups.GreaterThan):
    pass


class KeyTransformGte(KeyTransformNumericLookupMixin, lookups.GreaterThanOrEqual):
    pass


KeyTransform.register_lookup(KeyTransformIn)
KeyTransform.register_lookup(KeyTransformExact)
KeyTransform.register_lookup(KeyTransformIExact)
KeyTransform.register_lookup(KeyTransformIsNull)
KeyTransform.register_lookup(KeyTransformIContains)
KeyTransform.register_lookup(KeyTransformStartsWith)
KeyTransform.register_lookup(KeyTransformIStartsWith)
KeyTransform.register_lookup(KeyTransformEndsWith)
KeyTransform.register_lookup(KeyTransformIEndsWith)
KeyTransform.register_lookup(KeyTransformRegex)
KeyTransform.register_lookup(KeyTransformIRegex)

KeyTransform.register_lookup(KeyTransformLt)
KeyTransform.register_lookup(KeyTransformLte)
KeyTransform.register_lookup(KeyTransformGt)
KeyTransform.register_lookup(KeyTransformGte)


class KeyTransformFactory:
    def __init__(self, key_name):
        self.key_name = key_name

    def __call__(self, *args, **kwargs):
        return KeyTransform(self.key_name, *args, **kwargs)
