import logging

from django.contrib.gis.db.models import GeometryField
from django.db import OperationalError
from django.db.backends.mysql.schema import DatabaseSchemaEditor

logger = logging.getLogger("django.contrib.gis")


class MySQLGISSchemaEditor(DatabaseSchemaEditor):
    sql_add_spatial_index = "CREATE SPATIAL INDEX %(index)s ON %(table)s(%(column)s)"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geometry_sql = []

    def skip_default(self, field):
        # Geometry fields are stored as BLOB/TEXT, for which MySQL < 8.0.13
        # doesn't support defaults.
        if (
            isinstance(field, GeometryField)
            and not self._supports_limited_data_type_defaults
        ):
            return True
        return super().skip_default(field)

    def quote_value(self, value):
        if isinstance(value, self.connection.ops.Adapter):
            return super().quote_value(str(value))
        return super().quote_value(value)

    def column_sql(self, model, field, include_default=False):
        """
        Returns the SQL string for a column, handling spatial index creation for geometry fields if necessary. 
        When the field is a geometry field with a spatial index and is not nullable, this function appends the SQL required to create the spatial index to the internal geometry SQL list.
        """
        column_sql = super().column_sql(model, field, include_default)
        # MySQL doesn't support spatial indexes on NULL columns
        if isinstance(field, GeometryField) and field.spatial_index and not field.null:
            qn = self.connection.ops.quote_name
            db_table = model._meta.db_table
            self.geometry_sql.append(
                self.sql_add_spatial_index
                % {
                    "index": qn(self._create_spatial_index_name(model, field)),
                    "table": qn(db_table),
                    "column": qn(field.column),
                }
            )
        return column_sql

    def create_model(self, model):
        super().create_model(model)
        self.create_spatial_indexes()

    def add_field(self, model, field):
        super().add_field(model, field)
        self.create_spatial_indexes()

    def remove_field(self, model, field):
        """
        Removes a field from a model, handling the special case where the field is a spatial GeometryField with an existing index, in which case it attempts to drop the associated spatial index before proceeding with the standard field removal process.
        """
        if isinstance(field, GeometryField) and field.spatial_index and not field.null:
            index_name = self._create_spatial_index_name(model, field)
            sql = self._delete_index_sql(model, index_name)
            try:
                self.execute(sql)
            except OperationalError:
                logger.error(
                    "Couldn't remove spatial index: %s (may be expected "
                    "if your storage engine doesn't support them).",
                    sql,
                )

        super().remove_field(model, field)

    def _create_spatial_index_name(self, model, field):
        return "%s_%s_id" % (model._meta.db_table, field.column)

    def create_spatial_indexes(self):
        """
        Creates spatial indexes on the database tables by executing a series of SQL queries.

        This method is necessary to enable efficient spatial queries, but it only works with table engines that support spatial indexes, such as MyISAM, Aria, and InnoDB.

        After execution, the list of SQL queries is reset, allowing for new spatial indexes to be created in subsequent calls.
        """
        for sql in self.geometry_sql:
            try:
                self.execute(sql)
            except OperationalError:
                logger.error(
                    f"Cannot create SPATIAL INDEX {sql}. Only MyISAM, Aria, and InnoDB "
                    f"support them.",
                )
        self.geometry_sql = []
