from django.db.migrations.exceptions import NodeNotFoundError
from django.test import SimpleTestCase


class ExceptionTests(SimpleTestCase):
    def test_node_not_found_error_repr(self):
        """
        Tests the string representation of a NodeNotFoundError exception.

        This test case verifies that the repr method of NodeNotFoundError returns a string 
        that accurately represents the exception, including the node that caused the error.

        The test checks that the string representation of the exception matches the expected 
        format, helping ensure that the exception can be easily identified and understood 
        when it occurs.

        The node is represented as a tuple containing the application label and migration 
        label, which are used to construct the exception's string representation.

        Validates the exception's repr method to ensure it provides useful information for 
        debugging and error handling purposes.
        """
        node = ("some_app_label", "some_migration_label")
        error_repr = repr(NodeNotFoundError("some message", node))
        self.assertEqual(
            error_repr, "NodeNotFoundError(('some_app_label', 'some_migration_label'))"
        )
