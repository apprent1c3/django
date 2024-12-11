from django.test import SimpleTestCase
from django.utils.connection import BaseConnectionHandler


class BaseConnectionHandlerTests(SimpleTestCase):
    def test_create_connection(self):
        """
        Tests the implementation of the create_connection method in BaseConnectionHandler subclasses.

        Verifies that attempting to create a connection using an instance of BaseConnectionHandler
        directly raises a NotImplementedError, ensuring that subclasses correctly override this method.

        The test validates the expected error message, confirming that the NotImplementedError
        is properly propagated with a descriptive message, indicating that subclasses must implement
        the create_connection method.

        This test case ensures that the BaseConnectionHandler class is correctly used as an abstract
        base class and that its subclasses provide the necessary implementation details for creating
        connections.
        """
        handler = BaseConnectionHandler()
        msg = "Subclasses must implement create_connection()."
        with self.assertRaisesMessage(NotImplementedError, msg):
            handler.create_connection(None)

    def test_all_initialized_only(self):
        handler = BaseConnectionHandler({"default": {}})
        self.assertEqual(handler.all(initialized_only=True), [])
