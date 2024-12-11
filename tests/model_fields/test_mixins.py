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
        self.instance = Foo()
        self.field = Example()

    # RemovedInDjango60Warning: when the deprecation ends, replace with:
    # def test_cache_name_not_implemented(self):
    #   with self.assertRaises(NotImplementedError):
    #       FieldCacheMixin().cache_name
    def test_get_cache_name_not_implemented(self):
        """

        Tests that calling :meth:`get_cache_name` on an instance of :class:`FieldCacheMixin` raises a :exc:`NotImplementedError`.

        This test ensures that the :meth:`get_cache_name` method is correctly identified as an abstract method that must be implemented by any subclass of :class:`FieldCacheMixin`.

        """
        with self.assertRaises(NotImplementedError):
            FieldCacheMixin().get_cache_name()

    # RemovedInDjango60Warning.
    def test_get_cache_name_deprecated(self):
        msg = "Override ExampleOld.cache_name instead of get_cache_name()."
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            result = ExampleOld().cache_name
        self.assertEqual(result, "example")

    def test_cache_name(self):
        result = Example().cache_name
        self.assertEqual(result, "example")

    def test_get_cached_value_missing(self):
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
        Tests whether the 'is_cached' method of a field returns False for an instance.

        This test case verifies that the 'is_cached' method correctly determines when
        an instance has not been cached. The test passes if the method returns False,
        indicating that the instance is not cached.

        .. note::
           This test is a crucial part of ensuring the caching mechanism is working as expected.

        """
        result = self.field.is_cached(self.instance)
        self.assertFalse(result)

    def test_is_cached_true(self):
        """
        Checks if the :meth:`is_cached` method of the field correctly identifies when a value is cached for a given instance. The test sets a cached value for the instance and then asserts that :meth:`is_cached` returns True, confirming the value's cached status.
        """
        self.field.set_cached_value(self.instance, 1)
        result = self.field.is_cached(self.instance)
        self.assertTrue(result)

    def test_delete_cached_value(self):
        self.field.set_cached_value(self.instance, 1)
        self.field.delete_cached_value(self.instance)
        result = self.field.is_cached(self.instance)
        self.assertFalse(result)
