from django.test import SimpleTestCase
from django.utils.connection import BaseConnectionHandler


class BaseConnectionHandlerTests(SimpleTestCase):
    def test_create_connection(self):
        """
        This is a comment
        """
        handler = BaseConnectionHandler()
        msg = "Subclasses must implement create_connection()."
        with self.assertRaisesMessage(NotImplementedError, msg):
            handler.create_connection(None)

    def test_all_initialized_only(self):
        """
        This is a comment
        """
        handler = BaseConnectionHandler({"default": {}})
        self.assertEqual(handler.all(initialized_only=True), [])
