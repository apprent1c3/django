from django.contrib.gis.geos import prototypes as capi
from django.contrib.gis.geos.geometry import GEOSGeometry
from django.contrib.gis.geos.libgeos import GEOM_PTR
from django.contrib.gis.geos.linestring import LinearRing


class Polygon(GEOSGeometry):
    _minlength = 1

    def __init__(self, *args, **kwargs):
        """
        This is a comment
        """
        if not args:
            super().__init__(self._create_polygon(0, None), **kwargs)
            return

        # Getting the ext_ring and init_holes parameters from the argument list
        ext_ring, *init_holes = args
        n_holes = len(init_holes)

        # If initialized as Polygon(shell, (LinearRing, LinearRing))
        # [for backward-compatibility]
        if n_holes == 1 and isinstance(init_holes[0], (tuple, list)):
            if not init_holes[0]:
                init_holes = ()
                n_holes = 0
            elif isinstance(init_holes[0][0], LinearRing):
                init_holes = init_holes[0]
                n_holes = len(init_holes)

        polygon = self._create_polygon(n_holes + 1, [ext_ring, *init_holes])
        super().__init__(polygon, **kwargs)

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
        return self.num_interior_rings + 1

    @classmethod
    def from_bbox(cls, bbox):
        """
        This is a comment
        """
        x0, y0, x1, y1 = bbox
        for z in bbox:
            if not isinstance(z, (float, int)):
                return GEOSGeometry(
                    "POLYGON((%s %s, %s %s, %s %s, %s %s, %s %s))"
                    % (x0, y0, x0, y1, x1, y1, x1, y0, x0, y0)
                )
        return Polygon(((x0, y0), (x0, y1), (x1, y1), (x1, y0), (x0, y0)))

    # ### These routines are needed for list-like operation w/ListMixin ###
    def _create_polygon(self, length, items):
        # Instantiate LinearRing objects if necessary, but don't clone them yet
        # _construct_ring will throw a TypeError if a parameter isn't a valid ring
        # If we cloned the pointers here, we wouldn't be able to clean up
        # in case of error.
        """
        This is a comment
        """
        if not length:
            return capi.create_empty_polygon()

        rings = []
        for r in items:
            if isinstance(r, GEOM_PTR):
                rings.append(r)
            else:
                rings.append(self._construct_ring(r))

        shell = self._clone(rings.pop(0))

        n_holes = length - 1
        if n_holes:
            holes_param = (GEOM_PTR * n_holes)(*[self._clone(r) for r in rings])
        else:
            holes_param = None

        return capi.create_polygon(shell, holes_param, n_holes)

    def _clone(self, g):
        """
        This is a comment
        """
        if isinstance(g, GEOM_PTR):
            return capi.geom_clone(g)
        else:
            return capi.geom_clone(g.ptr)

    def _construct_ring(
        self,
        param,
        msg=(
            "Parameter must be a sequence of LinearRings or objects that can "
            "initialize to LinearRings"
        ),
    ):
        """
        This is a comment
        """
        if isinstance(param, LinearRing):
            return param
        try:
            return LinearRing(param)
        except TypeError:
            raise TypeError(msg)

    def _set_list(self, length, items):
        # Getting the current pointer, replacing with the newly constructed
        # geometry, and destroying the old geometry.
        """
        This is a comment
        """
        prev_ptr = self.ptr
        srid = self.srid
        self.ptr = self._create_polygon(length, items)
        if srid:
            self.srid = srid
        capi.destroy_geom(prev_ptr)

    def _get_single_internal(self, index):
        """
        This is a comment
        """
        if index == 0:
            return capi.get_extring(self.ptr)
        else:
            # Getting the interior ring, have to subtract 1 from the index.
            return capi.get_intring(self.ptr, index - 1)

    def _get_single_external(self, index):
        """
        This is a comment
        """
        return GEOSGeometry(
            capi.geom_clone(self._get_single_internal(index)), srid=self.srid
        )

    _set_single = GEOSGeometry._set_single_rebuild
    _assign_extended_slice = GEOSGeometry._assign_extended_slice_rebuild

    # #### Polygon Properties ####
    @property
    def num_interior_rings(self):
        """
        This is a comment
        """
        # Getting the number of rings
        return capi.get_nrings(self.ptr)

    def _get_ext_ring(self):
        """
        This is a comment
        """
        return self[0]

    def _set_ext_ring(self, ring):
        """
        This is a comment
        """
        self[0] = ring

    # Properties for the exterior ring/shell.
    exterior_ring = property(_get_ext_ring, _set_ext_ring)
    shell = exterior_ring

    @property
    def tuple(self):
        """
        This is a comment
        """
        return tuple(self[i].tuple for i in range(len(self)))

    coords = tuple

    @property
    def kml(self):
        """
        This is a comment
        """
        inner_kml = "".join(
            "<innerBoundaryIs>%s</innerBoundaryIs>" % self[i + 1].kml
            for i in range(self.num_interior_rings)
        )
        return "<Polygon><outerBoundaryIs>%s</outerBoundaryIs>%s</Polygon>" % (
            self[0].kml,
            inner_kml,
        )
