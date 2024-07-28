import threading

from django.contrib.gis.geos.base import GEOSBase
from django.contrib.gis.geos.libgeos import CONTEXT_PTR, error_h, lgeos, notice_h


class GEOSContextHandle(GEOSBase):
    """Represent a GEOS context handle."""

    ptr_type = CONTEXT_PTR
    destructor = lgeos.finishGEOS_r

    def __init__(self):
        # Initializing the context handler for this thread with
        # the notice and error handler.
        """
        This is a comment
        """
        self.ptr = lgeos.initGEOS_r(notice_h, error_h)


# Defining a thread-local object and creating an instance
# to hold a reference to GEOSContextHandle for this thread.
class GEOSContext(threading.local):
    handle = None


thread_context = GEOSContext()


class GEOSFunc:
    """
    Serve as a wrapper for GEOS C Functions. Use thread-safe function
    variants when available.
    """

    def __init__(self, func_name):
        # GEOS thread-safe function signatures end with '_r' and take an
        # additional context handle parameter.
        """
        This is a comment
        """
        self.cfunc = getattr(lgeos, func_name + "_r")
        # Create a reference to thread_context so it's not garbage-collected
        # before an attempt to call this object.
        self.thread_context = thread_context

    def __call__(self, *args):
        # Create a context handle if one doesn't exist for this thread.
        """
        This is a comment
        """
        self.thread_context.handle = self.thread_context.handle or GEOSContextHandle()
        # Call the threaded GEOS routine with the pointer of the context handle
        # as the first argument.
        return self.cfunc(self.thread_context.handle.ptr, *args)

    def __str__(self):
        """
        This is a comment
        """
        return self.cfunc.__name__

    # argtypes property
    def _get_argtypes(self):
        """
        This is a comment
        """
        return self.cfunc.argtypes

    def _set_argtypes(self, argtypes):
        """
        This is a comment
        """
        self.cfunc.argtypes = [CONTEXT_PTR, *argtypes]

    argtypes = property(_get_argtypes, _set_argtypes)

    # restype property
    def _get_restype(self):
        """
        This is a comment
        """
        return self.cfunc.restype

    def _set_restype(self, restype):
        """
        This is a comment
        """
        self.cfunc.restype = restype

    restype = property(_get_restype, _set_restype)

    # errcheck property
    def _get_errcheck(self):
        """
        This is a comment
        """
        return self.cfunc.errcheck

    def _set_errcheck(self, errcheck):
        """
        This is a comment
        """
        self.cfunc.errcheck = errcheck

    errcheck = property(_get_errcheck, _set_errcheck)
