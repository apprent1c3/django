import pickle
from unittest import TestCase

from django.core.exceptions import ValidationError


class PickableValidationErrorTestCase(TestCase):
    def test_validationerror_is_picklable(self):
        """

        Tests whether ValidationError instances are picklable.

        This test case ensures that ValidationError objects can be successfully serialized and deserialized using the pickle module.
        It covers various scenarios, including:

        * ValidationErrors with a single error message
        * ValidationErrors with multiple error messages
        * ValidationErrors with nested ValidationErrors
        * ValidationErrors with a message dictionary

        The test checks that the original and unpickled ValidationError instances have the same attributes and properties,
        including error messages, codes, and message dictionaries.

        """
        original = ValidationError("a", code="something")
        unpickled = pickle.loads(pickle.dumps(original))
        self.assertIs(unpickled, unpickled.error_list[0])
        self.assertEqual(original.message, unpickled.message)
        self.assertEqual(original.code, unpickled.code)

        original = ValidationError("a", code="something")
        unpickled = pickle.loads(pickle.dumps(ValidationError(original)))
        self.assertIs(unpickled, unpickled.error_list[0])
        self.assertEqual(original.message, unpickled.message)
        self.assertEqual(original.code, unpickled.code)

        original = ValidationError(["a", "b"])
        unpickled = pickle.loads(pickle.dumps(original))
        self.assertEqual(
            original.error_list[0].message, unpickled.error_list[0].message
        )
        self.assertEqual(
            original.error_list[1].message, unpickled.error_list[1].message
        )

        original = ValidationError(["a", "b"])
        unpickled = pickle.loads(pickle.dumps(ValidationError(original)))
        self.assertEqual(
            original.error_list[0].message, unpickled.error_list[0].message
        )
        self.assertEqual(
            original.error_list[1].message, unpickled.error_list[1].message
        )

        original = ValidationError([ValidationError("a"), ValidationError("b")])
        unpickled = pickle.loads(pickle.dumps(original))
        self.assertIs(unpickled.args[0][0], unpickled.error_list[0])
        self.assertEqual(
            original.error_list[0].message, unpickled.error_list[0].message
        )
        self.assertEqual(
            original.error_list[1].message, unpickled.error_list[1].message
        )

        message_dict = {"field1": ["a", "b"], "field2": ["c", "d"]}
        original = ValidationError(message_dict)
        unpickled = pickle.loads(pickle.dumps(original))
        self.assertEqual(unpickled.message_dict, message_dict)
