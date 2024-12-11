# Unit tests for cache framework
# Uses whatever cache backend is set in the test settings file.
import copy
import io
import os
import pickle
import re
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock, skipIf

from django.conf import settings
from django.core import management, signals
from django.core.cache import (
    DEFAULT_CACHE_ALIAS,
    CacheHandler,
    CacheKeyWarning,
    InvalidCacheKey,
    cache,
    caches,
)
from django.core.cache.backends.base import InvalidCacheBackendError
from django.core.cache.backends.redis import RedisCacheClient
from django.core.cache.utils import make_template_fragment_key
from django.db import close_old_connections, connection, connections
from django.db.backends.utils import CursorWrapper
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseNotModified,
    StreamingHttpResponse,
)
from django.middleware.cache import (
    CacheMiddleware,
    FetchFromCacheMiddleware,
    UpdateCacheMiddleware,
)
from django.middleware.csrf import CsrfViewMiddleware
from django.template import engines
from django.template.context_processors import csrf
from django.template.response import TemplateResponse
from django.test import (
    RequestFactory,
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    override_settings,
)
from django.test.signals import setting_changed
from django.test.utils import CaptureQueriesContext
from django.utils import timezone, translation
from django.utils.cache import (
    get_cache_key,
    learn_cache_key,
    patch_cache_control,
    patch_vary_headers,
)
from django.views.decorators.cache import cache_control, cache_page

from .models import Poll, expensive_calculation


# functions/classes for complex data type tests
def f():
    return 42


class C:
    def m(n):
        return 24


class Unpicklable:
    def __getstate__(self):
        raise pickle.PickleError()


def empty_response(request):
    return HttpResponse()


KEY_ERRORS_WITH_MEMCACHED_MSG = (
    "Cache key contains characters that will cause errors if used with memcached: %r"
)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }
)
class DummyCacheTests(SimpleTestCase):
    # The Dummy cache backend doesn't really behave like a test backend,
    # so it has its own test case.

    def test_simple(self):
        "Dummy cache backend ignores cache set calls"
        cache.set("key", "value")
        self.assertIsNone(cache.get("key"))

    def test_add(self):
        "Add doesn't do anything in dummy cache backend"
        self.assertIs(cache.add("addkey1", "value"), True)
        self.assertIs(cache.add("addkey1", "newvalue"), True)
        self.assertIsNone(cache.get("addkey1"))

    def test_non_existent(self):
        "Nonexistent keys aren't found in the dummy cache backend"
        self.assertIsNone(cache.get("does_not_exist"))
        self.assertEqual(cache.get("does_not_exist", "bang!"), "bang!")

    def test_get_many(self):
        "get_many returns nothing for the dummy cache backend"
        cache.set_many({"a": "a", "b": "b", "c": "c", "d": "d"})
        self.assertEqual(cache.get_many(["a", "c", "d"]), {})
        self.assertEqual(cache.get_many(["a", "b", "e"]), {})

    def test_get_many_invalid_key(self):
        msg = KEY_ERRORS_WITH_MEMCACHED_MSG % ":1:key with spaces"
        with self.assertWarnsMessage(CacheKeyWarning, msg):
            cache.get_many(["key with spaces"])

    def test_delete(self):
        "Cache deletion is transparently ignored on the dummy cache backend"
        cache.set_many({"key1": "spam", "key2": "eggs"})
        self.assertIsNone(cache.get("key1"))
        self.assertIs(cache.delete("key1"), False)
        self.assertIsNone(cache.get("key1"))
        self.assertIsNone(cache.get("key2"))

    def test_has_key(self):
        "The has_key method doesn't ever return True for the dummy cache backend"
        cache.set("hello1", "goodbye1")
        self.assertIs(cache.has_key("hello1"), False)
        self.assertIs(cache.has_key("goodbye1"), False)

    def test_in(self):
        "The in operator doesn't ever return True for the dummy cache backend"
        cache.set("hello2", "goodbye2")
        self.assertNotIn("hello2", cache)
        self.assertNotIn("goodbye2", cache)

    def test_incr(self):
        "Dummy cache values can't be incremented"
        cache.set("answer", 42)
        with self.assertRaises(ValueError):
            cache.incr("answer")
        with self.assertRaises(ValueError):
            cache.incr("does_not_exist")
        with self.assertRaises(ValueError):
            cache.incr("does_not_exist", -1)

    def test_decr(self):
        "Dummy cache values can't be decremented"
        cache.set("answer", 42)
        with self.assertRaises(ValueError):
            cache.decr("answer")
        with self.assertRaises(ValueError):
            cache.decr("does_not_exist")
        with self.assertRaises(ValueError):
            cache.decr("does_not_exist", -1)

    def test_touch(self):
        """Dummy cache can't do touch()."""
        self.assertIs(cache.touch("whatever"), False)

    def test_data_types(self):
        "All data types are ignored equally by the dummy cache"
        tests = {
            "string": "this is a string",
            "int": 42,
            "bool": True,
            "list": [1, 2, 3, 4],
            "tuple": (1, 2, 3, 4),
            "dict": {"A": 1, "B": 2},
            "function": f,
            "class": C,
        }
        for key, value in tests.items():
            with self.subTest(key=key):
                cache.set(key, value)
                self.assertIsNone(cache.get(key))

    def test_expiration(self):
        "Expiration has no effect on the dummy cache"
        cache.set("expire1", "very quickly", 1)
        cache.set("expire2", "very quickly", 1)
        cache.set("expire3", "very quickly", 1)

        time.sleep(2)
        self.assertIsNone(cache.get("expire1"))

        self.assertIs(cache.add("expire2", "newvalue"), True)
        self.assertIsNone(cache.get("expire2"))
        self.assertIs(cache.has_key("expire3"), False)

    def test_unicode(self):
        "Unicode values are ignored by the dummy cache"
        stuff = {
            "ascii": "ascii_value",
            "unicode_ascii": "Iñtërnâtiônàlizætiøn1",
            "Iñtërnâtiônàlizætiøn": "Iñtërnâtiônàlizætiøn2",
            "ascii2": {"x": 1},
        }
        for key, value in stuff.items():
            with self.subTest(key=key):
                cache.set(key, value)
                self.assertIsNone(cache.get(key))

    def test_set_many(self):
        "set_many does nothing for the dummy cache backend"
        self.assertEqual(cache.set_many({"a": 1, "b": 2}), [])
        self.assertEqual(cache.set_many({"a": 1, "b": 2}, timeout=2, version="1"), [])

    def test_set_many_invalid_key(self):
        """

        Tests the behavior of setting multiple values in the cache when an invalid key is provided.

        This test case verifies that the cache correctly raises a warning when attempting to set a value with a key that contains spaces, which is considered an invalid key.

        The expected warning message is checked to ensure it matches the expected error message for Memcached key errors.

        The test passes if the warning is raised with the correct message, indicating that the cache properly handles invalid keys and provides informative error messages.

        """
        msg = KEY_ERRORS_WITH_MEMCACHED_MSG % ":1:key with spaces"
        with self.assertWarnsMessage(CacheKeyWarning, msg):
            cache.set_many({"key with spaces": "foo"})

    def test_delete_many(self):
        "delete_many does nothing for the dummy cache backend"
        cache.delete_many(["a", "b"])

    def test_delete_many_invalid_key(self):
        """

        Tests that deleting multiple cache items with an invalid key raises a warning.

        The function verifies that attempting to delete cache items with keys containing
        spaces triggers a CacheKeyWarning, indicating the presence of invalid characters
        in the key. This ensures the cache deletion operation behaves correctly when
        encountering malformed keys.

        """
        msg = KEY_ERRORS_WITH_MEMCACHED_MSG % ":1:key with spaces"
        with self.assertWarnsMessage(CacheKeyWarning, msg):
            cache.delete_many(["key with spaces"])

    def test_clear(self):
        "clear does nothing for the dummy cache backend"
        cache.clear()

    def test_incr_version(self):
        "Dummy cache versions can't be incremented"
        cache.set("answer", 42)
        with self.assertRaises(ValueError):
            cache.incr_version("answer")
        with self.assertRaises(ValueError):
            cache.incr_version("does_not_exist")

    def test_decr_version(self):
        "Dummy cache versions can't be decremented"
        cache.set("answer", 42)
        with self.assertRaises(ValueError):
            cache.decr_version("answer")
        with self.assertRaises(ValueError):
            cache.decr_version("does_not_exist")

    def test_get_or_set(self):
        """

        Tests the functionality of the get_or_set method in the cache system.

        This method retrieves a value from the cache if the key exists, otherwise it sets the key with the provided default value and returns it.
        If the default value is None, the method sets the key to None and returns None.

        The purpose of this test is to verify that the get_or_set method behaves correctly in both scenarios, ensuring that the cache is updated and the expected values are returned.

        """
        self.assertEqual(cache.get_or_set("mykey", "default"), "default")
        self.assertIsNone(cache.get_or_set("mykey", None))

    def test_get_or_set_callable(self):
        """

        Retrieve a value from the cache or set it using a provided callable if the key does not exist.

        The provided callable is expected to return the default value to be cached when the key is not found.
        If the key already exists in the cache, its current value is returned instead of executing the callable.

        This method allows for a convenient way to populate the cache with default values when they are missing, while also 
        caching the results to avoid repeated executions of the callable for the same key.

        Parameters
        ----------
        key : str
            The key to retrieve or set in the cache.
        callable : function
            A function that returns the default value to be cached when the key is not found.

        Returns
        -------
        The cached value for the given key, or the result of the callable if the key is not found.

        """
        def my_callable():
            return "default"

        self.assertEqual(cache.get_or_set("mykey", my_callable), "default")
        self.assertEqual(cache.get_or_set("mykey", my_callable()), "default")


def custom_key_func(key, key_prefix, version):
    "A customized cache key function"
    return "CUSTOM-" + "-".join([key_prefix, str(version), key])


_caches_setting_base = {
    "default": {},
    "prefix": {"KEY_PREFIX": "cacheprefix{}".format(os.getpid())},
    "v2": {"VERSION": 2},
    "custom_key": {"KEY_FUNCTION": custom_key_func},
    "custom_key2": {"KEY_FUNCTION": "cache.tests.custom_key_func"},
    "cull": {"OPTIONS": {"MAX_ENTRIES": 30}},
    "zero_cull": {"OPTIONS": {"CULL_FREQUENCY": 0, "MAX_ENTRIES": 30}},
}


def caches_setting_for_tests(base=None, exclude=None, **params):
    # `base` is used to pull in the memcached config from the original settings,
    # `exclude` is a set of cache names denoting which `_caches_setting_base` keys
    # should be omitted.
    # `params` are test specific overrides and `_caches_settings_base` is the
    # base config for the tests.
    # This results in the following search order:
    # params -> _caches_setting_base -> base
    base = base or {}
    exclude = exclude or set()
    setting = {k: base.copy() for k in _caches_setting_base if k not in exclude}
    for key, cache_params in setting.items():
        cache_params.update(_caches_setting_base[key])
        cache_params.update(params)
    return setting


class BaseCacheTests:
    # A common set of tests to apply to all cache backends
    factory = RequestFactory()

    # Some clients raise custom exceptions when .incr() or .decr() are called
    # with a non-integer value.
    incr_decr_type_error = TypeError

    def tearDown(self):
        cache.clear()

    def test_simple(self):
        # Simple cache set/get works
        """
        Verifies the simple cache set and get functionality.

        This test case checks if a value can be successfully stored in the cache using a given key and then retrieved using the same key, ensuring data consistency and correctness. 

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the cached value does not match the expected value.

        """
        cache.set("key", "value")
        self.assertEqual(cache.get("key"), "value")

    def test_default_used_when_none_is_set(self):
        """If None is cached, get() returns it instead of the default."""
        cache.set("key_default_none", None)
        self.assertIsNone(cache.get("key_default_none", default="default"))

    def test_add(self):
        # A key can be added to a cache
        """

        Tests the functionality of adding key-value pairs to the cache.

        This test case verifies that adding a new key-value pair to the cache returns True, 
        attempting to add a key that already exists in the cache returns False, 
        and that the original value associated with the key is retained in the cache.

        """
        self.assertIs(cache.add("addkey1", "value"), True)
        self.assertIs(cache.add("addkey1", "newvalue"), False)
        self.assertEqual(cache.get("addkey1"), "value")

    def test_prefix(self):
        # Test for same cache key conflicts between shared backend
        cache.set("somekey", "value")

        # should not be set in the prefixed cache
        self.assertIs(caches["prefix"].has_key("somekey"), False)

        caches["prefix"].set("somekey", "value2")

        self.assertEqual(cache.get("somekey"), "value")
        self.assertEqual(caches["prefix"].get("somekey"), "value2")

    def test_non_existent(self):
        """Nonexistent cache keys return as None/default."""
        self.assertIsNone(cache.get("does_not_exist"))
        self.assertEqual(cache.get("does_not_exist", "bang!"), "bang!")

    def test_get_many(self):
        # Multiple cache keys can be returned using get_many
        cache.set_many({"a": "a", "b": "b", "c": "c", "d": "d"})
        self.assertEqual(
            cache.get_many(["a", "c", "d"]), {"a": "a", "c": "c", "d": "d"}
        )
        self.assertEqual(cache.get_many(["a", "b", "e"]), {"a": "a", "b": "b"})
        self.assertEqual(cache.get_many(iter(["a", "b", "e"])), {"a": "a", "b": "b"})
        cache.set_many({"x": None, "y": 1})
        self.assertEqual(cache.get_many(["x", "y"]), {"x": None, "y": 1})

    def test_delete(self):
        # Cache keys can be deleted
        cache.set_many({"key1": "spam", "key2": "eggs"})
        self.assertEqual(cache.get("key1"), "spam")
        self.assertIs(cache.delete("key1"), True)
        self.assertIsNone(cache.get("key1"))
        self.assertEqual(cache.get("key2"), "eggs")

    def test_delete_nonexistent(self):
        self.assertIs(cache.delete("nonexistent_key"), False)

    def test_has_key(self):
        # The cache can be inspected for cache keys
        """
        ..: Tests if the cache contains a given key.

            This function checks the presence of keys in the cache, regardless of their values.
            It verifies that a key is marked as present when a value is assigned to it, 
            and that a key is not marked as present if no value has been assigned.
            The test cases cover different scenarios, including keys with values, 
            keys with no expiry, and keys with a value of None.
        """
        cache.set("hello1", "goodbye1")
        self.assertIs(cache.has_key("hello1"), True)
        self.assertIs(cache.has_key("goodbye1"), False)
        cache.set("no_expiry", "here", None)
        self.assertIs(cache.has_key("no_expiry"), True)
        cache.set("null", None)
        self.assertIs(cache.has_key("null"), True)

    def test_in(self):
        # The in operator can be used to inspect cache contents
        cache.set("hello2", "goodbye2")
        self.assertIn("hello2", cache)
        self.assertNotIn("goodbye2", cache)
        cache.set("null", None)
        self.assertIn("null", cache)

    def test_incr(self):
        # Cache values can be incremented
        cache.set("answer", 41)
        self.assertEqual(cache.incr("answer"), 42)
        self.assertEqual(cache.get("answer"), 42)
        self.assertEqual(cache.incr("answer", 10), 52)
        self.assertEqual(cache.get("answer"), 52)
        self.assertEqual(cache.incr("answer", -10), 42)
        with self.assertRaises(ValueError):
            cache.incr("does_not_exist")
        with self.assertRaises(ValueError):
            cache.incr("does_not_exist", -1)
        cache.set("null", None)
        with self.assertRaises(self.incr_decr_type_error):
            cache.incr("null")

    def test_decr(self):
        # Cache values can be decremented
        """
        Decrements the value of a given key in the cache by a specified amount.

        Args:
            key (str): The key of the value to decrement.
            amount (int, optional): The amount to decrement the value by. Defaults to 1.

        Returns:
            int: The new value of the key after decrementing.

        Raises:
            ValueError: If the key does not exist in the cache.
            TypeError: If the value of the key is not numeric.

        Notes:
            Decrementing by a negative amount will effectively increment the value.
            Attempting to decrement a non-numeric value will raise an error.
        """
        cache.set("answer", 43)
        self.assertEqual(cache.decr("answer"), 42)
        self.assertEqual(cache.get("answer"), 42)
        self.assertEqual(cache.decr("answer", 10), 32)
        self.assertEqual(cache.get("answer"), 32)
        self.assertEqual(cache.decr("answer", -10), 42)
        with self.assertRaises(ValueError):
            cache.decr("does_not_exist")
        with self.assertRaises(ValueError):
            cache.incr("does_not_exist", -1)
        cache.set("null", None)
        with self.assertRaises(self.incr_decr_type_error):
            cache.decr("null")

    def test_close(self):
        """
        Tests whether the cache object has a close method and can be successfully closed.

        This test verifies the existence of the close method in the cache object and 
        confirms that it can be called without errors, ensuring proper cleanup and 
        resource release when the cache is no longer needed.
        """
        self.assertTrue(hasattr(cache, "close"))
        cache.close()

    def test_data_types(self):
        # Many different data types can be cached
        """

        Tests the caching of various data types.

        This function verifies that the cache can store and retrieve different types of data,
        including strings, integers, boolean values, lists, tuples, dictionaries, functions, and classes.
        It performs a series of tests, each checking that the cached value matches the original value.
        If any test fails, it will report which specific data type failed to be cached correctly.

        """
        tests = {
            "string": "this is a string",
            "int": 42,
            "bool": True,
            "list": [1, 2, 3, 4],
            "tuple": (1, 2, 3, 4),
            "dict": {"A": 1, "B": 2},
            "function": f,
            "class": C,
        }
        for key, value in tests.items():
            with self.subTest(key=key):
                cache.set(key, value)
                self.assertEqual(cache.get(key), value)

    def test_cache_read_for_model_instance(self):
        # Don't want fields with callable as default to be called on cache read
        """

        Tests the cache read functionality for a model instance.

        This test case verifies that an instance of the Poll model can be successfully 
        cached and retrieved, with its attributes intact. It also checks that an 
        expensive calculation is only performed once during this process, 
        ensuring the cache is being utilized as expected.

        The test covers the following scenarios:
        - Creating a new Poll instance and caching it
        - Retrieving the cached instance and verifying its attributes
        - Confirming that the expensive calculation is only run once

        """
        expensive_calculation.num_runs = 0
        Poll.objects.all().delete()
        my_poll = Poll.objects.create(question="Well?")
        self.assertEqual(Poll.objects.count(), 1)
        pub_date = my_poll.pub_date
        cache.set("question", my_poll)
        cached_poll = cache.get("question")
        self.assertEqual(cached_poll.pub_date, pub_date)
        # We only want the default expensive calculation run once
        self.assertEqual(expensive_calculation.num_runs, 1)

    def test_cache_write_for_model_instance_with_deferred(self):
        # Don't want fields with callable as default to be called on cache write
        expensive_calculation.num_runs = 0
        Poll.objects.all().delete()
        Poll.objects.create(question="What?")
        self.assertEqual(expensive_calculation.num_runs, 1)
        defer_qs = Poll.objects.defer("question")
        self.assertEqual(defer_qs.count(), 1)
        self.assertEqual(expensive_calculation.num_runs, 1)
        cache.set("deferred_queryset", defer_qs)
        # cache set should not re-evaluate default functions
        self.assertEqual(expensive_calculation.num_runs, 1)

    def test_cache_read_for_model_instance_with_deferred(self):
        # Don't want fields with callable as default to be called on cache read
        expensive_calculation.num_runs = 0
        Poll.objects.all().delete()
        Poll.objects.create(question="What?")
        self.assertEqual(expensive_calculation.num_runs, 1)
        defer_qs = Poll.objects.defer("question")
        self.assertEqual(defer_qs.count(), 1)
        cache.set("deferred_queryset", defer_qs)
        self.assertEqual(expensive_calculation.num_runs, 1)
        runs_before_cache_read = expensive_calculation.num_runs
        cache.get("deferred_queryset")
        # We only want the default expensive calculation run on creation and set
        self.assertEqual(expensive_calculation.num_runs, runs_before_cache_read)

    def test_expiration(self):
        # Cache values can be set to expire
        """

        Tests the expiration mechanism of the cache.

        This function verifies that cache entries are correctly removed after their expiration time has passed.
        It sets multiple cache entries with a short expiration time, waits for the expiration time to pass, 
        and then checks that the entries are no longer present in the cache. 
        It also tests that expired keys can be reused with new values and that the has_key method correctly reports their absence.

        """
        cache.set("expire1", "very quickly", 1)
        cache.set("expire2", "very quickly", 1)
        cache.set("expire3", "very quickly", 1)

        time.sleep(2)
        self.assertIsNone(cache.get("expire1"))

        self.assertIs(cache.add("expire2", "newvalue"), True)
        self.assertEqual(cache.get("expire2"), "newvalue")
        self.assertIs(cache.has_key("expire3"), False)

    def test_touch(self):
        # cache.touch() updates the timeout.
        cache.set("expire1", "very quickly", timeout=1)
        self.assertIs(cache.touch("expire1", timeout=4), True)
        time.sleep(2)
        self.assertIs(cache.has_key("expire1"), True)
        time.sleep(3)
        self.assertIs(cache.has_key("expire1"), False)
        # cache.touch() works without the timeout argument.
        cache.set("expire1", "very quickly", timeout=1)
        self.assertIs(cache.touch("expire1"), True)
        time.sleep(2)
        self.assertIs(cache.has_key("expire1"), True)

        self.assertIs(cache.touch("nonexistent"), False)

    def test_unicode(self):
        # Unicode values can be cached
        """

        Tests the cache functionality with a variety of Unicode keys and values.

        This test case verifies that the cache can store and retrieve values with
        ASCII, Unicode, and nested dictionary keys. It also checks the correctness
        of cache deletion and addition operations. The test covers the following
        scenarios:

        * Setting and getting values with Unicode keys
        * Deleting keys with Unicode names
        * Adding new key-value pairs with Unicode keys
        * Setting multiple keys at once using the set_many method

        The test uses a dictionary with a mix of ASCII and Unicode keys to exercise
        the cache functionality and ensure that it works correctly with different
        types of input data.

        """
        stuff = {
            "ascii": "ascii_value",
            "unicode_ascii": "Iñtërnâtiônàlizætiøn1",
            "Iñtërnâtiônàlizætiøn": "Iñtërnâtiônàlizætiøn2",
            "ascii2": {"x": 1},
        }
        # Test `set`
        for key, value in stuff.items():
            with self.subTest(key=key):
                cache.set(key, value)
                self.assertEqual(cache.get(key), value)

        # Test `add`
        for key, value in stuff.items():
            with self.subTest(key=key):
                self.assertIs(cache.delete(key), True)
                self.assertIs(cache.add(key, value), True)
                self.assertEqual(cache.get(key), value)

        # Test `set_many`
        for key, value in stuff.items():
            self.assertIs(cache.delete(key), True)
        cache.set_many(stuff)
        for key, value in stuff.items():
            with self.subTest(key=key):
                self.assertEqual(cache.get(key), value)

    def test_binary_string(self):
        # Binary strings should be cacheable
        from zlib import compress, decompress

        value = "value_to_be_compressed"
        compressed_value = compress(value.encode())

        # Test set
        cache.set("binary1", compressed_value)
        compressed_result = cache.get("binary1")
        self.assertEqual(compressed_value, compressed_result)
        self.assertEqual(value, decompress(compressed_result).decode())

        # Test add
        self.assertIs(cache.add("binary1-add", compressed_value), True)
        compressed_result = cache.get("binary1-add")
        self.assertEqual(compressed_value, compressed_result)
        self.assertEqual(value, decompress(compressed_result).decode())

        # Test set_many
        cache.set_many({"binary1-set_many": compressed_value})
        compressed_result = cache.get("binary1-set_many")
        self.assertEqual(compressed_value, compressed_result)
        self.assertEqual(value, decompress(compressed_result).decode())

    def test_set_many(self):
        # Multiple keys can be set using set_many
        """

        Tests the set_many method of the cache, which allows setting multiple key-value pairs at once.

        This test verifies that the set_many method successfully stores the provided data
        and that it can be retrieved using the get method.

        The test case includes setting two key-value pairs and then asserting that the
        retrieved values match the expected values.

        """
        cache.set_many({"key1": "spam", "key2": "eggs"})
        self.assertEqual(cache.get("key1"), "spam")
        self.assertEqual(cache.get("key2"), "eggs")

    def test_set_many_returns_empty_list_on_success(self):
        """set_many() returns an empty list when all keys are inserted."""
        failing_keys = cache.set_many({"key1": "spam", "key2": "eggs"})
        self.assertEqual(failing_keys, [])

    def test_set_many_expiration(self):
        # set_many takes a second ``timeout`` parameter
        """
        Tests setting multiple cache entries with an expiration time.

        Verifies that multiple cache entries are correctly stored and then expire after the specified time, resulting in None being returned when attempting to retrieve the expired entries.

        :param none:
        :returns: none
        :raises AssertionError: If either of the cache entries do not expire correctly
        """
        cache.set_many({"key1": "spam", "key2": "eggs"}, 1)
        time.sleep(2)
        self.assertIsNone(cache.get("key1"))
        self.assertIsNone(cache.get("key2"))

    def test_set_many_empty_data(self):
        self.assertEqual(cache.set_many({}), [])

    def test_delete_many(self):
        # Multiple keys can be deleted using delete_many
        """
        Tests the deletion of multiple items from the cache.

        Verifies that the delete_many method correctly removes the specified items from the cache,
        while leaving other items untouched. The test sets multiple items in the cache, deletes a subset
        of them, and then checks that the deleted items are no longer present and the remaining items
        are still accessible with their original values.
        """
        cache.set_many({"key1": "spam", "key2": "eggs", "key3": "ham"})
        cache.delete_many(["key1", "key2"])
        self.assertIsNone(cache.get("key1"))
        self.assertIsNone(cache.get("key2"))
        self.assertEqual(cache.get("key3"), "ham")

    def test_delete_many_no_keys(self):
        self.assertIsNone(cache.delete_many([]))

    def test_clear(self):
        # The cache can be emptied using clear
        """
        Tests the cache's clear functionality.

        Verifies that clearing the cache removes all stored values, making them inaccessible
        for future retrievals. This ensures the cache is properly reset to its original state.
        """
        cache.set_many({"key1": "spam", "key2": "eggs"})
        cache.clear()
        self.assertIsNone(cache.get("key1"))
        self.assertIsNone(cache.get("key2"))

    def test_long_timeout(self):
        """
        Follow memcached's convention where a timeout greater than 30 days is
        treated as an absolute expiration timestamp instead of a relative
        offset (#12399).
        """
        cache.set("key1", "eggs", 60 * 60 * 24 * 30 + 1)  # 30 days + 1 second
        self.assertEqual(cache.get("key1"), "eggs")

        self.assertIs(cache.add("key2", "ham", 60 * 60 * 24 * 30 + 1), True)
        self.assertEqual(cache.get("key2"), "ham")

        cache.set_many(
            {"key3": "sausage", "key4": "lobster bisque"}, 60 * 60 * 24 * 30 + 1
        )
        self.assertEqual(cache.get("key3"), "sausage")
        self.assertEqual(cache.get("key4"), "lobster bisque")

    def test_forever_timeout(self):
        """
        Passing in None into timeout results in a value that is cached forever
        """
        cache.set("key1", "eggs", None)
        self.assertEqual(cache.get("key1"), "eggs")

        self.assertIs(cache.add("key2", "ham", None), True)
        self.assertEqual(cache.get("key2"), "ham")
        self.assertIs(cache.add("key1", "new eggs", None), False)
        self.assertEqual(cache.get("key1"), "eggs")

        cache.set_many({"key3": "sausage", "key4": "lobster bisque"}, None)
        self.assertEqual(cache.get("key3"), "sausage")
        self.assertEqual(cache.get("key4"), "lobster bisque")

        cache.set("key5", "belgian fries", timeout=1)
        self.assertIs(cache.touch("key5", timeout=None), True)
        time.sleep(2)
        self.assertEqual(cache.get("key5"), "belgian fries")

    def test_zero_timeout(self):
        """
        Passing in zero into timeout results in a value that is not cached
        """
        cache.set("key1", "eggs", 0)
        self.assertIsNone(cache.get("key1"))

        self.assertIs(cache.add("key2", "ham", 0), True)
        self.assertIsNone(cache.get("key2"))

        cache.set_many({"key3": "sausage", "key4": "lobster bisque"}, 0)
        self.assertIsNone(cache.get("key3"))
        self.assertIsNone(cache.get("key4"))

        cache.set("key5", "belgian fries", timeout=5)
        self.assertIs(cache.touch("key5", timeout=0), True)
        self.assertIsNone(cache.get("key5"))

    def test_float_timeout(self):
        # Make sure a timeout given as a float doesn't crash anything.
        cache.set("key1", "spam", 100.2)
        self.assertEqual(cache.get("key1"), "spam")

    def _perform_cull_test(self, cull_cache_name, initial_count, final_count):
        """

        Performs a cull test on a cache to verify its behavior.

        This method populates a cache with a specified number of key-value pairs,
        then checks the cache's contents after culling to ensure the expected number of
        items remain. The test skips if the specified cache is not a valid
        backend.

        :param cull_cache_name: The name of the cache to be tested.
        :param initial_count: The initial number of items to populate the cache with.
        :param final_count: The expected number of items remaining in the cache after culling.

        """
        try:
            cull_cache = caches[cull_cache_name]
        except InvalidCacheBackendError:
            self.skipTest("Culling isn't implemented.")

        # Create initial cache key entries. This will overflow the cache,
        # causing a cull.
        for i in range(1, initial_count):
            cull_cache.set("cull%d" % i, "value", 1000)
        count = 0
        # Count how many keys are left in the cache.
        for i in range(1, initial_count):
            if cull_cache.has_key("cull%d" % i):
                count += 1
        self.assertEqual(count, final_count)

    def test_cull(self):
        self._perform_cull_test("cull", 50, 29)

    def test_zero_cull(self):
        self._perform_cull_test("zero_cull", 50, 19)

    def test_cull_delete_when_store_empty(self):
        """

        Tests the cull cache deletion behavior when the cache store is empty.

        This test case ensures that when the cache store is empty and the max entries
        is set to unlimited, adding a new entry to the cache does not trigger a delete
        operation. It verifies that the newly added key is present in the cache.

        """
        try:
            cull_cache = caches["cull"]
        except InvalidCacheBackendError:
            self.skipTest("Culling isn't implemented.")
        old_max_entries = cull_cache._max_entries
        # Force _cull to delete on first cached record.
        cull_cache._max_entries = -1
        try:
            cull_cache.set("force_cull_delete", "value", 1000)
            self.assertIs(cull_cache.has_key("force_cull_delete"), True)
        finally:
            cull_cache._max_entries = old_max_entries

    def _perform_invalid_key_test(self, key, expected_warning, key_func=None):
        """
        All the builtin backends should warn (except memcached that should
        error) on keys that would be refused by memcached. This encourages
        portable caching code without making it too difficult to use production
        backends with more liberal key rules. Refs #6447.
        """

        # mimic custom ``make_key`` method being defined since the default will
        # never show the below warnings
        def func(key, *args):
            return key

        old_func = cache.key_func
        cache.key_func = key_func or func

        tests = [
            ("add", [key, 1]),
            ("get", [key]),
            ("set", [key, 1]),
            ("incr", [key]),
            ("decr", [key]),
            ("touch", [key]),
            ("delete", [key]),
            ("get_many", [[key, "b"]]),
            ("set_many", [{key: 1, "b": 2}]),
            ("delete_many", [[key, "b"]]),
        ]
        try:
            for operation, args in tests:
                with self.subTest(operation=operation):
                    with self.assertWarns(CacheKeyWarning) as cm:
                        getattr(cache, operation)(*args)
                    self.assertEqual(str(cm.warning), expected_warning)
        finally:
            cache.key_func = old_func

    def test_invalid_key_characters(self):
        # memcached doesn't allow whitespace or control characters in keys.
        """
        Tests the handling of invalid key characters, specifically checking that keys containing spaces and non-ASCII characters are correctly identified and reported as errors, with the expected error message including the problematic key.
        """
        key = "key with spaces and 清"
        self._perform_invalid_key_test(key, KEY_ERRORS_WITH_MEMCACHED_MSG % key)

    def test_invalid_key_length(self):
        # memcached limits key length to 250.
        key = ("a" * 250) + "清"
        expected_warning = (
            "Cache key will cause errors if used with memcached: "
            "%r (longer than %s)" % (key, 250)
        )
        self._perform_invalid_key_test(key, expected_warning)

    def test_invalid_with_version_key_length(self):
        # Custom make_key() that adds a version to the key and exceeds the
        # limit.
        """
        Tests the handling of invalid cache keys with lengths close to the maximum allowed by memcached.

        Specifically, this test checks that a warning is raised when a key, after being modified by a provided key function, exceeds the maximum allowed length of 250 characters for memcached compatibility.

        The test generates a key that, when modified, is just beyond this limit and verifies that the expected warning message is produced, ensuring that the system correctly identifies and reports potential issues with cache key lengths.
        """
        def key_func(key, *args):
            return key + ":1"

        key = "a" * 249
        expected_warning = (
            "Cache key will cause errors if used with memcached: "
            "%r (longer than %s)" % (key_func(key), 250)
        )
        self._perform_invalid_key_test(key, expected_warning, key_func=key_func)

    def test_cache_versioning_get_set(self):
        # set, using default version = 1
        cache.set("answer1", 42)
        self.assertEqual(cache.get("answer1"), 42)
        self.assertEqual(cache.get("answer1", version=1), 42)
        self.assertIsNone(cache.get("answer1", version=2))

        self.assertIsNone(caches["v2"].get("answer1"))
        self.assertEqual(caches["v2"].get("answer1", version=1), 42)
        self.assertIsNone(caches["v2"].get("answer1", version=2))

        # set, default version = 1, but manually override version = 2
        cache.set("answer2", 42, version=2)
        self.assertIsNone(cache.get("answer2"))
        self.assertIsNone(cache.get("answer2", version=1))
        self.assertEqual(cache.get("answer2", version=2), 42)

        self.assertEqual(caches["v2"].get("answer2"), 42)
        self.assertIsNone(caches["v2"].get("answer2", version=1))
        self.assertEqual(caches["v2"].get("answer2", version=2), 42)

        # v2 set, using default version = 2
        caches["v2"].set("answer3", 42)
        self.assertIsNone(cache.get("answer3"))
        self.assertIsNone(cache.get("answer3", version=1))
        self.assertEqual(cache.get("answer3", version=2), 42)

        self.assertEqual(caches["v2"].get("answer3"), 42)
        self.assertIsNone(caches["v2"].get("answer3", version=1))
        self.assertEqual(caches["v2"].get("answer3", version=2), 42)

        # v2 set, default version = 2, but manually override version = 1
        caches["v2"].set("answer4", 42, version=1)
        self.assertEqual(cache.get("answer4"), 42)
        self.assertEqual(cache.get("answer4", version=1), 42)
        self.assertIsNone(cache.get("answer4", version=2))

        self.assertIsNone(caches["v2"].get("answer4"))
        self.assertEqual(caches["v2"].get("answer4", version=1), 42)
        self.assertIsNone(caches["v2"].get("answer4", version=2))

    def test_cache_versioning_add(self):
        # add, default version = 1, but manually override version = 2
        self.assertIs(cache.add("answer1", 42, version=2), True)
        self.assertIsNone(cache.get("answer1", version=1))
        self.assertEqual(cache.get("answer1", version=2), 42)

        self.assertIs(cache.add("answer1", 37, version=2), False)
        self.assertIsNone(cache.get("answer1", version=1))
        self.assertEqual(cache.get("answer1", version=2), 42)

        self.assertIs(cache.add("answer1", 37, version=1), True)
        self.assertEqual(cache.get("answer1", version=1), 37)
        self.assertEqual(cache.get("answer1", version=2), 42)

        # v2 add, using default version = 2
        self.assertIs(caches["v2"].add("answer2", 42), True)
        self.assertIsNone(cache.get("answer2", version=1))
        self.assertEqual(cache.get("answer2", version=2), 42)

        self.assertIs(caches["v2"].add("answer2", 37), False)
        self.assertIsNone(cache.get("answer2", version=1))
        self.assertEqual(cache.get("answer2", version=2), 42)

        self.assertIs(caches["v2"].add("answer2", 37, version=1), True)
        self.assertEqual(cache.get("answer2", version=1), 37)
        self.assertEqual(cache.get("answer2", version=2), 42)

        # v2 add, default version = 2, but manually override version = 1
        self.assertIs(caches["v2"].add("answer3", 42, version=1), True)
        self.assertEqual(cache.get("answer3", version=1), 42)
        self.assertIsNone(cache.get("answer3", version=2))

        self.assertIs(caches["v2"].add("answer3", 37, version=1), False)
        self.assertEqual(cache.get("answer3", version=1), 42)
        self.assertIsNone(cache.get("answer3", version=2))

        self.assertIs(caches["v2"].add("answer3", 37), True)
        self.assertEqual(cache.get("answer3", version=1), 42)
        self.assertEqual(cache.get("answer3", version=2), 37)

    def test_cache_versioning_has_key(self):
        """

        Tests the functionality of cache versioning with respect to key existence.

        Checks that a key is correctly reported as present or absent in the cache
        across different versions. This includes verifying that a key is visible
        in its version of origin and not in other versions where it has not been set.

        """
        cache.set("answer1", 42)

        # has_key
        self.assertIs(cache.has_key("answer1"), True)
        self.assertIs(cache.has_key("answer1", version=1), True)
        self.assertIs(cache.has_key("answer1", version=2), False)

        self.assertIs(caches["v2"].has_key("answer1"), False)
        self.assertIs(caches["v2"].has_key("answer1", version=1), True)
        self.assertIs(caches["v2"].has_key("answer1", version=2), False)

    def test_cache_versioning_delete(self):
        """

        Test cache versioning delete functionality.

        This test case verifies the correct behavior of the delete operation in a cache
        with versioning enabled. It checks that deleting a key removes the associated
        value from the cache, while leaving other versions of the key intact. The test
        also ensures that deleting a specific version of a key only removes that version,
        leaving other versions unchanged.

        The test covers various scenarios, including:

        * Deleting a key without specifying a version, which removes all versions of the key
        * Deleting a specific version of a key, which leaves other versions intact
        * Deleting a key using a specific cache instance, which only affects that instance

        By verifying the behavior of the delete operation in these different scenarios,
        this test ensures that the cache versioning system is working correctly.

        """
        cache.set("answer1", 37, version=1)
        cache.set("answer1", 42, version=2)
        self.assertIs(cache.delete("answer1"), True)
        self.assertIsNone(cache.get("answer1", version=1))
        self.assertEqual(cache.get("answer1", version=2), 42)

        cache.set("answer2", 37, version=1)
        cache.set("answer2", 42, version=2)
        self.assertIs(cache.delete("answer2", version=2), True)
        self.assertEqual(cache.get("answer2", version=1), 37)
        self.assertIsNone(cache.get("answer2", version=2))

        cache.set("answer3", 37, version=1)
        cache.set("answer3", 42, version=2)
        self.assertIs(caches["v2"].delete("answer3"), True)
        self.assertEqual(cache.get("answer3", version=1), 37)
        self.assertIsNone(cache.get("answer3", version=2))

        cache.set("answer4", 37, version=1)
        cache.set("answer4", 42, version=2)
        self.assertIs(caches["v2"].delete("answer4", version=1), True)
        self.assertIsNone(cache.get("answer4", version=1))
        self.assertEqual(cache.get("answer4", version=2), 42)

    def test_cache_versioning_incr_decr(self):
        cache.set("answer1", 37, version=1)
        cache.set("answer1", 42, version=2)
        self.assertEqual(cache.incr("answer1"), 38)
        self.assertEqual(cache.get("answer1", version=1), 38)
        self.assertEqual(cache.get("answer1", version=2), 42)
        self.assertEqual(cache.decr("answer1"), 37)
        self.assertEqual(cache.get("answer1", version=1), 37)
        self.assertEqual(cache.get("answer1", version=2), 42)

        cache.set("answer2", 37, version=1)
        cache.set("answer2", 42, version=2)
        self.assertEqual(cache.incr("answer2", version=2), 43)
        self.assertEqual(cache.get("answer2", version=1), 37)
        self.assertEqual(cache.get("answer2", version=2), 43)
        self.assertEqual(cache.decr("answer2", version=2), 42)
        self.assertEqual(cache.get("answer2", version=1), 37)
        self.assertEqual(cache.get("answer2", version=2), 42)

        cache.set("answer3", 37, version=1)
        cache.set("answer3", 42, version=2)
        self.assertEqual(caches["v2"].incr("answer3"), 43)
        self.assertEqual(cache.get("answer3", version=1), 37)
        self.assertEqual(cache.get("answer3", version=2), 43)
        self.assertEqual(caches["v2"].decr("answer3"), 42)
        self.assertEqual(cache.get("answer3", version=1), 37)
        self.assertEqual(cache.get("answer3", version=2), 42)

        cache.set("answer4", 37, version=1)
        cache.set("answer4", 42, version=2)
        self.assertEqual(caches["v2"].incr("answer4", version=1), 38)
        self.assertEqual(cache.get("answer4", version=1), 38)
        self.assertEqual(cache.get("answer4", version=2), 42)
        self.assertEqual(caches["v2"].decr("answer4", version=1), 37)
        self.assertEqual(cache.get("answer4", version=1), 37)
        self.assertEqual(cache.get("answer4", version=2), 42)

    def test_cache_versioning_get_set_many(self):
        # set, using default version = 1
        """
        Test cache versioning functionality by exercising the set_many and get_many operations with different versions.

        The test covers the behavior of set_many and get_many operations across different versions of the cache, 
        including setting and retrieving cache values with the default version, setting and retrieving cache values 
        with a specific version, and verifying that cache values are not visible across different versions unless 
        explicitly specified. It also checks the behavior when using multiple caches and versions.
        """
        cache.set_many({"ford1": 37, "arthur1": 42})
        self.assertEqual(
            cache.get_many(["ford1", "arthur1"]), {"ford1": 37, "arthur1": 42}
        )
        self.assertEqual(
            cache.get_many(["ford1", "arthur1"], version=1),
            {"ford1": 37, "arthur1": 42},
        )
        self.assertEqual(cache.get_many(["ford1", "arthur1"], version=2), {})

        self.assertEqual(caches["v2"].get_many(["ford1", "arthur1"]), {})
        self.assertEqual(
            caches["v2"].get_many(["ford1", "arthur1"], version=1),
            {"ford1": 37, "arthur1": 42},
        )
        self.assertEqual(caches["v2"].get_many(["ford1", "arthur1"], version=2), {})

        # set, default version = 1, but manually override version = 2
        cache.set_many({"ford2": 37, "arthur2": 42}, version=2)
        self.assertEqual(cache.get_many(["ford2", "arthur2"]), {})
        self.assertEqual(cache.get_many(["ford2", "arthur2"], version=1), {})
        self.assertEqual(
            cache.get_many(["ford2", "arthur2"], version=2),
            {"ford2": 37, "arthur2": 42},
        )

        self.assertEqual(
            caches["v2"].get_many(["ford2", "arthur2"]), {"ford2": 37, "arthur2": 42}
        )
        self.assertEqual(caches["v2"].get_many(["ford2", "arthur2"], version=1), {})
        self.assertEqual(
            caches["v2"].get_many(["ford2", "arthur2"], version=2),
            {"ford2": 37, "arthur2": 42},
        )

        # v2 set, using default version = 2
        caches["v2"].set_many({"ford3": 37, "arthur3": 42})
        self.assertEqual(cache.get_many(["ford3", "arthur3"]), {})
        self.assertEqual(cache.get_many(["ford3", "arthur3"], version=1), {})
        self.assertEqual(
            cache.get_many(["ford3", "arthur3"], version=2),
            {"ford3": 37, "arthur3": 42},
        )

        self.assertEqual(
            caches["v2"].get_many(["ford3", "arthur3"]), {"ford3": 37, "arthur3": 42}
        )
        self.assertEqual(caches["v2"].get_many(["ford3", "arthur3"], version=1), {})
        self.assertEqual(
            caches["v2"].get_many(["ford3", "arthur3"], version=2),
            {"ford3": 37, "arthur3": 42},
        )

        # v2 set, default version = 2, but manually override version = 1
        caches["v2"].set_many({"ford4": 37, "arthur4": 42}, version=1)
        self.assertEqual(
            cache.get_many(["ford4", "arthur4"]), {"ford4": 37, "arthur4": 42}
        )
        self.assertEqual(
            cache.get_many(["ford4", "arthur4"], version=1),
            {"ford4": 37, "arthur4": 42},
        )
        self.assertEqual(cache.get_many(["ford4", "arthur4"], version=2), {})

        self.assertEqual(caches["v2"].get_many(["ford4", "arthur4"]), {})
        self.assertEqual(
            caches["v2"].get_many(["ford4", "arthur4"], version=1),
            {"ford4": 37, "arthur4": 42},
        )
        self.assertEqual(caches["v2"].get_many(["ford4", "arthur4"], version=2), {})

    def test_incr_version(self):
        """
        Increments the version of a cache entry.

        Tests the functionality of incrementing the version of a cache entry, including
        retrieving values from different versions, handling non-existent keys, and
        checking the behavior of incrementing the version when the cache entry contains
        a null value.

        The version increment operation ensures that the value associated with the key
        is accessible only through the incremented version, effectively archiving the
        previous version.

        This test case covers various scenarios, including:
        - Versioning behavior when setting and retrieving cache entries.
        - Incrementing the version of an existing cache entry.
        - Handling attempts to increment the version of a non-existent cache entry.
        - Correct version handling for cache entries with null values.

        Note that this test is designed to validate the correctness of the cache version
        management functionality, ensuring that it behaves as expected in different
        scenarios.
        """
        cache.set("answer", 42, version=2)
        self.assertIsNone(cache.get("answer"))
        self.assertIsNone(cache.get("answer", version=1))
        self.assertEqual(cache.get("answer", version=2), 42)
        self.assertIsNone(cache.get("answer", version=3))

        self.assertEqual(cache.incr_version("answer", version=2), 3)
        self.assertIsNone(cache.get("answer"))
        self.assertIsNone(cache.get("answer", version=1))
        self.assertIsNone(cache.get("answer", version=2))
        self.assertEqual(cache.get("answer", version=3), 42)

        caches["v2"].set("answer2", 42)
        self.assertEqual(caches["v2"].get("answer2"), 42)
        self.assertIsNone(caches["v2"].get("answer2", version=1))
        self.assertEqual(caches["v2"].get("answer2", version=2), 42)
        self.assertIsNone(caches["v2"].get("answer2", version=3))

        self.assertEqual(caches["v2"].incr_version("answer2"), 3)
        self.assertIsNone(caches["v2"].get("answer2"))
        self.assertIsNone(caches["v2"].get("answer2", version=1))
        self.assertIsNone(caches["v2"].get("answer2", version=2))
        self.assertEqual(caches["v2"].get("answer2", version=3), 42)

        with self.assertRaises(ValueError):
            cache.incr_version("does_not_exist")

        cache.set("null", None)
        self.assertEqual(cache.incr_version("null"), 2)

    def test_decr_version(self):
        cache.set("answer", 42, version=2)
        self.assertIsNone(cache.get("answer"))
        self.assertIsNone(cache.get("answer", version=1))
        self.assertEqual(cache.get("answer", version=2), 42)

        self.assertEqual(cache.decr_version("answer", version=2), 1)
        self.assertEqual(cache.get("answer"), 42)
        self.assertEqual(cache.get("answer", version=1), 42)
        self.assertIsNone(cache.get("answer", version=2))

        caches["v2"].set("answer2", 42)
        self.assertEqual(caches["v2"].get("answer2"), 42)
        self.assertIsNone(caches["v2"].get("answer2", version=1))
        self.assertEqual(caches["v2"].get("answer2", version=2), 42)

        self.assertEqual(caches["v2"].decr_version("answer2"), 1)
        self.assertIsNone(caches["v2"].get("answer2"))
        self.assertEqual(caches["v2"].get("answer2", version=1), 42)
        self.assertIsNone(caches["v2"].get("answer2", version=2))

        with self.assertRaises(ValueError):
            cache.decr_version("does_not_exist", version=2)

        cache.set("null", None, version=2)
        self.assertEqual(cache.decr_version("null", version=2), 1)

    def test_custom_key_func(self):
        # Two caches with different key functions aren't visible to each other
        """
        Tests the functionality of custom key functions in cache storage.

        This test case verifies that values stored with a custom key are correctly retrieved 
        from their respective cache storage and not from the main cache or other custom key caches.
        It also ensures that values stored without a custom key are not accessible from custom key caches.
        """
        cache.set("answer1", 42)
        self.assertEqual(cache.get("answer1"), 42)
        self.assertIsNone(caches["custom_key"].get("answer1"))
        self.assertIsNone(caches["custom_key2"].get("answer1"))

        caches["custom_key"].set("answer2", 42)
        self.assertIsNone(cache.get("answer2"))
        self.assertEqual(caches["custom_key"].get("answer2"), 42)
        self.assertEqual(caches["custom_key2"].get("answer2"), 42)

    @override_settings(CACHE_MIDDLEWARE_ALIAS=DEFAULT_CACHE_ALIAS)
    def test_cache_write_unpicklable_object(self):
        """

        Tests writing an unpicklable object to the cache.

        This test case covers the scenario where an object that cannot be pickled, 
        such as an HttpResponse object with a cookie, is being written to the cache.

        It verifies that the cache is updated correctly after setting an unpicklable 
        object, specifically a response with a cookie, and that the cached data 
        is retrieved successfully with the correct content and cookies.

        The test also checks that updates to the cache are persisted across multiple 
        requests, ensuring that the cache remains consistent.

        """
        fetch_middleware = FetchFromCacheMiddleware(empty_response)

        request = self.factory.get("/cache/test")
        request._cache_update_cache = True
        get_cache_data = FetchFromCacheMiddleware(empty_response).process_request(
            request
        )
        self.assertIsNone(get_cache_data)

        content = "Testing cookie serialization."

        def get_response(req):
            """

            Returns an HTTP response object with a set cookie.

            This function generates an HTTP response and adds a 'foo' cookie with value 'bar' to it.
            The response can then be used to handle an incoming HTTP request.

            The returned response object includes the headers and cookies necessary to handle the request.
            The 'foo' cookie will be included in the response headers and will be stored on the client's browser.

            :param req: The incoming HTTP request.
            :rtype: HttpResponse

            """
            response = HttpResponse(content)
            response.set_cookie("foo", "bar")
            return response

        update_middleware = UpdateCacheMiddleware(get_response)
        response = update_middleware(request)

        get_cache_data = fetch_middleware.process_request(request)
        self.assertIsNotNone(get_cache_data)
        self.assertEqual(get_cache_data.content, content.encode())
        self.assertEqual(get_cache_data.cookies, response.cookies)

        UpdateCacheMiddleware(lambda req: get_cache_data)(request)
        get_cache_data = fetch_middleware.process_request(request)
        self.assertIsNotNone(get_cache_data)
        self.assertEqual(get_cache_data.content, content.encode())
        self.assertEqual(get_cache_data.cookies, response.cookies)

    def test_add_fail_on_pickleerror(self):
        # Shouldn't fail silently if trying to cache an unpicklable type.
        with self.assertRaises(pickle.PickleError):
            cache.add("unpicklable", Unpicklable())

    def test_set_fail_on_pickleerror(self):
        """
        Tests the behavior of the cache's set method when attempting to store an object that cannot be pickled. 
         Verifies that a PickleError is raised when trying to cache an unpicklable object.
        """
        with self.assertRaises(pickle.PickleError):
            cache.set("unpicklable", Unpicklable())

    def test_get_or_set(self):
        """

        Tests the get_or_set functionality of the cache.

        This function verifies that the cache correctly retrieves and sets values.
        It checks that a non-existent key returns None, that setting a key with a value 
        returns the value, and that subsequent gets for the same key return the value.
        Additionally, it checks that setting a key to None results in None being returned, 
        and that a default value can be provided for a key that returns None.

        """
        self.assertIsNone(cache.get("projector"))
        self.assertEqual(cache.get_or_set("projector", 42), 42)
        self.assertEqual(cache.get("projector"), 42)
        self.assertIsNone(cache.get_or_set("null", None))
        # Previous get_or_set() stores None in the cache.
        self.assertIsNone(cache.get("null", "default"))

    def test_get_or_set_callable(self):
        def my_callable():
            return "value"

        self.assertEqual(cache.get_or_set("mykey", my_callable), "value")
        self.assertEqual(cache.get_or_set("mykey", my_callable()), "value")

        self.assertIsNone(cache.get_or_set("null", lambda: None))
        # Previous get_or_set() stores None in the cache.
        self.assertIsNone(cache.get("null", "default"))

    def test_get_or_set_version(self):
        """
        Tests the get_or_set functionality of the cache.

        This function verifies the correctness of the cache's get_or_set method. 
        It checks that the method can successfully retrieve or set a value for a given key, 
        raises a TypeError if the required 'default' argument is missing, 
        and handles different versions of the cache. 

        It also tests the behavior when the key has no value in the cache for a specific version, 
        and when the key has a value in the cache for a different version. 

        The test covers various scenarios, including setting a value, 
        getting a value, and attempting to get or set a value without providing the required arguments.
        """
        msg = "get_or_set() missing 1 required positional argument: 'default'"
        self.assertEqual(cache.get_or_set("brian", 1979, version=2), 1979)
        with self.assertRaisesMessage(TypeError, msg):
            cache.get_or_set("brian")
        with self.assertRaisesMessage(TypeError, msg):
            cache.get_or_set("brian", version=1)
        self.assertIsNone(cache.get("brian", version=1))
        self.assertEqual(cache.get_or_set("brian", 42, version=1), 42)
        self.assertEqual(cache.get_or_set("brian", 1979, version=2), 1979)
        self.assertIsNone(cache.get("brian", version=3))

    def test_get_or_set_racing(self):
        """

        Tests the get_or_set functionality of the cache system.

        This test case verifies that if the cache does not have a value associated with a given key,
        it sets the value to a specified default and returns that default value.

        It also confirms that this behavior is correctly simulated when the cache's add functionality
        is mocked to return an unsuccessful attempt (False) to add the value to the cache.

        """
        with mock.patch(
            "%s.%s" % (settings.CACHES["default"]["BACKEND"], "add")
        ) as cache_add:
            # Simulate cache.add() failing to add a value. In that case, the
            # default value should be returned.
            cache_add.return_value = False
            self.assertEqual(cache.get_or_set("key", "default"), "default")


@override_settings(
    CACHES=caches_setting_for_tests(
        BACKEND="django.core.cache.backends.db.DatabaseCache",
        # Spaces are used in the table name to ensure quoting/escaping is working
        LOCATION="test cache table",
    )
)
class DBCacheTests(BaseCacheTests, TransactionTestCase):
    available_apps = ["cache"]

    def setUp(self):
        # The super calls needs to happen first for the settings override.
        """
        Sets up the environment for testing by creating a table and scheduling its removal after the test is completed.

        This method initializes the test setup by creating the necessary database table
        and ensures that it is properly cleaned up after the test has finished, regardless
        of its outcome, to maintain a consistent test environment.
        """
        super().setUp()
        self.create_table()
        self.addCleanup(self.drop_table)

    def create_table(self):
        management.call_command("createcachetable", verbosity=0)

    def drop_table(self):
        """

        Drops the 'test cache table' from the database.

        This function executes a SQL query to permanently delete the specified table and its contents. 
        It provides a convenient way to remove the table when it is no longer needed, 
        such as during database maintenance or testing.

        Note:
            This function does not check if the table exists before attempting to drop it. 
            It assumes that the table has already been created and may raise an error if it does not.

        """
        with connection.cursor() as cursor:
            table_name = connection.ops.quote_name("test cache table")
            cursor.execute("DROP TABLE %s" % table_name)

    def test_get_many_num_queries(self):
        cache.set_many({"a": 1, "b": 2})
        cache.set("expired", "expired", 0.01)
        with self.assertNumQueries(1):
            self.assertEqual(cache.get_many(["a", "b"]), {"a": 1, "b": 2})
        time.sleep(0.02)
        with self.assertNumQueries(2):
            self.assertEqual(cache.get_many(["a", "b", "expired"]), {"a": 1, "b": 2})

    def test_delete_many_num_queries(self):
        """

        Tests the delete_many function to ensure it can delete multiple cache entries in a single database query.

        This test verifies that deleting multiple cache keys via the delete_many function results in a single database query being executed.

        :param None:
        :raises AssertionError: If the delete_many function does not execute in a single database query.
        :return: None

        """
        cache.set_many({"a": 1, "b": 2, "c": 3})
        with self.assertNumQueries(1):
            cache.delete_many(["a", "b", "c"])

    def test_cull_queries(self):
        old_max_entries = cache._max_entries
        # Force _cull to delete on first cached record.
        cache._max_entries = -1
        with CaptureQueriesContext(connection) as captured_queries:
            try:
                cache.set("force_cull", "value", 1000)
            finally:
                cache._max_entries = old_max_entries
        num_count_queries = sum("COUNT" in query["sql"] for query in captured_queries)
        self.assertEqual(num_count_queries, 1)
        # Column names are quoted.
        for query in captured_queries:
            sql = query["sql"]
            if "expires" in sql:
                self.assertIn(connection.ops.quote_name("expires"), sql)
            if "cache_key" in sql:
                self.assertIn(connection.ops.quote_name("cache_key"), sql)

    def test_delete_cursor_rowcount(self):
        """
        The rowcount attribute should not be checked on a closed cursor.
        """

        class MockedCursorWrapper(CursorWrapper):
            is_closed = False

            def close(self):
                """

                Closes the current database connection.

                This method releases any system resources associated with the connection, 
                such as file descriptors or network sockets. Once closed, the connection 
                cannot be used to execute further queries.

                After calling this method, the connection is marked as closed to prevent 
                accidental re-use.

                """
                self.cursor.close()
                self.is_closed = True

            @property
            def rowcount(self):
                if self.is_closed:
                    raise Exception("Cursor is closed.")
                return self.cursor.rowcount

        cache.set_many({"a": 1, "b": 2})
        with mock.patch("django.db.backends.utils.CursorWrapper", MockedCursorWrapper):
            self.assertIs(cache.delete("a"), True)

    def test_zero_cull(self):
        self._perform_cull_test("zero_cull", 50, 18)

    def test_second_call_doesnt_crash(self):
        """
        Tests that running the 'createcachetable' management command multiple times does not result in a crash, and instead handles the case where the cache table already exists. The command is expected to log a message for each cache setup in the project settings, indicating that the cache table has been created or already exists. The test verifies that the correct output is generated when the command is run a second time.
        """
        out = io.StringIO()
        management.call_command("createcachetable", stdout=out)
        self.assertEqual(
            out.getvalue(),
            "Cache table 'test cache table' already exists.\n" * len(settings.CACHES),
        )

    @override_settings(
        CACHES=caches_setting_for_tests(
            BACKEND="django.core.cache.backends.db.DatabaseCache",
            # Use another table name to avoid the 'table already exists' message.
            LOCATION="createcachetable_dry_run_mode",
        )
    )
    def test_createcachetable_dry_run_mode(self):
        out = io.StringIO()
        management.call_command("createcachetable", dry_run=True, stdout=out)
        output = out.getvalue()
        self.assertTrue(output.startswith("CREATE TABLE"))

    def test_createcachetable_with_table_argument(self):
        """
        Delete and recreate cache table with legacy behavior (explicitly
        specifying the table name).
        """
        self.drop_table()
        out = io.StringIO()
        management.call_command(
            "createcachetable",
            "test cache table",
            verbosity=2,
            stdout=out,
        )
        self.assertEqual(out.getvalue(), "Cache table 'test cache table' created.\n")

    def test_has_key_query_columns_quoted(self):
        """
        Tests that the has_key query for the cache properly quotes the column names in the generated SQL.

        This test case ensures that when checking for the presence of a key in the cache, the corresponding database query correctly escapes the column names to prevent potential SQL injection vulnerabilities and to ensure compatibility with different database systems.

        The test verifies that the query executed contains the quoted names of the 'expires' and 'cache_key' columns, and that only a single query is executed.
        """
        with CaptureQueriesContext(connection) as captured_queries:
            cache.has_key("key")
        self.assertEqual(len(captured_queries), 1)
        sql = captured_queries[0]["sql"]
        # Column names are quoted.
        self.assertIn(connection.ops.quote_name("expires"), sql)
        self.assertIn(connection.ops.quote_name("cache_key"), sql)


@override_settings(USE_TZ=True)
class DBCacheWithTimeZoneTests(DBCacheTests):
    pass


class DBCacheRouter:
    """A router that puts the cache table on the 'other' database."""

    def db_for_read(self, model, **hints):
        """

        Returns the database to use for read operations for the given model.

        This method allows the model instance to specify a particular database for read
        operations. If the model is part of the 'django_cache' app, it returns the
        'other' database. Otherwise, it returns None, indicating that the default
        database should be used.

        :param model: The model instance for which the database should be determined
        :param hints: Additional hints for database selection
        :returns: The name of the database to use for read operations, or None for default

        """
        if model._meta.app_label == "django_cache":
            return "other"
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == "django_cache":
            return "other"
        return None

    def allow_migrate(self, db, app_label, **hints):
        if app_label == "django_cache":
            return db == "other"
        return None


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "my_cache_table",
        },
    },
)
class CreateCacheTableForDBCacheTests(TestCase):
    databases = {"default", "other"}

    @override_settings(DATABASE_ROUTERS=[DBCacheRouter()])
    def test_createcachetable_observes_database_router(self):
        # cache table should not be created on 'default'
        """

        Tests the creation of cache tables while observing the database router.

        This test case verifies that the 'createcachetable' management command behaves correctly 
        when using a database router. It checks that no queries are executed on the 'default' database 
        and a specific number of queries are executed on the 'other' database, depending on its capabilities.

        """
        with self.assertNumQueries(0, using="default"):
            management.call_command("createcachetable", database="default", verbosity=0)
        # cache table should be created on 'other'
        # Queries:
        #   1: check table doesn't already exist
        #   2: create savepoint (if transactional DDL is supported)
        #   3: create the table
        #   4: create the index
        #   5: release savepoint (if transactional DDL is supported)
        num = 5 if connections["other"].features.can_rollback_ddl else 3
        with self.assertNumQueries(num, using="other"):
            management.call_command("createcachetable", database="other", verbosity=0)


class PicklingSideEffect:
    def __init__(self, cache):
        """
        Initializes an instance of the class, setting up the caching mechanism.

        :param cache: The cache object to be used for storing and retrieving data.
        :note: The lock status is initially set to False, indicating that the cache is unlocked and available for use.
        """
        self.cache = cache
        self.locked = False

    def __getstate__(self):
        """
        Returns the state of the object as a dictionary for pickling purposes.

        This method is used by the Python pickling mechanism to serialize the object's state. It currently captures the locked state of the cache's lock and returns an empty dictionary, effectively ignoring any other attributes of the object during serialization.
        """
        self.locked = self.cache._lock.locked()
        return {}


limit_locmem_entries = override_settings(
    CACHES=caches_setting_for_tests(
        BACKEND="django.core.cache.backends.locmem.LocMemCache",
        OPTIONS={"MAX_ENTRIES": 9},
    )
)


@override_settings(
    CACHES=caches_setting_for_tests(
        BACKEND="django.core.cache.backends.locmem.LocMemCache",
    )
)
class LocMemCacheTests(BaseCacheTests, TestCase):
    def setUp(self):
        """
        Sets up the test environment by synchronizing cache data with a prefix, v2 and custom keys.

        This method is used to ensure that the caches are properly initialized before running tests.
        It updates the cache and expiration information for multiple cache keys, including 'prefix', 'v2', 'custom_key', and 'custom_key2',
        to match the data in the main cache. This allows for consistent testing across different cache configurations. 
        """
        super().setUp()

        # LocMem requires a hack to make the other caches
        # share a data store with the 'normal' cache.
        caches["prefix"]._cache = cache._cache
        caches["prefix"]._expire_info = cache._expire_info

        caches["v2"]._cache = cache._cache
        caches["v2"]._expire_info = cache._expire_info

        caches["custom_key"]._cache = cache._cache
        caches["custom_key"]._expire_info = cache._expire_info

        caches["custom_key2"]._cache = cache._cache
        caches["custom_key2"]._expire_info = cache._expire_info

    @override_settings(
        CACHES={
            "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
            "other": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "other",
            },
        }
    )
    def test_multiple_caches(self):
        "Multiple locmem caches are isolated"
        cache.set("value", 42)
        self.assertEqual(caches["default"].get("value"), 42)
        self.assertIsNone(caches["other"].get("value"))

    def test_locking_on_pickle(self):
        """#20613/#18541 -- Ensures pickling is done outside of the lock."""
        bad_obj = PicklingSideEffect(cache)
        cache.set("set", bad_obj)
        self.assertFalse(bad_obj.locked, "Cache was locked during pickling")

        self.assertIs(cache.add("add", bad_obj), True)
        self.assertFalse(bad_obj.locked, "Cache was locked during pickling")

    def test_incr_decr_timeout(self):
        """incr/decr does not modify expiry time (matches memcached behavior)"""
        key = "value"
        _key = cache.make_key(key)
        cache.set(key, 1, timeout=cache.default_timeout * 10)
        expire = cache._expire_info[_key]
        self.assertEqual(cache.incr(key), 2)
        self.assertEqual(expire, cache._expire_info[_key])
        self.assertEqual(cache.decr(key), 1)
        self.assertEqual(expire, cache._expire_info[_key])

    @limit_locmem_entries
    def test_lru_get(self):
        """get() moves cache keys."""
        for key in range(9):
            cache.set(key, key, timeout=None)
        for key in range(6):
            self.assertEqual(cache.get(key), key)
        cache.set(9, 9, timeout=None)
        for key in range(6):
            self.assertEqual(cache.get(key), key)
        for key in range(6, 9):
            self.assertIsNone(cache.get(key))
        self.assertEqual(cache.get(9), 9)

    @limit_locmem_entries
    def test_lru_set(self):
        """set() moves cache keys."""
        for key in range(9):
            cache.set(key, key, timeout=None)
        for key in range(3, 9):
            cache.set(key, key, timeout=None)
        cache.set(9, 9, timeout=None)
        for key in range(3, 10):
            self.assertEqual(cache.get(key), key)
        for key in range(3):
            self.assertIsNone(cache.get(key))

    @limit_locmem_entries
    def test_lru_incr(self):
        """incr() moves cache keys."""
        for key in range(9):
            cache.set(key, key, timeout=None)
        for key in range(6):
            self.assertEqual(cache.incr(key), key + 1)
        cache.set(9, 9, timeout=None)
        for key in range(6):
            self.assertEqual(cache.get(key), key + 1)
        for key in range(6, 9):
            self.assertIsNone(cache.get(key))
        self.assertEqual(cache.get(9), 9)


# memcached and redis backends aren't guaranteed to be available.
# To check the backends, the test settings file will need to contain at least
# one cache backend setting that points at your cache server.
configured_caches = {}
for _cache_params in settings.CACHES.values():
    configured_caches[_cache_params["BACKEND"]] = _cache_params

PyLibMCCache_params = configured_caches.get(
    "django.core.cache.backends.memcached.PyLibMCCache"
)
PyMemcacheCache_params = configured_caches.get(
    "django.core.cache.backends.memcached.PyMemcacheCache"
)

# The memcached backends don't support cull-related options like `MAX_ENTRIES`.
memcached_excluded_caches = {"cull", "zero_cull"}

RedisCache_params = configured_caches.get("django.core.cache.backends.redis.RedisCache")

# The redis backend does not support cull-related options like `MAX_ENTRIES`.
redis_excluded_caches = {"cull", "zero_cull"}


class BaseMemcachedTests(BaseCacheTests):
    # By default it's assumed that the client doesn't clean up connections
    # properly, in which case the backend must do so after each request.
    should_disconnect_on_close = True

    def test_location_multiple_servers(self):
        locations = [
            ["server1.tld", "server2:11211"],
            "server1.tld;server2:11211",
            "server1.tld,server2:11211",
        ]
        for location in locations:
            with self.subTest(location=location):
                params = {"BACKEND": self.base_params["BACKEND"], "LOCATION": location}
                with self.settings(CACHES={"default": params}):
                    self.assertEqual(cache._servers, ["server1.tld", "server2:11211"])

    def _perform_invalid_key_test(self, key, expected_warning):
        """
        While other backends merely warn, memcached should raise for an invalid
        key.
        """
        msg = expected_warning.replace(key, cache.make_key(key))
        tests = [
            ("add", [key, 1]),
            ("get", [key]),
            ("set", [key, 1]),
            ("incr", [key]),
            ("decr", [key]),
            ("touch", [key]),
            ("delete", [key]),
            ("get_many", [[key, "b"]]),
            ("set_many", [{key: 1, "b": 2}]),
            ("delete_many", [[key, "b"]]),
        ]
        for operation, args in tests:
            with self.subTest(operation=operation):
                with self.assertRaises(InvalidCacheKey) as cm:
                    getattr(cache, operation)(*args)
                self.assertEqual(str(cm.exception), msg)

    def test_invalid_with_version_key_length(self):
        # make_key() adds a version to the key and exceeds the limit.
        """
        @brief Tests that a cache key with a version and a length of 248 characters raises the expected warning.

        This test case verifies the handling of cache keys that exceed the recommended length when used with memcached, specifically when a version is included in the key. It checks if the correct warning message is triggered when such a long key is used, helping ensure that potential issues with memcached compatibility are identified and addressed.
        """
        key = "a" * 248
        expected_warning = (
            "Cache key will cause errors if used with memcached: "
            "%r (longer than %s)" % (key, 250)
        )
        self._perform_invalid_key_test(key, expected_warning)

    def test_default_never_expiring_timeout(self):
        # Regression test for #22845
        with self.settings(
            CACHES=caches_setting_for_tests(
                base=self.base_params, exclude=memcached_excluded_caches, TIMEOUT=None
            )
        ):
            cache.set("infinite_foo", "bar")
            self.assertEqual(cache.get("infinite_foo"), "bar")

    def test_default_far_future_timeout(self):
        # Regression test for #22845
        """
        Tests the cache functionality with a far future timeout setting.

        This test verifies that items can be successfully stored and retrieved from the cache
        when the timeout is set to a very large value, simulating a \"far future\" expiration date.
        The test configuration uses a custom cache setting with the specified timeout and
        excludes certain caches, ensuring a consistent environment for the test.
        The test checks if a cache key-value pair is correctly set and retrieved with the
        given settings, confirming the cache's behavior under these conditions.
        """
        with self.settings(
            CACHES=caches_setting_for_tests(
                base=self.base_params,
                exclude=memcached_excluded_caches,
                # 60*60*24*365, 1 year
                TIMEOUT=31536000,
            )
        ):
            cache.set("future_foo", "bar")
            self.assertEqual(cache.get("future_foo"), "bar")

    def test_memcached_deletes_key_on_failed_set(self):
        # By default memcached allows objects up to 1MB. For the cache_db session
        # backend to always use the current session, memcached needs to delete
        # the old key if it fails to set.
        """
        Tests that memcached correctly deletes a key when a set operation fails due to the value exceeding the maximum allowed length.

        The test verifies that setting a small value succeeds and can be retrieved, then attempts to set a large value that exceeds the maximum allowed length. It checks that after the failed set operation, the key is either deleted or the new value is stored, ensuring that memcached handles value length limits correctly.
        """
        max_value_length = 2**20

        cache.set("small_value", "a")
        self.assertEqual(cache.get("small_value"), "a")

        large_value = "a" * (max_value_length + 1)
        try:
            cache.set("small_value", large_value)
        except Exception:
            # Most clients (e.g. pymemcache or pylibmc) raise when the value is
            # too large. This test is primarily checking that the key was
            # deleted, so the return/exception behavior for the set() itself is
            # not important.
            pass
        # small_value should be deleted, or set if configured to accept larger values
        value = cache.get("small_value")
        self.assertTrue(value is None or value == large_value)

    def test_close(self):
        # For clients that don't manage their connections properly, the
        # connection is closed when the request is complete.
        """
        Test the behavior of closing, specifically the handling of disconnecting from the cache.

        Checks that the disconnect_all method of the cache class is called when the request_finished signal is sent,
        if the should_disconnect_on_close flag is True. This test ensures proper cleanup of old connections after a request
        has finished, by verifying that the disconnect_all method is invoked correctly.

        The test uses a mock object to monitor the disconnect_all method and asserts that it is called as expected, 
        depending on the value of should_disconnect_on_close. This guarantees that the cache connections are properly 
        managed when a request is closed, avoiding potential resource leaks or other issues.
        """
        signals.request_finished.disconnect(close_old_connections)
        try:
            with mock.patch.object(
                cache._class, "disconnect_all", autospec=True
            ) as mock_disconnect:
                signals.request_finished.send(self.__class__)
                self.assertIs(mock_disconnect.called, self.should_disconnect_on_close)
        finally:
            signals.request_finished.connect(close_old_connections)

    def test_set_many_returns_failing_keys(self):
        """

        Tests that the set_many function correctly identifies and returns keys that fail to be set.

        The test simulates a failure in the underlying set_multi method, then checks that the 
        set_many function accurately reports the keys that failed to be set. This ensures that 
        the function provides informative error reporting when batch setting operations fail.

        """
        def fail_set_multi(mapping, *args, **kwargs):
            return mapping.keys()

        with mock.patch.object(cache._class, "set_multi", side_effect=fail_set_multi):
            failing_keys = cache.set_many({"key": "value"})
            self.assertEqual(failing_keys, ["key"])


@unittest.skipUnless(PyLibMCCache_params, "PyLibMCCache backend not configured")
@override_settings(
    CACHES=caches_setting_for_tests(
        base=PyLibMCCache_params,
        exclude=memcached_excluded_caches,
    )
)
class PyLibMCCacheTests(BaseMemcachedTests, TestCase):
    base_params = PyLibMCCache_params
    # libmemcached manages its own connections.
    should_disconnect_on_close = False

    @property
    def incr_decr_type_error(self):
        return cache._lib.ClientError

    @override_settings(
        CACHES=caches_setting_for_tests(
            base=PyLibMCCache_params,
            exclude=memcached_excluded_caches,
            OPTIONS={
                "binary": True,
                "behaviors": {"tcp_nodelay": True},
            },
        )
    )
    def test_pylibmc_options(self):
        self.assertTrue(cache._cache.binary)
        self.assertEqual(cache._cache.behaviors["tcp_nodelay"], int(True))

    def test_pylibmc_client_servers(self):
        """

        Tests the pylibmc client server configuration by verifying the client server location
        against a variety of input locations for different backend setups.

        The test covers both IPv4 and IPv6 addresses, as well as Unix socket connections, 
        to ensure the client server location is correctly resolved and configured.

        Parameters are tested in the following combinations:
        - Unix socket locations
        - IPv4 addresses with and without a port number
        - IPv6 addresses with and without a port number

        The test asserts that the client servers are correctly set to the expected location
        for each test case, ensuring proper configuration of the cache client.

        """
        backend = self.base_params["BACKEND"]
        tests = [
            ("unix:/run/memcached/socket", "/run/memcached/socket"),
            ("/run/memcached/socket", "/run/memcached/socket"),
            ("localhost", "localhost"),
            ("localhost:11211", "localhost:11211"),
            ("[::1]", "[::1]"),
            ("[::1]:11211", "[::1]:11211"),
            ("127.0.0.1", "127.0.0.1"),
            ("127.0.0.1:11211", "127.0.0.1:11211"),
        ]
        for location, expected in tests:
            settings = {"default": {"BACKEND": backend, "LOCATION": location}}
            with self.subTest(location), self.settings(CACHES=settings):
                self.assertEqual(cache.client_servers, [expected])


@unittest.skipUnless(PyMemcacheCache_params, "PyMemcacheCache backend not configured")
@override_settings(
    CACHES=caches_setting_for_tests(
        base=PyMemcacheCache_params,
        exclude=memcached_excluded_caches,
    )
)
class PyMemcacheCacheTests(BaseMemcachedTests, TestCase):
    base_params = PyMemcacheCache_params

    @property
    def incr_decr_type_error(self):
        return cache._lib.exceptions.MemcacheClientError

    def test_pymemcache_highest_pickle_version(self):
        """
        Checks the configured pickling version for cache serialization.

        This test case verifies that the highest available pickling version is used 
        for both the default cache and all configured cache clients. It ensures 
        that the 'pickle_version' parameter in the serialization function is set 
        to the highest protocol version available in the `pickle` module, 
        providing optimal compatibility and efficiency for serialized data.
        """
        self.assertEqual(
            cache._cache.default_kwargs["serde"]._serialize_func.keywords[
                "pickle_version"
            ],
            pickle.HIGHEST_PROTOCOL,
        )
        for cache_key in settings.CACHES:
            for client_key, client in caches[cache_key]._cache.clients.items():
                with self.subTest(cache_key=cache_key, server=client_key):
                    self.assertEqual(
                        client.serde._serialize_func.keywords["pickle_version"],
                        pickle.HIGHEST_PROTOCOL,
                    )

    @override_settings(
        CACHES=caches_setting_for_tests(
            base=PyMemcacheCache_params,
            exclude=memcached_excluded_caches,
            OPTIONS={"no_delay": True},
        )
    )
    def test_pymemcache_options(self):
        self.assertIs(cache._cache.default_kwargs["no_delay"], True)


@override_settings(
    CACHES=caches_setting_for_tests(
        BACKEND="django.core.cache.backends.filebased.FileBasedCache",
    )
)
class FileBasedCacheTests(BaseCacheTests, TestCase):
    """
    Specific test cases for the file-based cache.
    """

    def setUp(self):
        """
        Sets up the test environment by creating a temporary directory and updating the cache locations for all caches in the settings to point to this directory. This ensures that each test runs with a clean cache, isolated from other tests. The cache settings change is also signaled to any registered listeners.
        """
        super().setUp()
        self.dirname = self.mkdtemp()
        # Caches location cannot be modified through override_settings /
        # modify_settings, hence settings are manipulated directly here and the
        # setting_changed signal is triggered manually.
        for cache_params in settings.CACHES.values():
            cache_params["LOCATION"] = self.dirname
        setting_changed.send(self.__class__, setting="CACHES", enter=False)

    def tearDown(self):
        super().tearDown()
        # Call parent first, as cache.clear() may recreate cache base directory
        shutil.rmtree(self.dirname)

    def mkdtemp(self):
        return tempfile.mkdtemp()

    def test_ignores_non_cache_files(self):
        fname = os.path.join(self.dirname, "not-a-cache-file")
        with open(fname, "w"):
            os.utime(fname, None)
        cache.clear()
        self.assertTrue(
            os.path.exists(fname), "Expected cache.clear to ignore non cache files"
        )
        os.remove(fname)

    def test_clear_does_not_remove_cache_dir(self):
        """

        Tests that clearing the cache using :func:`cache.clear` does not remove the cache directory.

        The function verifies that the cache directory remains intact after the cache has been cleared,
        ensuring that the directory is preserved for future use.

        """
        cache.clear()
        self.assertTrue(
            os.path.exists(self.dirname), "Expected cache.clear to keep the cache dir"
        )

    def test_creates_cache_dir_if_nonexistent(self):
        """
        Verifies that the cache directory is created if it does not exist.

        This test case ensures that an attempt to store data in the cache results in the
        creation of the cache directory if it has not been previously created. The test
        validates the cache directory's existence after an initial cache entry is set.

        :raises AssertionError: If the cache directory does not exist after setting a cache entry
        """
        os.rmdir(self.dirname)
        cache.set("foo", "bar")
        self.assertTrue(os.path.exists(self.dirname))

    def test_get_ignores_enoent(self):
        cache.set("foo", "bar")
        os.unlink(cache._key_to_file("foo"))
        # Returns the default instead of erroring.
        self.assertEqual(cache.get("foo", "baz"), "baz")

    @skipIf(
        sys.platform == "win32",
        "Windows only partially supports umasks and chmod.",
    )
    def test_cache_dir_permissions(self):
        """

        Tests the creation of the cache directory with correct permissions.

        The test creates a nested directory structure and updates cache locations 
        to use this new directory. It then sets a cache value and checks 
        if the cache directory exists. The test verifies that the directory and 
        its parents have the correct permissions (0750) to ensure secure cache operations.

        """
        os.rmdir(self.dirname)
        dir_path = Path(self.dirname) / "nested" / "filebasedcache"
        for cache_params in settings.CACHES.values():
            cache_params["LOCATION"] = dir_path
        setting_changed.send(self.__class__, setting="CACHES", enter=False)
        cache.set("foo", "bar")
        self.assertIs(dir_path.exists(), True)
        tests = [
            dir_path,
            dir_path.parent,
            dir_path.parent.parent,
        ]
        for directory in tests:
            with self.subTest(directory=directory):
                dir_mode = directory.stat().st_mode & 0o777
                self.assertEqual(dir_mode, 0o700)

    def test_get_does_not_ignore_non_filenotfound_exceptions(self):
        """

        Tests that the cache's get method does not ignore non-FileNotFoundError exceptions.

        Specifically, this test case verifies that when attempting to retrieve a value from the cache,
        if an OSError occurs (simulated by patching the built-in open function), the cache raises the exception instead of catching it.

        """
        with mock.patch("builtins.open", side_effect=OSError):
            with self.assertRaises(OSError):
                cache.get("foo")

    def test_empty_cache_file_considered_expired(self):
        """
        Tests that an empty cache file is considered expired.

        This test case checks the behavior of the cache expiration logic when
        encountering a cache file that contains no data. It verifies that such a file
        is correctly identified as expired, ensuring that the cache mechanism
        does not return stale or incomplete data.

        :returns: None
        :raises: AssertionError if the cache file is not considered expired
        """
        cache_file = cache._key_to_file("foo")
        with open(cache_file, "wb") as fh:
            fh.write(b"")
        with open(cache_file, "rb") as fh:
            self.assertIs(cache._is_expired(fh), True)

    def test_has_key_race_handling(self):
        self.assertIs(cache.add("key", "value"), True)
        with mock.patch("builtins.open", side_effect=FileNotFoundError) as mocked_open:
            self.assertIs(cache.has_key("key"), False)
            mocked_open.assert_called_once()

    def test_touch(self):
        """Override to manually advance time since file access can be slow."""

        class ManualTickingTime:
            def __init__(self):
                # Freeze time, calling `sleep` will manually advance it.
                self._time = time.time()

            def time(self):
                return self._time

            def sleep(self, seconds):
                self._time += seconds

        mocked_time = ManualTickingTime()
        with (
            mock.patch("django.core.cache.backends.filebased.time", new=mocked_time),
            mock.patch("django.core.cache.backends.base.time", new=mocked_time),
            mock.patch("cache.tests.time", new=mocked_time),
        ):
            super().test_touch()


@unittest.skipUnless(RedisCache_params, "Redis backend not configured")
@override_settings(
    CACHES=caches_setting_for_tests(
        base=RedisCache_params,
        exclude=redis_excluded_caches,
    )
)
class RedisCacheTests(BaseCacheTests, TestCase):
    def setUp(self):
        import redis

        super().setUp()
        self.lib = redis

    @property
    def incr_decr_type_error(self):
        return self.lib.ResponseError

    def test_incr_write_connection(self):
        """
        Tests that the cache's incr method establishes a write connection to Redis.

        Verifies that when incrementing a value in the cache, the get_client method is 
        called with the 'write' parameter set to True, ensuring data consistency and 
        allowing for writes to the Redis cache backend.
        """
        cache.set("number", 42)
        with mock.patch(
            "django.core.cache.backends.redis.RedisCacheClient.get_client"
        ) as mocked_get_client:
            cache.incr("number")
            self.assertEqual(mocked_get_client.call_args.kwargs, {"write": True})

    def test_cache_client_class(self):
        self.assertIs(cache._class, RedisCacheClient)
        self.assertIsInstance(cache._cache, RedisCacheClient)

    def test_get_backend_timeout_method(self):
        """

        Tests the get_backend_timeout method to ensure it handles different input scenarios correctly.

        The method is expected to return the input timeout value if it is a positive integer,
        return 0 if the input timeout value is negative, and return None if the input timeout value is None.

        This test case validates the functionality of the get_backend_timeout method
        by checking its output for positive, negative, and None input values.

        """
        positive_timeout = 10
        positive_backend_timeout = cache.get_backend_timeout(positive_timeout)
        self.assertEqual(positive_backend_timeout, positive_timeout)

        negative_timeout = -5
        negative_backend_timeout = cache.get_backend_timeout(negative_timeout)
        self.assertEqual(negative_backend_timeout, 0)

        none_timeout = None
        none_backend_timeout = cache.get_backend_timeout(none_timeout)
        self.assertIsNone(none_backend_timeout)

    def test_get_connection_pool_index(self):
        pool_index = cache._cache._get_connection_pool_index(write=True)
        self.assertEqual(pool_index, 0)
        pool_index = cache._cache._get_connection_pool_index(write=False)
        if len(cache._cache._servers) == 1:
            self.assertEqual(pool_index, 0)
        else:
            self.assertGreater(pool_index, 0)
            self.assertLess(pool_index, len(cache._cache._servers))

    def test_get_connection_pool(self):
        pool = cache._cache._get_connection_pool(write=True)
        self.assertIsInstance(pool, self.lib.ConnectionPool)

        pool = cache._cache._get_connection_pool(write=False)
        self.assertIsInstance(pool, self.lib.ConnectionPool)

    def test_get_client(self):
        self.assertIsInstance(cache._cache.get_client(), self.lib.Redis)

    def test_serializer_dumps(self):
        """

        Tests the dumps functionality of the serializer.

        Verifies that the serializer correctly dumps different data types, 
        including integers, booleans, and strings. Ensures that integers are 
        dumps correctly without any changes, while booleans and strings are 
        dumps as bytes.

        """
        self.assertEqual(cache._cache._serializer.dumps(123), 123)
        self.assertIsInstance(cache._cache._serializer.dumps(True), bytes)
        self.assertIsInstance(cache._cache._serializer.dumps("abc"), bytes)

    @override_settings(
        CACHES=caches_setting_for_tests(
            base=RedisCache_params,
            exclude=redis_excluded_caches,
            OPTIONS={
                "db": 5,
                "socket_timeout": 0.1,
                "retry_on_timeout": True,
            },
        )
    )
    def test_redis_pool_options(self):
        """

        Tests the Redis pool options for cache connections.

        Verifies that the connection pool settings are correctly applied when using Redis as the cache backend.
        The test checks the database number, socket timeout, and retry on timeout settings.

        """
        pool = cache._cache._get_connection_pool(write=False)
        self.assertEqual(pool.connection_kwargs["db"], 5)
        self.assertEqual(pool.connection_kwargs["socket_timeout"], 0.1)
        self.assertIs(pool.connection_kwargs["retry_on_timeout"], True)


class FileBasedCachePathLibTests(FileBasedCacheTests):
    def mkdtemp(self):
        """
        Create a temporary directory in the file system, returning its path as a Path object.

        The directory is created using the parent class's :meth:`mkdtemp` method and the result is then converted to a :class:`~pathlib.Path` object for convenience and easier manipulation.

        The returned Path object can be used for further file system operations, such as creating files or subdirectories within the temporary directory. 

        Note that the directory and its contents will need to be cleaned up manually when no longer needed.
        """
        tmp_dir = super().mkdtemp()
        return Path(tmp_dir)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "cache.liberal_backend.CacheClass",
        },
    }
)
class CustomCacheKeyValidationTests(SimpleTestCase):
    """
    Tests for the ability to mixin a custom ``validate_key`` method to
    a custom cache backend that otherwise inherits from a builtin
    backend, and override the default key validation. Refs #6447.
    """

    def test_custom_key_validation(self):
        # this key is both longer than 250 characters, and has spaces
        """
        Tests the validation of custom keys in the cache.

        This test ensures that the cache system correctly handles and retrieves values 
        for keys that may contain special characters, such as spaces.

        Verifies that a key-value pair can be successfully stored and retrieved, even 
        when the key is quite long or contains non-alphanumeric characters.

        The test case checks the cache's ability to set and get a value using a key 
        with spaces, confirming that the cache behaves as expected under these 
        conditions. 
        """
        key = "some key with spaces" * 15
        val = "a value"
        cache.set(key, val)
        self.assertEqual(cache.get(key), val)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "cache.closeable_cache.CacheClass",
        }
    }
)
class CacheClosingTests(SimpleTestCase):
    def test_close(self):
        """

        Tests whether the cache is properly closed after a request is finished.

        This test ensures that the cache remains open before the request finishes and 
        is successfully closed afterwards. It uses a signal to simulate the completion 
        of a request and then verifies the cache's state to confirm the expected behavior.

        """
        self.assertFalse(cache.closed)
        signals.request_finished.send(self.__class__)
        self.assertTrue(cache.closed)

    def test_close_only_initialized(self):
        with self.settings(
            CACHES={
                "cache_1": {
                    "BACKEND": "cache.closeable_cache.CacheClass",
                },
                "cache_2": {
                    "BACKEND": "cache.closeable_cache.CacheClass",
                },
            }
        ):
            self.assertEqual(caches.all(initialized_only=True), [])
            signals.request_finished.send(self.__class__)
            self.assertEqual(caches.all(initialized_only=True), [])


DEFAULT_MEMORY_CACHES_SETTINGS = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}
NEVER_EXPIRING_CACHES_SETTINGS = copy.deepcopy(DEFAULT_MEMORY_CACHES_SETTINGS)
NEVER_EXPIRING_CACHES_SETTINGS["default"]["TIMEOUT"] = None


class DefaultNonExpiringCacheKeyTests(SimpleTestCase):
    """
    Settings having Cache arguments with a TIMEOUT=None create Caches that will
    set non-expiring keys.
    """

    def setUp(self):
        # The 5 minute (300 seconds) default expiration time for keys is
        # defined in the implementation of the initializer method of the
        # BaseCache type.
        self.DEFAULT_TIMEOUT = caches[DEFAULT_CACHE_ALIAS].default_timeout

    def tearDown(self):
        del self.DEFAULT_TIMEOUT

    def test_default_expiration_time_for_keys_is_5_minutes(self):
        """The default expiration time of a cache key is 5 minutes.

        This value is defined in
        django.core.cache.backends.base.BaseCache.__init__().
        """
        self.assertEqual(300, self.DEFAULT_TIMEOUT)

    def test_caches_with_unset_timeout_has_correct_default_timeout(self):
        """Caches that have the TIMEOUT parameter undefined in the default
        settings will use the default 5 minute timeout.
        """
        cache = caches[DEFAULT_CACHE_ALIAS]
        self.assertEqual(self.DEFAULT_TIMEOUT, cache.default_timeout)

    @override_settings(CACHES=NEVER_EXPIRING_CACHES_SETTINGS)
    def test_caches_set_with_timeout_as_none_has_correct_default_timeout(self):
        """Memory caches that have the TIMEOUT parameter set to `None` in the
        default settings with have `None` as the default timeout.

        This means "no timeout".
        """
        cache = caches[DEFAULT_CACHE_ALIAS]
        self.assertIsNone(cache.default_timeout)
        self.assertIsNone(cache.get_backend_timeout())

    @override_settings(CACHES=DEFAULT_MEMORY_CACHES_SETTINGS)
    def test_caches_with_unset_timeout_set_expiring_key(self):
        """Memory caches that have the TIMEOUT parameter unset will set cache
        keys having the default 5 minute timeout.
        """
        key = "my-key"
        value = "my-value"
        cache = caches[DEFAULT_CACHE_ALIAS]
        cache.set(key, value)
        cache_key = cache.make_key(key)
        self.assertIsNotNone(cache._expire_info[cache_key])

    @override_settings(CACHES=NEVER_EXPIRING_CACHES_SETTINGS)
    def test_caches_set_with_timeout_as_none_set_non_expiring_key(self):
        """Memory caches that have the TIMEOUT parameter set to `None` will set
        a non expiring key by default.
        """
        key = "another-key"
        value = "another-value"
        cache = caches[DEFAULT_CACHE_ALIAS]
        cache.set(key, value)
        cache_key = cache.make_key(key)
        self.assertIsNone(cache._expire_info[cache_key])


@override_settings(
    CACHE_MIDDLEWARE_KEY_PREFIX="settingsprefix",
    CACHE_MIDDLEWARE_SECONDS=1,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        },
    },
    USE_I18N=False,
    ALLOWED_HOSTS=[".example.com"],
)
class CacheUtils(SimpleTestCase):
    """TestCase for django.utils.cache functions."""

    host = "www.example.com"
    path = "/cache/test/"
    factory = RequestFactory(headers={"host": host})

    def tearDown(self):
        cache.clear()

    def _get_request_cache(self, method="GET", query_string=None, update_cache=None):
        request = self._get_request(
            self.host, self.path, method, query_string=query_string
        )
        request._cache_update_cache = update_cache if update_cache else True
        return request

    def test_patch_vary_headers(self):
        headers = (
            # Initial vary, new headers, resulting vary.
            (None, ("Accept-Encoding",), "Accept-Encoding"),
            ("Accept-Encoding", ("accept-encoding",), "Accept-Encoding"),
            ("Accept-Encoding", ("ACCEPT-ENCODING",), "Accept-Encoding"),
            ("Cookie", ("Accept-Encoding",), "Cookie, Accept-Encoding"),
            (
                "Cookie, Accept-Encoding",
                ("Accept-Encoding",),
                "Cookie, Accept-Encoding",
            ),
            (
                "Cookie, Accept-Encoding",
                ("Accept-Encoding", "cookie"),
                "Cookie, Accept-Encoding",
            ),
            (None, ("Accept-Encoding", "COOKIE"), "Accept-Encoding, COOKIE"),
            (
                "Cookie,     Accept-Encoding",
                ("Accept-Encoding", "cookie"),
                "Cookie, Accept-Encoding",
            ),
            (
                "Cookie    ,     Accept-Encoding",
                ("Accept-Encoding", "cookie"),
                "Cookie, Accept-Encoding",
            ),
            ("*", ("Accept-Language", "Cookie"), "*"),
            ("Accept-Language, Cookie", ("*",), "*"),
        )
        for initial_vary, newheaders, resulting_vary in headers:
            with self.subTest(initial_vary=initial_vary, newheaders=newheaders):
                response = HttpResponse()
                if initial_vary is not None:
                    response.headers["Vary"] = initial_vary
                patch_vary_headers(response, newheaders)
                self.assertEqual(response.headers["Vary"], resulting_vary)

    def test_get_cache_key(self):
        """

        Tests the functionality of getting and learning cache keys for HTTP requests.

        This test case covers the following scenarios:
        - Getting the cache key for a request when no cache key has been learned yet.
        - Learning the cache key for a request and verifying that it matches the expected value.
        - Learning the cache key with a custom key prefix and verifying that the cache key is correctly generated.

        The test ensures that the cache key generation is correct for different scenarios, including requests without learned cache keys and requests with custom key prefixes.

        """
        request = self.factory.get(self.path)
        response = HttpResponse()
        # Expect None if no headers have been set yet.
        self.assertIsNone(get_cache_key(request))
        # Set headers to an empty list.
        learn_cache_key(request, response)

        self.assertEqual(
            get_cache_key(request),
            "views.decorators.cache.cache_page.settingsprefix.GET."
            "18a03f9c9649f7d684af5db3524f5c99.d41d8cd98f00b204e9800998ecf8427e",
        )
        # A specified key_prefix is taken into account.
        key_prefix = "localprefix"
        learn_cache_key(request, response, key_prefix=key_prefix)
        self.assertEqual(
            get_cache_key(request, key_prefix=key_prefix),
            "views.decorators.cache.cache_page.localprefix.GET."
            "18a03f9c9649f7d684af5db3524f5c99.d41d8cd98f00b204e9800998ecf8427e",
        )

    def test_get_cache_key_with_query(self):
        """
        Tests the functionality of generating a cache key for a given request.

        The cache key is initially None, indicating that no cache key has been learned.
        After calling learn_cache_key with a request and response, the cache key is updated
        and can be retrieved using get_cache_key. The test verifies that the generated cache
        key matches the expected string value.

        The test case covers the scenario where a GET request is made with query parameters,
        demonstrating that the cache key takes into account the request method and query string.

        """
        request = self.factory.get(self.path, {"test": 1})
        response = HttpResponse()
        # Expect None if no headers have been set yet.
        self.assertIsNone(get_cache_key(request))
        # Set headers to an empty list.
        learn_cache_key(request, response)
        # The querystring is taken into account.
        self.assertEqual(
            get_cache_key(request),
            "views.decorators.cache.cache_page.settingsprefix.GET."
            "beaf87a9a99ee81c673ea2d67ccbec2a.d41d8cd98f00b204e9800998ecf8427e",
        )

    def test_cache_key_varies_by_url(self):
        """
        get_cache_key keys differ by fully-qualified URL instead of path
        """
        request1 = self.factory.get(self.path, headers={"host": "sub-1.example.com"})
        learn_cache_key(request1, HttpResponse())
        request2 = self.factory.get(self.path, headers={"host": "sub-2.example.com"})
        learn_cache_key(request2, HttpResponse())
        self.assertNotEqual(get_cache_key(request1), get_cache_key(request2))

    def test_learn_cache_key(self):
        """

        Tests the generation of a cache key using the learn_cache_key function.

        This test case verifies that the cache key is correctly generated based on the
        request and response headers. The 'Vary' header in the response is set to
        'Pony', which affects the cache key generation. The test asserts that the
        generated cache key matches the expected value.

        The cache key generation process takes into account various factors, including
        the request method, path, and response headers, to ensure that the cache is
        properly invalidated when the response changes. This test ensures that the
        cache key is correctly generated and stored for later use.

        """
        request = self.factory.head(self.path)
        response = HttpResponse()
        response.headers["Vary"] = "Pony"
        # Make sure that the Vary header is added to the key hash
        learn_cache_key(request, response)

        self.assertEqual(
            get_cache_key(request),
            "views.decorators.cache.cache_page.settingsprefix.GET."
            "18a03f9c9649f7d684af5db3524f5c99.d41d8cd98f00b204e9800998ecf8427e",
        )

    def test_patch_cache_control(self):
        tests = (
            # Initial Cache-Control, kwargs to patch_cache_control, expected
            # Cache-Control parts.
            (None, {"private": True}, {"private"}),
            ("", {"private": True}, {"private"}),
            # no-cache.
            ("", {"no_cache": "Set-Cookie"}, {"no-cache=Set-Cookie"}),
            ("", {"no-cache": "Set-Cookie"}, {"no-cache=Set-Cookie"}),
            ("no-cache=Set-Cookie", {"no_cache": True}, {"no-cache"}),
            ("no-cache=Set-Cookie,no-cache=Link", {"no_cache": True}, {"no-cache"}),
            (
                "no-cache=Set-Cookie",
                {"no_cache": "Link"},
                {"no-cache=Set-Cookie", "no-cache=Link"},
            ),
            (
                "no-cache=Set-Cookie,no-cache=Link",
                {"no_cache": "Custom"},
                {"no-cache=Set-Cookie", "no-cache=Link", "no-cache=Custom"},
            ),
            # Test whether private/public attributes are mutually exclusive
            ("private", {"private": True}, {"private"}),
            ("private", {"public": True}, {"public"}),
            ("public", {"public": True}, {"public"}),
            ("public", {"private": True}, {"private"}),
            (
                "must-revalidate,max-age=60,private",
                {"public": True},
                {"must-revalidate", "max-age=60", "public"},
            ),
            (
                "must-revalidate,max-age=60,public",
                {"private": True},
                {"must-revalidate", "max-age=60", "private"},
            ),
            (
                "must-revalidate,max-age=60",
                {"public": True},
                {"must-revalidate", "max-age=60", "public"},
            ),
        )

        cc_delim_re = re.compile(r"\s*,\s*")

        for initial_cc, newheaders, expected_cc in tests:
            with self.subTest(initial_cc=initial_cc, newheaders=newheaders):
                response = HttpResponse()
                if initial_cc is not None:
                    response.headers["Cache-Control"] = initial_cc
                patch_cache_control(response, **newheaders)
                parts = set(cc_delim_re.split(response.headers["Cache-Control"]))
                self.assertEqual(parts, expected_cc)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "KEY_PREFIX": "cacheprefix",
        },
    },
)
class PrefixedCacheUtils(CacheUtils):
    pass


@override_settings(
    CACHE_MIDDLEWARE_SECONDS=60,
    CACHE_MIDDLEWARE_KEY_PREFIX="test",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        },
    },
)
class CacheHEADTest(SimpleTestCase):
    path = "/cache/test/"
    factory = RequestFactory()

    def tearDown(self):
        cache.clear()

    def _set_cache(self, request, msg):
        return UpdateCacheMiddleware(lambda req: HttpResponse(msg))(request)

    def test_head_caches_correctly(self):
        """
        Tests if the cache is updated and retrieved correctly for a HEAD request, verifying that the cached content matches the expected test content.
        """
        test_content = "test content"

        request = self.factory.head(self.path)
        request._cache_update_cache = True
        self._set_cache(request, test_content)

        request = self.factory.head(self.path)
        request._cache_update_cache = True
        get_cache_data = FetchFromCacheMiddleware(empty_response).process_request(
            request
        )
        self.assertIsNotNone(get_cache_data)
        self.assertEqual(test_content.encode(), get_cache_data.content)

    def test_head_with_cached_get(self):
        """

         Tests that a HEAD request can successfully retrieve cached data from a previous GET request.

         This test ensures that the caching mechanism is working correctly by first sending a GET request,
         caching its response, and then sending a HEAD request to verify that the cached data is returned.
         The test asserts that the cached data is not None and matches the expected content.

        """
        test_content = "test content"

        request = self.factory.get(self.path)
        request._cache_update_cache = True
        self._set_cache(request, test_content)

        request = self.factory.head(self.path)
        get_cache_data = FetchFromCacheMiddleware(empty_response).process_request(
            request
        )
        self.assertIsNotNone(get_cache_data)
        self.assertEqual(test_content.encode(), get_cache_data.content)


@override_settings(
    CACHE_MIDDLEWARE_KEY_PREFIX="settingsprefix",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        },
    },
    LANGUAGES=[
        ("en", "English"),
        ("es", "Spanish"),
    ],
)
class CacheI18nTest(SimpleTestCase):
    path = "/cache/test/"
    factory = RequestFactory()

    def tearDown(self):
        cache.clear()

    @override_settings(USE_I18N=True, USE_TZ=False)
    def test_cache_key_i18n_translation(self):
        """

        Tests that cache keys are properly generated when internationalization is enabled.

        This function verifies that the cache key includes the language name when translation
        is active, ensuring that cache is properly segregated by language. It simulates an
        HTTP request, retrieves the current language, and checks that the generated cache
        key contains the language name. Additionally, it confirms that the cache key
        generated by the learn_cache_key function matches the one generated by the
        get_cache_key function.

        The test case sets internationalization to True and timezone to False to isolate
        the impact of translation on cache key generation.

        """
        request = self.factory.get(self.path)
        lang = translation.get_language()
        response = HttpResponse()
        key = learn_cache_key(request, response)
        self.assertIn(
            lang,
            key,
            "Cache keys should include the language name when translation is active",
        )
        key2 = get_cache_key(request)
        self.assertEqual(key, key2)

    def check_accept_language_vary(self, accept_language, vary, reference_key):
        """
        Checks if the cache key generated for a request with the specified Accept-Language
        header and Vary header matches the expected reference key.

        The function simulates a request to the current path with the provided Accept-Language
        header and tests if the cache key generated by the learn_cache_key and get_cache_key
        functions matches the reference key.

        :param accept_language: The Accept-Language header value to use for the request.
        :param vary: The value of the Vary header in the response.
        :param reference_key: The expected cache key to match against.

        """
        request = self.factory.get(self.path)
        request.META["HTTP_ACCEPT_LANGUAGE"] = accept_language
        request.META["HTTP_ACCEPT_ENCODING"] = "gzip;q=1.0, identity; q=0.5, *;q=0"
        response = HttpResponse()
        response.headers["Vary"] = vary
        key = learn_cache_key(request, response)
        key2 = get_cache_key(request)
        self.assertEqual(key, reference_key)
        self.assertEqual(key2, reference_key)

    @override_settings(USE_I18N=True, USE_TZ=False)
    def test_cache_key_i18n_translation_accept_language(self):
        lang = translation.get_language()
        self.assertEqual(lang, "en")
        request = self.factory.get(self.path)
        request.META["HTTP_ACCEPT_ENCODING"] = "gzip;q=1.0, identity; q=0.5, *;q=0"
        response = HttpResponse()
        response.headers["Vary"] = "accept-encoding"
        key = learn_cache_key(request, response)
        self.assertIn(
            lang,
            key,
            "Cache keys should include the language name when translation is active",
        )
        self.check_accept_language_vary(
            "en-us", "cookie, accept-language, accept-encoding", key
        )
        self.check_accept_language_vary(
            "en-US", "cookie, accept-encoding, accept-language", key
        )
        self.check_accept_language_vary(
            "en-US,en;q=0.8", "accept-encoding, accept-language, cookie", key
        )
        self.check_accept_language_vary(
            "en-US,en;q=0.8,ko;q=0.6", "accept-language, cookie, accept-encoding", key
        )
        self.check_accept_language_vary(
            "ko-kr,ko;q=0.8,en-us;q=0.5,en;q=0.3 ",
            "accept-encoding, cookie, accept-language",
            key,
        )
        self.check_accept_language_vary(
            "ko-KR,ko;q=0.8,en-US;q=0.6,en;q=0.4",
            "accept-language, accept-encoding, cookie",
            key,
        )
        self.check_accept_language_vary(
            "ko;q=1.0,en;q=0.5", "cookie, accept-language, accept-encoding", key
        )
        self.check_accept_language_vary(
            "ko, en", "cookie, accept-encoding, accept-language", key
        )
        self.check_accept_language_vary(
            "ko-KR, en-US", "accept-encoding, accept-language, cookie", key
        )

    @override_settings(USE_I18N=False, USE_TZ=True)
    def test_cache_key_i18n_timezone(self):
        """

        Tests the generation of cache keys when internationalization and time zones are disabled/enabled.

        Verifies that the cache key includes the current time zone name when time zones are active.
        Also checks that the cache key generated by the learn_cache_key function is identical to the one generated by the get_cache_key function.

        This test ensures that cache keys are correctly generated in a scenario where internationalization is disabled and time zones are enabled.

        """
        request = self.factory.get(self.path)
        tz = timezone.get_current_timezone_name()
        response = HttpResponse()
        key = learn_cache_key(request, response)
        self.assertIn(
            tz,
            key,
            "Cache keys should include the time zone name when time zones are active",
        )
        key2 = get_cache_key(request)
        self.assertEqual(key, key2)

    @override_settings(USE_I18N=False)
    def test_cache_key_no_i18n(self):
        request = self.factory.get(self.path)
        lang = translation.get_language()
        tz = timezone.get_current_timezone_name()
        response = HttpResponse()
        key = learn_cache_key(request, response)
        self.assertNotIn(
            lang,
            key,
            "Cache keys shouldn't include the language name when i18n isn't active",
        )
        self.assertNotIn(
            tz,
            key,
            "Cache keys shouldn't include the time zone name when i18n isn't active",
        )

    @override_settings(
        CACHE_MIDDLEWARE_KEY_PREFIX="test",
        CACHE_MIDDLEWARE_SECONDS=60,
        USE_I18N=True,
    )
    def test_middleware(self):
        """
        Tests the caching middleware functionality.

        This test case verifies the behavior of the caching middleware under various scenarios, including:
        - Cache key generation with query strings
        - Cache updating and retrieval with different query string parameters
        - Cache handling with internationalization (i18n) support, including language activation and deactivation

        It checks that the cache is properly updated and retrieved when the request query string changes, and that the cache is correctly handled when the language is switched.

        The test uses a mock request and response to simulate real-world usage, and it asserts the expected behavior of the caching middleware in each scenario.

        Returns:
            None

        Raises:
            AssertionError: If the caching middleware does not behave as expected in any of the test scenarios
        """
        def set_cache(request, lang, msg):
            """

            Sets a cache for a given HTTP request with a specific language and message.

            This function activates the specified language and updates the cache with the provided message.
            It returns an HTTP response with the message. The caching is handled by the UpdateCacheMiddleware.

            :param request: The HTTP request for which the cache should be set
            :param lang: The language to be activated for the request
            :param msg: The message to be included in the HTTP response
            :return: An HTTP response with the message and updated cache

            """
            def get_response(req):
                return HttpResponse(msg)

            translation.activate(lang)
            return UpdateCacheMiddleware(get_response)(request)

        # cache with non empty request.GET
        request = self.factory.get(self.path, {"foo": "bar", "other": "true"})
        request._cache_update_cache = True

        get_cache_data = FetchFromCacheMiddleware(empty_response).process_request(
            request
        )
        # first access, cache must return None
        self.assertIsNone(get_cache_data)
        content = "Check for cache with QUERY_STRING"

        def get_response(req):
            return HttpResponse(content)

        UpdateCacheMiddleware(get_response)(request)
        get_cache_data = FetchFromCacheMiddleware(empty_response).process_request(
            request
        )
        # cache must return content
        self.assertIsNotNone(get_cache_data)
        self.assertEqual(get_cache_data.content, content.encode())
        # different QUERY_STRING, cache must be empty
        request = self.factory.get(self.path, {"foo": "bar", "somethingelse": "true"})
        request._cache_update_cache = True
        get_cache_data = FetchFromCacheMiddleware(empty_response).process_request(
            request
        )
        self.assertIsNone(get_cache_data)

        # i18n tests
        en_message = "Hello world!"
        es_message = "Hola mundo!"

        request = self.factory.get(self.path)
        request._cache_update_cache = True
        set_cache(request, "en", en_message)
        get_cache_data = FetchFromCacheMiddleware(empty_response).process_request(
            request
        )
        # The cache can be recovered
        self.assertIsNotNone(get_cache_data)
        self.assertEqual(get_cache_data.content, en_message.encode())
        # change the session language and set content
        request = self.factory.get(self.path)
        request._cache_update_cache = True
        set_cache(request, "es", es_message)
        # change again the language
        translation.activate("en")
        # retrieve the content from cache
        get_cache_data = FetchFromCacheMiddleware(empty_response).process_request(
            request
        )
        self.assertEqual(get_cache_data.content, en_message.encode())
        # change again the language
        translation.activate("es")
        get_cache_data = FetchFromCacheMiddleware(empty_response).process_request(
            request
        )
        self.assertEqual(get_cache_data.content, es_message.encode())
        # reset the language
        translation.deactivate()

    @override_settings(
        CACHE_MIDDLEWARE_KEY_PREFIX="test",
        CACHE_MIDDLEWARE_SECONDS=60,
    )
    def test_middleware_doesnt_cache_streaming_response(self):
        """
        Tests that the middleware does not cache responses when a view returns a streaming HTTP response.

        This test case verifies that the cache middleware correctly handles streaming responses 
        by checking if the cache is bypassed in such cases. It ensures that the cache is not populated 
        when a view returns a StreamingHttpResponse, which is essential for maintaining the 
        integrity of the cached data and preventing potential issues with cached responses.

        The test scenario covers the following steps:
        - It sets up a request and checks if the cache is initially empty.
        - It simulates a view that returns a streaming response and updates the cache.
        - It then checks again if the cache is still empty, verifying that the streaming response 
          was not cached.

        By confirming that the cache middleware behaves as expected in this scenario, this test 
        ensures that the caching mechanism works correctly and efficiently handles different 
        types of HTTP responses, including streaming content.
        """
        request = self.factory.get(self.path)
        get_cache_data = FetchFromCacheMiddleware(empty_response).process_request(
            request
        )
        self.assertIsNone(get_cache_data)

        def get_stream_response(req):
            return StreamingHttpResponse(["Check for cache with streaming content."])

        UpdateCacheMiddleware(get_stream_response)(request)

        get_cache_data = FetchFromCacheMiddleware(empty_response).process_request(
            request
        )
        self.assertIsNone(get_cache_data)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "KEY_PREFIX": "cacheprefix",
        },
    },
)
class PrefixedCacheI18nTest(CacheI18nTest):
    pass


def hello_world_view(request, value):
    return HttpResponse("Hello World %s" % value)


def csrf_view(request):
    return HttpResponse(csrf(request)["csrf_token"])


@override_settings(
    CACHE_MIDDLEWARE_ALIAS="other",
    CACHE_MIDDLEWARE_KEY_PREFIX="middlewareprefix",
    CACHE_MIDDLEWARE_SECONDS=30,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        },
        "other": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "other",
            "TIMEOUT": "1",
        },
    },
)
class CacheMiddlewareTest(SimpleTestCase):
    factory = RequestFactory()

    def setUp(self):
        """
        Sets up the test environment by initializing the default and other caches.

           Retrieves the default and other caches from the cache backend and assigns 
           them to instance variables. Ensures that both caches are cleared after the 
           test has finished running by scheduling cleanup operations. This setup is 
           typically used in test classes to provide a clean cache state for each test 
           case, allowing for more reliable and isolated testing of cache-dependent 
           functionality.
        """
        self.default_cache = caches["default"]
        self.addCleanup(self.default_cache.clear)
        self.other_cache = caches["other"]
        self.addCleanup(self.other_cache.clear)

    def test_constructor(self):
        """
        The constructor is correctly distinguishing between usage of
        CacheMiddleware as Middleware vs. usage of CacheMiddleware as view
        decorator and setting attributes appropriately.
        """
        # If only one argument is passed in construction, it's being used as
        # middleware.
        middleware = CacheMiddleware(empty_response)

        # Now test object attributes against values defined in setUp above
        self.assertEqual(middleware.cache_timeout, 30)
        self.assertEqual(middleware.key_prefix, "middlewareprefix")
        self.assertEqual(middleware.cache_alias, "other")
        self.assertEqual(middleware.cache, self.other_cache)

        # If more arguments are being passed in construction, it's being used
        # as a decorator. First, test with "defaults":
        as_view_decorator = CacheMiddleware(
            empty_response, cache_alias=None, key_prefix=None
        )

        self.assertEqual(
            as_view_decorator.cache_timeout, 30
        )  # Timeout value for 'default' cache, i.e. 30
        self.assertEqual(as_view_decorator.key_prefix, "")
        # Value of DEFAULT_CACHE_ALIAS from django.core.cache
        self.assertEqual(as_view_decorator.cache_alias, "default")
        self.assertEqual(as_view_decorator.cache, self.default_cache)

        # Next, test with custom values:
        as_view_decorator_with_custom = CacheMiddleware(
            hello_world_view, cache_timeout=60, cache_alias="other", key_prefix="foo"
        )

        self.assertEqual(as_view_decorator_with_custom.cache_timeout, 60)
        self.assertEqual(as_view_decorator_with_custom.key_prefix, "foo")
        self.assertEqual(as_view_decorator_with_custom.cache_alias, "other")
        self.assertEqual(as_view_decorator_with_custom.cache, self.other_cache)

    def test_update_cache_middleware_constructor(self):
        """
        Tests the constructor of the UpdateCacheMiddleware class.

        Verifies that the middleware object is initialized with the correct default values, 
        including cache timeout, page timeout, key prefix, cache alias, and cache instance.

        Checks that the middleware constructor correctly sets up the object with 
        the expected attributes when no explicit configuration is provided.
        """
        middleware = UpdateCacheMiddleware(empty_response)
        self.assertEqual(middleware.cache_timeout, 30)
        self.assertIsNone(middleware.page_timeout)
        self.assertEqual(middleware.key_prefix, "middlewareprefix")
        self.assertEqual(middleware.cache_alias, "other")
        self.assertEqual(middleware.cache, self.other_cache)

    def test_fetch_cache_middleware_constructor(self):
        """
        Tests the constructor of FetchFromCacheMiddleware to ensure it properly initializes 
        with the expected key prefix and cache configuration. 
        The test verifies that the middleware's key prefix, cache alias, and cache instance 
        are set as expected, allowing for correct functionality in caching operations.
        """
        middleware = FetchFromCacheMiddleware(empty_response)
        self.assertEqual(middleware.key_prefix, "middlewareprefix")
        self.assertEqual(middleware.cache_alias, "other")
        self.assertEqual(middleware.cache, self.other_cache)

    def test_middleware(self):
        middleware = CacheMiddleware(hello_world_view)
        prefix_middleware = CacheMiddleware(hello_world_view, key_prefix="prefix1")
        timeout_middleware = CacheMiddleware(hello_world_view, cache_timeout=1)

        request = self.factory.get("/view/")

        # Put the request through the request middleware
        result = middleware.process_request(request)
        self.assertIsNone(result)

        response = hello_world_view(request, "1")

        # Now put the response through the response middleware
        response = middleware.process_response(request, response)

        # Repeating the request should result in a cache hit
        result = middleware.process_request(request)
        self.assertIsNotNone(result)
        self.assertEqual(result.content, b"Hello World 1")

        # The same request through a different middleware won't hit
        result = prefix_middleware.process_request(request)
        self.assertIsNone(result)

        # The same request with a timeout _will_ hit
        result = timeout_middleware.process_request(request)
        self.assertIsNotNone(result)
        self.assertEqual(result.content, b"Hello World 1")

    def test_view_decorator(self):
        # decorate the same view with different cache decorators
        """
        Tests the behavior of the `cache_page` decorator with various cache configurations.

        The test covers the following scenarios:

        * Default cache with and without a key prefix
        * Explicitly specifying the default cache with and without a key prefix
        * Using a different cache (named 'other') with and without a key prefix
        * Verifying that the cache expires after the specified time (3 seconds)

        The test ensures that the cache is correctly updated and retrieved for different views and cache configurations, and that the cached response is served until the cache expires.
        """
        default_view = cache_page(3)(hello_world_view)
        default_with_prefix_view = cache_page(3, key_prefix="prefix1")(hello_world_view)

        explicit_default_view = cache_page(3, cache="default")(hello_world_view)
        explicit_default_with_prefix_view = cache_page(
            3, cache="default", key_prefix="prefix1"
        )(hello_world_view)

        other_view = cache_page(1, cache="other")(hello_world_view)
        other_with_prefix_view = cache_page(1, cache="other", key_prefix="prefix2")(
            hello_world_view
        )

        request = self.factory.get("/view/")

        # Request the view once
        response = default_view(request, "1")
        self.assertEqual(response.content, b"Hello World 1")

        # Request again -- hit the cache
        response = default_view(request, "2")
        self.assertEqual(response.content, b"Hello World 1")

        # Requesting the same view with the explicit cache should yield the same result
        response = explicit_default_view(request, "3")
        self.assertEqual(response.content, b"Hello World 1")

        # Requesting with a prefix will hit a different cache key
        response = explicit_default_with_prefix_view(request, "4")
        self.assertEqual(response.content, b"Hello World 4")

        # Hitting the same view again gives a cache hit
        response = explicit_default_with_prefix_view(request, "5")
        self.assertEqual(response.content, b"Hello World 4")

        # And going back to the implicit cache will hit the same cache
        response = default_with_prefix_view(request, "6")
        self.assertEqual(response.content, b"Hello World 4")

        # Requesting from an alternate cache won't hit cache
        response = other_view(request, "7")
        self.assertEqual(response.content, b"Hello World 7")

        # But a repeated hit will hit cache
        response = other_view(request, "8")
        self.assertEqual(response.content, b"Hello World 7")

        # And prefixing the alternate cache yields yet another cache entry
        response = other_with_prefix_view(request, "9")
        self.assertEqual(response.content, b"Hello World 9")

        # But if we wait a couple of seconds...
        time.sleep(2)

        # ... the default cache will still hit
        caches["default"]
        response = default_view(request, "11")
        self.assertEqual(response.content, b"Hello World 1")

        # ... the default cache with a prefix will still hit
        response = default_with_prefix_view(request, "12")
        self.assertEqual(response.content, b"Hello World 4")

        # ... the explicit default cache will still hit
        response = explicit_default_view(request, "13")
        self.assertEqual(response.content, b"Hello World 1")

        # ... the explicit default cache with a prefix will still hit
        response = explicit_default_with_prefix_view(request, "14")
        self.assertEqual(response.content, b"Hello World 4")

        # .. but a rapidly expiring cache won't hit
        response = other_view(request, "15")
        self.assertEqual(response.content, b"Hello World 15")

        # .. even if it has a prefix
        response = other_with_prefix_view(request, "16")
        self.assertEqual(response.content, b"Hello World 16")

    def test_cache_page_timeout(self):
        # Page timeout takes precedence over the "max-age" section of the
        # "Cache-Control".
        """

        Test the interaction between cache page timeout and cache control max age.

        This test case evaluates the behavior of the cache page functionality when the 
        cache timeout is set to different values relative to the cache control max age.
        It checks that the cache is updated or invalidated correctly based on these settings.

        The test covers two scenarios: 
        - When the page timeout is greater than the max age, the cache should not be updated.
        - When the page timeout is less than or equal to the max age, the cache should be updated.

        It verifies that the response content is correct in each scenario, ensuring the cache 
        behavior aligns with the expected functionality.

        """
        tests = [
            (1, 3),  # max_age < page_timeout.
            (3, 1),  # max_age > page_timeout.
        ]
        for max_age, page_timeout in tests:
            with self.subTest(max_age=max_age, page_timeout=page_timeout):
                view = cache_page(timeout=page_timeout)(
                    cache_control(max_age=max_age)(hello_world_view)
                )
                request = self.factory.get("/view/")
                response = view(request, "1")
                self.assertEqual(response.content, b"Hello World 1")
                time.sleep(1)
                response = view(request, "2")
                self.assertEqual(
                    response.content,
                    b"Hello World 1" if page_timeout > max_age else b"Hello World 2",
                )
            cache.clear()

    def test_cached_control_private_not_cached(self):
        """Responses with 'Cache-Control: private' are not cached."""
        view_with_private_cache = cache_page(3)(
            cache_control(private=True)(hello_world_view)
        )
        request = self.factory.get("/view/")
        response = view_with_private_cache(request, "1")
        self.assertEqual(response.content, b"Hello World 1")
        response = view_with_private_cache(request, "2")
        self.assertEqual(response.content, b"Hello World 2")

    def test_sensitive_cookie_not_cached(self):
        """
        Django must prevent caching of responses that set a user-specific (and
        maybe security sensitive) cookie in response to a cookie-less request.
        """
        request = self.factory.get("/view/")
        csrf_middleware = CsrfViewMiddleware(csrf_view)
        csrf_middleware.process_view(request, csrf_view, (), {})
        cache_middleware = CacheMiddleware(csrf_middleware)

        self.assertIsNone(cache_middleware.process_request(request))
        cache_middleware(request)

        # Inserting a CSRF cookie in a cookie-less request prevented caching.
        self.assertIsNone(cache_middleware.process_request(request))

    def test_304_response_has_http_caching_headers_but_not_cached(self):
        """
        Tests that a view decorated with cache_page returns a 304 response with HTTP caching headers but is not cached itself.

        The test verifies that the view is called twice, and that the response contains Cache-Control and Expires headers, while also confirming that it returns an HttpResponseNotModified status. This ensures that the cache_page decorator behaves correctly when the underlying view returns a 304 status, balancing caching and freshness of responses.
        """
        original_view = mock.Mock(return_value=HttpResponseNotModified())
        view = cache_page(2)(original_view)
        request = self.factory.get("/view/")
        # The view shouldn't be cached on the second call.
        view(request).close()
        response = view(request)
        response.close()
        self.assertEqual(original_view.call_count, 2)
        self.assertIsInstance(response, HttpResponseNotModified)
        self.assertIn("Cache-Control", response)
        self.assertIn("Expires", response)

    def test_per_thread(self):
        """The cache instance is different for each thread."""
        thread_caches = []
        middleware = CacheMiddleware(empty_response)

        def runner():
            thread_caches.append(middleware.cache)

        for _ in range(2):
            thread = threading.Thread(target=runner)
            thread.start()
            thread.join()

        self.assertIsNot(thread_caches[0], thread_caches[1])

    def test_cache_control_max_age(self):
        view = cache_page(2)(hello_world_view)
        request = self.factory.get("/view/")

        # First request. Freshly created response gets returned with no Age
        # header.
        with mock.patch.object(
            time, "time", return_value=1468749600
        ):  # Sun, 17 Jul 2016 10:00:00 GMT
            response = view(request, 1)
            response.close()
            self.assertIn("Expires", response)
            self.assertEqual(response["Expires"], "Sun, 17 Jul 2016 10:00:02 GMT")
            self.assertIn("Cache-Control", response)
            self.assertEqual(response["Cache-Control"], "max-age=2")
            self.assertNotIn("Age", response)

        # Second request one second later. Response from the cache gets
        # returned with an Age header set to 1 (second).
        with mock.patch.object(
            time, "time", return_value=1468749601
        ):  # Sun, 17 Jul 2016 10:00:01 GMT
            response = view(request, 1)
            response.close()
            self.assertIn("Expires", response)
            self.assertEqual(response["Expires"], "Sun, 17 Jul 2016 10:00:02 GMT")
            self.assertIn("Cache-Control", response)
            self.assertEqual(response["Cache-Control"], "max-age=2")
            self.assertIn("Age", response)
            self.assertEqual(response["Age"], "1")


@override_settings(
    CACHE_MIDDLEWARE_KEY_PREFIX="settingsprefix",
    CACHE_MIDDLEWARE_SECONDS=1,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        },
    },
    USE_I18N=False,
)
class TestWithTemplateResponse(SimpleTestCase):
    """
    Tests various headers w/ TemplateResponse.

    Most are probably redundant since they manipulate the same object
    anyway but the ETag header is 'special' because it relies on the
    content being complete (which is not necessarily always the case
    with a TemplateResponse)
    """

    path = "/cache/test/"
    factory = RequestFactory()

    def tearDown(self):
        cache.clear()

    def test_patch_vary_headers(self):
        """

        Tests the functionality of the patch_vary_headers function to update the 'Vary' header in a response.

        This function validates the patch_vary_headers function with various test cases, 
        including scenarios where the initial 'Vary' header is set to None, contains 'Accept-Encoding', 
        'Cookie', or both, and checks if the resulting 'Vary' header matches the expected output after patching.

        The test cases cover different combinations of initial and new headers to ensure correct handling 
        of 'Vary' header updates in different situations.

        """
        headers = (
            # Initial vary, new headers, resulting vary.
            (None, ("Accept-Encoding",), "Accept-Encoding"),
            ("Accept-Encoding", ("accept-encoding",), "Accept-Encoding"),
            ("Accept-Encoding", ("ACCEPT-ENCODING",), "Accept-Encoding"),
            ("Cookie", ("Accept-Encoding",), "Cookie, Accept-Encoding"),
            (
                "Cookie, Accept-Encoding",
                ("Accept-Encoding",),
                "Cookie, Accept-Encoding",
            ),
            (
                "Cookie, Accept-Encoding",
                ("Accept-Encoding", "cookie"),
                "Cookie, Accept-Encoding",
            ),
            (None, ("Accept-Encoding", "COOKIE"), "Accept-Encoding, COOKIE"),
            (
                "Cookie,     Accept-Encoding",
                ("Accept-Encoding", "cookie"),
                "Cookie, Accept-Encoding",
            ),
            (
                "Cookie    ,     Accept-Encoding",
                ("Accept-Encoding", "cookie"),
                "Cookie, Accept-Encoding",
            ),
        )
        for initial_vary, newheaders, resulting_vary in headers:
            with self.subTest(initial_vary=initial_vary, newheaders=newheaders):
                template = engines["django"].from_string("This is a test")
                response = TemplateResponse(HttpRequest(), template)
                if initial_vary is not None:
                    response.headers["Vary"] = initial_vary
                patch_vary_headers(response, newheaders)
                self.assertEqual(response.headers["Vary"], resulting_vary)

    def test_get_cache_key(self):
        """

        Tests the functionality of getting and learning cache keys.

        The function tests the behavior of the get_cache_key function in different scenarios.
        It first checks if the cache key is None when it has not been learned yet.
        Then it teaches the function to learn the cache key from a request and response.
        It verifies that the learned cache key matches the expected value.
        Additionally, it tests the behavior when a custom key prefix is provided and checks that the learned cache key includes the prefix.

        """
        request = self.factory.get(self.path)
        template = engines["django"].from_string("This is a test")
        response = TemplateResponse(HttpRequest(), template)
        key_prefix = "localprefix"
        # Expect None if no headers have been set yet.
        self.assertIsNone(get_cache_key(request))
        # Set headers to an empty list.
        learn_cache_key(request, response)

        self.assertEqual(
            get_cache_key(request),
            "views.decorators.cache.cache_page.settingsprefix.GET."
            "58a0a05c8a5620f813686ff969c26853.d41d8cd98f00b204e9800998ecf8427e",
        )
        # A specified key_prefix is taken into account.
        learn_cache_key(request, response, key_prefix=key_prefix)
        self.assertEqual(
            get_cache_key(request, key_prefix=key_prefix),
            "views.decorators.cache.cache_page.localprefix.GET."
            "58a0a05c8a5620f813686ff969c26853.d41d8cd98f00b204e9800998ecf8427e",
        )

    def test_get_cache_key_with_query(self):
        """

        Tests the functionality of the get_cache_key function when a query string is present in the request.
        This test ensures that the cache key is generated correctly, taking into account the query string parameters.
        It validates that the cache key is initially None, then assigns a cache key using the learn_cache_key function,
        and finally asserts that the generated cache key matches the expected value.

        :raises AssertionError: If the generated cache key does not match the expected value.

        """
        request = self.factory.get(self.path, {"test": 1})
        template = engines["django"].from_string("This is a test")
        response = TemplateResponse(HttpRequest(), template)
        # Expect None if no headers have been set yet.
        self.assertIsNone(get_cache_key(request))
        # Set headers to an empty list.
        learn_cache_key(request, response)
        # The querystring is taken into account.
        self.assertEqual(
            get_cache_key(request),
            "views.decorators.cache.cache_page.settingsprefix.GET."
            "0f1c2d56633c943073c4569d9a9502fe.d41d8cd98f00b204e9800998ecf8427e",
        )


class TestMakeTemplateFragmentKey(SimpleTestCase):
    def test_without_vary_on(self):
        """
        Tests that a template fragment key is generated correctly without specifying a 'Vary On' parameter.

        The generated key is expected to be a combination of a prefix, the template name, and a hash value.

        Parameters: None

        Returns: None

        Raises: AssertionError if the generated key does not match the expected output.

        Note: This test case assumes that the make_template_fragment_key function is working correctly and is used to verify its output under specific conditions.
        """
        key = make_template_fragment_key("a.fragment")
        self.assertEqual(
            key, "template.cache.a.fragment.d41d8cd98f00b204e9800998ecf8427e"
        )

    def test_with_one_vary_on(self):
        """

        Test that a template fragment key is generated correctly when varying on a single value.

        This test case checks that the generated key matches the expected format and hash value
        when passed a template name and a list containing a single variation string.

        """
        key = make_template_fragment_key("foo", ["abc"])
        self.assertEqual(key, "template.cache.foo.493e283d571a73056196f1a68efd0f66")

    def test_with_many_vary_on(self):
        """
        Test that template fragment keys are generated correctly when varying on multiple values.

        This test ensures that the key generation process properly incorporates the provided values ('abc' and 'def') into the resulting cache key for a given template ('bar'). The test validates the expected output against a precomputed cache key, verifying that the generated key matches the expected format and content.
        """
        key = make_template_fragment_key("bar", ["abc", "def"])
        self.assertEqual(key, "template.cache.bar.17c1a507a0cb58384f4c639067a93520")

    def test_proper_escaping(self):
        key = make_template_fragment_key("spam", ["abc:def%"])
        self.assertEqual(key, "template.cache.spam.06c8ae8e8c430b69fb0a6443504153dc")

    def test_with_ints_vary_on(self):
        """
        Tests that the key generated by the make_template_fragment_key function for an integer list is correct. 
         The test verifies the key generated for the template fragment 'foo' with a list of integers [1, 2, 3, 4, 5] matches the expected key 'template.cache.foo.7ae8fd2e0d25d651c683bdeebdb29461'.
        """
        key = make_template_fragment_key("foo", [1, 2, 3, 4, 5])
        self.assertEqual(key, "template.cache.foo.7ae8fd2e0d25d651c683bdeebdb29461")

    def test_with_unicode_vary_on(self):
        """
        Tests the generation of a template fragment cache key when the key components contain Unicode characters.

         The test case verifies that the cache key is generated correctly when the cache key components include Unicode characters, such as degrees and emojis, and checks that the resulting key matches the expected key.
        """
        key = make_template_fragment_key("foo", ["42º", "😀"])
        self.assertEqual(key, "template.cache.foo.7ced1c94e543668590ba39b3c08b0237")

    def test_long_vary_on(self):
        """
        Tests that long vary_on strings are correctly hashed and truncated in template fragment keys.

        The function verifies that a long string passed to the vary_on parameter is properly processed
        and results in a predictable and consistent cache key, demonstrating the function's ability
        to handle large inputs without errors or inconsistencies in cache key generation.
        """
        key = make_template_fragment_key("foo", ["x" * 10000])
        self.assertEqual(key, "template.cache.foo.3670b349b5124aa56bdb50678b02b23a")


class CacheHandlerTest(SimpleTestCase):
    def test_same_instance(self):
        """
        Attempting to retrieve the same alias should yield the same instance.
        """
        cache1 = caches["default"]
        cache2 = caches["default"]

        self.assertIs(cache1, cache2)

    def test_per_thread(self):
        """
        Requesting the same alias from separate threads should yield separate
        instances.
        """
        c = []

        def runner():
            c.append(caches["default"])

        for x in range(2):
            t = threading.Thread(target=runner)
            t.start()
            t.join()

        self.assertIsNot(c[0], c[1])

    def test_nonexistent_alias(self):
        """
        Tests that accessing a non-existent cache alias raises an InvalidCacheBackendError.

        This test case checks the system's behavior when attempting to retrieve a cache connection
        that does not exist, verifying that it correctly identifies and reports the issue.

        The expected exception, InvalidCacheBackendError, is raised with a message indicating
        that the specified connection does not exist. This ensures that the system handles
        non-existent cache aliases robustly and provides clear error messages to aid in debugging.
        """
        msg = "The connection 'nonexistent' doesn't exist."
        with self.assertRaisesMessage(InvalidCacheBackendError, msg):
            caches["nonexistent"]

    def test_nonexistent_backend(self):
        test_caches = CacheHandler(
            {
                "invalid_backend": {
                    "BACKEND": "django.nonexistent.NonexistentBackend",
                },
            }
        )
        msg = (
            "Could not find backend 'django.nonexistent.NonexistentBackend': "
            "No module named 'django.nonexistent'"
        )
        with self.assertRaisesMessage(InvalidCacheBackendError, msg):
            test_caches["invalid_backend"]

    def test_all(self):
        """

        Tests the retrieval of all caches from the CacheHandler.

        This function verifies that the all() method returns the correct list of caches, 
        both when filtering for initialized caches and when including all caches.

        It checks the following cases:
        - An empty list is returned when no caches are initialized.
        - A list containing the initialized cache is returned when initialized_only=True.
        - The total number of caches is correctly reported when initialized_only=False.
        - The list of initialized caches is equal to the total list of caches when all caches are initialized.

        """
        test_caches = CacheHandler(
            {
                "cache_1": {
                    "BACKEND": "django.core.cache.backends.dummy.DummyCache",
                },
                "cache_2": {
                    "BACKEND": "django.core.cache.backends.dummy.DummyCache",
                },
            }
        )
        self.assertEqual(test_caches.all(initialized_only=True), [])
        cache_1 = test_caches["cache_1"]
        self.assertEqual(test_caches.all(initialized_only=True), [cache_1])
        self.assertEqual(len(test_caches.all()), 2)
        # .all() initializes all caches.
        self.assertEqual(len(test_caches.all(initialized_only=True)), 2)
        self.assertEqual(test_caches.all(), test_caches.all(initialized_only=True))
