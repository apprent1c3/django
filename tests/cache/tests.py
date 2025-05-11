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
        """
        Test that cache deletion is handled correctly on a dummy cache backend, 
        verifying that deletion operations are effectively ignored and do not affect 
        subsequent cache retrieval operations.
        """
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
        """
        Tests that attempting to increment a dummy cache value or a non-existent value raises a ValueError.
        """
        cache.set("answer", 42)
        with self.assertRaises(ValueError):
            cache.incr("answer")
        with self.assertRaises(ValueError):
            cache.incr("does_not_exist")
        with self.assertRaises(ValueError):
            cache.incr("does_not_exist", -1)

    def test_decr(self):
        """
        Checks that attempting to decrement non-numeric or non-existent cache values raises a ValueError.
        """
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
        """
        Tests that the dummy cache ignores all supported data types, ensuring no values are stored or retrieved.
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
                self.assertIsNone(cache.get(key))

    def test_expiration(self):
        """
        Tests the expiration behavior of the cache, verifying that expired keys are properly removed and cannot be retrieved or updated.
        """
        cache.set("expire1", "very quickly", 1)
        cache.set("expire2", "very quickly", 1)
        cache.set("expire3", "very quickly", 1)

        time.sleep(2)
        self.assertIsNone(cache.get("expire1"))

        self.assertIs(cache.add("expire2", "newvalue"), True)
        self.assertIsNone(cache.get("expire2"))
        self.assertIs(cache.has_key("expire3"), False)

    def test_unicode(self):
        """

        Tests the behavior of the dummy cache when storing and retrieving keys and values 
        that contain Unicode characters, verifying that Unicode values are ignored.

        """
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
        msg = KEY_ERRORS_WITH_MEMCACHED_MSG % ":1:key with spaces"
        with self.assertWarnsMessage(CacheKeyWarning, msg):
            cache.set_many({"key with spaces": "foo"})

    def test_delete_many(self):
        "delete_many does nothing for the dummy cache backend"
        cache.delete_many(["a", "b"])

    def test_delete_many_invalid_key(self):
        msg = KEY_ERRORS_WITH_MEMCACHED_MSG % ":1:key with spaces"
        with self.assertWarnsMessage(CacheKeyWarning, msg):
            cache.delete_many(["key with spaces"])

    def test_clear(self):
        "clear does nothing for the dummy cache backend"
        cache.clear()

    def test_incr_version(self):
        """
        Tests that attempting to increment the version of a dummy cache or a non-existent cache raises a ValueError.
        """
        cache.set("answer", 42)
        with self.assertRaises(ValueError):
            cache.incr_version("answer")
        with self.assertRaises(ValueError):
            cache.incr_version("does_not_exist")

    def test_decr_version(self):
        """
        Tests that decrementing the version of a dummy cache or non-existent cache entry raises a ValueError.
        """
        cache.set("answer", 42)
        with self.assertRaises(ValueError):
            cache.decr_version("answer")
        with self.assertRaises(ValueError):
            cache.decr_version("does_not_exist")

    def test_get_or_set(self):
        self.assertEqual(cache.get_or_set("mykey", "default"), "default")
        self.assertIsNone(cache.get_or_set("mykey", None))

    def test_get_or_set_callable(self):
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
    """
    Generates a cache setting dictionary for testing purposes, 
    customizable via a base setting and parameters, with optional exclusion of certain cache settings.
    """
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
        cache.set("key", "value")
        self.assertEqual(cache.get("key"), "value")

    def test_default_used_when_none_is_set(self):
        """If None is cached, get() returns it instead of the default."""
        cache.set("key_default_none", None)
        self.assertIsNone(cache.get("key_default_none", default="default"))

    def test_add(self):
        # A key can be added to a cache
        self.assertIs(cache.add("addkey1", "value"), True)
        self.assertIs(cache.add("addkey1", "newvalue"), False)
        self.assertEqual(cache.get("addkey1"), "value")

    def test_prefix(self):
        # Test for same cache key conflicts between shared backend
        """

        Tests that cache values with and without the specified prefix do not interfere with each other.
        Verifies that setting and getting cache values with a prefix maintains separate storage from the main cache.

        """
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
        """

        Tests the retrieval of multiple values from the cache.

        Verifies that the function returns the expected values for existing keys and
        omits non-existent keys from the result. Also checks that the function works
        with both lists and iterators as input, and that it correctly handles keys
        with None values.

        """
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
        """
        Deletes a key from the cache and verifies the deletion was successful.
        """
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
        Checks if the cache contains a key, regardless of its value or expiration time.
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
        """
        Checks the functionality of storing and retrieving items in the cache, ensuring that set keys can be found and non-set keys cannot, including handling of null values.
        """
        cache.set("hello2", "goodbye2")
        self.assertIn("hello2", cache)
        self.assertNotIn("goodbye2", cache)
        cache.set("null", None)
        self.assertIn("null", cache)

    def test_incr(self):
        # Cache values can be incremented
        """

        Tests the increment functionality of the cache.

        Verifies that incrementing a cached value by default and by a specified amount
        returns the expected result, and that the cache is updated accordingly.
        Also tests error handling for non-existent keys and incompatible value types.

        """
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

        Tests the decrement functionality of the cache.

        Verifies that values can be decremented by a specified amount, and that 
        attempting to decrement a non-existent or invalid value raises an error.

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
        self.assertTrue(hasattr(cache, "close"))
        cache.close()

    def test_data_types(self):
        # Many different data types can be cached
        """
        Tests the caching functionality with various data types.

        Verifies that a cache can store and retrieve values of different types, including
        strings, integers, booleans, lists, tuples, dictionaries, functions, and classes.
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

        Tests that a model instance can be successfully cached and read from the cache.

        Verifies that the instance's attributes are preserved and that an expensive calculation 
        associated with the instance is only performed once, when the instance is first retrieved.

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
        """
        Tests the cache writing functionality for a model instance with deferred fields, ensuring that the cache is properly populated without invoking unnecessary calculations.
        """
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
        """

        Tests that reading a model instance with deferred fields from the cache does not trigger an expensive calculation.

        Verifies that the cache effectively bypasses the database query and expensive calculation when retrieving a deferred queryset.

        """
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

        Verifies that cached items are properly removed after their expiration time has passed,
        and that subsequent operations behave as expected on expired items.
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
        """
        Tests the touch method of the cache by setting keys with timeouts and verifying whether they are still accessible after the timeout has been extended or expired.
        """
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
        Tests the cache functionality with various keys and values, including those containing ASCII and Unicode characters, to ensure proper storage, retrieval, and deletion.
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
        """
        Tests the functionality of storing and retrieving binary strings in the cache, ensuring that compressed and decompressed values are correctly stored and retrieved using various cache methods.
        """
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
        cache.set_many({"key1": "spam", "key2": "eggs"})
        self.assertEqual(cache.get("key1"), "spam")
        self.assertEqual(cache.get("key2"), "eggs")

    def test_set_many_returns_empty_list_on_success(self):
        """set_many() returns an empty list when all keys are inserted."""
        failing_keys = cache.set_many({"key1": "spam", "key2": "eggs"})
        self.assertEqual(failing_keys, [])

    def test_set_many_expiration(self):
        # set_many takes a second ``timeout`` parameter
        cache.set_many({"key1": "spam", "key2": "eggs"}, 1)
        time.sleep(2)
        self.assertIsNone(cache.get("key1"))
        self.assertIsNone(cache.get("key2"))

    def test_set_many_empty_data(self):
        self.assertEqual(cache.set_many({}), [])

    def test_delete_many(self):
        # Multiple keys can be deleted using delete_many
        """
        Deletes multiple keys from the cache and verifies the deletion.
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
        cache.set_many({"key1": "spam", "key2": "eggs"})
        cache.clear()
        self.assertIsNone(cache.get("key1"))
        self.assertIsNone(cache.get("key2"))

    def test_long_timeout(self):
        """
        Tests cache expiration behavior when timeout exceeds 30 days, adhering to memcached's convention of treating such timeouts as absolute expiration timestamps.
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
        Tests the behavior of the cache when a timeout of None is used, 
        verifying that cache items are cached forever and not expired.
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
        Verifies that caching with a timeout of zero results in no caching, ensuring that values are not stored or retrieved.
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
        Perform culling test on a given cache.

        Checks if a cache is properly culling items, verifying that the number of items
        remaining after culling matches the expected final count. The test does this by
        first populating the cache with a set of items, then checking how many of those
        items are still present after the cache has had a chance to cull them.

        :param cull_cache_name: Name of the cache to test.
        :param initial_count: Number of items to initially populate the cache with.
        :param final_count: Expected number of items remaining after culling.

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
        Tests cache culling behavior when the cache store is empty, specifically 
        verifying that a cache entry can still be added and retrieved even when 
        culling is enabled with no maximum entries limit.
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
        Checks that the cache backends correctly handle and warn about invalid cache keys, 
        ensuring portable caching code without restrictions from more liberal key rules.
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
        Checks if a cache key exceeds the maximum length supported by memcached when a version key is appended, triggering a warning if the length exceeds 250 characters.
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
        """
        Tests the functionality of cache versioning for the get and set operations, ensuring that data stored under different versions is correctly retrieved and distinguished between different cache versions.
        """
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
        """
        Tests the functionality of cache versioning, ensuring that different versions of cache can coexist and be updated independently, and that adding a new version of a cached item does not affect existing versions.
        """
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
        Tests the has_key functionality of the cache with versioning.

        Verifies that keys are correctly identified as present or absent in the cache,
        regardless of version, and that version-specific checks work as expected.
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

        Tests the deletion of cache entries with versioning, ensuring that the correct version
        is removed and that other versions of the same key remain intact.

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
        """
        Tests cache versioning with increment and decrement operations.

        Verifies that increment and decrement operations are performed correctly
        across different cache versions, ensuring that each version's value is
        updated independently and that the correct value is retrieved for each version.
        """
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
        Tests the behavior of setting and retrieving multiple cache values with versioning, ensuring that cache keys are correctly stored and retrieved across different versions, and that cache values are not inadvertently shared between versions.
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

        Tests the cache versioning system, ensuring that values are correctly stored and retrieved
        with specific versions, and that incrementing the version of a key replaces the old value
        with the new one.

        Checks that getting a value with the wrong version returns None, and that incrementing the
        version of a non-existent key raises a ValueError.

        Verifies that incrementing the version of a key that has a value of None also correctly
        increments the version and retrieves the value.

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
        """
        Decrements the version of a cached item, effectively removing the current version of the item while preserving previous versions. 

        This function tests the functionality of the cache's version decrement operation, ensuring it handles both existing and non-existent items, as well as the edge case of a null cached value.
        """
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
        Tests the functionality of a cache with custom key functions, ensuring that 
        keys generated by different functions store and retrieve values independently.
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

        Tests that the cache middleware can write and retrieve an HTTP response with an unpicklable object, such as a cookie.

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
        with self.assertRaises(pickle.PickleError):
            cache.set("unpicklable", Unpicklable())

    def test_get_or_set(self):
        """
        Checks the behavior of retrieving or setting a value in the cache, ensuring that it correctly handles initial and subsequent retrievals, as well as setting a value when it does not exist.
        """
        self.assertIsNone(cache.get("projector"))
        self.assertEqual(cache.get_or_set("projector", 42), 42)
        self.assertEqual(cache.get("projector"), 42)
        self.assertIsNone(cache.get_or_set("null", None))
        # Previous get_or_set() stores None in the cache.
        self.assertIsNone(cache.get("null", "default"))

    def test_get_or_set_callable(self):
        """
        Tests the functionality of get_or_set method for callable values and handles cached results correctly, ensuring the callable is invoked when the key is not in the cache and its result is stored for future use.
        """
        def my_callable():
            return "value"

        self.assertEqual(cache.get_or_set("mykey", my_callable), "value")
        self.assertEqual(cache.get_or_set("mykey", my_callable()), "value")

        self.assertIsNone(cache.get_or_set("null", lambda: None))
        # Previous get_or_set() stores None in the cache.
        self.assertIsNone(cache.get("null", "default"))

    def test_get_or_set_version(self):
        """
        Tests the functionality of get_or_set method in cache, 
        including its ability to handle different versions, 
        required arguments, and correct raise of exceptions.
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
        super().setUp()
        self.create_table()
        self.addCleanup(self.drop_table)

    def create_table(self):
        management.call_command("createcachetable", verbosity=0)

    def drop_table(self):
        with connection.cursor() as cursor:
            table_name = connection.ops.quote_name("test cache table")
            cursor.execute("DROP TABLE %s" % table_name)

    def test_get_many_num_queries(self):
        """
        Tests the get_many method of the cache, specifically its behavior 
        with regards to query optimization and cache expiration.
        """
        cache.set_many({"a": 1, "b": 2})
        cache.set("expired", "expired", 0.01)
        with self.assertNumQueries(1):
            self.assertEqual(cache.get_many(["a", "b"]), {"a": 1, "b": 2})
        time.sleep(0.02)
        with self.assertNumQueries(2):
            self.assertEqual(cache.get_many(["a", "b", "expired"]), {"a": 1, "b": 2})

    def test_delete_many_num_queries(self):
        cache.set_many({"a": 1, "b": 2, "c": 3})
        with self.assertNumQueries(1):
            cache.delete_many(["a", "b", "c"])

    def test_cull_queries(self):
        """
        Tests the cull queries mechanism in the cache system.

        Verifies that culling the cache correctly executes a single count query and properly quotes table column names.

        This test ensures the cache culling mechanism works as expected, maintaining data consistency and preventing potential SQL syntax errors.
        """
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
        Tests that cache delete doesn't raise an exception when trying to access the rowcount attribute on a closed cursor.
        """

        class MockedCursorWrapper(CursorWrapper):
            is_closed = False

            def close(self):
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
        Tests the creation of a cache table using the createcachetable command with the explicit table name argument, verifying the expected output.
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
        Tests that the has_key method of the cache includes quoted column names in its SQL query. Verifies that the query includes the 'expires' and 'cache_key' columns, and that only one query is executed.
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
        Tests if the createcachetable command observes the database router configuration, 
        verifying that it correctly creates cache tables in the specified databases without 
        executing unnecessary queries.
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
        self.cache = cache
        self.locked = False

    def __getstate__(self):
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

        Sets up caches for testing purposes by mirroring the main cache to various prefixes.

        This ensures that the test environment has access to a consistent cache state across different cache prefixes, including 'prefix', 'v2', 'custom_key', and 'custom_key2'.

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
        """
        Tests that cache operations are performed without acquiring a lock when pickling occurs, ensuring thread safety and preventing potential deadlocks.
        """
        bad_obj = PicklingSideEffect(cache)
        cache.set("set", bad_obj)
        self.assertFalse(bad_obj.locked, "Cache was locked during pickling")

        self.assertIs(cache.add("add", bad_obj), True)
        self.assertFalse(bad_obj.locked, "Cache was locked during pickling")

    def test_incr_decr_timeout(self):
        """
        Verifies that the increment and decrement operations do not modify the expiry time of a cached value, mirroring the behavior of memcached.
        """
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
        """
        Checks if cache entries are correctly moved to the end of the LRU order when retrieved, ensuring the least recently used items are evicted first.
        """
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
        """
        Tests the behavior of the cache's least recently used (LRU) eviction policy, verifying that set() operations update key access times and that expired or evicted keys are correctly removed from the cache.
        """
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
        """

        Verifies the correct functionality of the cache's increment operation (incr) and its impact on least-recently-used (LRU) cache key ordering.

        """
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
        """
        Tests the LOCATION parameter of the cache backend when provided in different formats, 
        ensuring it correctly parses multiple server addresses and updates the cache server list accordingly.
        """
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
        Performs tests for invalid cache keys, verifying that memcached raises an 
        exception for invalid keys instead of merely issuing a warning, as other 
        backends do.
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
        Checks that a failed set operation in memcached due to value size limits results in the key being deleted from the cache.
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
        Tests if the database connections are properly closed after a request is finished. Verifies that the disconnect_all method is called when expected, based on the should_disconnect_on_close flag.
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
        Tests that cache.set_many correctly identifies and returns the keys that fail when setting multiple values.
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
        Tests that pylibmc client correctly parses server locations from various input formats.
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
        Test that the highest pickle protocol is used for serialization in pymemcache clients.

        Verifies that the default pickle version for the cache and all cache clients is set to the highest available protocol, ensuring optimal compatibility and performance.
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
        Sets up the test environment by creating a temporary directory and configuring the cache locations in the settings to use this directory, then sends a signal to notify that the CACHES setting has changed.
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
        """
        Verifies that cache.clear() does not remove non-cache files, ensuring data integrity by ignoring files outside of cache management.
        """
        fname = os.path.join(self.dirname, "not-a-cache-file")
        with open(fname, "w"):
            os.utime(fname, None)
        cache.clear()
        self.assertTrue(
            os.path.exists(fname), "Expected cache.clear to ignore non cache files"
        )
        os.remove(fname)

    def test_clear_does_not_remove_cache_dir(self):
        cache.clear()
        self.assertTrue(
            os.path.exists(self.dirname), "Expected cache.clear to keep the cache dir"
        )

    def test_creates_cache_dir_if_nonexistent(self):
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

        Test the permissions of the cache directory.

        Verifies that the cache directory and its parents are created with the correct permissions 
        when the cache is set. The function simulates setting the cache and checks the permissions 
        of the cache directory and its parents to ensure they match the expected value.

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
        with mock.patch("builtins.open", side_effect=OSError):
            with self.assertRaises(OSError):
                cache.get("foo")

    def test_empty_cache_file_considered_expired(self):
        """
        Checks if an empty cache file is considered expired, ensuring that a cache entry with no data is not treated as valid.
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
        """
        Tests the touch functionality by manually advancing time to account for delays in file access.\"
        """

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

        Tests the get_backend_timeout method to ensure it correctly handles different input timeout values.

        The method is expected to return the input timeout when it is a positive integer, 0 when the input timeout is negative, and None when the input timeout is None.

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
        """
        Tests the retrieval of a connection pool index, verifying it returns 0 for write operations and a valid index for read operations based on the number of available servers.
        """
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
        pool = cache._cache._get_connection_pool(write=False)
        self.assertEqual(pool.connection_kwargs["db"], 5)
        self.assertEqual(pool.connection_kwargs["socket_timeout"], 0.1)
        self.assertIs(pool.connection_kwargs["retry_on_timeout"], True)


class FileBasedCachePathLibTests(FileBasedCacheTests):
    def mkdtemp(self):
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
        """
        Tests that when the TIMEOUT parameter is unset in memory caches, cache keys are set with the default 5 minute timeout.
        """
        key = "my-key"
        value = "my-value"
        cache = caches[DEFAULT_CACHE_ALIAS]
        cache.set(key, value)
        cache_key = cache.make_key(key)
        self.assertIsNotNone(cache._expire_info[cache_key])

    @override_settings(CACHES=NEVER_EXPIRING_CACHES_SETTINGS)
    def test_caches_set_with_timeout_as_none_set_non_expiring_key(self):
        """
        Tests if a cache with a timeout set to None stores keys without an expiration time.
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
        """

        Test the patch_vary_headers function to ensure it correctly updates the Vary header
        in HTTP responses based on the initial Vary value and new headers.

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
        Tests the functionality of getting and learning cache keys for HTTP requests, 
        including setting a custom key prefix and verifying cache key generation matches expected output.
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

        Tests the behavior of the get_cache_key function when a query is present in the request.

        Verifies that the cache key is initially None, then updated correctly after learning from a response.

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
        Tests that the cache key generation varies based on the fully-qualified URL, ensuring different cache keys are produced for the same path but different hostnames.
        """
        request1 = self.factory.get(self.path, headers={"host": "sub-1.example.com"})
        learn_cache_key(request1, HttpResponse())
        request2 = self.factory.get(self.path, headers={"host": "sub-2.example.com"})
        learn_cache_key(request2, HttpResponse())
        self.assertNotEqual(get_cache_key(request1), get_cache_key(request2))

    def test_learn_cache_key(self):
        """
        Tests the functionality of the learn_cache_key function by simulating a HEAD request and checking if the generated cache key matches the expected value.
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
        """

        Tests the functionality of patching Cache-Control headers in an HTTP response.

        The function verifies that the patch_cache_control function correctly updates the Cache-Control header
        of an HttpResponse object based on the provided initial Cache-Control value and new headers to apply.

        """
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
        Verifies that the cache is correctly updated and retrieved for HEAD requests.
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
        Tests that a HEAD request retrieves cached data from a previous GET request, ensuring cache middleware correctly handles requests and provides cached content when available.
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
        Tests that cache keys include the language name when internationalization is enabled.
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
        Checks if the cache key is correctly generated based on the Accept-Language header and Vary response header.

        :param str accept_language: The value of the Accept-Language header.
        :param str vary: The value of the Vary response header.
        :param str reference_key: The expected cache key.

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
        """
        Tests that the cache key includes language information when internationalization is enabled and the request contains an Accept-Language header. Verifies that cache keys are correctly generated for various Accept-Language header values, ensuring proper cache behavior with internationalization.
        """
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

        Tests that cache keys include the current timezone when timezones are active.

        Verifies the correctness of cache key generation by comparing the keys generated
        using `learn_cache_key` and `get_cache_key` functions, ensuring they include the
        current timezone name.

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
        """
        Tests that cache key generation excludes language and time zone information when internationalization is disabled.
        """
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

        Tests the behavior of cache middleware under various conditions, including 
        cache hits and misses, query string changes, and internationalization support.

        Specifically, this test case covers:

        * Cache miss when no cache entry exists for a given request
        * Cache hit when a cache entry exists for a given request
        * Cache invalidation when a query string changes
        * Cache behavior with internationalization enabled, including language-specific cache entries

        """
        def set_cache(request, lang, msg):
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
        Tests that the middleware correctly handles streaming responses by not caching them, ensuring that content is not stored in the cache when a streaming response is encountered.
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
        self.default_cache = caches["default"]
        self.addCleanup(self.default_cache.clear)
        self.other_cache = caches["other"]
        self.addCleanup(self.other_cache.clear)

    def test_constructor(self):
        """
        Tests that the CacheMiddleware constructor correctly initializes its attributes based on its usage as either middleware or a view decorator.
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

        Tests the constructor of UpdateCacheMiddleware, verifying the default values
        of cache timeout, page timeout, key prefix, cache alias, and cache instance.

        """
        middleware = UpdateCacheMiddleware(empty_response)
        self.assertEqual(middleware.cache_timeout, 30)
        self.assertIsNone(middleware.page_timeout)
        self.assertEqual(middleware.key_prefix, "middlewareprefix")
        self.assertEqual(middleware.cache_alias, "other")
        self.assertEqual(middleware.cache, self.other_cache)

    def test_fetch_cache_middleware_constructor(self):
        middleware = FetchFromCacheMiddleware(empty_response)
        self.assertEqual(middleware.key_prefix, "middlewareprefix")
        self.assertEqual(middleware.cache_alias, "other")
        self.assertEqual(middleware.cache, self.other_cache)

    def test_middleware(self):
        """

        Tests the functionality of the CacheMiddleware class.

        This test case verifies that the CacheMiddleware correctly handles caching
        of view responses, including cases with and without a key prefix and cache timeout.

        """
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
        Tests the behavior of the cache_page decorator with various cache settings and prefixes, ensuring that it correctly caches and retrieves view responses based on the provided parameters.
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
        Tests the behavior of caching pages with varying timeouts, ensuring that the cache is updated correctly when the specified timeouts are exceeded.
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
        """
        Tests that views with 'Cache-Control: private' headers are not cached by checking that subsequent requests return different responses.
        """
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

        Tests that Django does not cache responses containing security-sensitive cookies 
        set in response to a cookie-less request, ensuring user-specific data remains private.

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
        Verifies that a page view with a 304 response has appropriate HTTP caching headers but is not themselves cached, ensuring proper cache control and headers for responses indicating the resource hasn't been modified.
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
        """
        Verifies that the cache instance is unique to each thread, ensuring thread safety by preventing cache collisions between concurrent threads.
        """
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
        """

        Tests the Cache-Control max-age header and Expires header when using the cache_page decorator.
        Verifies that the Cache-Control max-age header is correctly set and the Age header is updated 
        as time passes, ensuring proper cache expiration and validation.

        """
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
        Tests the functionality of patch_vary_headers by verifying its effect on the Vary header of a response object, considering various initial values and new headers.
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

        Tests the functionality of cache key generation for a given HTTP request and response.

        Verifies that the cache key is correctly learned and generated with and without a custom key prefix.

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
        Tests the process of learning and retrieving a cache key for a given request, 
         ensuring that the cache key is generated correctly after the response has been processed.
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
        key = make_template_fragment_key("a.fragment")
        self.assertEqual(
            key, "template.cache.a.fragment.d41d8cd98f00b204e9800998ecf8427e"
        )

    def test_with_one_vary_on(self):
        key = make_template_fragment_key("foo", ["abc"])
        self.assertEqual(key, "template.cache.foo.493e283d571a73056196f1a68efd0f66")

    def test_with_many_vary_on(self):
        key = make_template_fragment_key("bar", ["abc", "def"])
        self.assertEqual(key, "template.cache.bar.17c1a507a0cb58384f4c639067a93520")

    def test_proper_escaping(self):
        key = make_template_fragment_key("spam", ["abc:def%"])
        self.assertEqual(key, "template.cache.spam.06c8ae8e8c430b69fb0a6443504153dc")

    def test_with_ints_vary_on(self):
        key = make_template_fragment_key("foo", [1, 2, 3, 4, 5])
        self.assertEqual(key, "template.cache.foo.7ae8fd2e0d25d651c683bdeebdb29461")

    def test_with_unicode_vary_on(self):
        key = make_template_fragment_key("foo", ["42º", "😀"])
        self.assertEqual(key, "template.cache.foo.7ced1c94e543668590ba39b3c08b0237")

    def test_long_vary_on(self):
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
        Verifies that requesting the same alias from separate threads yields distinct instances, ensuring thread safety.
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

        Tests the functionality of retrieving all caches handled by the CacheHandler.

        Verifies that the all() method correctly returns caches, including scenarios 
        where caches are initialized or not, and with the initialized_only parameter.

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
