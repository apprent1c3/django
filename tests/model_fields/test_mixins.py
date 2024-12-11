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
        Sets up the test environment by creating instances of the Foo and Example classes, assigning them to the instance and field attributes respectively, to be used throughout the test suite.
        """
        self.instance = Foo()
        self.field = Example()

    # RemovedInDjango60Warning: when the deprecation ends, replace with:
    # def test_cache_name_not_implemented(self):
    #   with self.assertRaises(NotImplementedError):
    #       FieldCacheMixin().cache_name
    def test_get_cache_name_not_implemented(self):
        """
        Tests that calling get_cache_name on an instance of FieldCacheMixin raises a NotImplementedError, 
        indicating that this method must be implemented by any subclass of FieldCacheMixin.
        """
        with self.assertRaises(NotImplementedError):
            FieldCacheMixin().get_cache_name()

    # RemovedInDjango60Warning.
    def test_get_cache_name_deprecated(self):
        """
        Tests the deprecation of the get_cache_name method in the ExampleOld class.

        This test verifies that accessing the cache_name attribute emits a RemovedInDjango60Warning
        and returns the expected cache name ('example'). The warning is raised to encourage
        developers to override the cache_name attribute instead of relying on the deprecated
        get_cache_name method, which will be removed in Django 6.0.
        """
        msg = "Override ExampleOld.cache_name instead of get_cache_name()."
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            result = ExampleOld().cache_name
        self.assertEqual(result, "example")

    def test_cache_name(self):
        """
        Tests the cache_name property to ensure it returns the expected string.

        Verifies that the cache_name property of an instance of the Example class returns
        the string 'example', as expected by the application's caching mechanism.

        This test is crucial to guarantee the correct functionality of the caching system,
        which relies on accurate and consistent cache names to store and retrieve data.

        """
        result = Example().cache_name
        self.assertEqual(result, "example")

    def test_get_cached_value_missing(self):
        with self.assertRaises(KeyError):
            self.field.get_cached_value(self.instance)

    def test_get_cached_value_default(self):
        """
        Tests whether :meth:`get_cached_value` returns the specified default value when no cached value is available.

        This method verifies that if no cached value is present for a given instance, the 
        :meth:`get_cached_value` method returns the provided default value instead of raising an exception or returning a 
        special value indicating the absence of a cached value. The test ensures that the default value 
        is correctly returned, allowing for predictable behavior in scenarios where no cached value exists.
        """
        default = object()
        result = self.field.get_cached_value(self.instance, default=default)
        self.assertIs(result, default)

    def test_get_cached_value_after_set(self):
        """
        Tests that a cached value set for an instance is correctly retrieved.

        Verifies that setting a cached value using :meth:`set_cached_value` and then
        retrieving it with :meth:`get_cached_value` returns the same value, ensuring
        that the caching mechanism is functioning as expected.

        The test covers the basic workflow of setting and getting a cached value,
        providing assurance that the cache is properly updated and retrieved.
        """
        value = object()

        self.field.set_cached_value(self.instance, value)
        result = self.field.get_cached_value(self.instance)

        self.assertIs(result, value)

    def test_is_cached_false(self):
        """
        Tests that the is_cached method of a field returns False.

        This test case verifies the functionality of the is_cached method by checking its return value for a given instance.
        It ensures that the method correctly reports whether the field's value is cached or not, confirming the expected behavior of returning False in this scenario.
        """
        result = self.field.is_cached(self.instance)
        self.assertFalse(result)

    def test_is_cached_true(self):
        self.field.set_cached_value(self.instance, 1)
        result = self.field.is_cached(self.instance)
        self.assertTrue(result)

    def test_delete_cached_value(self):
        """
        Tests the deletion of a cached value for a given instance.

        Verifies that after setting a cached value, deleting it results in the value no longer being flagged as cached. This ensures the cache is properly updated and reflects the expected state of the instance. The test covers the scenario where a cached value is first set and then removed, confirming that the removal is successful by checking the instance's cache status afterwards.
        """
        self.field.set_cached_value(self.instance, 1)
        self.field.delete_cached_value(self.instance)
        result = self.field.is_cached(self.instance)
        self.assertFalse(result)
