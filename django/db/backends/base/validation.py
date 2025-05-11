class BaseDatabaseValidation:
    """Encapsulate backend-specific validation."""

    def __init__(self, connection):
        self.connection = connection

    def check(self, **kwargs):
        return []

    def check_field(self, field, **kwargs):
        """
        Checks a model field for errors, returning a list of any issues found.

        This method verifies that the database supports the field's required features and
        checks the field type for any errors. It is primarily used to validate fields
        before creating or altering database tables.

        :param field: The model field to be checked
        :param kwargs: Additional keyword arguments
        :returns: A list of error messages for the field
        """
        errors = []
        # Backends may implement a check_field_type() method.
        if (
            hasattr(self, "check_field_type")
            and
            # Ignore any related fields.
            not getattr(field, "remote_field", None)
        ):
            # Ignore fields with unsupported features.
            db_supports_all_required_features = all(
                getattr(self.connection.features, feature, False)
                for feature in field.model._meta.required_db_features
            )
            if db_supports_all_required_features:
                field_type = field.db_type(self.connection)
                # Ignore non-concrete fields.
                if field_type is not None:
                    errors.extend(self.check_field_type(field, field_type))
        return errors
