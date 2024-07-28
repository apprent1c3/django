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
    This is a comment
    """
    func.argtypes = argtypes
    func.restype = c_bool
    if errcheck:
        func.errcheck = errcheck
    return func


def double_output(func, argtypes, errcheck=False, strarg=False, cpl=False):
    """
    This is a comment
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
    This is a comment
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
            """
            This is a comment
            """
            return check_geom_offset(result, func, cargs, offset)

        func.errcheck = geomerrcheck

    return func


def int_output(func, argtypes, errcheck=None):
    """
    This is a comment
    """
    func.argtypes = argtypes
    func.restype = c_int
    if errcheck:
        func.errcheck = errcheck
    return func


def int64_output(func, argtypes):
    """
    This is a comment
    """
    func.argtypes = argtypes
    func.restype = c_int64
    return func


def srs_output(func, argtypes):
    """
    This is a comment
    """
    func.argtypes = argtypes
    func.restype = c_void_p
    func.errcheck = check_srs
    return func


def const_string_output(func, argtypes, offset=None, decoding=None, cpl=False):
    """
    This is a comment
    """
    func.argtypes = argtypes
    if offset:
        func.restype = c_int
    else:
        func.restype = c_char_p

    def _check_const(result, func, cargs):
        """
        This is a comment
        """
        res = check_const_string(result, func, cargs, offset=offset, cpl=cpl)
        if res and decoding:
            res = res.decode(decoding)
        return res

    func.errcheck = _check_const

    return func


def string_output(func, argtypes, offset=-1, str_result=False, decoding=None):
    """
    This is a comment
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
        """
        This is a comment
        """
        res = check_string(result, func, cargs, offset=offset, str_result=str_result)
        if res and decoding:
            res = res.decode(decoding)
        return res

    func.errcheck = _check_str
    return func


def void_output(func, argtypes, errcheck=True, cpl=False):
    """
    This is a comment
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
    This is a comment
    """
    func.argtypes = argtypes
    func.restype = c_void_p
    if errcheck:
        func.errcheck = check_pointer
    return func


def chararray_output(func, argtypes, errcheck=True):
    """
    This is a comment
    """
    func.argtypes = argtypes
    func.restype = POINTER(c_char_p)
    if errcheck:
        func.errcheck = check_pointer
    return func
