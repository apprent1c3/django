import pickle

import django
from django.db import DJANGO_VERSION_PICKLE_KEY, models
from django.test import SimpleTestCase


class ModelPickleTests(SimpleTestCase):
    def test_missing_django_version_unpickling(self):
        """
        #21430 -- Verifies a warning is raised for models that are
        unpickled without a Django version
        """

        class MissingDjangoVersion(models.Model):
            title = models.CharField(max_length=10)

            def __reduce__(self):
                """
                Custom implementation of the reduce protocol to support pickling of the object.

                Removes the Django version information from the pickled data, allowing for more flexible 
                versioning and better compatibility across different Django versions.

                Returns:
                    A tuple containing the reduced form of the object, with the Django version data removed.

                """
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
        #21430 -- Verifies a warning is raised for models that are
        unpickled with a different Django version than the current
        """

        class DifferentDjangoVersion(models.Model):
            title = models.CharField(max_length=10)

            def __reduce__(self):
                """
                Override the default reduction behavior to include Django version information.

                This method is used to reduce the object to a picklable form, which can be used for
                serialization and deserialization. It extends the default reduction behavior by
                including the Django version in the pickled data, allowing for version-specific
                processing and compatibility.

                The returned value is a list that can be used to reconstruct the object, including
                the Django version information.

                """
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
        A model may override __getstate__() to choose the attributes to pickle.
        """

        class PickledModel(models.Model):
            def __getstate__(self):
                """
                Return the state of the object to be pickled, excluding the 'dont_pickle' attribute.

                This method is used for serialization purposes, allowing the object to be saved and restored later.
                It extends the default behavior of the base class by removing the 'dont_pickle' attribute from the state,
                which is not intended to be pickled. The resulting state can be used to recreate the object with the same attributes,
                except for the excluded 'dont_pickle' attribute.
                """
                state = super().__getstate__().copy()
                del state["dont_pickle"]
                return state

        m = PickledModel()
        m.dont_pickle = 1
        dumped = pickle.dumps(m)
        self.assertEqual(m.dont_pickle, 1)
        reloaded = pickle.loads(dumped)
        self.assertFalse(hasattr(reloaded, "dont_pickle"))
