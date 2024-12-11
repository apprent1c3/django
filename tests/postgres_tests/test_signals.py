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
        Asserts that the provided OIDs are valid.

        This function checks that the given OIDs are in a tuple format, not empty, and contain only integers.

        :arg oids: A tuple of object identifiers to be validated
        :raises AssertionError: If the provided OIDs do not meet the expected format and type requirements
        """
        self.assertIsInstance(oids, tuple)
        self.assertGreater(len(oids), 0)
        self.assertTrue(all(isinstance(oid, int) for oid in oids))

    def test_hstore_cache(self):
        get_hstore_oids(connection.alias)
        with self.assertNumQueries(0):
            get_hstore_oids(connection.alias)

    def test_citext_cache(self):
        """

        Tests the caching behavior of citext oids retrieval.

        Verifies that the function to retrieve citext oids caches its results, 
        by checking that a subsequent call with the same database connection alias 
        does not result in any additional database queries.

        Ensures that the caching mechanism works as expected, improving performance 
        by avoiding redundant database queries.

        """
        get_citext_oids(connection.alias)
        with self.assertNumQueries(0):
            get_citext_oids(connection.alias)

    def test_hstore_values(self):
        oids, array_oids = get_hstore_oids(connection.alias)
        self.assertOIDs(oids)
        self.assertOIDs(array_oids)

    def test_citext_values(self):
        oids, citext_oids = get_citext_oids(connection.alias)
        self.assertOIDs(oids)
        self.assertOIDs(citext_oids)

    def test_register_type_handlers_no_db(self):
        """Registering type handlers for the nodb connection does nothing."""
        with connection._nodb_cursor() as cursor:
            register_type_handlers(cursor.db)
