from django.test import SimpleTestCase
from django.test.client import FakePayload


class FakePayloadTests(SimpleTestCase):
    def test_write_after_read(self):
        """
        Tests that a payload object cannot be written to after it has been read, whether the read operation was a full read or a readline operation. This check is performed to ensure that the payload object maintains its expected state and behavior after a read operation has been executed, preventing potential data corruption or inconsistencies. The test verifies that attempting to write to the payload after a read operation raises a ValueError with a corresponding error message.
        """
        payload = FakePayload()
        for operation in [payload.read, payload.readline]:
            with self.subTest(operation=operation.__name__):
                operation()
                msg = "Unable to write a payload after it's been read"
                with self.assertRaisesMessage(ValueError, msg):
                    payload.write(b"abc")
