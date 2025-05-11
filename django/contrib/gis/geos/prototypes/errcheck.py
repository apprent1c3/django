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
    "Return the last C argument's value by reference."
    return args[-1]._obj.value


def check_dbl(result, func, cargs):
    "Check the status code and returns the double value passed in by reference."
    # Checking the status code
    if result != 1:
        return None
    # Double passed in by reference, return its value.
    return last_arg_byref(cargs)


def check_geom(result, func, cargs):
    "Error checking on routines that return Geometries."
    if not result:
        raise GEOSException(
            'Error encountered checking Geometry returned from GEOS C function "%s".'
            % func.__name__
        )
    return result


def check_minus_one(result, func, cargs):
    """
    Checks the result of a GEOS C function call for error indication (-1) and raises an exception if an error occurred, otherwise returns the result.
    """
    if result == -1:
        raise GEOSException(
            'Error encountered in GEOS C function "%s".' % func.__name__
        )
    else:
        return result


def check_predicate(result, func, cargs):
    """
    Checks the result of a GEOS C predicate function and returns a boolean value, raising an exception if an error occurs.
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
    Error checking for routines that return explicitly sized strings, freeing allocated memory and returning the string value if valid, or raising an exception on invalid string pointers.
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
    Checks the result of a GEOS C function that returns a string, freeing any allocated memory and raising an exception on errors.
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
