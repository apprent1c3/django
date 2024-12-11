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

        This function checks that the input 'oids' is a non-empty tuple containing only integers.

        Args:
            oids (tuple): A tuple of integer OIDs to be validated.

        Raises:
            AssertionError: If 'oids' is not a tuple, empty, or contains non-integer values.
        """
        self.assertIsInstance(oids, tuple)
        self.assertGreater(len(oids), 0)
        self.assertTrue(all(isinstance(oid, int) for oid in oids))

    def test_hstore_cache(self):
        """

        Tests the caching mechanism of the get_hstore_oids function.

        This test case ensures that the function's result is properly cached, 
        resulting in no additional database queries being executed when the 
        function is called multiple times with the same input.

        """
        get_hstore_oids(connection.alias)
        with self.assertNumQueries(0):
            get_hstore_oids(connection.alias)

    def test_citext_cache(self):
        get_citext_oids(connection.alias)
        with self.assertNumQueries(0):
            get_citext_oids(connection.alias)

    def test_hstore_values(self):
        oids, array_oids = get_hstore_oids(connection.alias)
        self.assertOIDs(oids)
        self.assertOIDs(array_oids)

    def test_citext_values(self):
        """

        Tests whether the citext values are properly resolved to their corresponding OIDs.

        This test case retrieves the OIDs for both regular and citext data types from the
        database connection, and then verifies that the OIDs are correctly assigned.
        The test covers the functionality of OID resolution for citext values, ensuring
        that they can be properly identified and processed in the database.

        """
        oids, citext_oids = get_citext_oids(connection.alias)
        self.assertOIDs(oids)
        self.assertOIDs(citext_oids)

    def test_register_type_handlers_no_db(self):
        """Registering type handlers for the nodb connection does nothing."""
        with connection._nodb_cursor() as cursor:
            register_type_handlers(cursor.db)
