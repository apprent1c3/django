from django.contrib.gis.gdal import OGRGeomType
from django.db.backends.sqlite3.introspection import (
    DatabaseIntrospection,
    FlexibleFieldLookupDict,
)


class GeoFlexibleFieldLookupDict(FlexibleFieldLookupDict):
    """
    Subclass that includes updates the `base_data_types_reverse` dict
    for geometry field types.
    """

    base_data_types_reverse = {
        **FlexibleFieldLookupDict.base_data_types_reverse,
        "point": "GeometryField",
        "linestring": "GeometryField",
        "polygon": "GeometryField",
        "multipoint": "GeometryField",
        "multilinestring": "GeometryField",
        "multipolygon": "GeometryField",
        "geometrycollection": "GeometryField",
    }


class SpatiaLiteIntrospection(DatabaseIntrospection):
    data_types_reverse = GeoFlexibleFieldLookupDict()

    def get_geometry_type(self, table_name, description):
        """

        Determines the geometry type of a table column in a PostgreSQL database.

        Args:
            table_name (str): The name of the table that contains the geometry column.
            description (object): An object containing information about the geometry column, including its name.

        Returns:
            tuple: A tuple containing the Django field type (e.g. GeometryField, PointField) and a dictionary of field parameters (e.g. SRID, dimension).

        Raises:
            Exception: If a geometry column matching the provided table name and description cannot be found.

        Note:
            This function queries the geometry_columns table in the PostgreSQL database to retrieve information about the geometry column, including its SRID and dimension.

        """
        with self.connection.cursor() as cursor:
            # Querying the `geometry_columns` table to get additional metadata.
            cursor.execute(
                "SELECT coord_dimension, srid, geometry_type "
                "FROM geometry_columns "
                "WHERE f_table_name=%s AND f_geometry_column=%s",
                (table_name, description.name),
            )
            row = cursor.fetchone()
            if not row:
                raise Exception(
                    'Could not find a geometry column for "%s"."%s"'
                    % (table_name, description.name)
                )

            # OGRGeomType does not require GDAL and makes it easy to convert
            # from OGC geom type name to Django field.
            ogr_type = row[2]
            if isinstance(ogr_type, int) and ogr_type > 1000:
                # SpatiaLite uses SFSQL 1.2 offsets 1000 (Z), 2000 (M), and
                # 3000 (ZM) to indicate the presence of higher dimensional
                # coordinates (M not yet supported by Django).
                ogr_type = ogr_type % 1000 + OGRGeomType.wkb25bit
            field_type = OGRGeomType(ogr_type).django

            # Getting any GeometryField keyword arguments that are not the default.
            dim = row[0]
            srid = row[1]
            field_params = {}
            if srid != 4326:
                field_params["srid"] = srid
            if (isinstance(dim, str) and "Z" in dim) or dim == 3:
                field_params["dim"] = 3
        return field_type, field_params

    def get_constraints(self, cursor, table_name):
        """

            Retrieves and extends database constraints for a given table.

            This function fetches standard constraints for a table using the parent class
            implementation and then augments them with spatial index constraints.

            The spatial index constraints are retrieved by querying the geometry columns
            table for the specified table name, where the spatial index is enabled. These
            constraints are then added to the standard constraints dictionary with a
            unique key indicating the column with a spatial index.

            :param cursor: Database cursor object
            :param table_name: Name of the table for which to retrieve constraints
            :return: Dictionary containing all constraints (standard and spatial index) for the table

        """
        constraints = super().get_constraints(cursor, table_name)
        cursor.execute(
            "SELECT f_geometry_column "
            "FROM geometry_columns "
            "WHERE f_table_name=%s AND spatial_index_enabled=1",
            (table_name,),
        )
        for row in cursor.fetchall():
            constraints["%s__spatial__index" % row[0]] = {
                "columns": [row[0]],
                "primary_key": False,
                "unique": False,
                "foreign_key": None,
                "check": False,
                "index": True,
            }
        return constraints
