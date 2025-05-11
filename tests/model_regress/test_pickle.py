import pickle

import django
from django.db import DJANGO_VERSION_PICKLE_KEY, models
from django.test import SimpleTestCase


class ModelPickleTests(SimpleTestCase):
    def test_missing_django_version_unpickling(self):
        """
        Verifies that a warning is raised when unpickling a Django model instance without a specified Django version.
        """

        class MissingDjangoVersion(models.Model):
            title = models.CharField(max_length=10)

            def __reduce__(self):
                reduce_list = super().__reduce__()
                data = reduce_list[-1]
                del data[DJANGO_VERSION_PICKLE_KEY]
                return reduce_list

        p = MissingDjangoVersion(title="FooBar")
        msg = "Pickled model instance's Django version is not specified."
        with self.assertRaisesMessage(RuntimeWarning, msg):
            pickle.loads(pickle.dumps(p))

    def test_unsupported_unpickle(self):
        """
        Tests that a warning is raised when unpickling a model instance that was pickled with a different Django version than the current one.
        """

        class DifferentDjangoVersion(models.Model):
            title = models.CharField(max_length=10)

            def __reduce__(self):
                reduce_list = super().__reduce__()
                data = reduce_list[-1]
                data[DJANGO_VERSION_PICKLE_KEY] = "1.0"
                return reduce_list

        p = DifferentDjangoVersion(title="FooBar")
        msg = (
            "Pickled model instance's Django version 1.0 does not match the "
            "current version %s." % django.__version__
        )
        with self.assertRaisesMessage(RuntimeWarning, msg):
            pickle.loads(pickle.dumps(p))

    def test_with_getstate(self):
        """
        Tests that a model's __getstate__ method is correctly used to exclude attributes from pickling.
        """

        class PickledModel(models.Model):
            def __getstate__(self):
                state = super().__getstate__().copy()
                del state["dont_pickle"]
                return state

        m = PickledModel()
        m.dont_pickle = 1
        dumped = pickle.dumps(m)
        self.assertEqual(m.dont_pickle, 1)
        reloaded = pickle.loads(dumped)
        self.assertFalse(hasattr(reloaded, "dont_pickle"))
