import base64
import os
import shutil
import string
import tempfile
import unittest
from datetime import timedelta
from http import cookies
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase, UpdateError
from django.contrib.sessions.backends.cache import SessionStore as CacheSession
from django.contrib.sessions.backends.cached_db import SessionStore as CacheDBSession
from django.contrib.sessions.backends.db import SessionStore as DatabaseSession
from django.contrib.sessions.backends.file import SessionStore as FileSession
from django.contrib.sessions.backends.signed_cookies import (
    SessionStore as CookieSession,
)
from django.contrib.sessions.exceptions import InvalidSessionKey, SessionInterrupted
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sessions.models import Session
from django.contrib.sessions.serializers import JSONSerializer
from django.core import management
from django.core.cache import caches
from django.core.cache.backends.base import InvalidCacheBackendError
from django.core.exceptions import ImproperlyConfigured
from django.core.signing import TimestampSigner
from django.http import HttpResponse
from django.test import (
    RequestFactory,
    SimpleTestCase,
    TestCase,
    ignore_warnings,
    override_settings,
)
from django.utils import timezone

from .models import SessionStore as CustomDatabaseSession


class SessionTestsMixin:
    # This does not inherit from TestCase to avoid any tests being run with this
    # class, which wouldn't work, and to allow different TestCase subclasses to
    # be used.

    backend = None  # subclasses must specify

    def setUp(self):
        self.session = self.backend()
        # NB: be careful to delete any sessions created; stale sessions fill up
        # the /tmp (with some backends) and eventually overwhelm it after lots
        # of runs (think buildbots)
        self.addCleanup(self.session.delete)

    def test_new_session(self):
        self.assertIs(self.session.modified, False)
        self.assertIs(self.session.accessed, False)

    def test_get_empty(self):
        self.assertIsNone(self.session.get("cat"))

    async def test_get_empty_async(self):
        self.assertIsNone(await self.session.aget("cat"))

    def test_store(self):
        """

        Tests the basic functionality of storing and retrieving data from the session.

        Verifies that the session is correctly modified when a new key-value pair is added,
        and that the stored value can be successfully retrieved and removed using the pop method.

        """
        self.session["cat"] = "dog"
        self.assertIs(self.session.modified, True)
        self.assertEqual(self.session.pop("cat"), "dog")

    async def test_store_async(self):
        """

        Tests the asynchronous functionality of storing and retrieving data from a session.

        This test case verifies that data can be successfully stored and retrieved using the 
        asynchronous methods of the session object. It checks that the session is marked as 
        modified after storing data and that the stored data can be correctly retrieved.

        """
        await self.session.aset("cat", "dog")
        self.assertIs(self.session.modified, True)
        self.assertEqual(await self.session.apop("cat"), "dog")

    def test_pop(self):
        """

        Tests the functionality of popping a key from the session dictionary.

        This test case verifies that the pop method correctly removes the specified key
        from the session and returns its associated value. It also checks that the 
        session's accessed and modified flags are set to True after popping a key, 
        and that the key is no longer present in the session after being popped.

        """
        self.session["some key"] = "exists"
        # Need to reset these to pretend we haven't accessed it:
        self.accessed = False
        self.modified = False

        self.assertEqual(self.session.pop("some key"), "exists")
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertIsNone(self.session.get("some key"))

    async def test_pop_async(self):
        """
        Tests the asynchronous pop operation on a session.

        The test sets a value for a given key, then removes and retrieves the value using the apop method.
        It verifies that the removed value matches the original value, and that the session's accessed and
        modified flags are set to True after the pop operation. Finally, it checks that the key is no longer
        present in the session by retrieving its value, which should be None.

        This test ensures that the apop method functions correctly in an asynchronous context, and that the
        session's state is updated accordingly after the operation.
        """
        await self.session.aset("some key", "exists")
        # Need to reset these to pretend we haven't accessed it:
        self.accessed = False
        self.modified = False

        self.assertEqual(await self.session.apop("some key"), "exists")
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertIsNone(await self.session.aget("some key"))

    def test_pop_default(self):
        """
        Tests the pop method of a session when a key is not present.

        This test checks that the default value provided is returned when a key does not exist in the session.
        It also verifies that accessing a non-existent key sets the session as accessed but not modified.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the expected default value is not returned or if the session's accessed or modified status is incorrect.

        """
        self.assertEqual(
            self.session.pop("some key", "does not exist"), "does not exist"
        )
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_pop_default_async(self):
        """

        Tests asynchronous pop operation with default value.

        Verifies that when a key does not exist in the session, the default value is returned.
        Additionally, checks that the accessed flag is set to True after the operation, while the modified flag remains False.

        """
        self.assertEqual(
            await self.session.apop("some key", "does not exist"), "does not exist"
        )
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_pop_default_named_argument(self):
        self.assertEqual(
            self.session.pop("some key", default="does not exist"), "does not exist"
        )
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_pop_default_named_argument_async(self):
        self.assertEqual(
            await self.session.apop("some key", default="does not exist"),
            "does not exist",
        )
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_pop_no_default_keyerror_raised(self):
        """

        Tests that popping a key from the session that does not exist raises a KeyError.

        Verifies that when attempting to remove a key that is not present in the session,
        the expected KeyError exception is raised, indicating that the key is not found.

        """
        with self.assertRaises(KeyError):
            self.session.pop("some key")

    async def test_pop_no_default_keyerror_raised_async(self):
        with self.assertRaises(KeyError):
            await self.session.apop("some key")

    def test_setdefault(self):
        self.assertEqual(self.session.setdefault("foo", "bar"), "bar")
        self.assertEqual(self.session.setdefault("foo", "baz"), "bar")
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)

    async def test_setdefault_async(self):
        self.assertEqual(await self.session.asetdefault("foo", "bar"), "bar")
        self.assertEqual(await self.session.asetdefault("foo", "baz"), "bar")
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)

    def test_update(self):
        """
        Tests the update functionality of the session object.

        Verifies that updating a key-value pair in the session correctly sets the accessed and modified flags, 
        and that the updated value can be successfully retrieved from the session.

        Checks the following conditions:
        - The session is marked as accessed after updating.
        - The session is marked as modified after updating.
        - The updated value is correctly stored in the session.

        Ensures the session's update mechanism is functioning as expected, allowing for reliable storage and retrieval of data.
        """
        self.session.update({"update key": 1})
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertEqual(self.session.get("update key", None), 1)

    async def test_update_async(self):
        """
        Tests the asynchronous update functionality of a session.

        Verifies that an asynchronous update operation successfully modifies the session,
        updates the accessed and modified status, and stores the updated value correctly.

        Upon successful execution, this test confirms that the session's state is updated
        correctly after an asynchronous update, and that the updated value can be retrieved
        later using an asynchronous get operation.
        """
        await self.session.aupdate({"update key": 1})
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertEqual(await self.session.aget("update key", None), 1)

    def test_has_key(self):
        """

        Tests that the session dict has a key after it is set.

        This function sets a value for a key in the session dictionary, 
        then checks if the key is present and if the session's accessed 
        and modified flags are updated correctly. Specifically, it 
        verifies that the key is in the session and that the accessed 
        flag is True, while the modified flag remains False.

        """
        self.session["some key"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertIn("some key", self.session)
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_has_key_async(self):
        await self.session.aset("some key", 1)
        self.session.modified = False
        self.session.accessed = False
        self.assertIs(await self.session.ahas_key("some key"), True)
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_values(self):
        """

        Tests the behavior of session values.

        This test case verifies the following scenarios:
        - That a new session has no values.
        - That accessing a session sets the 'accessed' flag to True.
        - That setting a value in a session does not modify the 'modified' flag when it is explicitly set to False.
        - That the 'accessed' flag is set to True after a value is retrieved from the session.

        """
        self.assertEqual(list(self.session.values()), [])
        self.assertIs(self.session.accessed, True)
        self.session["some key"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.values()), [1])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_values_async(self):
        self.assertEqual(list(await self.session.avalues()), [])
        self.assertIs(self.session.accessed, True)
        await self.session.aset("some key", 1)
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(await self.session.avalues()), [1])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_keys(self):
        """

        Tests the functionality of the session's keys method.

        Verifies that the method returns the expected keys and that accessing the keys
        modifies the session's accessed state, but does not affect its modified state.

        This test ensures that the session's keys are correctly enumerated and that the
        session's state is updated accordingly when the keys are accessed.

        """
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.keys()), ["x"])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_keys_async(self):
        await self.session.aset("x", 1)
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(await self.session.akeys()), ["x"])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_items(self):
        """
        Tests the functionality of retrieving items from a session object.
        Verifies that accessing session items updates the 'accessed' flag and does not modify the session state.
        Checks that the correct items are returned, with their corresponding values, and confirms the expected state of session flags after access.
        """
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.items()), [("x", 1)])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_items_async(self):
        """

        Tests the asynchronous retrieval of items from the session.

        This test case verifies that items can be successfully stored and retrieved
        from the session using the :meth:`aset` and :meth:`aitems` methods. Additionally,
        it checks that the session's :attr:`accessed` and :attr:`modified` flags are
        correctly updated after accessing the stored items.

        The test expects the session to contain the item 'x' with value 1 after storage,
        and that the :attr:`accessed` flag is set to True after retrieval. The
        :attr:`modified` flag should remain False, indicating that no changes were made
        to the session during the retrieval process.

        """
        await self.session.aset("x", 1)
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(await self.session.aitems()), [("x", 1)])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_clear(self):
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.items()), [("x", 1)])
        self.session.clear()
        self.assertEqual(list(self.session.items()), [])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)

    def test_save(self):
        """
        Tests the save functionality of the session.

        Verifies that the session is successfully saved by asserting its existence
        after the save operation. This ensures that the session data is properly
        persisted and can be retrieved using its session key.

        Returns:
            None

        """
        self.session.save()
        self.assertIs(self.session.exists(self.session.session_key), True)

    async def test_save_async(self):
        await self.session.asave()
        self.assertIs(await self.session.aexists(self.session.session_key), True)

    def test_delete(self):
        """
        Deletes the session and verifies its successful removal.

        Tests the deletion of a session by first saving the session, then removing it using its session key.
        The function asserts that the session no longer exists after deletion, confirming the operation was successful.
        """
        self.session.save()
        self.session.delete(self.session.session_key)
        self.assertIs(self.session.exists(self.session.session_key), False)

    async def test_delete_async(self):
        """
        Tests the asynchronous deletion of a session.

        Verifies that a session can be successfully deleted and that subsequent existence checks return False. 

        This test case ensures the correct functionality of the async session deletion process, 
        covering the steps of saving the session, deleting it, and then confirming its removal by checking for its existence.

        """
        await self.session.asave()
        await self.session.adelete(self.session.session_key)
        self.assertIs(await self.session.aexists(self.session.session_key), False)

    def test_flush(self):
        self.session["foo"] = "bar"
        self.session.save()
        prev_key = self.session.session_key
        self.session.flush()
        self.assertIs(self.session.exists(prev_key), False)
        self.assertNotEqual(self.session.session_key, prev_key)
        self.assertIsNone(self.session.session_key)
        self.assertIs(self.session.modified, True)
        self.assertIs(self.session.accessed, True)

    async def test_flush_async(self):
        await self.session.aset("foo", "bar")
        await self.session.asave()
        prev_key = self.session.session_key
        await self.session.aflush()
        self.assertIs(await self.session.aexists(prev_key), False)
        self.assertNotEqual(self.session.session_key, prev_key)
        self.assertIsNone(self.session.session_key)
        self.assertIs(self.session.modified, True)
        self.assertIs(self.session.accessed, True)

    def test_cycle(self):
        self.session["a"], self.session["b"] = "c", "d"
        self.session.save()
        prev_key = self.session.session_key
        prev_data = list(self.session.items())
        self.session.cycle_key()
        self.assertIs(self.session.exists(prev_key), False)
        self.assertNotEqual(self.session.session_key, prev_key)
        self.assertEqual(list(self.session.items()), prev_data)

    async def test_cycle_async(self):
        await self.session.aset("a", "c")
        await self.session.aset("b", "d")
        await self.session.asave()
        prev_key = self.session.session_key
        prev_data = list(await self.session.aitems())
        await self.session.acycle_key()
        self.assertIs(await self.session.aexists(prev_key), False)
        self.assertNotEqual(self.session.session_key, prev_key)
        self.assertEqual(list(await self.session.aitems()), prev_data)

    def test_cycle_with_no_session_cache(self):
        self.session["a"], self.session["b"] = "c", "d"
        self.session.save()
        prev_data = self.session.items()
        self.session = self.backend(self.session.session_key)
        self.assertIs(hasattr(self.session, "_session_cache"), False)
        self.session.cycle_key()
        self.assertCountEqual(self.session.items(), prev_data)

    async def test_cycle_with_no_session_cache_async(self):
        await self.session.aset("a", "c")
        await self.session.aset("b", "d")
        await self.session.asave()
        prev_data = await self.session.aitems()
        self.session = self.backend(self.session.session_key)
        self.assertIs(hasattr(self.session, "_session_cache"), False)
        await self.session.acycle_key()
        self.assertCountEqual(await self.session.aitems(), prev_data)

    def test_save_doesnt_clear_data(self):
        """
        Tests that saving a session does not clear its existing data.

        Verifies that after saving a session, previously stored values are still
        retained. This ensures that the save operation preserves the session's state
        and does not reset it to a default or empty state.

        The test checks for the persistence of session data by storing a value,
        saving the session, and then asserting that the stored value remains
        accessible after the save operation.
        """
        self.session["a"] = "b"
        self.session.save()
        self.assertEqual(self.session["a"], "b")

    async def test_save_doesnt_clear_data_async(self):
        await self.session.aset("a", "b")
        await self.session.asave()
        self.assertEqual(await self.session.aget("a"), "b")

    def test_invalid_key(self):
        # Submitting an invalid session key (either by guessing, or if the db has
        # removed the key) results in a new key being generated.
        try:
            session = self.backend("1")
            session.save()
            self.assertNotEqual(session.session_key, "1")
            self.assertIsNone(session.get("cat"))
            session.delete()
        finally:
            # Some backends leave a stale cache entry for the invalid
            # session key; make sure that entry is manually deleted
            session.delete("1")

    async def test_invalid_key_async(self):
        # Submitting an invalid session key (either by guessing, or if the db has
        # removed the key) results in a new key being generated.
        """
        Tests the behavior of the backend when an invalid key is provided in asynchronous mode.

        This test case creates a session with a known invalid key, attempts to store and retrieve data, 
        and verifies that the expected behavior is observed. It checks that the session key is 
        not equal to the provided invalid key and that retrieving a non-existent key returns None. 
        Finally, it ensures that the session is properly cleaned up after the test.

        The test aims to validate the robustness and correctness of the backend's handling of 
        asynchronous operations with invalid keys.
        """
        try:
            session = self.backend("1")
            await session.asave()
            self.assertNotEqual(session.session_key, "1")
            self.assertIsNone(await session.aget("cat"))
            await session.adelete()
        finally:
            # Some backends leave a stale cache entry for the invalid
            # session key; make sure that entry is manually deleted
            await session.adelete("1")

    def test_session_key_empty_string_invalid(self):
        """Falsey values (Such as an empty string) are rejected."""
        self.session._session_key = ""
        self.assertIsNone(self.session.session_key)

    def test_session_key_too_short_invalid(self):
        """Strings shorter than 8 characters are rejected."""
        self.session._session_key = "1234567"
        self.assertIsNone(self.session.session_key)

    def test_session_key_valid_string_saved(self):
        """Strings of length 8 and up are accepted and stored."""
        self.session._session_key = "12345678"
        self.assertEqual(self.session.session_key, "12345678")

    def test_session_key_is_read_only(self):
        """

        Tests that the session key attribute is read-only.

        Verifies that attempting to modify the session key raises an AttributeError, 
        ensuring that the session key cannot be changed after it has been set.

        """
        def set_session_key(session):
            session.session_key = session._get_new_session_key()

        with self.assertRaises(AttributeError):
            set_session_key(self.session)

    # Custom session expiry
    def test_default_expiry(self):
        # A normal session has a max age equal to settings
        self.assertEqual(self.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

        # So does a custom session with an idle expiration time of 0 (but it'll
        # expire at browser close)
        self.session.set_expiry(0)
        self.assertEqual(self.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

    async def test_default_expiry_async(self):
        # A normal session has a max age equal to settings.
        """

        Tests the default session expiry age and attempts to override it with an expiry age of 0.

        The test first checks if the default session expiry age matches the value specified in the settings.
        It then attempts to override the default expiry age by setting it to 0 and verifies if the new value is still reflected as the default session expiry age.

        """
        self.assertEqual(
            await self.session.aget_expiry_age(), settings.SESSION_COOKIE_AGE
        )
        # So does a custom session with an idle expiration time of 0 (but it'll
        # expire at browser close).
        await self.session.aset_expiry(0)
        self.assertEqual(
            await self.session.aget_expiry_age(), settings.SESSION_COOKIE_AGE
        )

    def test_custom_expiry_seconds(self):
        """

        Tests that custom expiry seconds are applied correctly to a session.

        This test case verifies that specifying a custom expiry time in seconds
        results in the expected expiry date and age being calculated for a session.
        It checks that the expiry date and age are correctly calculated based on the
        provided modification time and custom expiry seconds.

        """
        modification = timezone.now()

        self.session.set_expiry(10)

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    async def test_custom_expiry_seconds_async(self):
        """
        Tests the custom expiry seconds functionality asynchronously.

        Verifies that setting a custom expiry time and retrieving the corresponding expiry date and age returns the expected results.
        The test checks that the calculated expiry date is the modification time plus the specified number of seconds, and that the expiry age matches the set expiry time.
        This ensures that the custom expiry seconds are applied correctly and can be accurately retrieved.\"
        """
        modification = timezone.now()

        await self.session.aset_expiry(10)

        date = await self.session.aget_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = await self.session.aget_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    def test_custom_expiry_timedelta(self):
        """

        Tests that the session expiry date and age are correctly calculated 
        when a custom expiry time delta is set.

        Verifies that the session's expiry date and age are calculated 
        relative to the provided modification time and the set expiry time delta.

        """
        modification = timezone.now()

        # Mock timezone.now, because set_expiry calls it on this code path.
        original_now = timezone.now
        try:
            timezone.now = lambda: modification
            self.session.set_expiry(timedelta(seconds=10))
        finally:
            timezone.now = original_now

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    async def test_custom_expiry_timedelta_async(self):
        modification = timezone.now()

        # Mock timezone.now, because set_expiry calls it on this code path.
        original_now = timezone.now
        try:
            timezone.now = lambda: modification
            await self.session.aset_expiry(timedelta(seconds=10))
        finally:
            timezone.now = original_now

        date = await self.session.aget_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = await self.session.aget_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    def test_custom_expiry_datetime(self):
        """
        од KraljeviTests custom expiry datetime testing function.

            Tests that session expiry date and age are correctly calculated based on a custom expiry datetime.
            Verifies that setting a custom expiry time and then retrieving the expiry date and age yields the expected results.
        """
        modification = timezone.now()

        self.session.set_expiry(modification + timedelta(seconds=10))

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    async def test_custom_expiry_datetime_async(self):
        modification = timezone.now()

        await self.session.aset_expiry(modification + timedelta(seconds=10))

        date = await self.session.aget_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = await self.session.aget_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    def test_custom_expiry_reset(self):
        """
        Tests the custom session expiry reset functionality.

        This test method verifies that setting a custom expiry age for a session, then resetting it to its default value, results in the session expiry age being reset to the default session cookie age defined in the settings. It ensures that the session expiry age is correctly updated when setting and resetting custom expiry ages.
        """
        self.session.set_expiry(None)
        self.session.set_expiry(10)
        self.session.set_expiry(None)
        self.assertEqual(self.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

    async def test_custom_expiry_reset_async(self):
        """
        Tests the custom expiry reset functionality for a session.

        Verifies that setting a custom expiry value, then resetting it to the default,
        results in the session reverting to the default session cookie age specified
        in the application settings. This ensures that custom expiry values are properly
        cleared and the default behaviour is restored when necessary.
        """
        await self.session.aset_expiry(None)
        await self.session.aset_expiry(10)
        await self.session.aset_expiry(None)
        self.assertEqual(
            await self.session.aget_expiry_age(), settings.SESSION_COOKIE_AGE
        )

    def test_get_expire_at_browser_close(self):
        # Tests get_expire_at_browser_close with different settings and different
        # set_expiry calls
        with override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=False):
            self.session.set_expiry(10)
            self.assertIs(self.session.get_expire_at_browser_close(), False)

            self.session.set_expiry(0)
            self.assertIs(self.session.get_expire_at_browser_close(), True)

            self.session.set_expiry(None)
            self.assertIs(self.session.get_expire_at_browser_close(), False)

        with override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=True):
            self.session.set_expiry(10)
            self.assertIs(self.session.get_expire_at_browser_close(), False)

            self.session.set_expiry(0)
            self.assertIs(self.session.get_expire_at_browser_close(), True)

            self.session.set_expiry(None)
            self.assertIs(self.session.get_expire_at_browser_close(), True)

    async def test_get_expire_at_browser_close_async(self):
        # Tests get_expire_at_browser_close with different settings and different
        # set_expiry calls
        """
        Tests the asynchronous behavior of getting the expire-at-browser-close flag.

        This test checks how the expire-at-browser-close flag is affected by the 
        SESSION_EXPIRE_AT_BROWSER_CLOSE setting and the session expiry time. It verifies 
        that when the session expiry time is set to 0, the flag is set to True if the 
        SESSION_EXPIRE_AT_BROWSER_CLOSE setting is enabled, and to True otherwise. If the 
        session expiry time is set to a non-zero value or None, the flag is set to False 
        when the SESSION_EXPIRE_AT_BROWSER_CLOSE setting is disabled, and to True when it 
        is enabled. 

        The test covers the following cases:
        - SESSION_EXPIRE_AT_BROWSER_CLOSE setting is disabled
        - SESSION_EXPIRE_AT_BROWSER_CLOSE setting is enabled

        It ensures that the expire-at-browser-close flag behaves as expected under these 
        different conditions.
        """
        with override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=False):
            await self.session.aset_expiry(10)
            self.assertIs(await self.session.aget_expire_at_browser_close(), False)

            await self.session.aset_expiry(0)
            self.assertIs(await self.session.aget_expire_at_browser_close(), True)

            await self.session.aset_expiry(None)
            self.assertIs(await self.session.aget_expire_at_browser_close(), False)

        with override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=True):
            await self.session.aset_expiry(10)
            self.assertIs(await self.session.aget_expire_at_browser_close(), False)

            await self.session.aset_expiry(0)
            self.assertIs(await self.session.aget_expire_at_browser_close(), True)

            await self.session.aset_expiry(None)
            self.assertIs(await self.session.aget_expire_at_browser_close(), True)

    def test_decode(self):
        # Ensure we can decode what we encode
        """

        Tests the ability to decode previously encoded data.

        Verifies that the decode method of the session correctly reverses the encoding process,
        resulting in the original data being retrieved. This ensures the proper functionality of
        the encoding and decoding mechanisms within the session.

        :raises: AssertionError if the decoded data does not match the original data.

        """
        data = {"a test key": "a test value"}
        encoded = self.session.encode(data)
        self.assertEqual(self.session.decode(encoded), data)

    def test_decode_failure_logged_to_security(self):
        """
        Tests that session decoding failures are logged to the security system.

        Checks that when the session decoding process encounters invalid or corrupted data,
        a warning is logged to the django.security.SuspiciousSession logger with an appropriate message.
        Verifies that the decode method returns an empty dictionary in such cases and that
        the log output contains the expected 'Session data corrupted' message.
        """
        tests = [
            base64.b64encode(b"flaskdj:alkdjf").decode("ascii"),
            "bad:encoded:value",
        ]
        for encoded in tests:
            with self.subTest(encoded=encoded):
                with self.assertLogs(
                    "django.security.SuspiciousSession", "WARNING"
                ) as cm:
                    self.assertEqual(self.session.decode(encoded), {})
                # The failed decode is logged.
                self.assertIn("Session data corrupted", cm.output[0])

    def test_decode_serializer_exception(self):
        signer = TimestampSigner(salt=self.session.key_salt)
        encoded = signer.sign(b"invalid data")
        self.assertEqual(self.session.decode(encoded), {})

    def test_actual_expiry(self):
        old_session_key = None
        new_session_key = None
        try:
            self.session["foo"] = "bar"
            self.session.set_expiry(-timedelta(seconds=10))
            self.session.save()
            old_session_key = self.session.session_key
            # With an expiry date in the past, the session expires instantly.
            new_session = self.backend(self.session.session_key)
            new_session_key = new_session.session_key
            self.assertNotIn("foo", new_session)
        finally:
            self.session.delete(old_session_key)
            self.session.delete(new_session_key)

    async def test_actual_expiry_async(self):
        """
        Tests the actual expiry functionality of a session asynchronously.

        Verifies that a session key expires after a specified time period and that the
        data associated with the expired session key is no longer accessible.

        Ensures the session is properly cleaned up after the test, regardless of the
        outcome, by deleting both the old and new session keys from the backend storage.

        The test scenario involves setting a session value with an expiry time in the past,
        saving the session, and then checking if the value is accessible with a new session
        instance. The test asserts that the value is no longer available due to the expiry
        mechanism, confirming the correct behavior of the session expiry functionality.
        """
        old_session_key = None
        new_session_key = None
        try:
            await self.session.aset("foo", "bar")
            await self.session.aset_expiry(-timedelta(seconds=10))
            await self.session.asave()
            old_session_key = self.session.session_key
            # With an expiry date in the past, the session expires instantly.
            new_session = self.backend(self.session.session_key)
            new_session_key = new_session.session_key
            self.assertIs(await new_session.ahas_key("foo"), False)
        finally:
            await self.session.adelete(old_session_key)
            await self.session.adelete(new_session_key)

    def test_session_load_does_not_create_record(self):
        """
        Loading an unknown session key does not create a session record.

        Creating session records on load is a DOS vulnerability.
        """
        session = self.backend("someunknownkey")
        session.load()

        self.assertIsNone(session.session_key)
        self.assertIs(session.exists(session.session_key), False)
        # provided unknown key was cycled, not reused
        self.assertNotEqual(session.session_key, "someunknownkey")

    async def test_session_load_does_not_create_record_async(self):
        session = self.backend("someunknownkey")
        await session.aload()

        self.assertIsNone(session.session_key)
        self.assertIs(await session.aexists(session.session_key), False)
        # Provided unknown key was cycled, not reused.
        self.assertNotEqual(session.session_key, "someunknownkey")

    def test_session_save_does_not_resurrect_session_logged_out_in_other_context(self):
        """
        Sessions shouldn't be resurrected by a concurrent request.
        """
        # Create new session.
        s1 = self.backend()
        s1["test_data"] = "value1"
        s1.save(must_create=True)

        # Logout in another context.
        s2 = self.backend(s1.session_key)
        s2.delete()

        # Modify session in first context.
        s1["test_data"] = "value2"
        with self.assertRaises(UpdateError):
            # This should throw an exception as the session is deleted, not
            # resurrect the session.
            s1.save()

        self.assertEqual(s1.load(), {})

    async def test_session_asave_does_not_resurrect_session_logged_out_in_other_context(
        self,
    ):
        """Sessions shouldn't be resurrected by a concurrent request."""
        # Create new session.
        s1 = self.backend()
        await s1.aset("test_data", "value1")
        await s1.asave(must_create=True)

        # Logout in another context.
        s2 = self.backend(s1.session_key)
        await s2.adelete()

        # Modify session in first context.
        await s1.aset("test_data", "value2")
        with self.assertRaises(UpdateError):
            # This should throw an exception as the session is deleted, not
            # resurrect the session.
            await s1.asave()

        self.assertEqual(await s1.aload(), {})


class DatabaseSessionTests(SessionTestsMixin, TestCase):
    backend = DatabaseSession
    session_engine = "django.contrib.sessions.backends.db"

    @property
    def model(self):
        return self.backend.get_model_class()

    def test_session_str(self):
        "Session repr should be the session key."
        self.session["x"] = 1
        self.session.save()

        session_key = self.session.session_key
        s = self.model.objects.get(session_key=session_key)

        self.assertEqual(str(s), session_key)

    def test_session_get_decoded(self):
        """
        Test we can use Session.get_decoded to retrieve data stored
        in normal way
        """
        self.session["x"] = 1
        self.session.save()

        s = self.model.objects.get(session_key=self.session.session_key)

        self.assertEqual(s.get_decoded(), {"x": 1})

    def test_sessionmanager_save(self):
        """
        Test SessionManager.save method
        """
        # Create a session
        self.session["y"] = 1
        self.session.save()

        s = self.model.objects.get(session_key=self.session.session_key)
        # Change it
        self.model.objects.save(s.session_key, {"y": 2}, s.expire_date)
        # Clear cache, so that it will be retrieved from DB
        del self.session._session_cache
        self.assertEqual(self.session["y"], 2)

    def test_clearsessions_command(self):
        """
        Test clearsessions command for clearing expired sessions.
        """
        self.assertEqual(0, self.model.objects.count())

        # One object in the future
        self.session["foo"] = "bar"
        self.session.set_expiry(3600)
        self.session.save()

        # One object in the past
        other_session = self.backend()
        other_session["foo"] = "bar"
        other_session.set_expiry(-3600)
        other_session.save()

        # Two sessions are in the database before clearsessions...
        self.assertEqual(2, self.model.objects.count())
        with override_settings(SESSION_ENGINE=self.session_engine):
            management.call_command("clearsessions")
        # ... and one is deleted.
        self.assertEqual(1, self.model.objects.count())

    async def test_aclear_expired(self):
        self.assertEqual(await self.model.objects.acount(), 0)

        # Object in the future.
        await self.session.aset("key", "value")
        await self.session.aset_expiry(3600)
        await self.session.asave()
        # Object in the past.
        other_session = self.backend()
        await other_session.aset("key", "value")
        await other_session.aset_expiry(-3600)
        await other_session.asave()

        # Two sessions are in the database before clearing expired.
        self.assertEqual(await self.model.objects.acount(), 2)
        await self.session.aclear_expired()
        await other_session.aclear_expired()
        self.assertEqual(await self.model.objects.acount(), 1)


@override_settings(USE_TZ=True)
class DatabaseSessionWithTimeZoneTests(DatabaseSessionTests):
    pass


class CustomDatabaseSessionTests(DatabaseSessionTests):
    backend = CustomDatabaseSession
    session_engine = "sessions_tests.models"
    custom_session_cookie_age = 60 * 60 * 24  # One day.

    def test_extra_session_field(self):
        # Set the account ID to be picked up by a custom session storage
        # and saved to a custom session model database column.
        self.session["_auth_user_id"] = 42
        self.session.save()

        # Make sure that the customized create_model_instance() was called.
        s = self.model.objects.get(session_key=self.session.session_key)
        self.assertEqual(s.account_id, 42)

        # Make the session "anonymous".
        self.session.pop("_auth_user_id")
        self.session.save()

        # Make sure that save() on an existing session did the right job.
        s = self.model.objects.get(session_key=self.session.session_key)
        self.assertIsNone(s.account_id)

    def test_custom_expiry_reset(self):
        """
        Tests the functionality of resetting a custom session expiry.

        This test case verifies that setting a custom session expiry, then resetting it,
        results in the session expiry age being set to a predefined custom value.

        The test coverage includes setting and resetting the session expiry multiple times
        to ensure the custom session cookie age is correctly applied after each reset operation.

        It asserts that the final session expiry age is equal to the custom session cookie age,
        indicating a successful reset of the custom session expiry.
        """
        self.session.set_expiry(None)
        self.session.set_expiry(10)
        self.session.set_expiry(None)
        self.assertEqual(self.session.get_expiry_age(), self.custom_session_cookie_age)

    async def test_custom_expiry_reset_async(self):
        await self.session.aset_expiry(None)
        await self.session.aset_expiry(10)
        await self.session.aset_expiry(None)
        self.assertEqual(
            await self.session.aget_expiry_age(), self.custom_session_cookie_age
        )

    def test_default_expiry(self):
        """

        Tests if the session expiry age defaults to the custom session cookie age and 
        if setting the expiry age to 0 also uses the custom session cookie age.

        Verifies the expected behavior of session expiry age, ensuring it remains 
        consistent with the custom session cookie age in different scenarios.

        """
        self.assertEqual(self.session.get_expiry_age(), self.custom_session_cookie_age)
        self.session.set_expiry(0)
        self.assertEqual(self.session.get_expiry_age(), self.custom_session_cookie_age)

    async def test_default_expiry_async(self):
        self.assertEqual(
            await self.session.aget_expiry_age(), self.custom_session_cookie_age
        )
        await self.session.aset_expiry(0)
        self.assertEqual(
            await self.session.aget_expiry_age(), self.custom_session_cookie_age
        )


class CacheDBSessionTests(SessionTestsMixin, TestCase):
    backend = CacheDBSession

    def test_exists_searches_cache_first(self):
        self.session.save()
        with self.assertNumQueries(0):
            self.assertIs(self.session.exists(self.session.session_key), True)

    # Some backends might issue a warning
    @ignore_warnings(module="django.core.cache.backends.base")
    def test_load_overlong_key(self):
        """
        Tests the loading of a session when the session key exceeds the maximum allowed length.

        This test case verifies that the session load functionality behaves correctly 
        even when the session key is longer than expected, ensuring that an empty 
        session is returned in such cases to prevent potential errors or security 
        vulnerabilities.
        """
        self.session._session_key = (string.ascii_letters + string.digits) * 20
        self.assertEqual(self.session.load(), {})

    @override_settings(SESSION_CACHE_ALIAS="sessions")
    def test_non_default_cache(self):
        # 21000 - CacheDB backend should respect SESSION_CACHE_ALIAS.
        with self.assertRaises(InvalidCacheBackendError):
            self.backend()

    @override_settings(
        CACHES={"default": {"BACKEND": "cache.failing_cache.CacheClass"}}
    )
    def test_cache_set_failure_non_fatal(self):
        """Failing to write to the cache does not raise errors."""
        session = self.backend()
        session["key"] = "val"

        with self.assertLogs("django.contrib.sessions", "ERROR") as cm:
            session.save()

        # A proper ERROR log message was recorded.
        log = cm.records[-1]
        self.assertEqual(log.message, f"Error saving to cache ({session._cache})")
        self.assertEqual(str(log.exc_info[1]), "Faked exception saving to cache")

    @override_settings(
        CACHES={"default": {"BACKEND": "cache.failing_cache.CacheClass"}}
    )
    async def test_cache_async_set_failure_non_fatal(self):
        """Failing to write to the cache does not raise errors."""
        session = self.backend()
        await session.aset("key", "val")

        with self.assertLogs("django.contrib.sessions", "ERROR") as cm:
            await session.asave()

        # A proper ERROR log message was recorded.
        log = cm.records[-1]
        self.assertEqual(log.message, f"Error saving to cache ({session._cache})")
        self.assertEqual(str(log.exc_info[1]), "Faked exception saving to cache")


@override_settings(USE_TZ=True)
class CacheDBSessionWithTimeZoneTests(CacheDBSessionTests):
    pass


class FileSessionTests(SessionTestsMixin, SimpleTestCase):
    backend = FileSession

    def setUp(self):
        # Do file session tests in an isolated directory, and kill it after we're done.
        """
        Sets up the test environment to isolate session storage.

        This method prepares the test environment by creating a temporary directory to store session data. The original session file path is saved to be restored later. The session storage path is updated to point to the temporary directory. After the test is completed, the temporary directory is automatically removed to clean up.

        Preconditions: The test backend and settings are properly configured.
        Postconditions: The test environment is ready with isolated session storage.
        """
        self.original_session_file_path = settings.SESSION_FILE_PATH
        self.temp_session_store = settings.SESSION_FILE_PATH = self.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_session_store)
        # Reset the file session backend's internal caches
        if hasattr(self.backend, "_storage_path"):
            del self.backend._storage_path
        super().setUp()

    def tearDown(self):
        super().tearDown()
        settings.SESSION_FILE_PATH = self.original_session_file_path

    def mkdtemp(self):
        return tempfile.mkdtemp()

    @override_settings(
        SESSION_FILE_PATH="/if/this/directory/exists/you/have/a/weird/computer",
    )
    def test_configuration_check(self):
        """
        Tests that the backend raises an ImproperlyConfigured exception when the session file storage path is not a valid directory.

        Verifies that the configuration check is performed correctly and that an exception is raised when the storage path does not exist, ensuring that the backend is properly configured before use.
        """
        del self.backend._storage_path
        # Make sure the file backend checks for a good storage dir
        with self.assertRaises(ImproperlyConfigured):
            self.backend()

    def test_invalid_key_backslash(self):
        # Ensure we don't allow directory-traversal.
        # This is tested directly on _key_to_file, as load() will swallow
        # a SuspiciousOperation in the same way as an OSError - by creating
        # a new session, making it unclear whether the slashes were detected.
        with self.assertRaises(InvalidSessionKey):
            self.backend()._key_to_file("a\\b\\c")

    def test_invalid_key_forwardslash(self):
        # Ensure we don't allow directory-traversal
        with self.assertRaises(InvalidSessionKey):
            self.backend()._key_to_file("a/b/c")

    @override_settings(
        SESSION_ENGINE="django.contrib.sessions.backends.file",
        SESSION_COOKIE_AGE=0,
    )
    def test_clearsessions_command(self):
        """
        Test clearsessions command for clearing expired sessions.
        """
        storage_path = self.backend._get_storage_path()
        file_prefix = settings.SESSION_COOKIE_NAME

        def count_sessions():
            return len(
                [
                    session_file
                    for session_file in os.listdir(storage_path)
                    if session_file.startswith(file_prefix)
                ]
            )

        self.assertEqual(0, count_sessions())

        # One object in the future
        self.session["foo"] = "bar"
        self.session.set_expiry(3600)
        self.session.save()

        # One object in the past
        other_session = self.backend()
        other_session["foo"] = "bar"
        other_session.set_expiry(-3600)
        other_session.save()

        # One object in the present without an expiry (should be deleted since
        # its modification time + SESSION_COOKIE_AGE will be in the past when
        # clearsessions runs).
        other_session2 = self.backend()
        other_session2["foo"] = "bar"
        other_session2.save()

        # Three sessions are in the filesystem before clearsessions...
        self.assertEqual(3, count_sessions())
        management.call_command("clearsessions")
        # ... and two are deleted.
        self.assertEqual(1, count_sessions())


class FileSessionPathLibTests(FileSessionTests):
    def mkdtemp(self):
        """

        Create a temporary directory and return its path.

        This method creates a new, uniquely named temporary directory and returns
        a Path object representing the directory. The directory will exist on the
        filesystem until it is explicitly removed.

        Returns:
            Path: The path of the newly created temporary directory.

        """
        tmp_dir = super().mkdtemp()
        return Path(tmp_dir)


class CacheSessionTests(SessionTestsMixin, SimpleTestCase):
    backend = CacheSession

    # Some backends might issue a warning
    @ignore_warnings(module="django.core.cache.backends.base")
    def test_load_overlong_key(self):
        """
        Temmuz this function tests the behavior of loading a session when the session key is excessively long.

            It verifies that the session loads correctly and returns an empty dictionary when 
            the session key exceeds the expected length, ensuring that the session handling 
            mechanism can gracefully handle such edge cases.
        """
        self.session._session_key = (string.ascii_letters + string.digits) * 20
        self.assertEqual(self.session.load(), {})

    def test_default_cache(self):
        self.session.save()
        self.assertIsNotNone(caches["default"].get(self.session.cache_key))

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.dummy.DummyCache",
            },
            "sessions": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "session",
            },
        },
        SESSION_CACHE_ALIAS="sessions",
    )
    def test_non_default_cache(self):
        # Re-initialize the session backend to make use of overridden settings.
        """
        Tests that a non-default cache is used for session storage.

        This test verifies that session data is stored in a separate cache, 
        defined by the SESSION_CACHE_ALIAS setting, rather than the default cache. 
        It checks that the session cache key is not present in the default cache, 
        but is present in the sessions cache, ensuring correct cache usage for sessions.
        """
        self.session = self.backend()

        self.session.save()
        self.assertIsNone(caches["default"].get(self.session.cache_key))
        self.assertIsNotNone(caches["sessions"].get(self.session.cache_key))

    def test_create_and_save(self):
        """

        Tests the creation and saving of a session.

        This test case verifies that a session can be successfully created and saved.
        It also checks that the session is properly cached after saving.

        The test case covers the following steps:
            * Creation of a new session using the backend
            * Saving of the session
            * Verification that the session is cached with a valid cache key

        This ensures that the session management functionality is working as expected.

        """
        self.session = self.backend()
        self.session.create()
        self.session.save()
        self.assertIsNotNone(caches["default"].get(self.session.cache_key))

    async def test_create_and_save_async(self):
        """

        Tests the asynchronous creation and saving of a session.

        This test case verifies that a session can be successfully created and saved
        in an asynchronous manner. It checks that the session is properly cached after
        saving, ensuring that the cache contains the expected session data.

        """
        self.session = self.backend()
        await self.session.acreate()
        await self.session.asave()
        self.assertIsNotNone(caches["default"].get(await self.session.acache_key()))


class SessionMiddlewareTests(TestCase):
    request_factory = RequestFactory()

    @staticmethod
    def get_response_touching_session(request):
        request.session["hello"] = "world"
        return HttpResponse("Session test")

    @override_settings(SESSION_COOKIE_SECURE=True)
    def test_secure_session_cookie(self):
        """
        Tests that the session cookie is set with the secure flag when the SESSION_COOKIE_SECURE setting is enabled.

        This test ensures that when the SESSION_COOKIE_SECURE setting is True, the session cookie
        is sent over a secure connection, which helps protect against session hijacking attacks.

        It verifies that the session cookie contains the 'secure' attribute, indicating that the
        cookie should only be transmitted over a secure protocol, such as HTTPS.
        """
        request = self.request_factory.get("/")
        middleware = SessionMiddleware(self.get_response_touching_session)

        # Handle the response through the middleware
        response = middleware(request)
        self.assertIs(response.cookies[settings.SESSION_COOKIE_NAME]["secure"], True)

    @override_settings(SESSION_COOKIE_HTTPONLY=True)
    def test_httponly_session_cookie(self):
        request = self.request_factory.get("/")
        middleware = SessionMiddleware(self.get_response_touching_session)

        # Handle the response through the middleware
        response = middleware(request)
        self.assertIs(response.cookies[settings.SESSION_COOKIE_NAME]["httponly"], True)
        self.assertIn(
            cookies.Morsel._reserved["httponly"],
            str(response.cookies[settings.SESSION_COOKIE_NAME]),
        )

    @override_settings(SESSION_COOKIE_SAMESITE="Strict")
    def test_samesite_session_cookie(self):
        """

        Tests the setting of the SameSite attribute in the session cookie.

        This test checks that the session cookie is set with the SameSite attribute
        when the SESSION_COOKIE_SAMESITE setting is set to 'Strict'. It verifies that
        the middleware correctly sets the attribute in the session cookie.

        The test simulates a GET request and checks the response cookies to ensure
        the SameSite attribute is set as expected.

        """
        request = self.request_factory.get("/")
        middleware = SessionMiddleware(self.get_response_touching_session)
        response = middleware(request)
        self.assertEqual(
            response.cookies[settings.SESSION_COOKIE_NAME]["samesite"], "Strict"
        )

    @override_settings(SESSION_COOKIE_HTTPONLY=False)
    def test_no_httponly_session_cookie(self):
        """
        Tests that the session cookie does not have the HttpOnly flag set when the SESSION_COOKIE_HTTPONLY setting is False.

        This test case verifies the behavior of the SessionMiddleware when the SESSION_COOKIE_HTTPONLY setting is explicitly disabled.

        It checks that the session cookie in the response does not have the HttpOnly attribute, confirming that the session cookie is accessible to client-side scripts.
        """
        request = self.request_factory.get("/")
        middleware = SessionMiddleware(self.get_response_touching_session)
        response = middleware(request)
        self.assertEqual(response.cookies[settings.SESSION_COOKIE_NAME]["httponly"], "")
        self.assertNotIn(
            cookies.Morsel._reserved["httponly"],
            str(response.cookies[settings.SESSION_COOKIE_NAME]),
        )

    def test_session_save_on_500(self):
        def response_500(request):
            """

            Returns a server error response (500) with a custom error message.

            The response includes a generic error message 'Horrible error' and sets a session
            variable 'hello' to 'world' for further error handling or debugging purposes.

            :param request: The current HTTP request object.
            :rtype: HttpResponse
            :status: 500 Internal Server Error

            """
            response = HttpResponse("Horrible error")
            response.status_code = 500
            request.session["hello"] = "world"
            return response

        request = self.request_factory.get("/")
        SessionMiddleware(response_500)(request)

        # The value wasn't saved above.
        self.assertNotIn("hello", request.session.load())

    def test_session_save_on_5xx(self):
        """

        Tests that session data is not saved when a 5xx status code is returned by the view.

        This test case verifies that session data modified during the handling of a request
        is discarded when an HTTP 5xx error occurs, ensuring that session changes are only
        committed when the request is successfully processed.

        Verifies the correct behavior of the SessionMiddleware in handling session data
        when an internal server error occurs, maintaining data integrity and consistency.

        """
        def response_503(request):
            response = HttpResponse("Service Unavailable")
            response.status_code = 503
            request.session["hello"] = "world"
            return response

        request = self.request_factory.get("/")
        SessionMiddleware(response_503)(request)

        # The value wasn't saved above.
        self.assertNotIn("hello", request.session.load())

    def test_session_update_error_redirect(self):
        """
        Tests that SessionMiddleware correctly raises a SessionInterrupted exception and provides a helpful error message when a session is deleted during a request, potentially due to concurrent access, such as another request logging out the user.
        """
        def response_delete_session(request):
            request.session = DatabaseSession()
            request.session.save(must_create=True)
            request.session.delete()
            return HttpResponse()

        request = self.request_factory.get("/foo/")
        middleware = SessionMiddleware(response_delete_session)

        msg = (
            "The request's session was deleted before the request completed. "
            "The user may have logged out in a concurrent request, for example."
        )
        with self.assertRaisesMessage(SessionInterrupted, msg):
            # Handle the response through the middleware. It will try to save
            # the deleted session which will cause an UpdateError that's caught
            # and raised as a SessionInterrupted.
            middleware(request)

    def test_session_delete_on_end(self):
        """
        Tests that the session is properly deleted when the session end is triggered.

        This test verifies that when a view is decorated to end the session, the session
        cookie is correctly cleared in the response, and the 'Vary: Cookie' header is set,
        indicating that the response varies based on the cookie.

        It simulates a request with an existing session cookie, calls the view through a
        middleware that ends the session, and checks that the session cookie is removed
        in the response with an expiration date in the past, and that the 'Vary' header
        is correctly set to 'Cookie'.
        """
        def response_ending_session(request):
            """

            Terminates the current user session and returns a success response.

            This function is used to end a user's session, effectively logging them out.
            It removes all session data and returns a simple HTTP response with a test message.

            """
            request.session.flush()
            return HttpResponse("Session test")

        request = self.request_factory.get("/")
        middleware = SessionMiddleware(response_ending_session)

        # Before deleting, there has to be an existing cookie
        request.COOKIES[settings.SESSION_COOKIE_NAME] = "abc"

        # Handle the response through the middleware
        response = middleware(request)

        # The cookie was deleted, not recreated.
        # A deleted cookie header looks like:
        #  "Set-Cookie: sessionid=; expires=Thu, 01 Jan 1970 00:00:00 GMT; "
        #  "Max-Age=0; Path=/"
        self.assertEqual(
            'Set-Cookie: {}=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; '
            "Max-Age=0; Path=/; SameSite={}".format(
                settings.SESSION_COOKIE_NAME,
                settings.SESSION_COOKIE_SAMESITE,
            ),
            str(response.cookies[settings.SESSION_COOKIE_NAME]),
        )
        # SessionMiddleware sets 'Vary: Cookie' to prevent the 'Set-Cookie'
        # from being cached.
        self.assertEqual(response.headers["Vary"], "Cookie")

    @override_settings(
        SESSION_COOKIE_DOMAIN=".example.local", SESSION_COOKIE_PATH="/example/"
    )
    def test_session_delete_on_end_with_custom_domain_and_path(self):
        """
        Tests that a session is deleted correctly when the session's end is triggered, 
        using a custom domain and path for the session cookie. Verifies that the 
        Set-Cookie header in the response correctly sets the session cookie to expire 
        immediately, with the specified domain and path. This ensures that the session 
        is properly deleted at the end of the request, as configured by the application 
        settings for session cookie domain and path.
        """
        def response_ending_session(request):
            request.session.flush()
            return HttpResponse("Session test")

        request = self.request_factory.get("/")
        middleware = SessionMiddleware(response_ending_session)

        # Before deleting, there has to be an existing cookie
        request.COOKIES[settings.SESSION_COOKIE_NAME] = "abc"

        # Handle the response through the middleware
        response = middleware(request)

        # The cookie was deleted, not recreated.
        # A deleted cookie header with a custom domain and path looks like:
        #  Set-Cookie: sessionid=; Domain=.example.local;
        #              expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0;
        #              Path=/example/
        self.assertEqual(
            'Set-Cookie: {}=""; Domain=.example.local; expires=Thu, '
            "01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/example/; SameSite={}".format(
                settings.SESSION_COOKIE_NAME,
                settings.SESSION_COOKIE_SAMESITE,
            ),
            str(response.cookies[settings.SESSION_COOKIE_NAME]),
        )

    def test_flush_empty_without_session_cookie_doesnt_set_cookie(self):
        def response_ending_session(request):
            request.session.flush()
            return HttpResponse("Session test")

        request = self.request_factory.get("/")
        middleware = SessionMiddleware(response_ending_session)

        # Handle the response through the middleware
        response = middleware(request)

        # A cookie should not be set.
        self.assertEqual(response.cookies, {})
        # The session is accessed so "Vary: Cookie" should be set.
        self.assertEqual(response.headers["Vary"], "Cookie")

    def test_empty_session_saved(self):
        """
        If a session is emptied of data but still has a key, it should still
        be updated.
        """

        def response_set_session(request):
            # Set a session key and some data.
            request.session["foo"] = "bar"
            return HttpResponse("Session test")

        request = self.request_factory.get("/")
        middleware = SessionMiddleware(response_set_session)

        # Handle the response through the middleware.
        response = middleware(request)
        self.assertEqual(tuple(request.session.items()), (("foo", "bar"),))
        # A cookie should be set, along with Vary: Cookie.
        self.assertIn(
            "Set-Cookie: sessionid=%s" % request.session.session_key,
            str(response.cookies),
        )
        self.assertEqual(response.headers["Vary"], "Cookie")

        # Empty the session data.
        del request.session["foo"]
        # Handle the response through the middleware.
        response = HttpResponse("Session test")
        response = middleware.process_response(request, response)
        self.assertEqual(dict(request.session.values()), {})
        session = Session.objects.get(session_key=request.session.session_key)
        self.assertEqual(session.get_decoded(), {})
        # While the session is empty, it hasn't been flushed so a cookie should
        # still be set, along with Vary: Cookie.
        self.assertGreater(len(request.session.session_key), 8)
        self.assertIn(
            "Set-Cookie: sessionid=%s" % request.session.session_key,
            str(response.cookies),
        )
        self.assertEqual(response.headers["Vary"], "Cookie")


class CookieSessionTests(SessionTestsMixin, SimpleTestCase):
    backend = CookieSession

    def test_save(self):
        """
        This test tested exists() in the other session backends, but that
        doesn't make sense for us.
        """
        pass

    async def test_save_async(self):
        pass

    def test_cycle(self):
        """
        This test tested cycle_key() which would create a new session
        key for the same session data. But we can't invalidate previously
        signed cookies (other than letting them expire naturally) so
        testing for this behavior is meaningless.
        """
        pass

    async def test_cycle_async(self):
        pass

    @unittest.expectedFailure
    def test_actual_expiry(self):
        # The cookie backend doesn't handle non-default expiry dates, see #19201
        super().test_actual_expiry()

    async def test_actual_expiry_async(self):
        pass

    def test_unpickling_exception(self):
        # signed_cookies backend should handle unpickle exceptions gracefully
        # by creating a new session
        """
        Tests that an exception is properly handled when unpickling a session.

        Verifies that when the session's serializer is set to JSONSerializer and 
        an error occurs while loading the session (simulating a ValueError from 
        django.core.signing.loads), the session's load method behaves as expected.

        Ensures the session's save and load functionality works correctly in 
        conjunction with the serializer, and that signing errors are properly 
        trapped and handled during the loading process.
        """
        self.assertEqual(self.session.serializer, JSONSerializer)
        self.session.save()
        with mock.patch("django.core.signing.loads", side_effect=ValueError):
            self.session.load()

    @unittest.skip(
        "Cookie backend doesn't have an external store to create records in."
    )
    def test_session_load_does_not_create_record(self):
        pass

    @unittest.skip(
        "Cookie backend doesn't have an external store to create records in."
    )
    async def test_session_load_does_not_create_record_async(self):
        pass

    @unittest.skip(
        "CookieSession is stored in the client and there is no way to query it."
    )
    def test_session_save_does_not_resurrect_session_logged_out_in_other_context(self):
        pass

    @unittest.skip(
        "CookieSession is stored in the client and there is no way to query it."
    )
    async def test_session_asave_does_not_resurrect_session_logged_out_in_other_context(
        self,
    ):
        pass


class ClearSessionsCommandTests(SimpleTestCase):
    def test_clearsessions_unsupported(self):
        """
        Tests if the clearsessions command correctly raises an error when the session engine does not support clearing expired sessions.

        This test case verifies that the system behaves as expected when attempting to clear expired sessions with an unsupported session engine.
        It checks that a management.CommandError is raised with a specific error message when the clearsessions command is executed.
        The test ensures that the system handles unsupported session engines correctly and provides informative error messages to the user.
        """
        msg = (
            "Session engine 'sessions_tests.no_clear_expired' doesn't "
            "support clearing expired sessions."
        )
        with self.settings(SESSION_ENGINE="sessions_tests.no_clear_expired"):
            with self.assertRaisesMessage(management.CommandError, msg):
                management.call_command("clearsessions")


class SessionBaseTests(SimpleTestCase):
    not_implemented_msg = "subclasses of SessionBase must provide %s() method"

    def setUp(self):
        self.session = SessionBase()

    def test_create(self):
        """

        Tests that attempting to create an entry through the session raises a NotImplementedError.

        This test case verifies that an informative error message is provided when the 
        create functionality is not implemented, ensuring that users are properly notified 
        of the missing implementation.

        """
        msg = self.not_implemented_msg % "a create"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.session.create()

    async def test_acreate(self):
        msg = self.not_implemented_msg % "a create"
        with self.assertRaisesMessage(NotImplementedError, msg):
            await self.session.acreate()

    def test_delete(self):
        """
        Tests that attempting to delete an object raises a NotImplementedError.

        This test case ensures that the delete method is currently not implemented and 
        raises the expected error message when called. The message includes a clear 
        indication that a delete operation is not supported, providing helpful feedback 
        for future implementation or error handling purposes.
        """
        msg = self.not_implemented_msg % "a delete"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.session.delete()

    async def test_adelete(self):
        msg = self.not_implemented_msg % "a delete"
        with self.assertRaisesMessage(NotImplementedError, msg):
            await self.session.adelete()

    def test_exists(self):
        """

        Verifies that the exists method raises a NotImplementedError when called.

        This test case checks that attempting to check the existence of an object
        without a valid identifier will trigger a NotImplementedError with a 
        specific error message, ensuring that the method is not implemented 
        as expected.

        """
        msg = self.not_implemented_msg % "an exists"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.session.exists(None)

    async def test_aexists(self):
        """
        Tests that the 'aexists' method raises a NotImplementedError when invoked.

        This test case verfies that an attempt to use the 'aexists' method results in 
        the expected error, indicating that the method has not been implemented. The 
        error message includes a description of the unimplemented method. 

        :raises: NotImplementedError 

        """
        msg = self.not_implemented_msg % "an exists"
        with self.assertRaisesMessage(NotImplementedError, msg):
            await self.session.aexists(None)

    def test_load(self):
        """

        Tests that loading data raises a NotImplementedError.

        This test case checks that calling the load method on the session object
        results in a NotImplementedError being raised with the correct error message.
        The message indicates that the load functionality has not been implemented.

        """
        msg = self.not_implemented_msg % "a load"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.session.load()

    async def test_aload(self):
        """

        Test that the aload method raises a NotImplementedError with the expected message.

        This test case verifies that an attempt to call the aload method on the session
        object results in a NotImplementedError being raised, indicating that the method
        is not implemented. The error message is checked to ensure it matches the expected
        message for an 'a load' operation.

        """
        msg = self.not_implemented_msg % "a load"
        with self.assertRaisesMessage(NotImplementedError, msg):
            await self.session.aload()

    def test_save(self):
        """
        Tests that attempting to save raises a NotImplementedError with the expected message, 
        indicating that the save functionality has not been implemented.
        """
        msg = self.not_implemented_msg % "a save"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.session.save()

    async def test_asave(self):
        """
        Tests that calling the asave method on a session raises a NotImplementedError.

        This test ensures that an appropriate error message is provided when the 
        asave method is not implemented, helping to enforce its proper implementation 
        in subclasses or other parts of the codebase.

        The expected error message includes a specific phrase indicating that 'a save' 
        is not implemented, which is checked to ensure consistency in error handling.

        Raises:
            NotImplementedError: When the asave method is called without implementation.

        """
        msg = self.not_implemented_msg % "a save"
        with self.assertRaisesMessage(NotImplementedError, msg):
            await self.session.asave()

    def test_test_cookie(self):
        """
        Tests the functionality of setting and deleting a test cookie in a session.

         Verifies that a test cookie is initially not present in the session, 
         then checks that it is correctly set and deleted, ensuring that 
         the session accurately reflects the cookie's presence or absence.
        """
        self.assertIs(self.session.has_key(self.session.TEST_COOKIE_NAME), False)
        self.session.set_test_cookie()
        self.assertIs(self.session.test_cookie_worked(), True)
        self.session.delete_test_cookie()
        self.assertIs(self.session.has_key(self.session.TEST_COOKIE_NAME), False)

    async def test_atest_cookie(self):
        self.assertIs(await self.session.ahas_key(self.session.TEST_COOKIE_NAME), False)
        await self.session.aset_test_cookie()
        self.assertIs(await self.session.atest_cookie_worked(), True)
        await self.session.adelete_test_cookie()
        self.assertIs(await self.session.ahas_key(self.session.TEST_COOKIE_NAME), False)

    def test_is_empty(self):
        self.assertIs(self.session.is_empty(), True)
