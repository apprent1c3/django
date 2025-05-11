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
        Delegate attribute access to the underlying cursor, wrapping database error attributes for exceptions handling.
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
        Executes a stored database procedure with the given name, optionally passing positional and keyword parameters.

        :param procname: The name of the stored procedure to call
        :param params: Positional parameters to pass to the procedure
        :param kparams: Keyword parameters to pass to the procedure

        :raises NotSupportedError: If keyword parameters are used with a database backend that does not support them
        :raises RuntimeWarning: If the call is made before the application is fully initialized
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
        Execute a SQL query on the database.

        :param sql: The SQL statement to be executed
        :param params: Parameters to be used in the SQL query, or None for no parameters
        :return: The result of the query execution
        :warning: If the application is not ready, a RuntimeWarning is issued

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
        Executes a SQL query with multiple parameter sets in a single database call.

        :param sql: The SQL query to execute
        :param param_list: List of parameter tuples, one for each execution of the query
        :return: Result of the executemany operation
        :raises RuntimeError: If the database is in an invalid state or if the apps are not ready.
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

        It optionally uses the last executed query if :param:`use_last_executed_query` is True.
        Logged information includes the query itself, execution time, and query parameters.

        :param sql: The SQL query to be logged
        :param params: Parameters used in the SQL query
        :param use_last_executed_query: Whether to use the last executed query instead of the provided one
        :param many: Whether the query was executed multiple times with different parameters

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
    Context manager for logging and timing SQL transactions.

    Automatically logs the duration and details of the SQL query, if query logging is enabled on the connection.

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
    Split a time zone name into a 3-tuple of (name, sign, offset).
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
    Converts a string representation of time into a datetime.time object.

    Parameters
    ----------
    s : str
        Time in the format 'HH:MM:SS' or 'HH:MM:SS.SSSSSS'.

    Returns
    -------
    datetime.time
        The time as a datetime.time object, or None if the input string is empty.
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
    Converts a timestamp string into a datetime object, handling various input formats, including optional UTC offset. The function returns None if the input string is empty, otherwise it parses the string into its constituent date and time parts, then constructs a datetime object from these components.
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
    Split an SQL identifier into a two element tuple of (namespace, name).

    The identifier could be a table, column, or sequence name might be prefixed
    by a namespace.
    """
    try:
        namespace, name = identifier.split('"."')
    except ValueError:
        namespace, name = "", identifier
    return namespace.strip('"'), name.strip('"')


def truncate_name(identifier, length=None, hash_len=4):
    """
    Shorten an SQL identifier to a repeatable mangled version with the given
    length.

    If a quote stripped name contains a namespace, e.g. USERNAME"."TABLE,
    truncate the table portion only.
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
    Generate a 32-bit digest of a set of arguments that can be used to shorten
    identifying names.
    """
    h = md5(usedforsecurity=False)
    for arg in args:
        h.update(arg.encode())
    return h.hexdigest()[:length]


def format_number(value, max_digits, decimal_places):
    """
    Format a number into a string with the requisite number of digits and
    decimal places.
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
