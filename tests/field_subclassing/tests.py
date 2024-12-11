from django.db import connection, models
from django.test import SimpleTestCase

from .fields import CustomDescriptorField, CustomTypedField


class TestDbType(SimpleTestCase):
    def test_db_parameters_respects_db_type(self):
        """
        Tests that the db_parameters method of CustomTypedField returns the correct database type.

        This test case verifies that when a CustomTypedField is used, the database type 
        returned in the db_parameters dictionary respects the custom field type. It 
        ensures that the 'type' key in the db_parameters dictionary is set to 
        'custom_field' as expected. This check is crucial to guarantee that the custom 
        field is correctly represented in the database schema.
        """
        f = CustomTypedField()
        self.assertEqual(f.db_parameters(connection)["type"], "custom_field")


class DescriptorClassTest(SimpleTestCase):
    def test_descriptor_class(self):
        """
        teste the behavior of the CustomDescriptorField descriptor, specifically its getter and setter functionality.

            This function creates a test model instance, CustomDescriptorModel, with a CustomDescriptorField and then exercises the field's descriptor protocol.
            It verifies the field's behavior in terms of tracking the number of times the field is accessed (get) and assigned (set), demonstrating that the descriptor correctly increments the appropriate counters and updates the field's value.
            The function checks for the expected behavior under various scenarios, including initial field access, assignment, and subsequent accesses and assignments.
        """
        class CustomDescriptorModel(models.Model):
            name = CustomDescriptorField(max_length=32)

        m = CustomDescriptorModel()
        self.assertFalse(hasattr(m, "_name_get_count"))
        # The field is set to its default in the model constructor.
        self.assertEqual(m._name_set_count, 1)
        m.name = "foo"
        self.assertFalse(hasattr(m, "_name_get_count"))
        self.assertEqual(m._name_set_count, 2)
        self.assertEqual(m.name, "foo")
        self.assertEqual(m._name_get_count, 1)
        self.assertEqual(m._name_set_count, 2)
        m.name = "bar"
        self.assertEqual(m._name_get_count, 1)
        self.assertEqual(m._name_set_count, 3)
        self.assertEqual(m.name, "bar")
        self.assertEqual(m._name_get_count, 2)
        self.assertEqual(m._name_set_count, 3)
