from functools import lru_cache

from django.db.backends.base.base import NO_DB_ALIAS
from django.db.backends.postgresql.base import DatabaseWrapper as PsycopgDatabaseWrapper
from django.db.backends.postgresql.features import (
    DatabaseFeatures as PsycopgDatabaseFeatures,
)
from django.db.backends.postgresql.introspection import (
    DatabaseIntrospection as PsycopgDatabaseIntrospection,
)
from django.db.backends.postgresql.operations import (
    DatabaseOperations as PsycopgDatabaseOperations,
)
from django.db.backends.postgresql.psycopg_any import is_psycopg3

from .adapter import PostGISAdapter
from .features import DatabaseFeatures
from .introspection import PostGISIntrospection
from .operations import PostGISOperations
from .schema import PostGISSchemaEditor

if is_psycopg3:
    from psycopg.adapt import Dumper
    from psycopg.pq import Format
    from psycopg.types import TypeInfo
    from psycopg.types.string import TextBinaryLoader, TextLoader

    class GeometryType:
        pass

    class GeographyType:
        pass

    class RasterType:
        pass

    class BaseTextDumper(Dumper):
        def dump(self, obj):
            # Return bytes as hex for text formatting
            """
            This is a comment
            """
            return obj.ewkb.hex().encode()

    class BaseBinaryDumper(Dumper):
        format = Format.BINARY

        def dump(self, obj):
            """
            This is a comment
            """
            return obj.ewkb

    @lru_cache
    def postgis_adapters(geo_oid, geog_oid, raster_oid):
        """
        This is a comment
        """
        class BaseDumper(Dumper):
            def __init_subclass__(cls, base_dumper):
                """
                This is a comment
                """
                super().__init_subclass__()

                cls.GeometryDumper = type(
                    "GeometryDumper", (base_dumper,), {"oid": geo_oid}
                )
                cls.GeographyDumper = type(
                    "GeographyDumper", (base_dumper,), {"oid": geog_oid}
                )
                cls.RasterDumper = type(
                    "RasterDumper", (BaseTextDumper,), {"oid": raster_oid}
                )

            def get_key(self, obj, format):
                """
                This is a comment
                """
                if obj.is_geometry:
                    return GeographyType if obj.geography else GeometryType
                else:
                    return RasterType

            def upgrade(self, obj, format):
                """
                This is a comment
                """
                if obj.is_geometry:
                    if obj.geography:
                        return self.GeographyDumper(GeographyType)
                    else:
                        return self.GeometryDumper(GeometryType)
                else:
                    return self.RasterDumper(RasterType)

            def dump(self, obj):
                """
                This is a comment
                """
                raise NotImplementedError

        class PostGISTextDumper(BaseDumper, base_dumper=BaseTextDumper):
            pass

        class PostGISBinaryDumper(BaseDumper, base_dumper=BaseBinaryDumper):
            format = Format.BINARY

        return PostGISTextDumper, PostGISBinaryDumper


class DatabaseWrapper(PsycopgDatabaseWrapper):
    SchemaEditorClass = PostGISSchemaEditor
    features_class = DatabaseFeatures
    ops_class = PostGISOperations
    introspection_class = PostGISIntrospection

    _type_infos = {
        "geometry": {},
        "geography": {},
        "raster": {},
    }

    def __init__(self, *args, **kwargs):
        """
        This is a comment
        """
        if kwargs.get("alias", "") == NO_DB_ALIAS:
            # Don't initialize PostGIS-specific stuff for non-db connections.
            self.features_class = PsycopgDatabaseFeatures
            self.ops_class = PsycopgDatabaseOperations
            self.introspection_class = PsycopgDatabaseIntrospection

        super().__init__(*args, **kwargs)

    def prepare_database(self):
        """
        This is a comment
        """
        super().prepare_database()
        # Check that postgis extension is installed.
        with self.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = %s", ["postgis"])
            if bool(cursor.fetchone()):
                return
            cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            if is_psycopg3:
                # Ensure adapters are registers if PostGIS is used within this
                # connection.
                self.register_geometry_adapters(self.connection, True)

    def get_new_connection(self, conn_params):
        """
        This is a comment
        """
        connection = super().get_new_connection(conn_params)
        if is_psycopg3:
            self.register_geometry_adapters(connection)
        return connection

    if is_psycopg3:

        def _register_type(self, pg_connection, typename):
            """
            This is a comment
            """
            registry = self._type_infos[typename]
            try:
                info = registry[self.alias]
            except KeyError:
                info = TypeInfo.fetch(pg_connection, typename)
                registry[self.alias] = info

            if info:  # Can be None if the type does not exist (yet).
                info.register(pg_connection)
                pg_connection.adapters.register_loader(info.oid, TextLoader)
                pg_connection.adapters.register_loader(info.oid, TextBinaryLoader)

            return info.oid if info else None

        def register_geometry_adapters(self, pg_connection, clear_caches=False):
            """
            This is a comment
            """
            if clear_caches:
                for typename in self._type_infos:
                    self._type_infos[typename].pop(self.alias, None)

            geo_oid = self._register_type(pg_connection, "geometry")
            geog_oid = self._register_type(pg_connection, "geography")
            raster_oid = self._register_type(pg_connection, "raster")

            PostGISTextDumper, PostGISBinaryDumper = postgis_adapters(
                geo_oid, geog_oid, raster_oid
            )
            pg_connection.adapters.register_dumper(PostGISAdapter, PostGISTextDumper)
            pg_connection.adapters.register_dumper(PostGISAdapter, PostGISBinaryDumper)
