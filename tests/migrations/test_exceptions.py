from django.db.migrations.exceptions import NodeNotFoundError
from django.test import SimpleTestCase


class ExceptionTests(SimpleTestCase):
    def test_node_not_found_error_repr(self):
        """
        Tests that the representation of a NodeNotFoundError includes the missing node.

        Verifies that the repr function of NodeNotFoundError returns a string containing
        the missing node, which can be useful for debugging purposes when a node is not found.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the representation of the NodeNotFoundError does not match the expected format.

        """
        node = ("some_app_label", "some_migration_label")
        error_repr = repr(NodeNotFoundError("some message", node))
        self.assertEqual(
            error_repr, "NodeNotFoundError(('some_app_label', 'some_migration_label'))"
        )
