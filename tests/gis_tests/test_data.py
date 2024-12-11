"""
This module has the mock object definitions used to hold reference geometry
for the GEOS and GDAL tests.
"""

import json
import os

from django.utils.functional import cached_property

# Path where reference test data is located.
TEST_DATA = os.path.join(os.path.dirname(__file__), "data")


def tuplize(seq):
    "Turn all nested sequences to tuples in given sequence."
    if isinstance(seq, (list, tuple)):
        return tuple(tuplize(i) for i in seq)
    return seq


def strconvert(d):
    "Converts all keys in dictionary to str type."
    return {str(k): v for k, v in d.items()}


def get_ds_file(name, ext):
    return os.path.join(TEST_DATA, name, name + ".%s" % ext)


class TestObj:
    """
    Base testing object, turns keyword args into attributes.
    """

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestDS(TestObj):
    """
    Object for testing GDAL data sources.
    """

    def __init__(self, name, *, ext="shp", **kwargs):
        # Shapefile is default extension, unless specified otherwise.
        self.name = name
        self.ds = get_ds_file(name, ext)
        super().__init__(**kwargs)


class TestGeom(TestObj):
    """
    Testing object used for wrapping reference geometry data
    in GEOS/GDAL tests.
    """

    def __init__(self, *, coords=None, centroid=None, ext_ring_cs=None, **kwargs):
        # Converting lists to tuples of certain keyword args
        # so coordinate test cases will match (JSON has no
        # concept of tuple).
        if coords:
            self.coords = tuplize(coords)
        if centroid:
            self.centroid = tuple(centroid)
        self.ext_ring_cs = ext_ring_cs and tuplize(ext_ring_cs)
        super().__init__(**kwargs)


class TestGeomSet:
    """
    Each attribute of this object is a list of `TestGeom` instances.
    """

    def __init__(self, **kwargs):
        """

        Initializes the object with keyword arguments, dynamically setting attributes with the provided names.

        The keyword arguments should have values that are lists of dictionaries, where each dictionary represents a geometric test input.
        These dictionaries are converted to :class:`TestGeom` objects and stored as lists in the corresponding attributes of the object.

        For example, passing ``geo1=[{'param1': 'value1'}, {'param2': 'value2'}]`` and ``geo2=[{'param3': 'value3'}]`` would result in the object having attributes ``geo1`` and ``geo2`` with the respective lists of :class:`TestGeom` objects.

        """
        for key, value in kwargs.items():
            setattr(self, key, [TestGeom(**strconvert(kw)) for kw in value])


class TestDataMixin:
    """
    Mixin used for GEOS/GDAL test cases that defines a `geometries`
    property, which returns and/or loads the reference geometry data.
    """

    @cached_property
    def geometries(self):
        # Load up the test geometry data from fixture into global.
        """
        Returns a set of test geometries loaded from a predefined JSON file.

        This property provides access to a collection of geometric data, which is
        initialized only once and then cached for subsequent access. The geometries
        are represented as a :class:`TestGeomSet` instance, allowing for easy
        manipulation and querying of the data.

        :return: A :class:`TestGeomSet` object containing the test geometries.

        """
        with open(os.path.join(TEST_DATA, "geometries.json")) as f:
            geometries = json.load(f)
        return TestGeomSet(**strconvert(geometries))
