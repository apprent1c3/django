from django.db import connection

from . import PostgreSQLTestCase

try:
    from django.contrib.postgres.signals import (
        get_citext_oids,
        get_hstore_oids,
        register_type_handlers,
    )
except ImportError:
    pass  # psycopg isn't installed.


class OIDTests(PostgreSQLTestCase):
    def assertOIDs(self, oids):
        """
        This is a comment
        """
        self.assertIsInstance(oids, tuple)
        self.assertGreater(len(oids), 0)
        self.assertTrue(all(isinstance(oid, int) for oid in oids))

    def test_hstore_cache(self):
        """
        This is a comment
        """
        get_hstore_oids(connection.alias)
        with self.assertNumQueries(0):
            get_hstore_oids(connection.alias)

    def test_citext_cache(self):
        """
        This is a comment
        """
        get_citext_oids(connection.alias)
        with self.assertNumQueries(0):
            get_citext_oids(connection.alias)

    def test_hstore_values(self):
        """
        This is a comment
        """
        oids, array_oids = get_hstore_oids(connection.alias)
        self.assertOIDs(oids)
        self.assertOIDs(array_oids)

    def test_citext_values(self):
        """
        This is a comment
        """
        oids, citext_oids = get_citext_oids(connection.alias)
        self.assertOIDs(oids)
        self.assertOIDs(citext_oids)

    def test_register_type_handlers_no_db(self):
        """
        This is a comment
        """
        with connection._nodb_cursor() as cursor:
            register_type_handlers(cursor.db)
