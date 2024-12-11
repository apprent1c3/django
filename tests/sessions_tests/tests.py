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
        """
        Sets up the test environment by establishing a session with the backend.

         The session is created by instantiating the backend and storing it in the `session` attribute. 
         A cleanup function is also registered to ensure the session is deleted after the test, 
         regardless of the test outcome, to maintain a clean state.
        """
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
        Tests the functionality of storing and retrieving data from a session.

        This test case checks if data can be successfully stored in the session
        and if the session is marked as modified after storing data.
        It also verifies that the stored data can be correctly retrieved and removed
        from the session using the pop method.

        The test covers the following scenarios:
        - Storing a value in the session
        - Checking if the session is marked as modified after storing data
        - Retrieving and removing the stored value from the session
        """
        self.session["cat"] = "dog"
        self.assertIs(self.session.modified, True)
        self.assertEqual(self.session.pop("cat"), "dog")

    async def test_store_async(self):
        """

        Tests asynchronous storing and popping of key-value pairs in the session.

        Verifies that setting a key-value pair using the :meth:`aset` method modifies the session,
        and that the correct value is returned when popping the key using the :meth:`apop` method.

        """
        await self.session.aset("cat", "dog")
        self.assertIs(self.session.modified, True)
        self.assertEqual(await self.session.apop("cat"), "dog")

    def test_pop(self):
        self.session["some key"] = "exists"
        # Need to reset these to pretend we haven't accessed it:
        self.accessed = False
        self.modified = False

        self.assertEqual(self.session.pop("some key"), "exists")
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertIsNone(self.session.get("some key"))

    async def test_pop_async(self):
        await self.session.aset("some key", "exists")
        # Need to reset these to pretend we haven't accessed it:
        self.accessed = False
        self.modified = False

        self.assertEqual(await self.session.apop("some key"), "exists")
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertIsNone(await self.session.aget("some key"))

    def test_pop_default(self):
        self.assertEqual(
            self.session.pop("some key", "does not exist"), "does not exist"
        )
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_pop_default_async(self):
        """

        Tests the asynchronous pop operation with a default value when the key does not exist.

        Verifies that the default value is returned when the key is not found, and checks the state of the session after the operation,
        confirming that the session is marked as accessed but not modified.

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
        Tests that popping a key from the session raises a KeyError when the key does not exist and no default value is provided. Verifies that the session behaves as expected when attempting to remove a non-existent key, ensuring that the correct exception is raised in this scenario.
        """
        with self.assertRaises(KeyError):
            self.session.pop("some key")

    async def test_pop_no_default_keyerror_raised_async(self):
        """
        Tests that a KeyError is raised when attempting to asynchronously pop a key from the session using apop, without providing a default value, and the key does not exist.
        """
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
        self.session.update({"update key": 1})
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertEqual(self.session.get("update key", None), 1)

    async def test_update_async(self):
        """

        Tests the asynchronous update functionality of a session.

        Verifies that updating a value in the session successfully sets the 
        'accessed' and 'modified' flags to True. Additionally, confirms that 
        the updated value can be retrieved correctly using the asynchronous 
        get method.

        """
        await self.session.aupdate({"update key": 1})
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertEqual(await self.session.aget("update key", None), 1)

    def test_has_key(self):
        """

        Tests if a dictionary key is present in the session object and if accessing it updates the accessed flag correctly.

        This test case checks that the session object contains a specific key and that when the key is accessed, the session's accessed flag is set to True, while the modified flag remains unchanged.

        It verifies the following conditions:
        - The session object contains the key 'some key'.
        - Accessing the session object updates the accessed flag to True.
        - The modified flag remains False after accessing the session object.

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

        Tests the keys method of a session object.

        This test case verifies that the keys method returns the correct list of keys
        from the session object, and that accessing the keys updates the session's
        accessed status but does not modify the session's modified status.

        Ensures that the session object behaves correctly when its keys are accessed,
        including the update of internal state variables.

        """
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.keys()), ["x"])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_keys_async(self):
        """
        Tests the asynchronous retrieval of keys from a session.

        Verifies that the `akeys` method correctly returns a list of keys in the session.
        Also checks that accessing the keys updates the session's `accessed` flag, while
        the `modified` flag remains unchanged if no modifications were made.

        This test ensures proper functionality of the asynchronous key retrieval
        mechanism, providing a foundation for further session-related tests and operations.
        """
        await self.session.aset("x", 1)
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(await self.session.akeys()), ["x"])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_items(self):
        """

        Tests the behavior of the session's items method, verifying that it returns 
        the correct key-value pairs and updates the session's accessed status accordingly, 
        without modifying the session. 

        The function checks that accessing the session's items correctly returns the 
        stored data, and that it sets the session's accessed status to True. Additionally, 
        it confirms that the session's modified status remains unchanged (False).

        """
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.items()), [("x", 1)])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_items_async(self):
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

        Tests the functionality of saving a session.

        Verifies that after saving a session, the session exists and can be successfully retrieved using its session key.

        This test ensures the session persistence mechanism is working correctly, allowing for reliable storage and retrieval of session data.

        """
        self.session.save()
        self.assertIs(self.session.exists(self.session.session_key), True)

    async def test_save_async(self):
        await self.session.asave()
        self.assertIs(await self.session.aexists(self.session.session_key), True)

    def test_delete(self):
        self.session.save()
        self.session.delete(self.session.session_key)
        self.assertIs(self.session.exists(self.session.session_key), False)

    async def test_delete_async(self):
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
        """
        Tests the asynchronous flush functionality of a session.

        Verifies that after flushing the session, the previous session key no longer exists,
        a new session key is generated, and the session's modified and accessed flags are correctly set.
        The flush operation is expected to remove all data associated with the previous session key.
        This test ensures that the session is properly reset and a new session key is assigned after flushing.
        """
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
        """

        Tests the cycling of a session key, ensuring that the old key is deleted, 
        a new key is generated, and the session data remains intact.

        This test verifies that after the key cycle operation, the previous session key 
        no longer exists, the new session key is different from the previous one, and 
        the session data has been successfully transferred to the new key.

        """
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
        """

        Tests the functionality of cycling a session key without utilizing session cache.

        This test case ensures that when a session key is cycled, the data associated with the previous session is preserved and accessible.
        The session is initialized with some data, saved, and then the session key is cycled.
        After cycling the key, the test asserts that the new session does not have a session cache and that the data from the previous session is still present.

        """
        await self.session.aset("a", "c")
        await self.session.aset("b", "d")
        await self.session.asave()
        prev_data = await self.session.aitems()
        self.session = self.backend(self.session.session_key)
        self.assertIs(hasattr(self.session, "_session_cache"), False)
        await self.session.acycle_key()
        self.assertCountEqual(await self.session.aitems(), prev_data)

    def test_save_doesnt_clear_data(self):
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

        Tests that the session key attribute of a session object is read-only.

        Verifies that attempting to manually set or modify the session key raises an AttributeError, 
        ensuring the session key can only be generated or updated through the intended methods.

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
        modification = timezone.now()

        self.session.set_expiry(10)

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    async def test_custom_expiry_seconds_async(self):
        modification = timezone.now()

        await self.session.aset_expiry(10)

        date = await self.session.aget_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = await self.session.aget_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    def test_custom_expiry_timedelta(self):
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
        Tests that a custom expiry datetime can be successfully set and retrieved for a session.

        The session expiry is modified to a specific datetime, and then the expiry date and age are retrieved and verified to match the expected values.

        Checks the correct functioning of the session's expiry date and age calculation when a custom expiry datetime is provided, ensuring that the session's expiry details are accurately updated and retrieved.
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
        self.session.set_expiry(None)
        self.session.set_expiry(10)
        self.session.set_expiry(None)
        self.assertEqual(self.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

    async def test_custom_expiry_reset_async(self):
        await self.session.aset_expiry(None)
        await self.session.aset_expiry(10)
        await self.session.aset_expiry(None)
        self.assertEqual(
            await self.session.aget_expiry_age(), settings.SESSION_COOKIE_AGE
        )

    def test_get_expire_at_browser_close(self):
        # Tests get_expire_at_browser_close with different settings and different
        # set_expiry calls
        """
        Tests the functionality of the get_expire_at_browser_close method.

        This method determines whether a session will expire when the user closes their browser.
        It considers the SESSION_EXPIRE_AT_BROWSER_CLOSE setting and the session's expiry value.
        The session will expire at browser close if the expiry value is 0 and the setting is True.
        Otherwise, it will not expire at browser close unless the setting is True and the expiry value is None.

        The method is tested under different conditions, including when SESSION_EXPIRE_AT_BROWSER_CLOSE is both True and False,
        and when the session's expiry value is set to a positive number, 0, and None.
        """
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

        Tests the behavior of the session's expire_at_browser_close property.

        This test case checks how the session's expire_at_browser_close property is 
        affected by the session's expiry value and the SESSION_EXPIRE_AT_BROWSER_CLOSE 
        setting. The expire_at_browser_close property indicates whether the session 
        expires when the browser is closed.

        The test covers two scenarios: when SESSION_EXPIRE_AT_BROWSER_CLOSE is set to 
        False and when it is set to True. In each scenario, the test checks the 
        expire_at_browser_close property after setting the session's expiry value to 
        10 (a non-zero value), 0 (indicating expire at browser close), and None 
        (indicating no expiry).

        The test ensures that the expire_at_browser_close property behaves as expected 
        in these different scenarios.

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
        data = {"a test key": "a test value"}
        encoded = self.session.encode(data)
        self.assertEqual(self.session.decode(encoded), data)

    def test_decode_failure_logged_to_security(self):
        """
        Tests that decode failures in session data are logged to the security system.

        This test checks that when session data is corrupted or incorrectly encoded,
        the decode failure is logged as a warning to the 'django.security.SuspiciousSession' logger.
        The test uses a variety of malformed encoded session data to verify that the logging
        mechanism is triggered correctly and that the logged message contains the expected error text.

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
        """
        Test the functionality of clearing expired sessions.

        This test case verifies that the aclear_expired method correctly removes
        expired sessions from the database. It first sets up two sessions with
        different expiry times, then saves them. After calling aclear_expired on
        both sessions, it checks that only the session with a positive expiry time
        remains in the database.

        The test covers the following scenarios:

        * Setting up sessions with expiry times
        * Saving sessions to the database
        * Clearing expired sessions using the aclear_expired method
        * Verifying the correct number of sessions remains in the database after clearing expired sessions
        """
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
        """
        Tests the inclusion of extra fields in the session model.

        Verifies that arbitrary data stored in the session is correctly 
        persisted to and retrieved from the session model. Specifically, 
        it checks that a custom field ('account_id') is updated when 
        a corresponding key ('_auth_user_id') is added to or removed from 
        the session, and that the changes are correctly saved and 
        retrieved from the session model instance.

        The test covers the following scenarios:

        * Adding a custom key to the session and verifying its presence 
          in the session model
        * Removing the custom key from the session and verifying its 
          absence in the session model
        """
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

        Tests the reset functionality of custom session expiry.

        Verifies that setting a custom expiry age, then resetting it back to the default
        (None), results in the session expiry age being reset to the custom session cookie age.

        This test ensures that resetting the session expiry age correctly reverts to the
        previously defined custom session cookie age, rather than a default or zero value.

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
        """
        Verifies that the exists method checks the cache before performing a database query.

        This test ensures that the exists method prioritizes searching the cache for the session 
        instead of immediately querying the database. It confirms that the cache is utilized 
        correctly to minimize unnecessary database queries and optimize performance.

        :return: None
        """
        self.session.save()
        with self.assertNumQueries(0):
            self.assertIs(self.session.exists(self.session.session_key), True)

    # Some backends might issue a warning
    @ignore_warnings(module="django.core.cache.backends.base")
    def test_load_overlong_key(self):
        self.session._session_key = (string.ascii_letters + string.digits) * 20
        self.assertEqual(self.session.load(), {})

    @override_settings(SESSION_CACHE_ALIAS="sessions")
    def test_non_default_cache(self):
        # 21000 - CacheDB backend should respect SESSION_CACHE_ALIAS.
        """
        Raises an exception to verify that using a non-default cache alias raises an error, confirming the expected behavior when an invalid cache backend is utilized.
        """
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

        Initializes the test environment by setting up a temporary session store.

        This method overrides the default setUp behavior to ensure that each test runs
        with a clean and isolated session store. It achieves this by temporarily
        replacing the original session file path with a new, randomly generated
        directory. After the test is completed, the temporary directory is removed.

        The original session file path is preserved and restored after the test.
        Additionally, any existing storage path associated with the backend is deleted
        to prevent interference with the test's temporary storage. The parent class's
        setUp method is then called to perform any remaining setup tasks.

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

        Tests the configuration check for the backend by simulating an improperly configured session file path.
        Verifies that an ImproperlyConfigured exception is raised when the backend is initialized with an invalid configuration.

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
        Creates a temporary directory and returns its path as a Path object.

        This method generates a unique, temporary directory and provides its path
        in a convenient and Pythonic format. The directory is created in a location
        suitable for temporary files and will be deleted when no longer needed.

        :returns: Path object representing the temporary directory
        :rtype: Path
        """
        tmp_dir = super().mkdtemp()
        return Path(tmp_dir)


class CacheSessionTests(SessionTestsMixin, SimpleTestCase):
    backend = CacheSession

    # Some backends might issue a warning
    @ignore_warnings(module="django.core.cache.backends.base")
    def test_load_overlong_key(self):
        self.session._session_key = (string.ascii_letters + string.digits) * 20
        self.assertEqual(self.session.load(), {})

    def test_default_cache(self):
        """
        Tests the default cache behavior by verifying that a session's cache key is properly stored and retrievable after saving the session.
        """
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
        self.session = self.backend()

        self.session.save()
        self.assertIsNone(caches["default"].get(self.session.cache_key))
        self.assertIsNotNone(caches["sessions"].get(self.session.cache_key))

    def test_create_and_save(self):
        self.session = self.backend()
        self.session.create()
        self.session.save()
        self.assertIsNotNone(caches["default"].get(self.session.cache_key))

    async def test_create_and_save_async(self):
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
        request = self.request_factory.get("/")
        middleware = SessionMiddleware(self.get_response_touching_session)

        # Handle the response through the middleware
        response = middleware(request)
        self.assertIs(response.cookies[settings.SESSION_COOKIE_NAME]["secure"], True)

    @override_settings(SESSION_COOKIE_HTTPONLY=True)
    def test_httponly_session_cookie(self):
        """
        Tests that the session cookie is set with the HttpOnly flag when the SESSION_COOKIE_HTTPONLY setting is enabled.

        This test case verifies that the SessionMiddleware correctly sets the HttpOnly attribute on the session cookie 
        in the response, preventing JavaScript from accessing the session cookie. The test checks both the presence of 
        the HttpOnly flag in the cookie's attributes and its correct string representation in the cookie's value.
        """
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
        ARGE Test that the session cookie's SameSite attribute is set to 'Strict' when the SESSION_COOKIE_SAMESITE setting is set to 'Strict'.
        """
        request = self.request_factory.get("/")
        middleware = SessionMiddleware(self.get_response_touching_session)
        response = middleware(request)
        self.assertEqual(
            response.cookies[settings.SESSION_COOKIE_NAME]["samesite"], "Strict"
        )

    @override_settings(SESSION_COOKIE_HTTPONLY=False)
    def test_no_httponly_session_cookie(self):
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
        Tests if session data is not saved when a 5xx HTTP error occurs.

        This test simulates a scenario where the server returns a 503 Service Unavailable response,
        sets a session variable, and then verifies that the session data is not persisted.

        It covers the functionality of the SessionMiddleware to correctly handle session data
        when an HTTP error occurs, ensuring that the session remains unchanged in such cases.
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
        def response_delete_session(request):
            """
            Deletes the current user session.

            This function creates a new temporary database session, saves it to ensure its existence, 
            and then immediately deletes it. It returns an empty HTTP response.
            """
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
        Tests that an exception is correctly handled when unpickling a session.

        Checks that the session's serializer is properly set and that saving the session
        succeeds. Then, simulates an unpickling error by mocking the signing loads function
        to raise a ValueError, and verifies the behavior when loading the session.

        The test case ensures that the session loading process handles deserialization
        exceptions as expected, providing a reliable session management mechanism.
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
        msg = self.not_implemented_msg % "a create"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.session.create()

    async def test_acreate(self):
        msg = self.not_implemented_msg % "a create"
        with self.assertRaisesMessage(NotImplementedError, msg):
            await self.session.acreate()

    def test_delete(self):
        msg = self.not_implemented_msg % "a delete"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.session.delete()

    async def test_adelete(self):
        msg = self.not_implemented_msg % "a delete"
        with self.assertRaisesMessage(NotImplementedError, msg):
            await self.session.adelete()

    def test_exists(self):
        msg = self.not_implemented_msg % "an exists"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.session.exists(None)

    async def test_aexists(self):
        msg = self.not_implemented_msg % "an exists"
        with self.assertRaisesMessage(NotImplementedError, msg):
            await self.session.aexists(None)

    def test_load(self):
        """

        Tests the session's load functionality to ensure it raises a NotImplementedError.

        This test case verifies that an attempt to load the session results in the
        correct error message being raised, indicating that the load operation is not
        implemented.

        """
        msg = self.not_implemented_msg % "a load"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.session.load()

    async def test_aload(self):
        """

        Tests the asynchronous load functionality of the session.

        This test case verifies that attempting to asynchronously load data using the aload method raises a NotImplementedError with a specific message, indicating that the implementation is not provided.

        The test confirms the expected behavior when the aload method is not implemented, ensuring that the correct error message is propagated.

        """
        msg = self.not_implemented_msg % "a load"
        with self.assertRaisesMessage(NotImplementedError, msg):
            await self.session.aload()

    def test_save(self):
        """
        Tests that a NotImplementedError is raised when attempting to save a session.

        This test ensures that the session's save method is not implemented and produces the expected error message, 
        indicating that the method needs to be implemented by subclasses or concrete implementations.

        :raises: AssertionError if the session's save method does not raise a NotImplementedError with the expected message.
        """
        msg = self.not_implemented_msg % "a save"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.session.save()

    async def test_asave(self):
        msg = self.not_implemented_msg % "a save"
        with self.assertRaisesMessage(NotImplementedError, msg):
            await self.session.asave()

    def test_test_cookie(self):
        """
        Tests the functionality of setting, checking, and deleting a test cookie in a session.

        This test case ensures that a test cookie is successfully set, verified, and then deleted from the session.
        It covers the key aspects of test cookie management, including checking for the cookie's existence before and after setting and deleting it.
        The purpose of this test is to guarantee that the session's test cookie functionality is working as expected, which is crucial for session management and related operations.
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
