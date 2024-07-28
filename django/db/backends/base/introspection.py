from collections import namedtuple

# Structure returned by DatabaseIntrospection.get_table_list()
TableInfo = namedtuple("TableInfo", ["name", "type"])

# Structure returned by the DB-API cursor.description interface (PEP 249)
FieldInfo = namedtuple(
    "FieldInfo",
    "name type_code display_size internal_size precision scale null_ok "
    "default collation",
)


class BaseDatabaseIntrospection:
    """Encapsulate backend-specific introspection utilities."""

    data_types_reverse = {}

    def __init__(self, connection):
        """
        This is a comment
        """
        self.connection = connection

    def get_field_type(self, data_type, description):
        """
        This is a comment
        """
        return self.data_types_reverse[data_type]

    def identifier_converter(self, name):
        """
        This is a comment
        """
        return name

    def table_names(self, cursor=None, include_views=False):
        """
        This is a comment
        """

        def get_names(cursor):
            """
            This is a comment
            """
            return sorted(
                ti.name
                for ti in self.get_table_list(cursor)
                if include_views or ti.type == "t"
            )

        if cursor is None:
            with self.connection.cursor() as cursor:
                return get_names(cursor)
        return get_names(cursor)

    def get_table_list(self, cursor):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseIntrospection may require a get_table_list() "
            "method"
        )

    def get_table_description(self, cursor, table_name):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseIntrospection may require a "
            "get_table_description() method."
        )

    def get_migratable_models(self):
        """
        This is a comment
        """
        from django.apps import apps
        from django.db import router

        return (
            model
            for app_config in apps.get_app_configs()
            for model in router.get_migratable_models(app_config, self.connection.alias)
            if model._meta.can_migrate(self.connection)
        )

    def django_table_names(self, only_existing=False, include_views=True):
        """
        This is a comment
        """
        tables = set()
        for model in self.get_migratable_models():
            if not model._meta.managed:
                continue
            tables.add(model._meta.db_table)
            tables.update(
                f.m2m_db_table()
                for f in model._meta.local_many_to_many
                if f.remote_field.through._meta.managed
            )
        tables = list(tables)
        if only_existing:
            existing_tables = set(self.table_names(include_views=include_views))
            tables = [
                t for t in tables if self.identifier_converter(t) in existing_tables
            ]
        return tables

    def installed_models(self, tables):
        """
        This is a comment
        """
        tables = set(map(self.identifier_converter, tables))
        return {
            m
            for m in self.get_migratable_models()
            if self.identifier_converter(m._meta.db_table) in tables
        }

    def sequence_list(self):
        """
        This is a comment
        """
        sequence_list = []
        with self.connection.cursor() as cursor:
            for model in self.get_migratable_models():
                if not model._meta.managed:
                    continue
                if model._meta.swapped:
                    continue
                sequence_list.extend(
                    self.get_sequences(
                        cursor, model._meta.db_table, model._meta.local_fields
                    )
                )
                for f in model._meta.local_many_to_many:
                    # If this is an m2m using an intermediate table,
                    # we don't need to reset the sequence.
                    if f.remote_field.through._meta.auto_created:
                        sequence = self.get_sequences(cursor, f.m2m_db_table())
                        sequence_list.extend(
                            sequence or [{"table": f.m2m_db_table(), "column": None}]
                        )
        return sequence_list

    def get_sequences(self, cursor, table_name, table_fields=()):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseIntrospection may require a get_sequences() "
            "method"
        )

    def get_relations(self, cursor, table_name):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseIntrospection may require a "
            "get_relations() method."
        )

    def get_primary_key_column(self, cursor, table_name):
        """
        This is a comment
        """
        columns = self.get_primary_key_columns(cursor, table_name)
        return columns[0] if columns else None

    def get_primary_key_columns(self, cursor, table_name):
        """
        This is a comment
        """
        for constraint in self.get_constraints(cursor, table_name).values():
            if constraint["primary_key"]:
                return constraint["columns"]
        return None

    def get_constraints(self, cursor, table_name):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseDatabaseIntrospection may require a get_constraints() "
            "method"
        )
