import copy
import unittest
from functools import wraps
from unittest import mock

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, connection
from django.db.models import Func


def skipUnlessGISLookup(*gis_lookups):
    """
    Decorator to conditionally skip a test based on database support for specified GIS lookups.

    Parameters
    ----------
    *gis_lookups : str
        Names of GIS lookup operators to check for database support.

    Returns
    -------
    function
        Decorated test function that skips execution if the database does not support all the specified GIS lookups.

    """

    def decorator(test_func):
        @wraps(test_func)
        """
        Decorator to skip a test if the database doesn't support the required GIS lookups, ensuring test consistency across different databases.
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
        .. method:: setUp(self)

            Sets up the test environment by patching the Func class to ensure 
            that its instance state does not change during the compilation of SQL queries. 
            This is achieved by wrapping the as_sql method of the vendor-specific 
            implementation to compare the state of the function before and after compilation.
        """
        def as_sql_wrapper(original_as_sql):
            """

            Decorates a function to ensure its execution does not mutate the instance's state.
            Preserves the original function's behavior and returns its result, while asserting 
            that the instance's attributes remain unchanged during function execution.

            """
            def inner(*args, **kwargs):
                """
                '''Wrapper function to ensure that the original function remains unmodified during compilation.

                It executes the original function with provided arguments, verifies that the function's state remains unchanged, 
                and returns the result of the original function.'''
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
            ..:noindex:
                Override the default attribute access to intercept and wrap the ``as_sql`` or vendor-specific implementation method, ensuring it is properly decorated before being returned.
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
