import copy
import unittest
from functools import wraps
from unittest import mock

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, connection
from django.db.models import Func


def skipUnlessGISLookup(*gis_lookups):
    """
    Skip a test unless a database supports all of gis_lookups.
    """

    def decorator(test_func):
        @wraps(test_func)
        """

        Decorator to skip the test function if the database does not support all required GIS lookups.

        Raises:
            unittest.SkipTest: If the database does not support all GIS lookups in :data:`gis_lookups`.

        """
        def skip_wrapper(*args, **kwargs):
            if any(key not in connection.ops.gis_operators for key in gis_lookups):
                raise unittest.SkipTest(
                    "Database doesn't support all the lookups: %s"
                    % ", ".join(gis_lookups)
                )
            return test_func(*args, **kwargs)

        return skip_wrapper

    return decorator


_default_db = settings.DATABASES[DEFAULT_DB_ALIAS]["ENGINE"].rsplit(".")[-1]
# MySQL spatial indices can't handle NULL geometries.
gisfield_may_be_null = _default_db != "mysql"


class FuncTestMixin:
    """Assert that Func expressions aren't mutated during their as_sql()."""

    def setUp(self):
        """
        Sets up a test environment to ensure that database functions are not mutated during compilation, by patching the function's `as_sql` method to check for attribute changes.
        """
        def as_sql_wrapper(original_as_sql):
            """
            Ensures that a given function's state remains unchanged after execution.

            This wrapper function verifies that the original function does not mutate its instance during compilation, 
            by comparing its internal state before and after execution. If a mutation is detected, an assertion error is raised.

            :param original_as_sql: The original function to be wrapped.
            :returns: The wrapped function with the added assertion check.
            :raises: AssertionError if the function's state is changed during execution.

            """
            def inner(*args, **kwargs):
                """
                Ensures a function's internal state remains unchanged during execution.

                Invokes the original function with provided arguments, while verifying that its 
                attributes do not undergo any modifications in the process, raising an assertion 
                error if any changes are detected.

                Returns the result of the original function call.
                """
                func = original_as_sql.__self__
                # Resolve output_field before as_sql() so touching it in
                # as_sql() won't change __dict__.
                func.output_field
                __dict__original = copy.deepcopy(func.__dict__)
                result = original_as_sql(*args, **kwargs)
                msg = (
                    "%s Func was mutated during compilation." % func.__class__.__name__
                )
                self.assertEqual(func.__dict__, __dict__original, msg)
                return result

            return inner

        def __getattribute__(self, name):
            """

            Custom attribute accessor that intercepts access to the vendor implementation attribute,
            wrapping its result with as_sql_wrapper to handle vendor-specific SQL generation.

            """
            if name != vendor_impl:
                return __getattribute__original(self, name)
            try:
                as_sql = __getattribute__original(self, vendor_impl)
            except AttributeError:
                as_sql = __getattribute__original(self, "as_sql")
            return as_sql_wrapper(as_sql)

        vendor_impl = "as_" + connection.vendor
        __getattribute__original = Func.__getattribute__
        func_patcher = mock.patch.object(Func, "__getattribute__", __getattribute__)
        func_patcher.start()
        self.addCleanup(func_patcher.stop)
        super().setUp()
