from django.test import SimpleTestCase
from django.utils.connection import BaseConnectionHandler


class BaseConnectionHandlerTests(SimpleTestCase):
    def test_create_connection(self):
        """
        Tests that creating a connection using the BaseConnectionHandler raises a NotImplementedError.

        This test case ensures that the create_connection method is not implemented in the base class
        and must be implemented by subclasses. It verifies that attempting to create a connection
        without providing an implementation results in the expected error message.

        :raises: AssertionError if the expected NotImplementedError is not raised
        :raises: NotImplementedError with a message indicating that subclasses must implement create_connection
        """
        handler = BaseConnectionHandler()
        msg = "Subclasses must implement create_connection()."
        with self.assertRaisesMessage(NotImplementedError, msg):
            handler.create_connection(None)

    def test_all_initialized_only(self):
        handler = BaseConnectionHandler({"default": {}})
        self.assertEqual(handler.all(initialized_only=True), [])
