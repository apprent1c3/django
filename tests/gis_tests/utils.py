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
        def skip_wrapper(*args, **kwargs):
            """
            Skips the decorated test function if the database does not support all required geographic information system (GIS) lookups.

            Checks if the database supports all GIS lookups specified in :data:`gis_lookups` before executing the test function.
            If any of the required lookups are not supported, raises a :class:`~unittest.SkipTest` exception.
            Otherwise, calls the original test function with the provided arguments.

            This wrapper is used to ensure that GIS-related tests are only executed on databases that support the necessary functionality.

            """
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
        Set up test environment to ensure database function immutability during compilation.

        This set up method patches the :class:`Func` class to monitor its state during the compilation process.
        It checks if the function's internal state has changed after compilation by comparing its dictionary before and after the compilation.
        If any changes are detected, an assertion error is raised to prevent potential bugs.

        The patching is specific to the current database vendor and only affects the `as_sql` method or its vendor-specific variant.
        After the set up is complete, the original `__getattribute__` method is restored at the end of the test to prevent side effects. 
        """
        def as_sql_wrapper(original_as_sql):
            """
            Decorator function that wraps an ``as_sql`` method to ensure it does not mutate the object it is called on.

            The wrapped method is called with the original arguments and keyword arguments, but before and after the call, the object's internal state is checked to ensure it has not changed.

            If the object's internal state has changed, an assertion error is raised with a message indicating that the object was mutated during compilation.

            This decorator is useful for testing and validating the behavior of ``as_sql`` methods in immutable objects, helping to prevent unintended side effects and making the code more predictable and reliable.

            :returns: The result of the wrapped ``as_sql`` method call.

            """
            def inner(*args, **kwargs):
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
            Override the default attribute access to intercept and wrap the SQL generation functionality.

            This method customizes the attribute retrieval for the vendor implementation or the as_sql method.
            When the attribute being accessed is the vendor implementation, it attempts to retrieve it.
            If the vendor implementation is not found, it falls back to the as_sql method.
            The retrieved SQL generation function is then wrapped in a custom wrapper function to provide additional functionality.

            Returns the wrapped SQL generation function for the vendor implementation or the as_sql method.

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
