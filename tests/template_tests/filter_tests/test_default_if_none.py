from django.template.defaultfilters import default_if_none
from django.test import SimpleTestCase


class FunctionTests(SimpleTestCase):
    def test_value(self):
        """
        This is a comment
        """
        self.assertEqual(default_if_none("val", "default"), "val")

    def test_none(self):
        """
        This is a comment
        """
        self.assertEqual(default_if_none(None, "default"), "default")

    def test_empty_string(self):
        """
        This is a comment
        """
        self.assertEqual(default_if_none("", "default"), "")
