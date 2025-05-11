import pickle

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils.functional import SimpleLazyObject


class TestUtilsSimpleLazyObjectDjangoTestCase(TestCase):
    def test_pickle(self):
        """
        Tests the pickling of SimpleLazyObject instances, ensuring that they can be successfully serialized using the pickle module with various protocol versions.
        """
        user = User.objects.create_user("johndoe", "john@example.com", "pass")
        x = SimpleLazyObject(lambda: user)
        pickle.dumps(x)
        # Try the variant protocol levels.
        pickle.dumps(x, 0)
        pickle.dumps(x, 1)
        pickle.dumps(x, 2)
