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
        field = UUIDField(required=False)
        self.assertIsNone(field.clean(""))
        self.assertIsNone(field.clean(None))

    def test_uuidfield_3(self):
        field = UUIDField()
        with self.assertRaisesMessage(ValidationError, "Enter a valid UUID."):
            field.clean("550e8400")

    def test_uuidfield_4(self):
        """

        Tests the UUIDField's ability to properly prepare a UUID value for use.

        The preparation process involves converting a UUID object into a string
        representation. This test case verifies that the resulting string is in the
        correct format, which is a hexadecimal string separated by hyphens.

        The test uses a predefined UUID value to ensure consistency and reliability
        in the testing process. The expected output is a string that follows the
        standard UUID format, which is used for validation and comparison purposes.

        """
        field = UUIDField()
        value = field.prepare_value(uuid.UUID("550e8400e29b41d4a716446655440000"))
        self.assertEqual(value, "550e8400-e29b-41d4-a716-446655440000")
