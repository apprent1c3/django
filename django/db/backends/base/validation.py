class BaseDatabaseValidation:
    """Encapsulate backend-specific validation."""

    def __init__(self, connection):
        self.connection = connection

    def check(self, **kwargs):
        return []

    def check_field(self, field, **kwargs):
        """
        检查一个字段的类型并返回一份错误列表。

        此方法检查指定字段的类型并对其进行验证，返回一个包含所有错误信息的列表。如果数据库支持所需的功能，则会检查字段类型错误并返回相应的错误列表。如果没有错误，则返回一个空列表。

        参数：
            field (Field): 要检查的字段。
            **kwargs: 额外的关键字参数（未使用）。

        返回：
            list: 字段类型检查的错误列表。
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
