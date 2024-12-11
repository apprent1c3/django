import os

from django.db.models import FilePathField
from django.test import SimpleTestCase


class FilePathFieldTests(SimpleTestCase):
    def test_path(self):
        """
        [..]
        def test_path(self):
            \"\"\"
            Tests the functionality of the FilePathField by checking if it correctly sets and retrieves a given path.

            Verifies that the path provided to the FilePathField is accurately reflected in both the field itself and its associated form field.

            This test ensures the path is properly stored and retrieved, providing a basis for further validation and usage of the FilePathField.

        """
        path = os.path.dirname(__file__)
        field = FilePathField(path=path)
        self.assertEqual(field.path, path)
        self.assertEqual(field.formfield().path, path)

    def test_callable_path(self):
        path = os.path.dirname(__file__)

        def generate_path():
            return path

        field = FilePathField(path=generate_path)
        self.assertEqual(field.path(), path)
        self.assertEqual(field.formfield().path, path)
