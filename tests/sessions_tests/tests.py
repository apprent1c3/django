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
        self.session["cat"] = "dog"
        self.assertIs(self.session.modified, True)
        self.assertEqual(self.session.pop("cat"), "dog")

    async def test_store_async(self):
        await self.session.aset("cat", "dog")
        self.assertIs(self.session.modified, True)
        self.assertEqual(await self.session.apop("cat"), "dog")

    def test_pop(self):
        """
        Tests the removal of an item from a session using the pop method, verifying the correct return value and side effects on the session's accessed and modified state.
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
        Tests asynchronous population of a key from the session, verifying that the key is correctly removed and flags for access and modification are set accordingly.
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
        self.assertEqual(
            self.session.pop("some key", "does not exist"), "does not exist"
        )
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_pop_default_async(self):
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
        self.session.update({"update key": 1})
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertEqual(self.session.get("update key", None), 1)

    async def test_update_async(self):
        await self.session.aupdate({"update key": 1})
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)
        self.assertEqual(await self.session.aget("update key", None), 1)

    def test_has_key(self):
        """
        Tests the session's key presence detection, ensuring that accessing a session key sets the accessed flag to True and does not modify the session's modified flag.
        """
        self.session["some key"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertIn("some key", self.session)
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_has_key_async(self):
        """
        Tests if the session's has_key method works correctly in an asynchronous context, 
        including its effect on the session's 'accessed' and 'modified' state.
        """
        await self.session.aset("some key", 1)
        self.session.modified = False
        self.session.accessed = False
        self.assertIs(await self.session.ahas_key("some key"), True)
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_values(self):
        """
        Tests the behavior of session values, including empty values, setting values, and tracking accessed and modified states.
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
        """
        Tests the asynchronous value setting and retrieval functionality of the session.

        Verifies that a session can store and retrieve values asynchronously, 
        and that the session's accessed and modified status are updated accordingly.
        """
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
        Tests the keys() method of a session object by setting a value, verifying the key is present, and checking the accessed and modified flags are updated correctly.
        """
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.keys()), ["x"])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_keys_async(self):
        """
        Tests the asynchronous keys functionality of a session, verifying that accessing keys updates the session's accessed flag without modifying the modified flag.
        """
        await self.session.aset("x", 1)
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(await self.session.akeys()), ["x"])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_items(self):
        """
        Verifies the functionality of the session's items method, checking that it returns the expected key-value pairs and updates the session's accessed status accordingly.
        """
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.items()), [("x", 1)])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_items_async(self):
        """
        Tests asynchronous session item retrieval and access tracking. Verifies that item retrieval updates the session's access status while preserving its modification status.
        """
        await self.session.aset("x", 1)
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(await self.session.aitems()), [("x", 1)])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_clear(self):
        """
        Tests the clear method of a session object, verifying it correctly removes all items and updates the session's accessed and modified status.
        """
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.items()), [("x", 1)])
        self.session.clear()
        self.assertEqual(list(self.session.items()), [])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, True)

    def test_save(self):
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
        """
        Tests the session flush functionality to ensure that it correctly removes the session data and regenerates a new session key.
        """
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
        Tests the asynchronous session flush functionality.

        Verifies that flushing the session removes the previous session key, 
        updates the session key, and sets the session's modified and accessed flags accordingly.
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
        Tests the session cycle key functionality.

        This function verifies that cycling the session key successfully replaces the old key with a new one,
        removes the old session from the database, and preserves the session data.
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
        """
        Tests the asynchronous cycling of a session key, verifying that the old key is removed and the new key has the same data.
        """
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
        """
        Tests that the session cache is properly reset after cycling the session key when no session cache exists.

        Verifies that the session data remains intact after a key cycle operation, ensuring data consistency and preventing unintended data loss.
        """
        self.session["a"], self.session["b"] = "c", "d"
        self.session.save()
        prev_data = self.session.items()
        self.session = self.backend(self.session.session_key)
        self.assertIs(hasattr(self.session, "_session_cache"), False)
        self.session.cycle_key()
        self.assertCountEqual(self.session.items(), prev_data)

    async def test_cycle_with_no_session_cache_async(self):
        """
        Tests the cycle functionality when no session cache is present.

        Verifies that after cycling the session key, the session data remains unchanged.

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
        """
        Test that a session with an invalid key is handled correctly, ensuring it is created and saved without using the provided key and that data cannot be retrieved from it.
        """
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
        Tests the behavior of the session backend when an invalid key is provided, verifying that the session is properly created, saved, and deleted, and that data retrieval returns None for non-existent keys.
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
        """
        Tests that the custom expiry seconds for a session are set correctly, verifying that the calculated expiry date and age match the expected values based on the provided modification time.
        """
        modification = timezone.now()

        self.session.set_expiry(10)

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    async def test_custom_expiry_seconds_async(self):
        """

        Tests the functionality of setting a custom expiry time in seconds for a session.

        Verifies that the expiry date and age are correctly calculated based on the provided modification time and custom expiry seconds.

        """
        modification = timezone.now()

        await self.session.aset_expiry(10)

        date = await self.session.aget_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = await self.session.aget_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    def test_custom_expiry_timedelta(self):
        """
        Tests the custom expiry time delta for a session.

        Verifies that the session's expiry date and age are correctly calculated
        based on a custom expiry time delta set using the `set_expiry` method.
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
        """
        Tests the custom expiry time calculation using a timedelta, verifying that the expiry date and age are correctly calculated based on a simulated modification time.
        """
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
        Tests that custom session expiry datetime set and retrieved correctly.

        Verifies that the session expiry date and age are calculated as expected
        based on the provided modification time and expiry offset.
        """
        modification = timezone.now()

        self.session.set_expiry(modification + timedelta(seconds=10))

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    async def test_custom_expiry_datetime_async(self):
        """
        Tests asynchronous expiry date and age retrieval with a custom expiry datetime.

        Verifies that setting a custom expiry date and then retrieving the expiry date and age returns the expected values.
        """
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
        Tests the get_expire_at_browser_close method of the session.

        This method checks if the session expires when the browser is closed, 
        considering both global session settings and individual session expiry timeouts.
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

        Tests the behavior of getting the expire at browser close setting for a session.

        Verifies the session's expire at browser close setting is correctly determined based on 
        the global SESSION_EXPIRE_AT_BROWSER_CLOSE setting and the session's expiry value.

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
        Tests session decoding failure and logs a security warning when corrupted session data is encountered, ensuring that suspicious session activity is properly detected and reported.
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
        """

        Tests that a session expires immediately when its expiry time is set to a time in the past.

        Verifies that a session with an immediate expiry time is treated as expired and that
        its data is not accessible after expiry.

        """
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
        Tests that a session key expires after a certain period, effectively removing its data from the backend.

        Verifies that setting an expiration time and saving the session results in the session data being unavailable after the expiration time has passed, and that a new session key is generated when accessing the expired session.
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
        """
        Tests that loading a non-existent session using the asynchronous load method does not create a new session record.
        """
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
        Clears expired keys from the session.

        Tests that expired keys are properly removed when :meth:`aclear_expired` is called,
        ensuring that only valid keys remain in the session.
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
        Verifies that a session's extra fields are correctly synced with the database model, specifically the '_auth_user_id' field. 

         Tests that setting and saving the field in the session updates the model, and removing it from the session clears the corresponding model field.
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
        Sets up a temporary session store for the test case, overriding the default session file path and ensuring it is cleaned up after the test is completed.
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
        Tests that the session cookie has the HttpOnly flag set when SESSION_COOKIE_HTTPONLY is True.
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
        request = self.request_factory.get("/")
        middleware = SessionMiddleware(self.get_response_touching_session)
        response = middleware(request)
        self.assertEqual(
            response.cookies[settings.SESSION_COOKIE_NAME]["samesite"], "Strict"
        )

    @override_settings(SESSION_COOKIE_HTTPONLY=False)
    def test_no_httponly_session_cookie(self):
        """
        Tests that the session cookie is set without the HttpOnly flag when the SESSION_COOKIE_HTTPONLY setting is False.
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
        """
        Tests that session data is not saved when an Internal Server Error (500) occurs.
        """
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
        Tests that session data is not saved when a 5xx error response is returned by the view. This ensures that session modifications made during the request are not persisted in the case of an internal server error.
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
        Tests that a SessionInterrupted exception is raised when a session is updated and then deleted during the course of a request, simulating a concurrent session deletion, such as when a user logs out in a separate request.
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

        Tests that the session is deleted when the response ends, 
        by verifying the 'Set-Cookie' header in the response.

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

        Test that the session deletion process functions correctly when a custom domain and path are set for session cookies.

        Ensures that the session cookie is properly deleted and its expiration date set to the past when the session is ended.

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
        """
        Tests that the session middleware does not set a session cookie when a request 
        with no session cookie results in an empty session being flushed from the response.
        """
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
        msg = self.not_implemented_msg % "a load"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.session.load()

    async def test_aload(self):
        msg = self.not_implemented_msg % "a load"
        with self.assertRaisesMessage(NotImplementedError, msg):
            await self.session.aload()

    def test_save(self):
        msg = self.not_implemented_msg % "a save"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.session.save()

    async def test_asave(self):
        msg = self.not_implemented_msg % "a save"
        with self.assertRaisesMessage(NotImplementedError, msg):
            await self.session.asave()

    def test_test_cookie(self):
        """
        Tests the functionality of setting, verifying, and deleting a test cookie in the session.
        """
        self.assertIs(self.session.has_key(self.session.TEST_COOKIE_NAME), False)
        self.session.set_test_cookie()
        self.assertIs(self.session.test_cookie_worked(), True)
        self.session.delete_test_cookie()
        self.assertIs(self.session.has_key(self.session.TEST_COOKIE_NAME), False)

    async def test_atest_cookie(self):
        """
        Tests the functionality of setting and deleting a test cookie in a session.\"\"\"

        :param self: The test instance.
        :note: Verifies that the test cookie is initially absent, can be successfully set, and then deleted.
        """
        self.assertIs(await self.session.ahas_key(self.session.TEST_COOKIE_NAME), False)
        await self.session.aset_test_cookie()
        self.assertIs(await self.session.atest_cookie_worked(), True)
        await self.session.adelete_test_cookie()
        self.assertIs(await self.session.ahas_key(self.session.TEST_COOKIE_NAME), False)

    def test_is_empty(self):
        self.assertIs(self.session.is_empty(), True)
