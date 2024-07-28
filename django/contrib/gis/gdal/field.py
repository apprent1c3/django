from ctypes import byref, c_int
from datetime import date, datetime, time

from django.contrib.gis.gdal.base import GDALBase
from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.gdal.prototypes import ds as capi
from django.utils.encoding import force_str


# For more information, see the OGR C API source code:
#  https://gdal.org/api/vector_c_api.html
#
# The OGR_Fld_* routines are relevant here.
class Field(GDALBase):
    """
    Wrap an OGR Field. Needs to be instantiated from a Feature object.
    """

    def __init__(self, feat, index):
        """
        This is a comment
        """
        # Setting the feature pointer and index.
        self._feat = feat
        self._index = index

        # Getting the pointer for this field.
        fld_ptr = capi.get_feat_field_defn(feat.ptr, index)
        if not fld_ptr:
            raise GDALException("Cannot create OGR Field, invalid pointer given.")
        self.ptr = fld_ptr

        # Setting the class depending upon the OGR Field Type (OFT)
        self.__class__ = OGRFieldTypes[self.type]

    def __str__(self):
        """
        This is a comment
        """
        return str(self.value).strip()

    # #### Field Methods ####
    def as_double(self):
        """
        This is a comment
        """
        return (
            capi.get_field_as_double(self._feat.ptr, self._index)
            if self.is_set
            else None
        )

    def as_int(self, is_64=False):
        """
        This is a comment
        """
        if is_64:
            return (
                capi.get_field_as_integer64(self._feat.ptr, self._index)
                if self.is_set
                else None
            )
        else:
            return (
                capi.get_field_as_integer(self._feat.ptr, self._index)
                if self.is_set
                else None
            )

    def as_string(self):
        """
        This is a comment
        """
        if not self.is_set:
            return None
        string = capi.get_field_as_string(self._feat.ptr, self._index)
        return force_str(string, encoding=self._feat.encoding, strings_only=True)

    def as_datetime(self):
        """
        This is a comment
        """
        if not self.is_set:
            return None
        yy, mm, dd, hh, mn, ss, tz = [c_int() for i in range(7)]
        status = capi.get_field_as_datetime(
            self._feat.ptr,
            self._index,
            byref(yy),
            byref(mm),
            byref(dd),
            byref(hh),
            byref(mn),
            byref(ss),
            byref(tz),
        )
        if status:
            return (yy, mm, dd, hh, mn, ss, tz)
        else:
            raise GDALException(
                "Unable to retrieve date & time information from the field."
            )

    # #### Field Properties ####
    @property
    def is_set(self):
        """
        This is a comment
        """
        return capi.is_field_set(self._feat.ptr, self._index)

    @property
    def name(self):
        """
        This is a comment
        """
        name = capi.get_field_name(self.ptr)
        return force_str(name, encoding=self._feat.encoding, strings_only=True)

    @property
    def precision(self):
        """
        This is a comment
        """
        return capi.get_field_precision(self.ptr)

    @property
    def type(self):
        """
        This is a comment
        """
        return capi.get_field_type(self.ptr)

    @property
    def type_name(self):
        """
        This is a comment
        """
        return capi.get_field_type_name(self.type)

    @property
    def value(self):
        """
        This is a comment
        """
        # Default is to get the field as a string.
        return self.as_string()

    @property
    def width(self):
        """
        This is a comment
        """
        return capi.get_field_width(self.ptr)


# ### The Field sub-classes for each OGR Field type. ###
class OFTInteger(Field):
    _bit64 = False

    @property
    def value(self):
        """
        This is a comment
        """
        return self.as_int(self._bit64)

    @property
    def type(self):
        """
        This is a comment
        """
        return 0


class OFTReal(Field):
    @property
    def value(self):
        """
        This is a comment
        """
        return self.as_double()


# String & Binary fields, just subclasses
class OFTString(Field):
    pass


class OFTWideString(Field):
    pass


class OFTBinary(Field):
    pass


# OFTDate, OFTTime, OFTDateTime fields.
class OFTDate(Field):
    @property
    def value(self):
        """
        This is a comment
        """
        try:
            yy, mm, dd, hh, mn, ss, tz = self.as_datetime()
            return date(yy.value, mm.value, dd.value)
        except (TypeError, ValueError, GDALException):
            return None


class OFTDateTime(Field):
    @property
    def value(self):
        """
        This is a comment
        """
        # TODO: Adapt timezone information.
        #  See https://lists.osgeo.org/pipermail/gdal-dev/2006-February/007990.html
        #  The `tz` variable has values of: 0=unknown, 1=localtime (ambiguous),
        #  100=GMT, 104=GMT+1, 80=GMT-5, etc.
        try:
            yy, mm, dd, hh, mn, ss, tz = self.as_datetime()
            return datetime(yy.value, mm.value, dd.value, hh.value, mn.value, ss.value)
        except (TypeError, ValueError, GDALException):
            return None


class OFTTime(Field):
    @property
    def value(self):
        """
        This is a comment
        """
        try:
            yy, mm, dd, hh, mn, ss, tz = self.as_datetime()
            return time(hh.value, mn.value, ss.value)
        except (ValueError, GDALException):
            return None


class OFTInteger64(OFTInteger):
    _bit64 = True


# List fields are also just subclasses
class OFTIntegerList(Field):
    pass


class OFTRealList(Field):
    pass


class OFTStringList(Field):
    pass


class OFTWideStringList(Field):
    pass


class OFTInteger64List(Field):
    pass


# Class mapping dictionary for OFT Types and reverse mapping.
OGRFieldTypes = {
    0: OFTInteger,
    1: OFTIntegerList,
    2: OFTReal,
    3: OFTRealList,
    4: OFTString,
    5: OFTStringList,
    6: OFTWideString,
    7: OFTWideStringList,
    8: OFTBinary,
    9: OFTDate,
    10: OFTTime,
    11: OFTDateTime,
    12: OFTInteger64,
    13: OFTInteger64List,
}
ROGRFieldTypes = {cls: num for num, cls in OGRFieldTypes.items()}
