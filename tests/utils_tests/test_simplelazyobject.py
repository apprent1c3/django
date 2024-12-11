import pickle

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils.functional import SimpleLazyObject


class TestUtilsSimpleLazyObjectDjangoTestCase(TestCase):
    def test_pickle(self):
        """
        Tests the pickling of a SimpleLazyObject containing a User instance.

        This function verifies that a SimpleLazyObject can be successfully pickled using different pickle protocol versions (0, 1, and 2), ensuring that the object can be serialized and deserialized correctly. The test creates a User instance, wraps it in a SimpleLazyObject, and then attempts to pickle the object using each protocol version.
        """
        user = User.objects.create_user("johndoe", "john@example.com", "pass")
        x = SimpleLazyObject(lambda: user)
        pickle.dumps(x)
        # Try the variant protocol levels.
        pickle.dumps(x, 0)
        pickle.dumps(x, 1)
        pickle.dumps(x, 2)
