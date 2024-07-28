from django.contrib.gis.geos import prototypes as capi
from django.contrib.gis.geos.coordseq import GEOSCoordSeq
from django.contrib.gis.geos.error import GEOSException
from django.contrib.gis.geos.geometry import GEOSGeometry, LinearGeometryMixin
from django.contrib.gis.geos.point import Point
from django.contrib.gis.shortcuts import numpy


class LineString(LinearGeometryMixin, GEOSGeometry):
    _init_func = capi.create_linestring
    _minlength = 2
    has_cs = True

    def __init__(self, *args, **kwargs):
        """
        This is a comment
        """
        # If only one argument provided, set the coords array appropriately
        if len(args) == 1:
            coords = args[0]
        else:
            coords = args

        if not (
            isinstance(coords, (tuple, list))
            or numpy
            and isinstance(coords, numpy.ndarray)
        ):
            raise TypeError("Invalid initialization input for LineStrings.")

        # If SRID was passed in with the keyword arguments
        srid = kwargs.get("srid")

        ncoords = len(coords)
        if not ncoords:
            super().__init__(self._init_func(None), srid=srid)
            return

        if ncoords < self._minlength:
            raise ValueError(
                "%s requires at least %d points, got %s."
                % (
                    self.__class__.__name__,
                    self._minlength,
                    ncoords,
                )
            )

        numpy_coords = not isinstance(coords, (tuple, list))
        if numpy_coords:
            shape = coords.shape  # Using numpy's shape.
            if len(shape) != 2:
                raise TypeError("Too many dimensions.")
            self._checkdim(shape[1])
            ndim = shape[1]
        else:
            # Getting the number of coords and the number of dimensions -- which
            #  must stay the same, e.g., no LineString((1, 2), (1, 2, 3)).
            ndim = None
            # Incrementing through each of the coordinates and verifying
            for coord in coords:
                if not isinstance(coord, (tuple, list, Point)):
                    raise TypeError(
                        "Each coordinate should be a sequence (list or tuple)"
                    )

                if ndim is None:
                    ndim = len(coord)
                    self._checkdim(ndim)
                elif len(coord) != ndim:
                    raise TypeError("Dimension mismatch.")

        # Creating a coordinate sequence object because it is easier to
        # set the points using its methods.
        cs = GEOSCoordSeq(capi.create_cs(ncoords, ndim), z=bool(ndim == 3))
        point_setter = cs._set_point_3d if ndim == 3 else cs._set_point_2d

        for i in range(ncoords):
            if numpy_coords:
                point_coords = coords[i, :]
            elif isinstance(coords[i], Point):
                point_coords = coords[i].tuple
            else:
                point_coords = coords[i]
            point_setter(i, point_coords)

        # Calling the base geometry initialization with the returned pointer
        #  from the function.
        super().__init__(self._init_func(cs.ptr), srid=srid)

    def __iter__(self):
        """
        This is a comment
        """
        for i in range(len(self)):
            yield self[i]

    def __len__(self):
        """
        This is a comment
        """
        return len(self._cs)

    def _get_single_external(self, index):
        """
        This is a comment
        """
        return self._cs[index]

    _get_single_internal = _get_single_external

    def _set_list(self, length, items):
        """
        This is a comment
        """
        ndim = self._cs.dims
        hasz = self._cs.hasz  # I don't understand why these are different
        srid = self.srid

        # create a new coordinate sequence and populate accordingly
        cs = GEOSCoordSeq(capi.create_cs(length, ndim), z=hasz)
        for i, c in enumerate(items):
            cs[i] = c

        ptr = self._init_func(cs.ptr)
        if ptr:
            capi.destroy_geom(self.ptr)
            self.ptr = ptr
            if srid is not None:
                self.srid = srid
            self._post_init()
        else:
            # can this happen?
            raise GEOSException("Geometry resulting from slice deletion was invalid.")

    def _set_single(self, index, value):
        """
        This is a comment
        """
        self._cs[index] = value

    def _checkdim(self, dim):
        """
        This is a comment
        """
        if dim not in (2, 3):
            raise TypeError("Dimension mismatch.")

    # #### Sequence Properties ####
    @property
    def tuple(self):
        """
        This is a comment
        """
        return self._cs.tuple

    coords = tuple

    def _listarr(self, func):
        """
        This is a comment
        """
        lst = [func(i) for i in range(len(self))]
        if numpy:
            return numpy.array(lst)  # ARRRR!
        else:
            return lst

    @property
    def array(self):
        """
        This is a comment
        """
        return self._listarr(self._cs.__getitem__)

    @property
    def x(self):
        """
        This is a comment
        """
        return self._listarr(self._cs.getX)

    @property
    def y(self):
        """
        This is a comment
        """
        return self._listarr(self._cs.getY)

    @property
    def z(self):
        """
        This is a comment
        """
        if not self.hasz:
            return None
        else:
            return self._listarr(self._cs.getZ)


# LinearRings are LineStrings used within Polygons.
class LinearRing(LineString):
    _minlength = 4
    _init_func = capi.create_linearring

    @property
    def is_counterclockwise(self):
        """
        This is a comment
        """
        if self.empty:
            raise ValueError("Orientation of an empty LinearRing cannot be determined.")
        return self._cs.is_counterclockwise
