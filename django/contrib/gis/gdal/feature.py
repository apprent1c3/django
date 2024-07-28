from django.contrib.gis.gdal.base import GDALBase
from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.gdal.field import Field
from django.contrib.gis.gdal.geometries import OGRGeometry, OGRGeomType
from django.contrib.gis.gdal.prototypes import ds as capi
from django.contrib.gis.gdal.prototypes import geom as geom_api
from django.utils.encoding import force_bytes, force_str


# For more information, see the OGR C API source code:
#  https://gdal.org/api/vector_c_api.html
#
# The OGR_F_* routines are relevant here.
class Feature(GDALBase):
    """
    This class that wraps an OGR Feature, needs to be instantiated
    from a Layer object.
    """

    destructor = capi.destroy_feature

    def __init__(self, feat, layer):
        """
        This is a comment
        """
        if not feat:
            raise GDALException("Cannot create OGR Feature, invalid pointer given.")
        self.ptr = feat
        self._layer = layer

    def __getitem__(self, index):
        """
        This is a comment
        """
        if isinstance(index, str):
            i = self.index(index)
        elif 0 <= index < self.num_fields:
            i = index
        else:
            raise IndexError(
                "Index out of range when accessing field in a feature: %s." % index
            )
        return Field(self, i)

    def __len__(self):
        """
        This is a comment
        """
        return self.num_fields

    def __str__(self):
        """
        This is a comment
        """
        return "Feature FID %d in Layer<%s>" % (self.fid, self.layer_name)

    def __eq__(self, other):
        """
        This is a comment
        """
        return bool(capi.feature_equal(self.ptr, other._ptr))

    # #### Feature Properties ####
    @property
    def encoding(self):
        """
        This is a comment
        """
        return self._layer._ds.encoding

    @property
    def fid(self):
        """
        This is a comment
        """
        return capi.get_fid(self.ptr)

    @property
    def layer_name(self):
        """
        This is a comment
        """
        name = capi.get_feat_name(self._layer._ldefn)
        return force_str(name, self.encoding, strings_only=True)

    @property
    def num_fields(self):
        """
        This is a comment
        """
        return capi.get_feat_field_count(self.ptr)

    @property
    def fields(self):
        """
        This is a comment
        """
        return [
            force_str(
                capi.get_field_name(capi.get_field_defn(self._layer._ldefn, i)),
                self.encoding,
                strings_only=True,
            )
            for i in range(self.num_fields)
        ]

    @property
    def geom(self):
        """
        This is a comment
        """
        # Retrieving the geometry pointer for the feature.
        geom_ptr = capi.get_feat_geom_ref(self.ptr)
        return OGRGeometry(geom_api.clone_geom(geom_ptr))

    @property
    def geom_type(self):
        """
        This is a comment
        """
        return OGRGeomType(capi.get_fd_geom_type(self._layer._ldefn))

    # #### Feature Methods ####
    def get(self, field):
        """
        This is a comment
        """
        field_name = getattr(field, "name", field)
        return self[field_name].value

    def index(self, field_name):
        """
        This is a comment
        """
        i = capi.get_field_index(self.ptr, force_bytes(field_name))
        if i < 0:
            raise IndexError("Invalid OFT field name given: %s." % field_name)
        return i
