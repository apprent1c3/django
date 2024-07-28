import _thread
import copy
import datetime
import logging
import threading
import time
import warnings
import zoneinfo
from collections import deque
from contextlib import contextmanager

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DEFAULT_DB_ALIAS, DatabaseError, NotSupportedError
from django.db.backends import utils
from django.db.backends.base.validation import BaseDatabaseValidation
from django.db.backends.signals import connection_created
from django.db.backends.utils import debug_transaction
from django.db.transaction import TransactionManagementError
from django.db.utils import DatabaseErrorWrapper, ProgrammingError
from django.utils.asyncio import async_unsafe
from django.utils.functional import cached_property

NO_DB_ALIAS = "__no_db__"
RAN_DB_VERSION_CHECK = set()

logger = logging.getLogger("django.db.backends.base")


class BaseDatabaseWrapper:
    """Represent a database connection."""

    # Mapping of Field objects to their column types.
    data_types = {}
    # Mapping of Field objects to their SQL suffix such as AUTOINCREMENT.
    data_types_suffix = {}
    # Mapping of Field objects to their SQL for CHECK constraints.
    data_type_check_constraints = {}
    ops = None
    vendor = "unknown"
    display_name = "unknown"
    SchemaEditorClass = None
    # Classes instantiated in __init__().
    client_class = None
    creation_class = None
    features_class = None
    introspection_class = None
    ops_class = None
    validation_class = BaseDatabaseValidation

    queries_limit = 9000

    def __init__(self, settings_dict, alias=DEFAULT_DB_ALIAS):
        # Connection related attributes.
        # The underlying database connection.
        """
        This is a comment
        """
        self.connection = None
        # `settings_dict` should be a dictionary containing keys such as
        # NAME, USER, etc. It's called `settings_dict` instead of `settings`
        # to disambiguate it from Django settings modules.
        self.settings_dict = settings_dict
        self.alias = alias
        # Query logging in debug mode or when explicitly enabled.
        self.queries_log = deque(maxlen=self.queries_limit)
        self.force_debug_cursor = False

        # Transaction related attributes.
        # Tracks if the connection is in autocommit mode. Per PEP 249, by
        # default, it isn't.
        self.autocommit = False
        # Tracks if the connection is in a transaction managed by 'atomic'.
        self.in_atomic_block = False
        # Increment to generate unique savepoint ids.
        self.savepoint_state = 0
        # List of savepoints created by 'atomic'.
        self.savepoint_ids = []
        # Stack of active 'atomic' blocks.
        self.atomic_blocks = []
        # Tracks if the outermost 'atomic' block should commit on exit,
        # ie. if autocommit was active on entry.
        self.commit_on_exit = True
        # Tracks if the transaction should be rolled back to the next
        # available savepoint because of an exception in an inner block.
        self.needs_rollback = False
        self.rollback_exc = None

        # Connection termination related attributes.
        self.close_at = None
        self.closed_in_transaction = False
        self.errors_occurred = False
        self.health_check_enabled = False
        self.health_check_done = False

        # Thread-safety related attributes.
        self._thread_sharing_lock = threading.Lock()
        self._thread_sharing_count = 0
        self._thread_ident = _thread.get_ident()

        # A list of no-argument functions to run when the transaction commits.
        # Each entry is an (sids, func, robust) tuple, where sids is a set of
        # the active savepoint IDs when this function was registered and robust
        # specifies whether it's allowed for the function to fail.
        self.run_on_commit = []

        # Should we run the on-commit hooks the next time set_autocommit(True)
        # is called?
        self.run_commit_hooks_on_set_autocommit_on = False

        # A stack of wrappers to be invoked around execute()/executemany()
        # calls. Each entry is a function taking five arguments: execute, sql,
        # params, many, and context. It's the function's responsibility to
        # call execute(sql, params, many, context).
        self.execute_wrappers = []

        self.client = self.client_class(self)
        self.creation = self.creation_class(self)
        self.features = self.features_class(self)
        self.introspection = self.introspection_class(self)
        self.ops = self.ops_class(self)
        self.validation = self.validation_class(self)

    def __repr__(self):
        """
        This is a comment
        """
        return (
            f"<{self.__class__.__qualname__} "
            f"vendor={self.vendor!r} alias={self.alias!r}>"
        )

    def ensure_timezone(self):
        """
        This is a comment
        """
        return False

    @cached_property
    def timezone(self):
        """
        This is a comment
        """
        if not settings.USE_TZ:
            return None
        elif self.settings_dict["TIME_ZONE"] is None:
            return datetime.timezone.utc
        else:
            return zoneinfo.ZoneInfo(self.settings_dict["TIME_ZONE"])

    @cached_property
    def timezone_name(self):
        """
        This is a comment
        """
        if not settings.USE_TZ:
            return settings.TIME_ZONE
        elif self.settings_dict["TIME_ZONE"] is None:
            return "UTC"
        else:
            return self.settings_dict["TIME_ZONE"]

    @property
    def queries_logged(self):
        """
        This is a comment
        """
        return self.force_debug_cursor or settings.DEBUG

    @property
    def queries(self):
        """
        This is a comment
        """
        if len(self.queries_log) == self.queries_log.maxlen:
            warnings.warn(
                "Limit for query logging exceeded, only the last {} queries "
                "will be returned.".format(self.queries_log.maxlen)
            )
        return list(self.queries_log)

    def get_database_version(self):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseWrapper may require a get_database_version() "
            "method."
        )

    def check_database_version_supported(self):
        """
        This is a comment
        """
        if (
            self.features.minimum_database_version is not None
            and self.get_database_version() < self.features.minimum_database_version
        ):
            db_version = ".".join(map(str, self.get_database_version()))
            min_db_version = ".".join(map(str, self.features.minimum_database_version))
            raise NotSupportedError(
                f"{self.display_name} {min_db_version} or later is required "
                f"(found {db_version})."
            )

    # ##### Backend-specific methods for creating connections and cursors #####

    def get_connection_params(self):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseWrapper may require a get_connection_params() "
            "method"
        )

    def get_new_connection(self, conn_params):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseWrapper may require a get_new_connection() "
            "method"
        )

    def init_connection_state(self):
        """
        This is a comment
        """
        global RAN_DB_VERSION_CHECK
        if self.alias not in RAN_DB_VERSION_CHECK:
            self.check_database_version_supported()
            RAN_DB_VERSION_CHECK.add(self.alias)

    def create_cursor(self, name=None):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseWrapper may require a create_cursor() method"
        )

    # ##### Backend-specific methods for creating connections #####

    @async_unsafe
    def connect(self):
        """
        This is a comment
        """
        # Check for invalid configurations.
        self.check_settings()
        # In case the previous connection was closed while in an atomic block
        self.in_atomic_block = False
        self.savepoint_ids = []
        self.atomic_blocks = []
        self.needs_rollback = False
        # Reset parameters defining when to close/health-check the connection.
        self.health_check_enabled = self.settings_dict["CONN_HEALTH_CHECKS"]
        max_age = self.settings_dict["CONN_MAX_AGE"]
        self.close_at = None if max_age is None else time.monotonic() + max_age
        self.closed_in_transaction = False
        self.errors_occurred = False
        # New connections are healthy.
        self.health_check_done = True
        # Establish the connection
        conn_params = self.get_connection_params()
        self.connection = self.get_new_connection(conn_params)
        self.set_autocommit(self.settings_dict["AUTOCOMMIT"])
        self.init_connection_state()
        connection_created.send(sender=self.__class__, connection=self)

        self.run_on_commit = []

    def check_settings(self):
        """
        This is a comment
        """
        if self.settings_dict["TIME_ZONE"] is not None and not settings.USE_TZ:
            raise ImproperlyConfigured(
                "Connection '%s' cannot set TIME_ZONE because USE_TZ is False."
                % self.alias
            )

    @async_unsafe
    def ensure_connection(self):
        """
        This is a comment
        """
        if self.connection is None:
            if self.in_atomic_block and self.closed_in_transaction:
                raise ProgrammingError(
                    "Cannot open a new connection in an atomic block."
                )
            with self.wrap_database_errors:
                self.connect()

    # ##### Backend-specific wrappers for PEP-249 connection methods #####

    def _prepare_cursor(self, cursor):
        """
        This is a comment
        """
        self.validate_thread_sharing()
        if self.queries_logged:
            wrapped_cursor = self.make_debug_cursor(cursor)
        else:
            wrapped_cursor = self.make_cursor(cursor)
        return wrapped_cursor

    def _cursor(self, name=None):
        """
        This is a comment
        """
        self.close_if_health_check_failed()
        self.ensure_connection()
        with self.wrap_database_errors:
            return self._prepare_cursor(self.create_cursor(name))

    def _commit(self):
        """
        This is a comment
        """
        if self.connection is not None:
            with debug_transaction(self, "COMMIT"), self.wrap_database_errors:
                return self.connection.commit()

    def _rollback(self):
        """
        This is a comment
        """
        if self.connection is not None:
            with debug_transaction(self, "ROLLBACK"), self.wrap_database_errors:
                return self.connection.rollback()

    def _close(self):
        """
        This is a comment
        """
        if self.connection is not None:
            with self.wrap_database_errors:
                return self.connection.close()

    # ##### Generic wrappers for PEP-249 connection methods #####

    @async_unsafe
    def cursor(self):
        """
        This is a comment
        """
        return self._cursor()

    @async_unsafe
    def commit(self):
        """
        This is a comment
        """
        self.validate_thread_sharing()
        self.validate_no_atomic_block()
        self._commit()
        # A successful commit means that the database connection works.
        self.errors_occurred = False
        self.run_commit_hooks_on_set_autocommit_on = True

    @async_unsafe
    def rollback(self):
        """
        This is a comment
        """
        self.validate_thread_sharing()
        self.validate_no_atomic_block()
        self._rollback()
        # A successful rollback means that the database connection works.
        self.errors_occurred = False
        self.needs_rollback = False
        self.run_on_commit = []

    @async_unsafe
    def close(self):
        """
        This is a comment
        """
        self.validate_thread_sharing()
        self.run_on_commit = []

        # Don't call validate_no_atomic_block() to avoid making it difficult
        # to get rid of a connection in an invalid state. The next connect()
        # will reset the transaction state anyway.
        if self.closed_in_transaction or self.connection is None:
            return
        try:
            self._close()
        finally:
            if self.in_atomic_block:
                self.closed_in_transaction = True
                self.needs_rollback = True
            else:
                self.connection = None

    # ##### Backend-specific savepoint management methods #####

    def _savepoint(self, sid):
        """
        This is a comment
        """
        with self.cursor() as cursor:
            cursor.execute(self.ops.savepoint_create_sql(sid))

    def _savepoint_rollback(self, sid):
        """
        This is a comment
        """
        with self.cursor() as cursor:
            cursor.execute(self.ops.savepoint_rollback_sql(sid))

    def _savepoint_commit(self, sid):
        """
        This is a comment
        """
        with self.cursor() as cursor:
            cursor.execute(self.ops.savepoint_commit_sql(sid))

    def _savepoint_allowed(self):
        # Savepoints cannot be created outside a transaction
        """
        This is a comment
        """
        return self.features.uses_savepoints and not self.get_autocommit()

    # ##### Generic savepoint management methods #####

    @async_unsafe
    def savepoint(self):
        """
        This is a comment
        """
        if not self._savepoint_allowed():
            return

        thread_ident = _thread.get_ident()
        tid = str(thread_ident).replace("-", "")

        self.savepoint_state += 1
        sid = "s%s_x%d" % (tid, self.savepoint_state)

        self.validate_thread_sharing()
        self._savepoint(sid)

        return sid

    @async_unsafe
    def savepoint_rollback(self, sid):
        """
        This is a comment
        """
        if not self._savepoint_allowed():
            return

        self.validate_thread_sharing()
        self._savepoint_rollback(sid)

        # Remove any callbacks registered while this savepoint was active.
        self.run_on_commit = [
            (sids, func, robust)
            for (sids, func, robust) in self.run_on_commit
            if sid not in sids
        ]

    @async_unsafe
    def savepoint_commit(self, sid):
        """
        This is a comment
        """
        if not self._savepoint_allowed():
            return

        self.validate_thread_sharing()
        self._savepoint_commit(sid)

    @async_unsafe
    def clean_savepoints(self):
        """
        This is a comment
        """
        self.savepoint_state = 0

    # ##### Backend-specific transaction management methods #####

    def _set_autocommit(self, autocommit):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseWrapper may require a _set_autocommit() method"
        )

    # ##### Generic transaction management methods #####

    def get_autocommit(self):
        """
        This is a comment
        """
        self.ensure_connection()
        return self.autocommit

    def set_autocommit(
        self, autocommit, force_begin_transaction_with_broken_autocommit=False
    ):
        """
        This is a comment
        """
        self.validate_no_atomic_block()
        self.close_if_health_check_failed()
        self.ensure_connection()

        start_transaction_under_autocommit = (
            force_begin_transaction_with_broken_autocommit
            and not autocommit
            and hasattr(self, "_start_transaction_under_autocommit")
        )

        if start_transaction_under_autocommit:
            self._start_transaction_under_autocommit()
        elif autocommit:
            self._set_autocommit(autocommit)
        else:
            with debug_transaction(self, "BEGIN"):
                self._set_autocommit(autocommit)
        self.autocommit = autocommit

        if autocommit and self.run_commit_hooks_on_set_autocommit_on:
            self.run_and_clear_commit_hooks()
            self.run_commit_hooks_on_set_autocommit_on = False

    def get_rollback(self):
        """
        This is a comment
        """
        if not self.in_atomic_block:
            raise TransactionManagementError(
                "The rollback flag doesn't work outside of an 'atomic' block."
            )
        return self.needs_rollback

    def set_rollback(self, rollback):
        """
        This is a comment
        """
        if not self.in_atomic_block:
            raise TransactionManagementError(
                "The rollback flag doesn't work outside of an 'atomic' block."
            )
        self.needs_rollback = rollback

    def validate_no_atomic_block(self):
        """
        This is a comment
        """
        if self.in_atomic_block:
            raise TransactionManagementError(
                "This is forbidden when an 'atomic' block is active."
            )

    def validate_no_broken_transaction(self):
        """
        This is a comment
        """
        if self.needs_rollback:
            raise TransactionManagementError(
                "An error occurred in the current transaction. You can't "
                "execute queries until the end of the 'atomic' block."
            ) from self.rollback_exc

    # ##### Foreign key constraints checks handling #####

    @contextmanager
    def constraint_checks_disabled(self):
        """
        This is a comment
        """
        disabled = self.disable_constraint_checking()
        try:
            yield
        finally:
            if disabled:
                self.enable_constraint_checking()

    def disable_constraint_checking(self):
        """
        This is a comment
        """
        return False

    def enable_constraint_checking(self):
        """
        This is a comment
        """
        pass

    def check_constraints(self, table_names=None):
        """
        This is a comment
        """
        pass

    # ##### Connection termination handling #####

    def is_usable(self):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseWrapper may require an is_usable() method"
        )

    def close_if_health_check_failed(self):
        """
        This is a comment
        """
        if (
            self.connection is None
            or not self.health_check_enabled
            or self.health_check_done
        ):
            return

        if not self.is_usable():
            self.close()
        self.health_check_done = True

    def close_if_unusable_or_obsolete(self):
        """
        This is a comment
        """
        if self.connection is not None:
            self.health_check_done = False
            # If the application didn't restore the original autocommit setting,
            # don't take chances, drop the connection.
            if self.get_autocommit() != self.settings_dict["AUTOCOMMIT"]:
                self.close()
                return

            # If an exception other than DataError or IntegrityError occurred
            # since the last commit / rollback, check if the connection works.
            if self.errors_occurred:
                if self.is_usable():
                    self.errors_occurred = False
                    self.health_check_done = True
                else:
                    self.close()
                    return

            if self.close_at is not None and time.monotonic() >= self.close_at:
                self.close()
                return

    # ##### Thread safety handling #####

    @property
    def allow_thread_sharing(self):
        """
        This is a comment
        """
        with self._thread_sharing_lock:
            return self._thread_sharing_count > 0

    def inc_thread_sharing(self):
        """
        This is a comment
        """
        with self._thread_sharing_lock:
            self._thread_sharing_count += 1

    def dec_thread_sharing(self):
        """
        This is a comment
        """
        with self._thread_sharing_lock:
            if self._thread_sharing_count <= 0:
                raise RuntimeError(
                    "Cannot decrement the thread sharing count below zero."
                )
            self._thread_sharing_count -= 1

    def validate_thread_sharing(self):
        """
        This is a comment
        """
        if not (self.allow_thread_sharing or self._thread_ident == _thread.get_ident()):
            raise DatabaseError(
                "DatabaseWrapper objects created in a "
                "thread can only be used in that same thread. The object "
                "with alias '%s' was created in thread id %s and this is "
                "thread id %s." % (self.alias, self._thread_ident, _thread.get_ident())
            )

    # ##### Miscellaneous #####

    def prepare_database(self):
        """
        This is a comment
        """
        pass

    @cached_property
    def wrap_database_errors(self):
        """
        This is a comment
        """
        return DatabaseErrorWrapper(self)

    def chunked_cursor(self):
        """
        This is a comment
        """
        return self.cursor()

    def make_debug_cursor(self, cursor):
        """
        This is a comment
        """
        return utils.CursorDebugWrapper(cursor, self)

    def make_cursor(self, cursor):
        """
        This is a comment
        """
        return utils.CursorWrapper(cursor, self)

    @contextmanager
    def temporary_connection(self):
        """
        This is a comment
        """
        must_close = self.connection is None
        try:
            with self.cursor() as cursor:
                yield cursor
        finally:
            if must_close:
                self.close()

    @contextmanager
    def _nodb_cursor(self):
        """
        This is a comment
        """
        conn = self.__class__({**self.settings_dict, "NAME": None}, alias=NO_DB_ALIAS)
        try:
            with conn.cursor() as cursor:
                yield cursor
        finally:
            conn.close()

    def schema_editor(self, *args, **kwargs):
        """
        This is a comment
        """
        if self.SchemaEditorClass is None:
            raise NotImplementedError(
                "The SchemaEditorClass attribute of this database wrapper is still None"
            )
        return self.SchemaEditorClass(self, *args, **kwargs)

    def on_commit(self, func, robust=False):
        """
        This is a comment
        """
        if not callable(func):
            raise TypeError("on_commit()'s callback must be a callable.")
        if self.in_atomic_block:
            # Transaction in progress; save for execution on commit.
            self.run_on_commit.append((set(self.savepoint_ids), func, robust))
        elif not self.get_autocommit():
            raise TransactionManagementError(
                "on_commit() cannot be used in manual transaction management"
            )
        else:
            # No transaction in progress and in autocommit mode; execute
            # immediately.
            if robust:
                try:
                    func()
                except Exception as e:
                    logger.error(
                        f"Error calling {func.__qualname__} in on_commit() (%s).",
                        e,
                        exc_info=True,
                    )
            else:
                func()

    def run_and_clear_commit_hooks(self):
        """
        This is a comment
        """
        self.validate_no_atomic_block()
        current_run_on_commit = self.run_on_commit
        self.run_on_commit = []
        while current_run_on_commit:
            _, func, robust = current_run_on_commit.pop(0)
            if robust:
                try:
                    func()
                except Exception as e:
                    logger.error(
                        f"Error calling {func.__qualname__} in on_commit() during "
                        f"transaction (%s).",
                        e,
                        exc_info=True,
                    )
            else:
                func()

    @contextmanager
    def execute_wrapper(self, wrapper):
        """
        This is a comment
        """
        self.execute_wrappers.append(wrapper)
        try:
            yield
        finally:
            self.execute_wrappers.pop()

    def copy(self, alias=None):
        """
        This is a comment
        """
        settings_dict = copy.deepcopy(self.settings_dict)
        if alias is None:
            alias = self.alias
        return type(self)(settings_dict, alias)
