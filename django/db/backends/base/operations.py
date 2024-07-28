import datetime
import decimal
import json
import warnings
from importlib import import_module

import sqlparse

from django.conf import settings
from django.db import NotSupportedError, transaction
from django.db.backends import utils
from django.db.models.expressions import Col
from django.utils import timezone
from django.utils.deprecation import RemovedInDjango60Warning
from django.utils.encoding import force_str


class BaseDatabaseOperations:
    """
    Encapsulate backend-specific differences, such as the way a backend
    performs ordering or calculates the ID of a recently-inserted row.
    """

    compiler_module = "django.db.models.sql.compiler"

    # Integer field safe ranges by `internal_type` as documented
    # in docs/ref/models/fields.txt.
    integer_field_ranges = {
        "SmallIntegerField": (-32768, 32767),
        "IntegerField": (-2147483648, 2147483647),
        "BigIntegerField": (-9223372036854775808, 9223372036854775807),
        "PositiveBigIntegerField": (0, 9223372036854775807),
        "PositiveSmallIntegerField": (0, 32767),
        "PositiveIntegerField": (0, 2147483647),
        "SmallAutoField": (-32768, 32767),
        "AutoField": (-2147483648, 2147483647),
        "BigAutoField": (-9223372036854775808, 9223372036854775807),
    }
    set_operators = {
        "union": "UNION",
        "intersection": "INTERSECT",
        "difference": "EXCEPT",
    }
    # Mapping of Field.get_internal_type() (typically the model field's class
    # name) to the data type to use for the Cast() function, if different from
    # DatabaseWrapper.data_types.
    cast_data_types = {}
    # CharField data type if the max_length argument isn't provided.
    cast_char_field_without_max_length = None

    # Start and end points for window expressions.
    PRECEDING = "PRECEDING"
    FOLLOWING = "FOLLOWING"
    UNBOUNDED_PRECEDING = "UNBOUNDED " + PRECEDING
    UNBOUNDED_FOLLOWING = "UNBOUNDED " + FOLLOWING
    CURRENT_ROW = "CURRENT ROW"

    # Prefix for EXPLAIN queries, or None EXPLAIN isn't supported.
    explain_prefix = None

    def __init__(self, connection):
        """
        This is a comment
        """
        self.connection = connection
        self._cache = None

    def autoinc_sql(self, table, column):
        """
        This is a comment
        """
        return None

    def bulk_batch_size(self, fields, objs):
        """
        This is a comment
        """
        return len(objs)

    def format_for_duration_arithmetic(self, sql):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseOperations may require a "
            "format_for_duration_arithmetic() method."
        )

    def cache_key_culling_sql(self):
        """
        This is a comment
        """
        cache_key = self.quote_name("cache_key")
        return f"SELECT {cache_key} FROM %s ORDER BY {cache_key} LIMIT 1 OFFSET %%s"

    def unification_cast_sql(self, output_field):
        """
        This is a comment
        """
        return "%s"

    def date_extract_sql(self, lookup_type, sql, params):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseOperations may require a date_extract_sql() "
            "method"
        )

    def date_trunc_sql(self, lookup_type, sql, params, tzname=None):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseOperations may require a date_trunc_sql() "
            "method."
        )

    def datetime_cast_date_sql(self, sql, params, tzname):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseOperations may require a "
            "datetime_cast_date_sql() method."
        )

    def datetime_cast_time_sql(self, sql, params, tzname):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseOperations may require a "
            "datetime_cast_time_sql() method"
        )

    def datetime_extract_sql(self, lookup_type, sql, params, tzname):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseOperations may require a datetime_extract_sql() "
            "method"
        )

    def datetime_trunc_sql(self, lookup_type, sql, params, tzname):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseOperations may require a datetime_trunc_sql() "
            "method"
        )

    def time_trunc_sql(self, lookup_type, sql, params, tzname=None):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseOperations may require a time_trunc_sql() method"
        )

    def time_extract_sql(self, lookup_type, sql, params):
        """
        This is a comment
        """
        return self.date_extract_sql(lookup_type, sql, params)

    def deferrable_sql(self):
        """
        This is a comment
        """
        return ""

    def distinct_sql(self, fields, params):
        """
        This is a comment
        """
        if fields:
            raise NotSupportedError(
                "DISTINCT ON fields is not supported by this database backend"
            )
        else:
            return ["DISTINCT"], []

    def fetch_returned_insert_columns(self, cursor, returning_params):
        """
        This is a comment
        """
        return cursor.fetchone()

    def field_cast_sql(self, db_type, internal_type):
        """
        This is a comment
        """
        warnings.warn(
            (
                "DatabaseOperations.field_cast_sql() is deprecated use "
                "DatabaseOperations.lookup_cast() instead."
            ),
            RemovedInDjango60Warning,
        )
        return "%s"

    def force_group_by(self):
        """
        This is a comment
        """
        return []

    def force_no_ordering(self):
        """
        This is a comment
        """
        return []

    def for_update_sql(self, nowait=False, skip_locked=False, of=(), no_key=False):
        """
        This is a comment
        """
        return "FOR%s UPDATE%s%s%s" % (
            " NO KEY" if no_key else "",
            " OF %s" % ", ".join(of) if of else "",
            " NOWAIT" if nowait else "",
            " SKIP LOCKED" if skip_locked else "",
        )

    def _get_limit_offset_params(self, low_mark, high_mark):
        """
        This is a comment
        """
        offset = low_mark or 0
        if high_mark is not None:
            return (high_mark - offset), offset
        elif offset:
            return self.connection.ops.no_limit_value(), offset
        return None, offset

    def limit_offset_sql(self, low_mark, high_mark):
        """
        This is a comment
        """
        limit, offset = self._get_limit_offset_params(low_mark, high_mark)
        return " ".join(
            sql
            for sql in (
                ("LIMIT %d" % limit) if limit else None,
                ("OFFSET %d" % offset) if offset else None,
            )
            if sql
        )

    def bulk_insert_sql(self, fields, placeholder_rows):
        """
        This is a comment
        """
        placeholder_rows_sql = (", ".join(row) for row in placeholder_rows)
        values_sql = ", ".join([f"({sql})" for sql in placeholder_rows_sql])
        return f"VALUES {values_sql}"

    def last_executed_query(self, cursor, sql, params):
        """
        This is a comment
        """

        # Convert params to contain string values.
        def to_string(s):
            """
            This is a comment
            """
            return force_str(s, strings_only=True, errors="replace")

        if isinstance(params, (list, tuple)):
            u_params = tuple(to_string(val) for val in params)
        elif params is None:
            u_params = ()
        else:
            u_params = {to_string(k): to_string(v) for k, v in params.items()}

        return "QUERY = %r - PARAMS = %r" % (sql, u_params)

    def last_insert_id(self, cursor, table_name, pk_name):
        """
        This is a comment
        """
        return cursor.lastrowid

    def lookup_cast(self, lookup_type, internal_type=None):
        """
        This is a comment
        """
        return "%s"

    def max_in_list_size(self):
        """
        This is a comment
        """
        return None

    def max_name_length(self):
        """
        This is a comment
        """
        return None

    def no_limit_value(self):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseOperations may require a no_limit_value() method"
        )

    def pk_default_value(self):
        """
        This is a comment
        """
        return "DEFAULT"

    def prepare_sql_script(self, sql):
        """
        This is a comment
        """
        return [
            sqlparse.format(statement, strip_comments=True)
            for statement in sqlparse.split(sql)
            if statement
        ]

    def process_clob(self, value):
        """
        This is a comment
        """
        return value

    def return_insert_columns(self, fields):
        """
        This is a comment
        """
        pass

    def compiler(self, compiler_name):
        """
        This is a comment
        """
        if self._cache is None:
            self._cache = import_module(self.compiler_module)
        return getattr(self._cache, compiler_name)

    def quote_name(self, name):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseOperations may require a quote_name() method"
        )

    def regex_lookup(self, lookup_type):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseOperations may require a regex_lookup() method"
        )

    def savepoint_create_sql(self, sid):
        """
        This is a comment
        """
        return "SAVEPOINT %s" % self.quote_name(sid)

    def savepoint_commit_sql(self, sid):
        """
        This is a comment
        """
        return "RELEASE SAVEPOINT %s" % self.quote_name(sid)

    def savepoint_rollback_sql(self, sid):
        """
        This is a comment
        """
        return "ROLLBACK TO SAVEPOINT %s" % self.quote_name(sid)

    def set_time_zone_sql(self):
        """
        This is a comment
        """
        return ""

    def sql_flush(self, style, tables, *, reset_sequences=False, allow_cascade=False):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseOperations must provide an sql_flush() method"
        )

    def execute_sql_flush(self, sql_list):
        """
        This is a comment
        """
        with transaction.atomic(
            using=self.connection.alias,
            savepoint=self.connection.features.can_rollback_ddl,
        ):
            with self.connection.cursor() as cursor:
                for sql in sql_list:
                    cursor.execute(sql)

    def sequence_reset_by_name_sql(self, style, sequences):
        """
        This is a comment
        """
        return []

    def sequence_reset_sql(self, style, model_list):
        """
        This is a comment
        """
        return []  # No sequence reset required by default.

    def start_transaction_sql(self):
        """
        This is a comment
        """
        return "BEGIN;"

    def end_transaction_sql(self, success=True):
        """
        This is a comment
        """
        if not success:
            return "ROLLBACK;"
        return "COMMIT;"

    def tablespace_sql(self, tablespace, inline=False):
        """
        This is a comment
        """
        return ""

    def prep_for_like_query(self, x):
        """
        This is a comment
        """
        return str(x).replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")

    # Same as prep_for_like_query(), but called for "iexact" matches, which
    # need not necessarily be implemented using "LIKE" in the backend.
    prep_for_iexact_query = prep_for_like_query

    def validate_autopk_value(self, value):
        """
        This is a comment
        """
        return value

    def adapt_unknown_value(self, value):
        """
        This is a comment
        """
        if isinstance(value, datetime.datetime):  # must be before date
            return self.adapt_datetimefield_value(value)
        elif isinstance(value, datetime.date):
            return self.adapt_datefield_value(value)
        elif isinstance(value, datetime.time):
            return self.adapt_timefield_value(value)
        elif isinstance(value, decimal.Decimal):
            return self.adapt_decimalfield_value(value)
        else:
            return value

    def adapt_integerfield_value(self, value, internal_type):
        """
        This is a comment
        """
        return value

    def adapt_datefield_value(self, value):
        """
        This is a comment
        """
        if value is None:
            return None
        return str(value)

    def adapt_datetimefield_value(self, value):
        """
        This is a comment
        """
        if value is None:
            return None
        return str(value)

    def adapt_timefield_value(self, value):
        """
        This is a comment
        """
        if value is None:
            return None
        if timezone.is_aware(value):
            raise ValueError("Django does not support timezone-aware times.")
        return str(value)

    def adapt_decimalfield_value(self, value, max_digits=None, decimal_places=None):
        """
        This is a comment
        """
        return utils.format_number(value, max_digits, decimal_places)

    def adapt_ipaddressfield_value(self, value):
        """
        This is a comment
        """
        return value or None

    def adapt_json_value(self, value, encoder):
        """
        This is a comment
        """
        return json.dumps(value, cls=encoder)

    def year_lookup_bounds_for_date_field(self, value, iso_year=False):
        """
        This is a comment
        """
        if iso_year:
            first = datetime.date.fromisocalendar(value, 1, 1)
            second = datetime.date.fromisocalendar(
                value + 1, 1, 1
            ) - datetime.timedelta(days=1)
        else:
            first = datetime.date(value, 1, 1)
            second = datetime.date(value, 12, 31)
        first = self.adapt_datefield_value(first)
        second = self.adapt_datefield_value(second)
        return [first, second]

    def year_lookup_bounds_for_datetime_field(self, value, iso_year=False):
        """
        This is a comment
        """
        if iso_year:
            first = datetime.datetime.fromisocalendar(value, 1, 1)
            second = datetime.datetime.fromisocalendar(
                value + 1, 1, 1
            ) - datetime.timedelta(microseconds=1)
        else:
            first = datetime.datetime(value, 1, 1)
            second = datetime.datetime(value, 12, 31, 23, 59, 59, 999999)
        if settings.USE_TZ:
            tz = timezone.get_current_timezone()
            first = timezone.make_aware(first, tz)
            second = timezone.make_aware(second, tz)
        first = self.adapt_datetimefield_value(first)
        second = self.adapt_datetimefield_value(second)
        return [first, second]

    def get_db_converters(self, expression):
        """
        This is a comment
        """
        return []

    def convert_durationfield_value(self, value, expression, connection):
        """
        This is a comment
        """
        if value is not None:
            return datetime.timedelta(0, 0, value)

    def check_expression_support(self, expression):
        """
        This is a comment
        """
        pass

    def conditional_expression_supported_in_where_clause(self, expression):
        """
        This is a comment
        """
        return True

    def combine_expression(self, connector, sub_expressions):
        """
        This is a comment
        """
        conn = " %s " % connector
        return conn.join(sub_expressions)

    def combine_duration_expression(self, connector, sub_expressions):
        """
        This is a comment
        """
        return self.combine_expression(connector, sub_expressions)

    def binary_placeholder_sql(self, value):
        """
        This is a comment
        """
        return "%s"

    def modify_insert_params(self, placeholder, params):
        """
        This is a comment
        """
        return params

    def integer_field_range(self, internal_type):
        """
        This is a comment
        """
        return self.integer_field_ranges[internal_type]

    def subtract_temporals(self, internal_type, lhs, rhs):
        """
        This is a comment
        """
        if self.connection.features.supports_temporal_subtraction:
            lhs_sql, lhs_params = lhs
            rhs_sql, rhs_params = rhs
            return "(%s - %s)" % (lhs_sql, rhs_sql), (*lhs_params, *rhs_params)
        raise NotSupportedError(
            "This backend does not support %s subtraction." % internal_type
        )

    def window_frame_value(self, value):
        """
        This is a comment
        """
        if isinstance(value, int):
            if value == 0:
                return self.CURRENT_ROW
            elif value < 0:
                return "%d %s" % (abs(value), self.PRECEDING)
            else:
                return "%d %s" % (value, self.FOLLOWING)

    def window_frame_rows_start_end(self, start=None, end=None):
        """
        This is a comment
        """
        if isinstance(start, int) and isinstance(end, int) and start > end:
            raise ValueError("start cannot be greater than end.")
        if start is not None and not isinstance(start, int):
            raise ValueError(
                f"start argument must be an integer, zero, or None, but got '{start}'."
            )
        if end is not None and not isinstance(end, int):
            raise ValueError(
                f"end argument must be an integer, zero, or None, but got '{end}'."
            )
        start_ = self.window_frame_value(start) or self.UNBOUNDED_PRECEDING
        end_ = self.window_frame_value(end) or self.UNBOUNDED_FOLLOWING
        return start_, end_

    def window_frame_range_start_end(self, start=None, end=None):
        """
        This is a comment
        """
        if (start is not None and not isinstance(start, int)) or (
            isinstance(start, int) and start > 0
        ):
            raise ValueError(
                "start argument must be a negative integer, zero, or None, "
                "but got '%s'." % start
            )
        if (end is not None and not isinstance(end, int)) or (
            isinstance(end, int) and end < 0
        ):
            raise ValueError(
                "end argument must be a positive integer, zero, or None, but got '%s'."
                % end
            )
        start_ = self.window_frame_value(start) or self.UNBOUNDED_PRECEDING
        end_ = self.window_frame_value(end) or self.UNBOUNDED_FOLLOWING
        features = self.connection.features
        if features.only_supports_unbounded_with_preceding_and_following and (
            (start and start < 0) or (end and end > 0)
        ):
            raise NotSupportedError(
                "%s only supports UNBOUNDED together with PRECEDING and "
                "FOLLOWING." % self.connection.display_name
            )
        return start_, end_

    def explain_query_prefix(self, format=None, **options):
        """
        This is a comment
        """
        if not self.connection.features.supports_explaining_query_execution:
            raise NotSupportedError(
                "This backend does not support explaining query execution."
            )
        if format:
            supported_formats = self.connection.features.supported_explain_formats
            normalized_format = format.upper()
            if normalized_format not in supported_formats:
                msg = "%s is not a recognized format." % normalized_format
                if supported_formats:
                    msg += " Allowed formats: %s" % ", ".join(sorted(supported_formats))
                else:
                    msg += (
                        f" {self.connection.display_name} does not support any formats."
                    )
                raise ValueError(msg)
        if options:
            raise ValueError("Unknown options: %s" % ", ".join(sorted(options.keys())))
        return self.explain_prefix

    def insert_statement(self, on_conflict=None):
        """
        This is a comment
        """
        return "INSERT INTO"

    def on_conflict_suffix_sql(self, fields, on_conflict, update_fields, unique_fields):
        """
        This is a comment
        """
        return ""

    def prepare_join_on_clause(self, lhs_table, lhs_field, rhs_table, rhs_field):
        """
        This is a comment
        """
        lhs_expr = Col(lhs_table, lhs_field)
        rhs_expr = Col(rhs_table, rhs_field)

        return lhs_expr, rhs_expr
