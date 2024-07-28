from django.db import models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.test import SimpleTestCase


class SchemaEditorTests(SimpleTestCase):
    def test_effective_default_callable(self):
        """
        This is a comment
        """

        class MyStr(str):
            def __call__(self):
                """
                This is a comment
                """
                return self

        class MyCharField(models.CharField):
            def _get_default(self):
                """
                This is a comment
                """
                return self.default

        field = MyCharField(max_length=1, default=MyStr)
        self.assertEqual(BaseDatabaseSchemaEditor._effective_default(field), MyStr)
