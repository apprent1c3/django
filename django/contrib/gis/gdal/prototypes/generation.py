"""
 This module contains functions that generate ctypes prototypes for the
 GDAL routines.
"""

from ctypes import POINTER, c_bool, c_char_p, c_double, c_int, c_int64, c_void_p
from functools import partial

from django.contrib.gis.gdal.prototypes.errcheck import (
    check_arg_errcode,
    check_const_string,
    check_errcode,
    check_geom,
    check_geom_offset,
    check_pointer,
    check_srs,
    check_str_arg,
    check_string,
)


class gdal_char_p(c_char_p):
    pass


def bool_output(func, argtypes, errcheck=None):
    """

    Modify a ctypes function to return a boolean value.

    This function configures the input and output types of a ctypes function and optionally sets an error checking function. The modified function returns a boolean value (True or False).

    """
    func.argtypes = argtypes
    func.restype = c_bool
    if errcheck:
        func.errcheck = errcheck
    return func


def double_output(func, argtypes, errcheck=False, strarg=False, cpl=False):
    """
    Configures a ctypes function to return a double value and optionally adds error checking and string argument handling.

    :param func: The ctypes function to be configured
    :param argtypes: The argument types of the function
    :param errcheck: Whether to enable error checking (default: False)
    :param strarg: Whether to check for string argument errors (default: False)
    :param cpl: A flag used in error checking (default: False)
    :return: The configured ctypes function
    """
    func.argtypes = argtypes
    func.restype = c_double
    if errcheck:
        func.errcheck = partial(check_arg_errcode, cpl=cpl)
    if strarg:
        func.errcheck = check_str_arg
    return func


def geom_output(func, argtypes, offset=None):
    """

    Generate a function wrapper with specified argument and return types, 
    configured to handle geometry output either by reference or directly.

    """
    # Setting the argument types
    func.argtypes = argtypes

    if not offset:
        # When a geometry pointer is directly returned.
        func.restype = c_void_p
        func.errcheck = check_geom
    else:
        # Error code returned, geometry is returned by-reference.
        func.restype = c_int

        def geomerrcheck(result, func, cargs):
            return check_geom_offset(result, func, cargs, offset)

        func.errcheck = geomerrcheck

    return func


def int_output(func, argtypes, errcheck=None):
    """
    Configures a ctypes function to return an integer value, specifying the argument types and optionally an error checking function.
    """
    func.argtypes = argtypes
    func.restype = c_int
    if errcheck:
        func.errcheck = errcheck
    return func


def int64_output(func, argtypes):
    "Generate a ctypes function that returns a 64-bit integer value."
    func.argtypes = argtypes
    func.restype = c_int64
    return func


def srs_output(func, argtypes):
    """
    Generate a ctypes prototype for a function that returns a Spatial Reference System, configuring it to accept the specified C argument types and handle errors accordingly.
    """
    func.argtypes = argtypes
    func.restype = c_void_p
    func.errcheck = check_srs
    return func


def const_string_output(func, argtypes, offset=None, decoding=None, cpl=False):
    """
    Configures a ctypes function to output a constant string, handling optional offset, decoding, and exception checking.

    _PARAM func_: The ctypes function to configure.
    _PARAM argtypes_: The argument types of the function.
    _PARAM offset_: The offset at which the string is stored, defaults to None.
    _PARAM decoding_: The decoding to apply to the result, defaults to None.
    _PARAM cpl_: A flag to control exception checking, defaults to False.

    _RETURNS_: The configured function.
    """
    func.argtypes = argtypes
    if offset:
        func.restype = c_int
    else:
        func.restype = c_char_p

    def _check_const(result, func, cargs):
        res = check_const_string(result, func, cargs, offset=offset, cpl=cpl)
        if res and decoding:
            res = res.decode(decoding)
        return res

    func.errcheck = _check_const

    return func


def string_output(func, argtypes, offset=-1, str_result=False, decoding=None):
    """
    Generates a ctypes prototype for a given function that returns a string from a GDAL pointer, handling memory management and string decoding as specified. The function configures the prototype's argument and return types, and sets up error checking for string results.
    """
    func.argtypes = argtypes
    if str_result:
        # Use subclass of c_char_p so the error checking routine
        # can free the memory at the pointer's address.
        func.restype = gdal_char_p
    else:
        # Error code is returned
        func.restype = c_int

    # Dynamically defining our error-checking function with the
    # given offset.
    def _check_str(result, func, cargs):
        res = check_string(result, func, cargs, offset=offset, str_result=str_result)
        if res and decoding:
            res = res.decode(decoding)
        return res

    func.errcheck = _check_str
    return func


def void_output(func, argtypes, errcheck=True, cpl=False):
    """
    Configures a function with specified argument types and error checking behavior, suitable for functions returning error codes that require examination. Allows for customization of error checking and CPL behavior.
    """
    if argtypes:
        func.argtypes = argtypes
    if errcheck:
        # `errcheck` keyword may be set to False for routines that
        # return void, rather than a status code.
        func.restype = c_int
        func.errcheck = partial(check_errcode, cpl=cpl)
    else:
        func.restype = None

    return func


def voidptr_output(func, argtypes, errcheck=True):
    """
    Configures a C function that returns a void pointer, setting its argument and return types, and optionally enabling error checking.
    """
    func.argtypes = argtypes
    func.restype = c_void_p
    if errcheck:
        func.errcheck = check_pointer
    return func


def chararray_output(func, argtypes, errcheck=True):
    """
    Configures a ctypes function to return an array of char pointers, setting the function's argument and return types, and optionally enabling error checking to verify the returned pointer.
    """
    func.argtypes = argtypes
    func.restype = POINTER(c_char_p)
    if errcheck:
        func.errcheck = check_pointer
    return func
