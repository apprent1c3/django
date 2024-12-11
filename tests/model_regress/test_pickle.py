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
                Custom implementation of the Pickle reduction protocol.

                This method is used to reduce the object to a serializable form, allowing it to be pickled.
                It modifies the default reduction behavior by removing a specific version indicator from the serialized data.

                Returns:
                    list: A list containing the reduced object's state, compatible with the Pickle protocol.

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
                Custom implementation of the :meth:`__reduce__` method to support serialization of the object.

                This method is used by the :mod:`pickle` module to serialize the object, and is intended to be used internally by Django.
                The implementation extends the parent class's :meth:`__reduce__` method and modifies the resulting pickle data to include
                a specific version identifier (:const:`DJANGO_VERSION_PICKLE_KEY`) with a value of '1.0'. This ensures that the object
                can be properly deserialized by compatible versions of Django. 

                :return: A tuple containing the reduced representation of the object, ready for serialization.

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
                Override the default state retrieval to exclude specific attributes.

                This method returns a dictionary representing the object's state, 
                suitable for pickling. It intentionally omits the 'dont_pickle' attribute 
                to prevent its serialization. This customization is necessary to 
                ensure proper object reconstruction during the deserialization process.

                Returns:
                    dict: The object's state without the 'dont_pickle' attribute
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
