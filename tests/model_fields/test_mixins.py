from django.db.models.fields.mixins import FieldCacheMixin
from django.test import SimpleTestCase
from django.utils.deprecation import RemovedInDjango60Warning
from django.utils.functional import cached_property

from .models import Foo


# RemovedInDjango60Warning.
class ExampleOld(FieldCacheMixin):
    def get_cache_name(self):
        return "example"


class Example(FieldCacheMixin):
    @cached_property
    def cache_name(self):
        return "example"


class FieldCacheMixinTests(SimpleTestCase):
    def setUp(self):
        """

        Sets up the test environment by creating instances of necessary classes.

        This method is used to initialize the test fixture, creating a new instance of
        Foo and Example, which are then stored as instance variables for use in
        subsequent tests.

        """
        self.instance = Foo()
        self.field = Example()

    # RemovedInDjango60Warning: when the deprecation ends, replace with:
    # def test_cache_name_not_implemented(self):
    #   with self.assertRaises(NotImplementedError):
    #       FieldCacheMixin().cache_name
    def test_get_cache_name_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            FieldCacheMixin().get_cache_name()

    # RemovedInDjango60Warning.
    def test_get_cache_name_deprecated(self):
        msg = "Override ExampleOld.cache_name instead of get_cache_name()."
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            result = ExampleOld().cache_name
        self.assertEqual(result, "example")

    def test_cache_name(self):
        """
        Tests that the cache_name property returns the expected value.

        This test case verifies that the cache_name property is correctly set to a lowercase
        version of the class name, in this case 'example'.

        It ensures that the caching mechanism is properly naming cache entries based on the
        class name, which helps to maintain cache consistency and avoid potential collisions.

        """
        result = Example().cache_name
        self.assertEqual(result, "example")

    def test_get_cached_value_missing(self):
        """
        Tests that a KeyError is raised when attempting to retrieve a cached value for a non-existent key.

        This test case verifies the expected behavior of the get_cached_value method when the requested value is not present in the cache. It ensures that a KeyError exception is properly raised, indicating that the value is missing from the cache.

        :raises: KeyError if the value is not found in the cache
        """
        with self.assertRaises(KeyError):
            self.field.get_cached_value(self.instance)

    def test_get_cached_value_default(self):
        default = object()
        result = self.field.get_cached_value(self.instance, default=default)
        self.assertIs(result, default)

    def test_get_cached_value_after_set(self):
        value = object()

        self.field.set_cached_value(self.instance, value)
        result = self.field.get_cached_value(self.instance)

        self.assertIs(result, value)

    def test_is_cached_false(self):
        """
        Tests that the is_cached method returns False for an instance.

        This test case verifies the correctness of the caching mechanism by checking 
        that the is_cached method correctly identifies when an instance is not cached. 

        The test assumes that the instance in question has not been previously cached, 
        and checks the return value of the is_cached method to ensure it is False, 
        indicating that the instance is not cached.
        """
        result = self.field.is_cached(self.instance)
        self.assertFalse(result)

    def test_is_cached_true(self):
        """
        Tests whether the :meth:`is_cached` method returns True when a cached value is set for a given instance.

        This test case verifies the functionality of the :class:`field` instance by setting a cached value 
        and then checking if the :meth:`is_cached` method correctly identifies the presence of this cached value.

        :param none:
        :raises AssertionError: If the :meth:`is_cached` method does not return True when a cached value is set.
        :return: None
        """
        self.field.set_cached_value(self.instance, 1)
        result = self.field.is_cached(self.instance)
        self.assertTrue(result)

    def test_delete_cached_value(self):
        """
        Tests that deleting a cached value removes it from the cache.

        This test sets a cached value for a given instance, then immediately deletes it.
        It verifies that the value is no longer cached by checking if the field reports
        it as cached, expecting a False result to confirm successful deletion.
        """
        self.field.set_cached_value(self.instance, 1)
        self.field.delete_cached_value(self.instance)
        result = self.field.is_cached(self.instance)
        self.assertFalse(result)
