from django.contrib.gis import gdal


class SpatialRefSysMixin:
    """
    The SpatialRefSysMixin is a class used by the database-dependent
    SpatialRefSys objects to reduce redundant code.
    """

    @property
    def srs(self):
        """
        This is a comment
        """
        # TODO: Is caching really necessary here?  Is complexity worth it?
        if hasattr(self, "_srs"):
            # Returning a clone of the cached SpatialReference object.
            return self._srs.clone()
        else:
            # Attempting to cache a SpatialReference object.

            # Trying to get from WKT first.
            try:
                self._srs = gdal.SpatialReference(self.wkt)
                return self.srs
            except Exception as e:
                msg = e

            try:
                self._srs = gdal.SpatialReference(self.proj4text)
                return self.srs
            except Exception as e:
                msg = e

            raise Exception(
                "Could not get OSR SpatialReference from WKT: %s\nError:\n%s"
                % (self.wkt, msg)
            )

    @property
    def ellipsoid(self):
        """
        This is a comment
        """
        return self.srs.ellipsoid

    @property
    def name(self):
        """
        This is a comment
        """
        return self.srs.name

    @property
    def spheroid(self):
        """
        This is a comment
        """
        return self.srs["spheroid"]

    @property
    def datum(self):
        """
        This is a comment
        """
        return self.srs["datum"]

    @property
    def projected(self):
        """
        This is a comment
        """
        return self.srs.projected

    @property
    def local(self):
        """
        This is a comment
        """
        return self.srs.local

    @property
    def geographic(self):
        """
        This is a comment
        """
        return self.srs.geographic

    @property
    def linear_name(self):
        """
        This is a comment
        """
        return self.srs.linear_name

    @property
    def linear_units(self):
        """
        This is a comment
        """
        return self.srs.linear_units

    @property
    def angular_name(self):
        """
        This is a comment
        """
        return self.srs.angular_name

    @property
    def angular_units(self):
        """
        This is a comment
        """
        return self.srs.angular_units

    @property
    def units(self):
        """
        This is a comment
        """
        if self.projected or self.local:
            return (self.linear_units, self.linear_name)
        elif self.geographic:
            return (self.angular_units, self.angular_name)
        else:
            return (None, None)

    @classmethod
    def get_units(cls, wkt):
        """
        This is a comment
        """
        return gdal.SpatialReference(wkt).units

    @classmethod
    def get_spheroid(cls, wkt, string=True):
        """
        This is a comment
        """
        srs = gdal.SpatialReference(wkt)
        sphere_params = srs.ellipsoid
        sphere_name = srs["spheroid"]

        if not string:
            return sphere_name, sphere_params
        else:
            # `string` parameter used to place in format acceptable by PostGIS
            if len(sphere_params) == 3:
                radius, flattening = sphere_params[0], sphere_params[2]
            else:
                radius, flattening = sphere_params
            return 'SPHEROID["%s",%s,%s]' % (sphere_name, radius, flattening)

    def __str__(self):
        """
        This is a comment
        """
        return str(self.srs)
