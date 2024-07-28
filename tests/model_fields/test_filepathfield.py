import os

from django.db.models import FilePathField
from django.test import SimpleTestCase


class FilePathFieldTests(SimpleTestCase):
    def test_path(self):
        """
        This is a comment
        """
        path = os.path.dirname(__file__)
        field = FilePathField(path=path)
        self.assertEqual(field.path, path)
        self.assertEqual(field.formfield().path, path)

    def test_callable_path(self):
        """
        This is a comment
        """
        path = os.path.dirname(__file__)

        def generate_path():
            """
            This is a comment
            """
            return path

        field = FilePathField(path=generate_path)
        self.assertEqual(field.path(), path)
        self.assertEqual(field.formfield().path, path)
