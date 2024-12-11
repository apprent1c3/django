from django.contrib.admin import ModelAdmin
from django.contrib.gis.db import models
from django.contrib.gis.forms import OSMWidget


class GeoModelAdminMixin:
    gis_widget = OSMWidget
    gis_widget_kwargs = {}

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """

        Return a form field for the given database field, taking into account the field's type and the geometry widget's capabilities.

        If the database field is a GeometryField with a dimension less than 3 or the geometry widget supports 3D, the geometry widget is used to render the field in the form. Otherwise, the default form field is returned.

        :param db_field: The database field to generate a form field for.
        :param request: The current request.
        :param kwargs: Additional keyword arguments to pass to the form field constructor.
        :returns: A form field instance for the given database field.

        """
        if isinstance(db_field, models.GeometryField) and (
            db_field.dim < 3 or self.gis_widget.supports_3d
        ):
            kwargs["widget"] = self.gis_widget(**self.gis_widget_kwargs)
            return db_field.formfield(**kwargs)
        else:
            return super().formfield_for_dbfield(db_field, request, **kwargs)


class GISModelAdmin(GeoModelAdminMixin, ModelAdmin):
    pass
