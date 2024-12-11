from django.db.migrations.exceptions import NodeNotFoundError
from django.test import SimpleTestCase


class ExceptionTests(SimpleTestCase):
    def test_node_not_found_error_repr(self):
        """

        Tests the string representation of a NodeNotFoundError exception.

        The test case verifies that the repr function returns a string in the expected format
        when a NodeNotFoundError is raised, including the node that triggered the error.

        """
        node = ("some_app_label", "some_migration_label")
        error_repr = repr(NodeNotFoundError("some message", node))
        self.assertEqual(
            error_repr, "NodeNotFoundError(('some_app_label', 'some_migration_label'))"
        )
