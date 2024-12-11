from django.db import connection
from django.db.backends.base.introspection import BaseDatabaseIntrospection
from django.test import SimpleTestCase


class SimpleDatabaseIntrospectionTests(SimpleTestCase):
    may_require_msg = (
        "subclasses of BaseDatabaseIntrospection may require a %s() method"
    )

    def setUp(self):
        self.introspection = BaseDatabaseIntrospection(connection=connection)

    def test_get_table_list(self):
        """
        Tests the get_table_list method of the introspection object to ensure it raises a NotImplementedError when called with None.

        This test case verifies that the get_table_list method behaves as expected when provided with no database connection, 
        confirming that an appropriate error is generated with a specific error message when this method is not implemented.

        The test checks for the presence of a NotImplementedError with a message indicating that the method should be implemented 
        to handle the requested operation, thus ensuring the proper handling of unimplemented functionality in the introspection object.
        """
        msg = self.may_require_msg % "get_table_list"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.introspection.get_table_list(None)

    def test_get_table_description(self):
        msg = self.may_require_msg % "get_table_description"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.introspection.get_table_description(None, None)

    def test_get_sequences(self):
        msg = self.may_require_msg % "get_sequences"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.introspection.get_sequences(None, None)

    def test_get_relations(self):
        msg = self.may_require_msg % "get_relations"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.introspection.get_relations(None, None)

    def test_get_constraints(self):
        msg = self.may_require_msg % "get_constraints"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.introspection.get_constraints(None, None)
