from django.core.management.commands.inspectdb import Command as InspectDBCommand


class Command(InspectDBCommand):
    db_module = "django.contrib.gis.db"

    def get_field_type(self, connection, table_name, row):
        """
        Determines the type of a database field.

            Refines the field type if it's a GeometryField by fetching additional
            geometry-specific parameters from the database connection.

            Args:
                connection: The database connection to use for introspection.
                table_name (str): The name of the table the field belongs to.
                row: The database row containing the field information.

            Returns:
                A tuple containing the field type, its parameters, and any notes.

        """
        field_type, field_params, field_notes = super().get_field_type(
            connection, table_name, row
        )
        if field_type == "GeometryField":
            # Getting a more specific field type and any additional parameters
            # from the `get_geometry_type` routine for the spatial backend.
            field_type, geo_params = connection.introspection.get_geometry_type(
                table_name, row
            )
            field_params.update(geo_params)
        return field_type, field_params, field_notes
