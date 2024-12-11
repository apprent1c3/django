from django.db.models.utils import create_namedtuple_class
from django.test import SimpleTestCase


class NamedTupleClassTests(SimpleTestCase):
    def test_immutability(self):
        """
        Tests the immutability of a dynamically created namedtuple class by attempting to assign a value to a non-existent field, verifying that an AttributeError is raised.
        """
        row_class = create_namedtuple_class("field1", "field2")
        row = row_class("value1", "value2")
        with self.assertRaises(AttributeError):
            row.field3 = "value3"
