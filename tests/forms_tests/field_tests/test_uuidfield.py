import uuid

from django.core.exceptions import ValidationError
from django.forms import UUIDField
from django.test import SimpleTestCase


class UUIDFieldTest(SimpleTestCase):
    def test_uuidfield_1(self):
        field = UUIDField()
        value = field.clean("550e8400e29b41d4a716446655440000")
        self.assertEqual(value, uuid.UUID("550e8400e29b41d4a716446655440000"))

    def test_clean_value_with_dashes(self):
        field = UUIDField()
        value = field.clean("550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(value, uuid.UUID("550e8400e29b41d4a716446655440000"))

    def test_uuidfield_2(self):
        """
        Tests the functionality of the UUIDField when it is set as not required.

        Checks that the field correctly handles empty strings and None values, 
        by asserting that they are cleaned to None.
        """
        field = UUIDField(required=False)
        self.assertIsNone(field.clean(""))
        self.assertIsNone(field.clean(None))

    def test_uuidfield_3(self):
        """
        Tests that the UUIDField raises a ValidationError when given an invalid UUID string.

        This test case checks that the field correctly identifies and rejects a string that is
        not a valid UUID, ensuring that only properly formatted UUIDs are accepted.

        The test expects a ValidationError to be raised with the message 'Enter a valid UUID.',
        demonstrating that the UUIDField enforces proper UUID formatting and does not allow
        invalid input to pass through undetected.
        """
        field = UUIDField()
        with self.assertRaisesMessage(ValidationError, "Enter a valid UUID."):
            field.clean("550e8400")

    def test_uuidfield_4(self):
        field = UUIDField()
        value = field.prepare_value(uuid.UUID("550e8400e29b41d4a716446655440000"))
        self.assertEqual(value, "550e8400-e29b-41d4-a716-446655440000")
