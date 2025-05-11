import json
from functools import lru_cache, partial

from django.conf import settings
from django.db.backends.base.operations import BaseDatabaseOperations
from django.db.backends.postgresql.psycopg_any import (
    Inet,
    Jsonb,
    errors,
    is_psycopg3,
    mogrify,
)
from django.db.backends.utils import split_tzname_delta
from django.db.models.constants import OnConflict
from django.db.models.functions import Cast
from django.utils.regex_helper import _lazy_re_compile


@lru_cache
def get_json_dumps(encoder):
    if encoder is None:
        return json.dumps
    return partial(json.dumps, cls=encoder)


class DatabaseOperations(BaseDatabaseOperations):
    cast_char_field_without_max_length = "varchar"
    explain_prefix = "EXPLAIN"
    explain_options = frozenset(
        [
            "ANALYZE",
            "BUFFERS",
            "COSTS",
            "GENERIC_PLAN",
            "SETTINGS",
            "SUMMARY",
            "TIMING",
            "VERBOSE",
            "WAL",
        ]
    )
    cast_data_types = {
        "AutoField": "integer",
        "BigAutoField": "bigint",
        "SmallAutoField": "smallint",
    }

    if is_psycopg3:
        from psycopg.types import numeric

        integerfield_type_map = {
            "SmallIntegerField": numeric.Int2,
            "IntegerField": numeric.Int4,
            "BigIntegerField": numeric.Int8,
            "PositiveSmallIntegerField": numeric.Int2,
            "PositiveIntegerField": numeric.Int4,
            "PositiveBigIntegerField": numeric.Int8,
        }

    def unification_cast_sql(self, output_field):
        internal_type = output_field.get_internal_type()
        if internal_type in (
            "GenericIPAddressField",
            "IPAddressField",
            "TimeField",
            "UUIDField",
        ):
            # PostgreSQL will resolve a union as type 'text' if input types are
            # 'unknown'.
            # https://www.postgresql.org/docs/current/typeconv-union-case.html
            # These fields cannot be implicitly cast back in the default
            # PostgreSQL configuration so we need to explicitly cast them.
            # We must also remove components of the type within brackets:
            # varchar(255) -> varchar.
            return (
                "CAST(%%s AS %s)" % output_field.db_type(self.connection).split("(")[0]
            )
        return "%s"

    # EXTRACT format cannot be passed in parameters.
    _extract_format_re = _lazy_re_compile(r"[A-Z_]+")

    def date_extract_sql(self, lookup_type, sql, params):
        # https://www.postgresql.org/docs/current/functions-datetime.html#FUNCTIONS-DATETIME-EXTRACT
        """
        Returns a SQL expression to extract a specific date component from a given SQL expression.

        The lookup type determines the date component to extract, such as 'week_day', 'iso_week_day', or 'iso_year', 
        or any other standard SQL date extraction format (e.g. 'YEAR', 'MONTH', 'DAY'). 

        The function returns a tuple containing the generated SQL expression and the original parameters.
        Raises a ValueError if the lookup type is not recognized.\"\"\"

         \"\"\" 
         Args:
            lookup_type (str): The type of date component to extract.
            sql (str): The SQL expression to extract the date component from.
            params: The parameters associated with the SQL expression.

         Returns:
            tuple: A tuple containing the generated SQL expression and the original parameters.

        """
        if lookup_type == "week_day":
            # For consistency across backends, we return Sunday=1, Saturday=7.
            return f"EXTRACT(DOW FROM {sql}) + 1", params
        elif lookup_type == "iso_week_day":
            return f"EXTRACT(ISODOW FROM {sql})", params
        elif lookup_type == "iso_year":
            return f"EXTRACT(ISOYEAR FROM {sql})", params

        lookup_type = lookup_type.upper()
        if not self._extract_format_re.fullmatch(lookup_type):
            raise ValueError(f"Invalid lookup type: {lookup_type!r}")
        return f"EXTRACT({lookup_type} FROM {sql})", params

    def date_trunc_sql(self, lookup_type, sql, params, tzname=None):
        sql, params = self._convert_sql_to_tz(sql, params, tzname)
        # https://www.postgresql.org/docs/current/functions-datetime.html#FUNCTIONS-DATETIME-TRUNC
        return f"DATE_TRUNC(%s, {sql})", (lookup_type, *params)

    def _prepare_tzname_delta(self, tzname):
        """
        Adjusts the given timezone name by inverting its offset.

        This function takes a timezone name, possibly including an offset (e.g. 'UTC+2'), 
        and returns a modified version with the offset inverted (e.g. 'UTC-2'). If no offset is present, 
        the original timezone name is returned unchanged.
        """
        tzname, sign, offset = split_tzname_delta(tzname)
        if offset:
            sign = "-" if sign == "+" else "+"
            return f"{tzname}{sign}{offset}"
        return tzname

    def _convert_sql_to_tz(self, sql, params, tzname):
        if tzname and settings.USE_TZ:
            tzname_param = self._prepare_tzname_delta(tzname)
            return f"{sql} AT TIME ZONE %s", (*params, tzname_param)
        return sql, params

    def datetime_cast_date_sql(self, sql, params, tzname):
        sql, params = self._convert_sql_to_tz(sql, params, tzname)
        return f"({sql})::date", params

    def datetime_cast_time_sql(self, sql, params, tzname):
        sql, params = self._convert_sql_to_tz(sql, params, tzname)
        return f"({sql})::time", params

    def datetime_extract_sql(self, lookup_type, sql, params, tzname):
        sql, params = self._convert_sql_to_tz(sql, params, tzname)
        if lookup_type == "second":
            # Truncate fractional seconds.
            return f"EXTRACT(SECOND FROM DATE_TRUNC(%s, {sql}))", ("second", *params)
        return self.date_extract_sql(lookup_type, sql, params)

    def datetime_trunc_sql(self, lookup_type, sql, params, tzname):
        sql, params = self._convert_sql_to_tz(sql, params, tzname)
        # https://www.postgresql.org/docs/current/functions-datetime.html#FUNCTIONS-DATETIME-TRUNC
        return f"DATE_TRUNC(%s, {sql})", (lookup_type, *params)

    def time_extract_sql(self, lookup_type, sql, params):
        if lookup_type == "second":
            # Truncate fractional seconds.
            return f"EXTRACT(SECOND FROM DATE_TRUNC(%s, {sql}))", ("second", *params)
        return self.date_extract_sql(lookup_type, sql, params)

    def time_trunc_sql(self, lookup_type, sql, params, tzname=None):
        sql, params = self._convert_sql_to_tz(sql, params, tzname)
        return f"DATE_TRUNC(%s, {sql})::time", (lookup_type, *params)

    def deferrable_sql(self):
        return " DEFERRABLE INITIALLY DEFERRED"

    def fetch_returned_insert_rows(self, cursor):
        """
        Given a cursor object that has just performed an INSERT...RETURNING
        statement into a table, return the tuple of returned data.
        """
        return cursor.fetchall()

    def lookup_cast(self, lookup_type, internal_type=None):
        """
        Returns a SQL lookup string based on the given lookup type and internal type.

        The lookup string is modified to match the specified internal type, handling cases such as
        IP address fields and text fields, as well as supporting different lookup types like exact,
        contains, starts with, and regex matches. The function also applies case insensitivity
        where necessary.
        """
        lookup = "%s"
        # Cast text lookups to text to allow things like filter(x__contains=4)
        if lookup_type in (
            "iexact",
            "contains",
            "icontains",
            "startswith",
            "istartswith",
            "endswith",
            "iendswith",
            "regex",
            "iregex",
        ):
            if internal_type in ("IPAddressField", "GenericIPAddressField"):
                lookup = "HOST(%s)"
            else:
                lookup = "%s::text"

        # Use UPPER(x) for case-insensitive lookups; it's faster.
        if lookup_type in ("iexact", "icontains", "istartswith", "iendswith"):
            lookup = "UPPER(%s)" % lookup

        return lookup

    def no_limit_value(self):
        return None

    def prepare_sql_script(self, sql):
        return [sql]

    def quote_name(self, name):
        if name.startswith('"') and name.endswith('"'):
            return name  # Quoting once is enough.
        return '"%s"' % name

    def compose_sql(self, sql, params):
        return mogrify(sql, params, self.connection)

    def set_time_zone_sql(self):
        return "SELECT set_config('TimeZone', %s, false)"

    def sql_flush(self, style, tables, *, reset_sequences=False, allow_cascade=False):
        """
        Generate SQL to truncate a list of tables.

        Truncation style and tables to truncate are required parameters.
        Optional parameters allow resetting of IDENTITY columns and cascade truncation.

        Returns a list of SQL statements as strings.

        """
        if not tables:
            return []

        # Perform a single SQL 'TRUNCATE x, y, z...;' statement. It allows us
        # to truncate tables referenced by a foreign key in any other table.
        sql_parts = [
            style.SQL_KEYWORD("TRUNCATE"),
            ", ".join(style.SQL_FIELD(self.quote_name(table)) for table in tables),
        ]
        if reset_sequences:
            sql_parts.append(style.SQL_KEYWORD("RESTART IDENTITY"))
        if allow_cascade:
            sql_parts.append(style.SQL_KEYWORD("CASCADE"))
        return ["%s;" % " ".join(sql_parts)]

    def sequence_reset_by_name_sql(self, style, sequences):
        # 'ALTER SEQUENCE sequence_name RESTART WITH 1;'... style SQL statements
        # to reset sequence indices
        """
        Generates SQL statements to reset sequences by name, allowing for custom database style. 

        :param style: Database style object.
        :param sequences: List of dictionaries containing sequence information, with keys 'table' and optionally 'column'.
        :return: List of SQL statements to reset the sequences.
        """
        sql = []
        for sequence_info in sequences:
            table_name = sequence_info["table"]
            # 'id' will be the case if it's an m2m using an autogenerated
            # intermediate table (see BaseDatabaseIntrospection.sequence_list).
            column_name = sequence_info["column"] or "id"
            sql.append(
                "%s setval(pg_get_serial_sequence('%s','%s'), 1, false);"
                % (
                    style.SQL_KEYWORD("SELECT"),
                    style.SQL_TABLE(self.quote_name(table_name)),
                    style.SQL_FIELD(column_name),
                )
            )
        return sql

    def tablespace_sql(self, tablespace, inline=False):
        if inline:
            return "USING INDEX TABLESPACE %s" % self.quote_name(tablespace)
        else:
            return "TABLESPACE %s" % self.quote_name(tablespace)

    def sequence_reset_sql(self, style, model_list):
        """
        Generate SQL statements to reset sequences for a list of database models.

        This function iterates over the models and their AutoField instances to construct
        SQL commands that reset the sequence values to the maximum existing value plus one.
        The generated SQL is formatted according to the provided style.

        :param style: The style to use for formatting the SQL output.
        :param model_list: A list of database models for which to reset sequences.
        :return: A list of SQL statements to reset the sequences for the given models.
        """
        from django.db import models

        output = []
        qn = self.quote_name
        for model in model_list:
            # Use `coalesce` to set the sequence for each model to the max pk
            # value if there are records, or 1 if there are none. Set the
            # `is_called` property (the third argument to `setval`) to true if
            # there are records (as the max pk value is already in use),
            # otherwise set it to false. Use pg_get_serial_sequence to get the
            # underlying sequence name from the table name and column name.

            for f in model._meta.local_fields:
                if isinstance(f, models.AutoField):
                    output.append(
                        "%s setval(pg_get_serial_sequence('%s','%s'), "
                        "coalesce(max(%s), 1), max(%s) %s null) %s %s;"
                        % (
                            style.SQL_KEYWORD("SELECT"),
                            style.SQL_TABLE(qn(model._meta.db_table)),
                            style.SQL_FIELD(f.column),
                            style.SQL_FIELD(qn(f.column)),
                            style.SQL_FIELD(qn(f.column)),
                            style.SQL_KEYWORD("IS NOT"),
                            style.SQL_KEYWORD("FROM"),
                            style.SQL_TABLE(qn(model._meta.db_table)),
                        )
                    )
                    # Only one AutoField is allowed per model, so don't bother
                    # continuing.
                    break
        return output

    def prep_for_iexact_query(self, x):
        return x

    def max_name_length(self):
        """
        Return the maximum length of an identifier.

        The maximum length of an identifier is 63 by default, but can be
        changed by recompiling PostgreSQL after editing the NAMEDATALEN
        macro in src/include/pg_config_manual.h.

        This implementation returns 63, but can be overridden by a custom
        database backend that inherits most of its behavior from this one.
        """
        return 63

    def distinct_sql(self, fields, params):
        """
        Returns a SQL query fragment and parameters to select distinct rows based on specified fields. If fields are provided, the query uses the \"DISTINCT ON\" syntax to select distinct rows based on those fields; otherwise, it uses the standard \"DISTINCT\" keyword to select all distinct rows.
        """
        if fields:
            params = [param for param_list in params for param in param_list]
            return (["DISTINCT ON (%s)" % ", ".join(fields)], params)
        else:
            return ["DISTINCT"], []

    if is_psycopg3:

        def last_executed_query(self, cursor, sql, params):
            """
            Return the last executed SQL query.

            This function takes into account the database connection features and 
            whether server-side binding is used. If server-side binding is used, 
            it attempts to compose the SQL query with the given parameters. If not, 
            it returns the last query executed by the cursor, if available.

            :param cursor: the database cursor
            :param sql: the SQL query string
            :param params: the query parameters
            :returns: the last executed SQL query or None if not available
            """
            if self.connection.features.uses_server_side_binding:
                try:
                    return self.compose_sql(sql, params)
                except errors.DataError:
                    return None
            else:
                if cursor._query and cursor._query.query is not None:
                    return cursor._query.query.decode()
                return None

    else:

        def last_executed_query(self, cursor, sql, params):
            # https://www.psycopg.org/docs/cursor.html#cursor.query
            # The query attribute is a Psycopg extension to the DB API 2.0.
            if cursor.query is not None:
                return cursor.query.decode()
            return None

    def return_insert_columns(self, fields):
        if not fields:
            return "", ()
        columns = [
            "%s.%s"
            % (
                self.quote_name(field.model._meta.db_table),
                self.quote_name(field.column),
            )
            for field in fields
        ]
        return "RETURNING %s" % ", ".join(columns), ()

    if is_psycopg3:

        def adapt_integerfield_value(self, value, internal_type):
            if value is None or hasattr(value, "resolve_expression"):
                return value
            return self.integerfield_type_map[internal_type](value)

    def adapt_datefield_value(self, value):
        return value

    def adapt_datetimefield_value(self, value):
        return value

    def adapt_timefield_value(self, value):
        return value

    def adapt_decimalfield_value(self, value, max_digits=None, decimal_places=None):
        return value

    def adapt_ipaddressfield_value(self, value):
        if value:
            return Inet(value)
        return None

    def adapt_json_value(self, value, encoder):
        return Jsonb(value, dumps=get_json_dumps(encoder))

    def subtract_temporals(self, internal_type, lhs, rhs):
        """
        Overrides subtraction operation for DateField type, computing the difference in days between two dates.

        :param internal_type: Type of field being operated on
        :param lhs: Left-hand side of the subtraction operation
        :param rhs: Right-hand side of the subtraction operation
        :return: SQL query string and parameters for the subtraction operation
        """
        if internal_type == "DateField":
            lhs_sql, lhs_params = lhs
            rhs_sql, rhs_params = rhs
            params = (*lhs_params, *rhs_params)
            return "(interval '1 day' * (%s - %s))" % (lhs_sql, rhs_sql), params
        return super().subtract_temporals(internal_type, lhs, rhs)

    def explain_query_prefix(self, format=None, **options):
        """
        Return a query prefix for explanation purposes, applying given format and options.

        The prefix is extended by the specified format and valid options passed as keyword arguments.
        Valid options are transformed into uppercase 'true' or 'false' strings, while invalid options are ignored.
        The resulting prefix is a string that represents the query's explanation configuration.
        """
        extra = {}
        # Normalize options.
        if options:
            options = {
                name.upper(): "true" if value else "false"
                for name, value in options.items()
            }
            for valid_option in self.explain_options:
                value = options.pop(valid_option, None)
                if value is not None:
                    extra[valid_option] = value
        prefix = super().explain_query_prefix(format, **options)
        if format:
            extra["FORMAT"] = format
        if extra:
            prefix += " (%s)" % ", ".join("%s %s" % i for i in extra.items())
        return prefix

    def on_conflict_suffix_sql(self, fields, on_conflict, update_fields, unique_fields):
        """
        Generates the SQL suffix to handle conflicts for a given set of fields.

        Determines the appropriate SQL syntax based on the specified conflict resolution strategy (ignore or update)
        and constructs the necessary clause with quoted field names.

        Args:
            fields: The fields involved in the conflict.
            on_conflict: The conflict resolution strategy to apply.
            update_fields: The fields to update in case of a conflict.
            unique_fields: The unique constraint fields that may cause a conflict.

        Returns:
            The SQL suffix to handle conflicts, or a default implementation if the strategy is not recognized.
        """
        if on_conflict == OnConflict.IGNORE:
            return "ON CONFLICT DO NOTHING"
        if on_conflict == OnConflict.UPDATE:
            return "ON CONFLICT(%s) DO UPDATE SET %s" % (
                ", ".join(map(self.quote_name, unique_fields)),
                ", ".join(
                    [
                        f"{field} = EXCLUDED.{field}"
                        for field in map(self.quote_name, update_fields)
                    ]
                ),
            )
        return super().on_conflict_suffix_sql(
            fields,
            on_conflict,
            update_fields,
            unique_fields,
        )

    def prepare_join_on_clause(self, lhs_table, lhs_field, rhs_table, rhs_field):
        lhs_expr, rhs_expr = super().prepare_join_on_clause(
            lhs_table, lhs_field, rhs_table, rhs_field
        )

        if lhs_field.db_type(self.connection) != rhs_field.db_type(self.connection):
            rhs_expr = Cast(rhs_expr, lhs_field)

        return lhs_expr, rhs_expr
