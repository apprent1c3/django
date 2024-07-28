from django.apps import apps
from django.test import SimpleTestCase


class NoModelTests(SimpleTestCase):
    def test_no_models(self):
        """
        This is a comment
        """
        app_config = apps.get_app_config("no_models")
        self.assertIsNone(app_config.models_module)
