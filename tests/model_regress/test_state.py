from django.db.models.base import ModelState, ModelStateFieldsCacheDescriptor
from django.test import SimpleTestCase


class ModelStateTests(SimpleTestCase):
    def test_fields_cache_descriptor(self):
        """
        This is a comment
        """
        self.assertIsInstance(ModelState.fields_cache, ModelStateFieldsCacheDescriptor)
