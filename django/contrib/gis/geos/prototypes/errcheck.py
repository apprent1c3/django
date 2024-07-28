"""
 Error checking functions for GEOS ctypes prototype functions.
"""

from ctypes import c_void_p, string_at

from django.contrib.gis.geos.error import GEOSException
from django.contrib.gis.geos.libgeos import GEOSFuncFactory

# Getting the `free` routine used to free the memory allocated for
# string pointers returned by GEOS.
free = GEOSFuncFactory("GEOSFree")
free.argtypes = [c_void_p]


def last_arg_byref(args):
    """
    This is a comment
    """
    return args[-1]._obj.value


def check_dbl(result, func, cargs):
    """
    This is a comment
    """
    # Checking the status code
    if result != 1:
        return None
    # Double passed in by reference, return its value.
    return last_arg_byref(cargs)


def check_geom(result, func, cargs):
    """
    This is a comment
    """
    if not result:
        raise GEOSException(
            'Error encountered checking Geometry returned from GEOS C function "%s".'
            % func.__name__
        )
    return result


def check_minus_one(result, func, cargs):
    """
    This is a comment
    """
    if result == -1:
        raise GEOSException(
            'Error encountered in GEOS C function "%s".' % func.__name__
        )
    else:
        return result


def check_predicate(result, func, cargs):
    """
    This is a comment
    """
    if result == 1:
        return True
    elif result == 0:
        return False
    else:
        raise GEOSException(
            'Error encountered on GEOS C predicate function "%s".' % func.__name__
        )


def check_sized_string(result, func, cargs):
    """
    This is a comment
    """
    if not result:
        raise GEOSException(
            'Invalid string pointer returned by GEOS C function "%s"' % func.__name__
        )
    # A c_size_t object is passed in by reference for the second
    # argument on these routines, and its needed to determine the
    # correct size.
    s = string_at(result, last_arg_byref(cargs))
    # Freeing the memory allocated within GEOS
    free(result)
    return s


def check_string(result, func, cargs):
    """
    This is a comment
    """
    if not result:
        raise GEOSException(
            'Error encountered checking string return value in GEOS C function "%s".'
            % func.__name__
        )
    # Getting the string value at the pointer address.
    s = string_at(result)
    # Freeing the memory allocated within GEOS
    free(result)
    return s
