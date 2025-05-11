import datetime
import decimal
import functools
import logging
import time
import warnings
from contextlib import contextmanager
from hashlib import md5

from django.apps import apps
from django.db import NotSupportedError
from django.utils.dateparse import parse_time

logger = logging.getLogger("django.db.backends")


class CursorWrapper:
    def __init__(self, cursor, db):
        self.cursor = cursor
        self.db = db

    WRAP_ERROR_ATTRS = frozenset(["fetchone", "fetchmany", "fetchall", "nextset"])

    APPS_NOT_READY_WARNING_MSG = (
        "Accessing the database during app initialization is discouraged. To fix this "
        "warning, avoid executing queries in AppConfig.ready() or when your app "
        "modules are imported."
    )

    def __getattr__(self, attr):
        """
        Delegates attribute access to the underlying cursor object, optionally wrapping database error handling around the accessed attribute.
        """
        cursor_attr = getattr(self.cursor, attr)
        if attr in CursorWrapper.WRAP_ERROR_ATTRS:
            return self.db.wrap_database_errors(cursor_attr)
        else:
            return cursor_attr

    def __iter__(self):
        with self.db.wrap_database_errors:
            yield from self.cursor

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        # Close instead of passing through to avoid backend-specific behavior
        # (#17671). Catch errors liberally because errors in cleanup code
        # aren't useful.
        try:
            self.close()
        except self.db.Database.Error:
            pass

    # The following methods cannot be implemented in __getattr__, because the
    # code must run when the method is invoked, not just when it is accessed.

    def callproc(self, procname, params=None, kparams=None):
        # Keyword parameters for callproc aren't supported in PEP 249, but the
        # database driver may support them (e.g. oracledb).
        """
        Invokes a stored database procedure with optional positional and keyword parameters.

        Args:
            procname (str): Name of the stored procedure to call.
            params (tuple, optional): Positional parameters to pass to the procedure. Defaults to None.
            kparams (dict, optional): Keyword parameters to pass to the procedure. Defaults to None.

        Note:
            The support for keyword parameters depends on the database backend.
            This method raises a warning if the Django application is not ready and no stored application configurations are available.

        """
        if kparams is not None and not self.db.features.supports_callproc_kwargs:
            raise NotSupportedError(
                "Keyword parameters for callproc are not supported on this "
                "database backend."
            )
        # Raise a warning during app initialization (stored_app_configs is only
        # ever set during testing).
        if not apps.ready and not apps.stored_app_configs:
            warnings.warn(self.APPS_NOT_READY_WARNING_MSG, category=RuntimeWarning)
        self.db.validate_no_broken_transaction()
        with self.db.wrap_database_errors:
            if params is None and kparams is None:
                return self.cursor.callproc(procname)
            elif kparams is None:
                return self.cursor.callproc(procname, params)
            else:
                params = params or ()
                return self.cursor.callproc(procname, params, kparams)

    def execute(self, sql, params=None):
        return self._execute_with_wrappers(
            sql, params, many=False, executor=self._execute
        )

    def executemany(self, sql, param_list):
        return self._execute_with_wrappers(
            sql, param_list, many=True, executor=self._executemany
        )

    def _execute_with_wrappers(self, sql, params, many, executor):
        context = {"connection": self.db, "cursor": self}
        for wrapper in reversed(self.db.execute_wrappers):
            executor = functools.partial(wrapper, executor)
        return executor(sql, params, many, context)

    def _execute(self, sql, params, *ignored_wrapper_args):
        # Raise a warning during app initialization (stored_app_configs is only
        # ever set during testing).
        """
        Executes a SQL query on the database, handling potential errors and warnings.

        Parameters
        ----------
        sql : str
            The SQL query to be executed.
        params : tuple or None
            Parameters to be used in the SQL query, or None if no parameters are required.

        Returns
        -------
        The result of the SQL query execution.

        Notes
        -----
        If the Django application is not ready, a runtime warning is issued. The function also checks for broken database transactions and wraps database errors.

        """
        if not apps.ready and not apps.stored_app_configs:
            warnings.warn(self.APPS_NOT_READY_WARNING_MSG, category=RuntimeWarning)
        self.db.validate_no_broken_transaction()
        with self.db.wrap_database_errors:
            if params is None:
                # params default might be backend specific.
                return self.cursor.execute(sql)
            else:
                return self.cursor.execute(sql, params)

    def _executemany(self, sql, param_list, *ignored_wrapper_args):
        # Raise a warning during app initialization (stored_app_configs is only
        # ever set during testing).
        """

        Executes a single SQL query with multiple sets of parameters.

        This method is used to efficiently execute the same SQL query with different parameters.
        It checks for database readiness and validates that there are no broken transactions before execution.

        """
        if not apps.ready and not apps.stored_app_configs:
            warnings.warn(self.APPS_NOT_READY_WARNING_MSG, category=RuntimeWarning)
        self.db.validate_no_broken_transaction()
        with self.db.wrap_database_errors:
            return self.cursor.executemany(sql, param_list)


class CursorDebugWrapper(CursorWrapper):
    # XXX callproc isn't instrumented at this time.

    def execute(self, sql, params=None):
        with self.debug_sql(sql, params, use_last_executed_query=True):
            return super().execute(sql, params)

    def executemany(self, sql, param_list):
        with self.debug_sql(sql, param_list, many=True):
            return super().executemany(sql, param_list)

    @contextmanager
    def debug_sql(
        self, sql=None, params=None, use_last_executed_query=False, many=False
    ):
        """

        Context manager to measure and log the execution time of a SQL query.

         Measures the time taken to execute the query and logs the query with its execution time and parameters.
         The query is also added to the database's query log.

         :param str sql: The SQL query to be executed
         :param params: The parameters for the SQL query
         :param bool use_last_executed_query: Whether to use the last executed query
         :param bool many: Whether the query is executed multiple times

        """
        start = time.monotonic()
        try:
            yield
        finally:
            stop = time.monotonic()
            duration = stop - start
            if use_last_executed_query:
                sql = self.db.ops.last_executed_query(self.cursor, sql, params)
            try:
                times = len(params) if many else ""
            except TypeError:
                # params could be an iterator.
                times = "?"
            self.db.queries_log.append(
                {
                    "sql": "%s times: %s" % (times, sql) if many else sql,
                    "time": "%.3f" % duration,
                }
            )
            logger.debug(
                "(%.3f) %s; args=%s; alias=%s",
                duration,
                sql,
                params,
                self.db.alias,
                extra={
                    "duration": duration,
                    "sql": sql,
                    "params": params,
                    "alias": self.db.alias,
                },
            )


@contextmanager
def debug_transaction(connection, sql):
    """
    A context manager that measures the execution time of a transaction and logs the result.

    Logs the SQL query, its execution time, and connection details for debugging purposes if query logging is enabled for the connection.

    Calling this function creates a runtime context that ensures execution time is captured and logged when the block is exited, allowing for performance monitoring and debugging of database transactions.
    """
    start = time.monotonic()
    try:
        yield
    finally:
        if connection.queries_logged:
            stop = time.monotonic()
            duration = stop - start
            connection.queries_log.append(
                {
                    "sql": "%s" % sql,
                    "time": "%.3f" % duration,
                }
            )
            logger.debug(
                "(%.3f) %s; args=%s; alias=%s",
                duration,
                sql,
                None,
                connection.alias,
                extra={
                    "duration": duration,
                    "sql": sql,
                    "alias": connection.alias,
                },
            )


def split_tzname_delta(tzname):
    """
    Split a time zone name into its components, including the base time zone name, offset sign and offset in hours and minutes. The function returns a tuple with three values: name, sign of the offset and the offset itself, or returns the original time zone name with None values if it cannot be parsed into the expected format.
    """
    for sign in ["+", "-"]:
        if sign in tzname:
            name, offset = tzname.rsplit(sign, 1)
            if offset and parse_time(offset):
                if ":" not in offset:
                    offset = f"{offset}:00"
                return name, sign, offset
    return tzname, None, None


###############################################
# Converters from database (string) to Python #
###############################################


def typecast_date(s):
    return (
        datetime.date(*map(int, s.split("-"))) if s else None
    )  # return None if s is null


def typecast_time(s):  # does NOT store time zone information
    """

    Converts a time string in 'HH:MM:SS.SSSSSS' format to a datetime.time object.

    Returns None for empty input string.

    """
    if not s:
        return None
    hour, minutes, seconds = s.split(":")
    if "." in seconds:  # check whether seconds have a fractional part
        seconds, microseconds = seconds.split(".")
    else:
        microseconds = "0"
    return datetime.time(
        int(hour), int(minutes), int(seconds), int((microseconds + "000000")[:6])
    )


def typecast_timestamp(s):  # does NOT store time zone information
    # "2005-07-29 15:48:00.590358-05"
    # "2005-07-29 09:56:00-05"
    """
    Converts a string representation of a timestamp into a datetime object, handling various input formats and time zones. Returns None for empty input strings.
    """
    if not s:
        return None
    if " " not in s:
        return typecast_date(s)
    d, t = s.split()
    # Remove timezone information.
    if "-" in t:
        t, _ = t.split("-", 1)
    elif "+" in t:
        t, _ = t.split("+", 1)
    dates = d.split("-")
    times = t.split(":")
    seconds = times[2]
    if "." in seconds:  # check whether seconds have a fractional part
        seconds, microseconds = seconds.split(".")
    else:
        microseconds = "0"
    return datetime.datetime(
        int(dates[0]),
        int(dates[1]),
        int(dates[2]),
        int(times[0]),
        int(times[1]),
        int(seconds),
        int((microseconds + "000000")[:6]),
    )


###############################################
# Converters from Python to database (string) #
###############################################


def split_identifier(identifier):
    """
    Split an SQL identifier into its namespace and name components, handling both prefixed and unprefixed names.
    """
    try:
        namespace, name = identifier.split('"."')
    except ValueError:
        namespace, name = "", identifier
    return namespace.strip('"'), name.strip('"')


def truncate_name(identifier, length=None, hash_len=4):
    """
    Shorten an SQL identifier to a consistent, mangled version with a specified length, truncating the table portion only if the identifier contains a namespace.
    """
    namespace, name = split_identifier(identifier)

    if length is None or len(name) <= length:
        return identifier

    digest = names_digest(name, length=hash_len)
    return "%s%s%s" % (
        '%s"."' % namespace if namespace else "",
        name[: length - hash_len],
        digest,
    )


def names_digest(*args, length):
    """
    Generate a condensed identifier from multiple input strings, producing a fixed-length hash digest that can be used to shorten identifying names, based on the provided arguments and desired output length.
    """
    h = md5(usedforsecurity=False)
    for arg in args:
        h.update(arg.encode())
    return h.hexdigest()[:length]


def format_number(value, max_digits, decimal_places):
    """
    Format a number into a string, controlling the total number of digits and the number of decimal places, to ensure consistent numerical output.
    """
    if value is None:
        return None
    context = decimal.getcontext().copy()
    if max_digits is not None:
        context.prec = max_digits
    if decimal_places is not None:
        value = value.quantize(
            decimal.Decimal(1).scaleb(-decimal_places), context=context
        )
    else:
        context.traps[decimal.Rounded] = 1
        value = context.create_decimal(value)
    return "{:f}".format(value)


def strip_quotes(table_name):
    """
    Strip quotes off of quoted table names to make them safe for use in index
    names, sequence names, etc. For example '"USER"."TABLE"' (an Oracle naming
    scheme) becomes 'USER"."TABLE'.
    """
    has_quotes = table_name.startswith('"') and table_name.endswith('"')
    return table_name[1:-1] if has_quotes else table_name
