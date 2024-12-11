from django.core.management.commands.inspectdb import Command as InspectDBCommand


class Command(InspectDBCommand):
    db_module = "django.contrib.gis.db"

    def get_field_type(self, connection, table_name, row):
        """
        Returns the type of a given database field along with its parameters and notes.

        Determines the field type by first delegating to the parent class, then checks if the field is of type 'GeometryField'. 
        If it is, additional geometry-specific type information is retrieved from the database connection and merged with the existing field parameters.
        The function returns a tuple containing the field type, its parameters, and any additional notes about the field.

        Parameters:
            connection (object): The database connection to introspect.
            table_name (str): The name of the table containing the field.
            row (dict): The row in the table that describes the field.

        Returns:
            tuple: A tuple containing the field type (str), field parameters (dict), and field notes (str).
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
