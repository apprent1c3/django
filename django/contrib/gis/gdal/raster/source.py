import json
import os
import sys
import uuid
from ctypes import (
    addressof,
    byref,
    c_buffer,
    c_char_p,
    c_double,
    c_int,
    c_void_p,
    string_at,
)
from pathlib import Path

from django.contrib.gis.gdal.driver import Driver
from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.gdal.prototypes import raster as capi
from django.contrib.gis.gdal.raster.band import BandList
from django.contrib.gis.gdal.raster.base import GDALRasterBase
from django.contrib.gis.gdal.raster.const import (
    GDAL_RESAMPLE_ALGORITHMS,
    VSI_DELETE_BUFFER_ON_READ,
    VSI_FILESYSTEM_PREFIX,
    VSI_MEM_FILESYSTEM_BASE_PATH,
    VSI_TAKE_BUFFER_OWNERSHIP,
)
from django.contrib.gis.gdal.srs import SpatialReference, SRSException
from django.contrib.gis.geometry import json_regex
from django.utils.encoding import force_bytes, force_str
from django.utils.functional import cached_property


class TransformPoint(list):
    indices = {
        "origin": (0, 3),
        "scale": (1, 5),
        "skew": (2, 4),
    }

    def __init__(self, raster, prop):
        """
        Initializes the object with a raster and a property, extracting the corresponding geotransform coordinates and setting up the base class with these coordinates.
        """
        x = raster.geotransform[self.indices[prop][0]]
        y = raster.geotransform[self.indices[prop][1]]
        super().__init__([x, y])
        self._raster = raster
        self._prop = prop

    @property
    def x(self):
        return self[0]

    @x.setter
    def x(self, value):
        gtf = self._raster.geotransform
        gtf[self.indices[self._prop][0]] = value
        self._raster.geotransform = gtf

    @property
    def y(self):
        return self[1]

    @y.setter
    def y(self, value):
        gtf = self._raster.geotransform
        gtf[self.indices[self._prop][1]] = value
        self._raster.geotransform = gtf


class GDALRaster(GDALRasterBase):
    """
    Wrap a raster GDAL Data Source object.
    """

    destructor = capi.close_ds

    def __init__(self, ds_input, write=False):
        """
        Initializes a raster data source object, allowing for various input types such as file paths, JSON strings, byte buffers, or dictionaries containing creation parameters. The input data source can be read-only or writable, depending on the specified `write` flag. The function handles different input formats and validation, creating a new data source if necessary, and raises exceptions for invalid inputs or failed creation attempts.
        """
        self._write = 1 if write else 0
        Driver.ensure_registered()

        # Preprocess json inputs. This converts json strings to dictionaries,
        # which are parsed below the same way as direct dictionary inputs.
        if isinstance(ds_input, str) and json_regex.match(ds_input):
            ds_input = json.loads(ds_input)

        # If input is a valid file path, try setting file as source.
        if isinstance(ds_input, (str, Path)):
            ds_input = str(ds_input)
            if not ds_input.startswith(VSI_FILESYSTEM_PREFIX) and not os.path.exists(
                ds_input
            ):
                raise GDALException(
                    'Unable to read raster source input "%s".' % ds_input
                )
            try:
                # GDALOpen will auto-detect the data source type.
                self._ptr = capi.open_ds(force_bytes(ds_input), self._write)
            except GDALException as err:
                raise GDALException(
                    'Could not open the datasource at "{}" ({}).'.format(ds_input, err)
                )
        elif isinstance(ds_input, bytes):
            # Create a new raster in write mode.
            self._write = 1
            # Get size of buffer.
            size = sys.getsizeof(ds_input)
            # Pass data to ctypes, keeping a reference to the ctypes object so
            # that the vsimem file remains available until the GDALRaster is
            # deleted.
            self._ds_input = c_buffer(ds_input)
            # Create random name to reference in vsimem filesystem.
            vsi_path = os.path.join(VSI_MEM_FILESYSTEM_BASE_PATH, str(uuid.uuid4()))
            # Create vsimem file from buffer.
            capi.create_vsi_file_from_mem_buffer(
                force_bytes(vsi_path),
                byref(self._ds_input),
                size,
                VSI_TAKE_BUFFER_OWNERSHIP,
            )
            # Open the new vsimem file as a GDALRaster.
            try:
                self._ptr = capi.open_ds(force_bytes(vsi_path), self._write)
            except GDALException:
                # Remove the broken file from the VSI filesystem.
                capi.unlink_vsi_file(force_bytes(vsi_path))
                raise GDALException("Failed creating VSI raster from the input buffer.")
        elif isinstance(ds_input, dict):
            # A new raster needs to be created in write mode
            self._write = 1

            # Create driver (in memory by default)
            driver = Driver(ds_input.get("driver", "MEM"))

            # For out of memory drivers, check filename argument
            if driver.name != "MEM" and "name" not in ds_input:
                raise GDALException(
                    'Specify name for creation of raster with driver "{}".'.format(
                        driver.name
                    )
                )

            # Check if width and height where specified
            if "width" not in ds_input or "height" not in ds_input:
                raise GDALException(
                    "Specify width and height attributes for JSON or dict input."
                )

            # Check if srid was specified
            if "srid" not in ds_input:
                raise GDALException("Specify srid for JSON or dict input.")

            # Create null terminated gdal options array.
            papsz_options = []
            for key, val in ds_input.get("papsz_options", {}).items():
                option = "{}={}".format(key, val)
                papsz_options.append(option.upper().encode())
            papsz_options.append(None)

            # Convert papszlist to ctypes array.
            papsz_options = (c_char_p * len(papsz_options))(*papsz_options)

            # Create GDAL Raster
            self._ptr = capi.create_ds(
                driver._ptr,
                force_bytes(ds_input.get("name", "")),
                ds_input["width"],
                ds_input["height"],
                ds_input.get("nr_of_bands", len(ds_input.get("bands", []))),
                ds_input.get("datatype", 6),
                byref(papsz_options),
            )

            # Set band data if provided
            for i, band_input in enumerate(ds_input.get("bands", [])):
                band = self.bands[i]
                if "nodata_value" in band_input:
                    band.nodata_value = band_input["nodata_value"]
                    # Instantiate band filled with nodata values if only
                    # partial input data has been provided.
                    if band.nodata_value is not None and (
                        "data" not in band_input
                        or "size" in band_input
                        or "shape" in band_input
                    ):
                        band.data(data=(band.nodata_value,), shape=(1, 1))
                # Set band data values from input.
                band.data(
                    data=band_input.get("data"),
                    size=band_input.get("size"),
                    shape=band_input.get("shape"),
                    offset=band_input.get("offset"),
                )

            # Set SRID
            self.srs = ds_input.get("srid")

            # Set additional properties if provided
            if "origin" in ds_input:
                self.origin.x, self.origin.y = ds_input["origin"]

            if "scale" in ds_input:
                self.scale.x, self.scale.y = ds_input["scale"]

            if "skew" in ds_input:
                self.skew.x, self.skew.y = ds_input["skew"]
        elif isinstance(ds_input, c_void_p):
            # Instantiate the object using an existing pointer to a gdal raster.
            self._ptr = ds_input
        else:
            raise GDALException(
                'Invalid data source input type: "{}".'.format(type(ds_input))
            )

    def __del__(self):
        if self.is_vsi_based:
            # Remove the temporary file from the VSI in-memory filesystem.
            capi.unlink_vsi_file(force_bytes(self.name))
        super().__del__()

    def __str__(self):
        return self.name

    def __repr__(self):
        """
        Short-hand representation because WKB may be very large.
        """
        return "<Raster object at %s>" % hex(addressof(self._ptr))

    def _flush(self):
        """
        Flush all data from memory into the source file if it exists.
        The data that needs flushing are geotransforms, coordinate systems,
        nodata_values and pixel values. This function will be called
        automatically wherever it is needed.
        """
        # Raise an Exception if the value is being changed in read mode.
        if not self._write:
            raise GDALException(
                "Raster needs to be opened in write mode to change values."
            )
        capi.flush_ds(self._ptr)

    @property
    def vsi_buffer(self):
        """
        Retrieves the contents of a VSI file as a bytes buffer, if the current object represents a VSI-based file in memory. Returns None otherwise.
        """
        if not (
            self.is_vsi_based and self.name.startswith(VSI_MEM_FILESYSTEM_BASE_PATH)
        ):
            return None
        # Prepare an integer that will contain the buffer length.
        out_length = c_int()
        # Get the data using the vsi file name.
        dat = capi.get_mem_buffer_from_vsi_file(
            force_bytes(self.name),
            byref(out_length),
            VSI_DELETE_BUFFER_ON_READ,
        )
        # Read the full buffer pointer.
        return string_at(dat, out_length.value)

    @cached_property
    def is_vsi_based(self):
        return self._ptr and self.name.startswith(VSI_FILESYSTEM_PREFIX)

    @property
    def name(self):
        """
        Return the name of this raster. Corresponds to filename
        for file-based rasters.
        """
        return force_str(capi.get_ds_description(self._ptr))

    @cached_property
    def driver(self):
        """
        Return the GDAL Driver used for this raster.
        """
        ds_driver = capi.get_ds_driver(self._ptr)
        return Driver(ds_driver)

    @property
    def width(self):
        """
        Width (X axis) in pixels.
        """
        return capi.get_ds_xsize(self._ptr)

    @property
    def height(self):
        """
        Height (Y axis) in pixels.
        """
        return capi.get_ds_ysize(self._ptr)

    @property
    def srs(self):
        """
        Return the SpatialReference used in this GDALRaster, represented as a SpatialReference object, or None if no spatial reference system is defined.
        """
        try:
            wkt = capi.get_ds_projection_ref(self._ptr)
            if not wkt:
                return None
            return SpatialReference(wkt, srs_type="wkt")
        except SRSException:
            return None

    @srs.setter
    def srs(self, value):
        """
        Sets the spatial reference system (SRS) for the GDALRaster, accepting either a SpatialReference object or a compatible input for the SpatialReference constructor.
        """
        if isinstance(value, SpatialReference):
            srs = value
        elif isinstance(value, (int, str)):
            srs = SpatialReference(value)
        else:
            raise ValueError("Could not create a SpatialReference from input.")
        capi.set_ds_projection_ref(self._ptr, srs.wkt.encode())
        self._flush()

    @property
    def srid(self):
        """
        Shortcut to access the srid of this GDALRaster.
        """
        return self.srs.srid

    @srid.setter
    def srid(self, value):
        """
        Shortcut to set this GDALRaster's srs from an srid.
        """
        self.srs = value

    @property
    def geotransform(self):
        """
        Return the geotransform of the data source.
        Return the default geotransform if it does not exist or has not been
        set previously. The default is [0.0, 1.0, 0.0, 0.0, 0.0, -1.0].
        """
        # Create empty ctypes double array for data
        gtf = (c_double * 6)()
        capi.get_ds_geotransform(self._ptr, byref(gtf))
        return list(gtf)

    @geotransform.setter
    def geotransform(self, values):
        """
        Set the geotransform for the data source, specifying its spatial reference.

        The geotransform is a six-element tuple of numeric values. It defines the affine transformation from image coordinates to georeferenced coordinates, typically in a format of (top-left x, x-pixel size, x-rotation, top-left y, y-rotation, y-pixel size).

        :raises: ValueError if the geotransform is not provided as 6 numeric values.
        """
        if len(values) != 6 or not all(isinstance(x, (int, float)) for x in values):
            raise ValueError("Geotransform must consist of 6 numeric values.")
        # Create ctypes double array with input and write data
        values = (c_double * 6)(*values)
        capi.set_ds_geotransform(self._ptr, byref(values))
        self._flush()

    @property
    def origin(self):
        """
        Coordinates of the raster origin.
        """
        return TransformPoint(self, "origin")

    @property
    def scale(self):
        """
        Pixel scale in units of the raster projection.
        """
        return TransformPoint(self, "scale")

    @property
    def skew(self):
        """
        Skew of pixels (rotation parameters).
        """
        return TransformPoint(self, "skew")

    @property
    def extent(self):
        """
        Get the bounding box of an object as a 4-tuple (xmin, ymin, xmax, ymax).
        """
        # Calculate boundary values based on scale and size
        xval = self.origin.x + self.scale.x * self.width
        yval = self.origin.y + self.scale.y * self.height
        # Calculate min and max values
        xmin = min(xval, self.origin.x)
        xmax = max(xval, self.origin.x)
        ymin = min(yval, self.origin.y)
        ymax = max(yval, self.origin.y)

        return xmin, ymin, xmax, ymax

    @property
    def bands(self):
        return BandList(self)

    def warp(self, ds_input, resampling="NearestNeighbour", max_error=0.0):
        """
        Return a warped GDALRaster with the given input characteristics.

        The function takes in parameters that define the target raster, including its spatial reference system, resolution, and output filename.
        It allows for specifying a resampling algorithm and a maximum error threshold for the warping process.
        If certain parameters are not provided, default values are used that match the original source raster.
        The function returns the resulting warped raster object.
        """
        # Get the parameters defining the geotransform, srid, and size of the raster
        ds_input.setdefault("width", self.width)
        ds_input.setdefault("height", self.height)
        ds_input.setdefault("srid", self.srs.srid)
        ds_input.setdefault("origin", self.origin)
        ds_input.setdefault("scale", self.scale)
        ds_input.setdefault("skew", self.skew)
        # Get the driver, name, and datatype of the target raster
        ds_input.setdefault("driver", self.driver.name)

        if "name" not in ds_input:
            ds_input["name"] = self.name + "_copy." + self.driver.name

        if "datatype" not in ds_input:
            ds_input["datatype"] = self.bands[0].datatype()

        # Instantiate raster bands filled with nodata values.
        ds_input["bands"] = [{"nodata_value": bnd.nodata_value} for bnd in self.bands]

        # Create target raster
        target = GDALRaster(ds_input, write=True)

        # Select resampling algorithm
        algorithm = GDAL_RESAMPLE_ALGORITHMS[resampling]

        # Reproject image
        capi.reproject_image(
            self._ptr,
            self.srs.wkt.encode(),
            target._ptr,
            target.srs.wkt.encode(),
            algorithm,
            0.0,
            max_error,
            c_void_p(),
            c_void_p(),
            c_void_p(),
        )

        # Make sure all data is written to file
        target._flush()

        return target

    def clone(self, name=None):
        """
        Create a copy of the current GDALRaster instance.

        The clone can be optionally given a custom name. If no name is provided,
        a default name will be generated based on the original raster's name and driver,
        or a unique temporary filename if the raster is in-memory.

        Returns a new GDALRaster instance that is a copy of the current one.
        """
        if name:
            clone_name = name
        elif self.driver.name != "MEM":
            clone_name = self.name + "_copy." + self.driver.name
        else:
            clone_name = os.path.join(VSI_MEM_FILESYSTEM_BASE_PATH, str(uuid.uuid4()))
        return GDALRaster(
            capi.copy_ds(
                self.driver._ptr,
                force_bytes(clone_name),
                self._ptr,
                c_int(),
                c_char_p(),
                c_void_p(),
                c_void_p(),
            ),
            write=self._write,
        )

    def transform(
        self, srs, driver=None, name=None, resampling="NearestNeighbour", max_error=0.0
    ):
        """
        Reprojects this raster into the specified spatial reference system.

            :param srs: Spatial reference system (int, str or SpatialReference object) to transform into.
            :param driver: Name of the driver to use for transformation.
            :param name: Name of the transformed raster.
            :param resampling: Resampling algorithm (default is 'NearestNeighbour').
            :param max_error: Maximum allowed error for transformation (default is 0.0).

            :return: Reprojected raster.

        """
        # Convert the resampling algorithm name into an algorithm id
        algorithm = GDAL_RESAMPLE_ALGORITHMS[resampling]

        if isinstance(srs, SpatialReference):
            target_srs = srs
        elif isinstance(srs, (int, str)):
            target_srs = SpatialReference(srs)
        else:
            raise TypeError(
                "Transform only accepts SpatialReference, string, and integer "
                "objects."
            )

        if target_srs.srid == self.srid and (not driver or driver == self.driver.name):
            return self.clone(name)
        # Create warped virtual dataset in the target reference system
        target = capi.auto_create_warped_vrt(
            self._ptr,
            self.srs.wkt.encode(),
            target_srs.wkt.encode(),
            algorithm,
            max_error,
            c_void_p(),
        )
        target = GDALRaster(target)

        # Construct the target warp dictionary from the virtual raster
        data = {
            "srid": target_srs.srid,
            "width": target.width,
            "height": target.height,
            "origin": [target.origin.x, target.origin.y],
            "scale": [target.scale.x, target.scale.y],
            "skew": [target.skew.x, target.skew.y],
        }

        # Set the driver and filepath if provided
        if driver:
            data["driver"] = driver

        if name:
            data["name"] = name

        # Warp the raster into new srid
        return self.warp(data, resampling=resampling, max_error=max_error)

    @property
    def info(self):
        """
        Return information about this raster in a string format equivalent
        to the output of the gdalinfo command line utility.
        """
        return capi.get_ds_info(self.ptr, None).decode()
