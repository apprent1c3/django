from django.core.serializers.base import DeserializedObject
from django.test import SimpleTestCase

from .models import Author


class TestDeserializedObjectTests(SimpleTestCase):
    def test_repr(self):
        """
        Tests the string representation of a DeserializedObject instance.

        Verifies that the repr function returns a string in the expected format,
        including the object type and the serialized form of the wrapped object.
        In this case, an Author object is used as the wrapped object and the test
        checks that the representation string includes the object type (Author) and
        its primary key (pk).
        """
        author = Author(name="John", pk=1)
        deserial_obj = DeserializedObject(obj=author)
        self.assertEqual(
            repr(deserial_obj), "<DeserializedObject: serializers.Author(pk=1)>"
        )
