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
        """

        Initializes the object with arbitrary keyword arguments.

        The constructor dynamically sets instance attributes based on the provided keyword arguments.
        Any keyword arguments passed to the constructor will become attributes of the object, allowing for flexible and dynamic initialization.

        """
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestDS(TestObj):
    """
    Object for testing GDAL data sources.
    """

    def __init__(self, name, *, ext="shp", **kwargs):
        # Shapefile is default extension, unless specified otherwise.
        """
        Initializes a new instance of the class.

        Parameters
        ----------
        name : str
            The name of the instance.
        ext : str, optional
            The file extension (default is 'shp').

        Additional keyword arguments are passed to the parent class's initializer.

        This method sets up the basic attributes of the instance, including the name and a dataset file object, which is retrieved using the provided name and extension.
        """
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
        """

        Initialize the object with optional coordinate and centroid data.

        The initializer can accept coordinates, a centroid, and an exterior ring coordinate system.
        If coordinates are provided, they are converted into a tuple for internal use.
        Similarly, the centroid is stored as a tuple and the exterior ring coordinate system is
        converted and stored if provided. Any additional keyword arguments are passed to the parent
        class initializer.

        :param coords: Optional coordinate data
        :param centroid: Optional centroid data
        :param ext_ring_cs: Optional exterior ring coordinate system

        """
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
        Returns a set of geometries from a predefined JSON file.

        This property loads the geometries from a JSON file located at a test data path and
        returns them as a :class:`TestGeomSet` object. The data is loaded and converted to
        the appropriate formats, allowing for easy access to the geometries.

        The geometries are cached to improve performance, meaning they are only loaded from
        the file once and subsequent calls to this property will return the cached result.

        :rtype: TestGeomSet
        """
        with open(os.path.join(TEST_DATA, "geometries.json")) as f:
            geometries = json.load(f)
        return TestGeomSet(**strconvert(geometries))
