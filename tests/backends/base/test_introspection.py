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
        :param None: 
        :raises NotImplementedError: Tests that calling get_table_list with no arguments raises a NotImplementedError with the expected message, ensuring that the method is not implemented and will fail as expected when invoked.
        """
        msg = self.may_require_msg % "get_table_list"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.introspection.get_table_list(None)

    def test_get_table_description(self):
        """
        Tests the get_table_description method to ensure it raises a NotImplementedError when called.

        This test case verifies that the introspection object properly handles an unsupported operation,
        returning the expected error message. The test passes if the get_table_description method raises
        a NotImplementedError with the specified message, indicating that the operation is not implemented.

        :raises: AssertionError if the get_table_description method does not raise a NotImplementedError
        :raises: NotImplementedError from the get_table_description method with the expected error message
        """
        msg = self.may_require_msg % "get_table_description"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.introspection.get_table_description(None, None)

    def test_get_sequences(self):
        msg = self.may_require_msg % "get_sequences"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.introspection.get_sequences(None, None)

    def test_get_relations(self):
        """
        Tests that getting relations raises a NotImplementedError.

        Verifies the correct behavior of the get_relations method by checking that it
        raises a NotImplementedError with the expected error message when called with
        None arguments. This ensures that the method has not been implemented and will
        inform users that they need to provide a proper implementation for their use case.
        """
        msg = self.may_require_msg % "get_relations"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.introspection.get_relations(None, None)

    def test_get_constraints(self):
        msg = self.may_require_msg % "get_constraints"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.introspection.get_constraints(None, None)
