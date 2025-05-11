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
        Tests the pop method of the session object, ensuring it correctly removes and returns a value, and updates the accessed and modified states.
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
        Tests the asynchronous pop operation in a session by storing a value, then verifying its retrieval and removal.
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

        Tests that accessing a session key causes the session's 'accessed' flag to be set to True,
        while leaving the 'modified' flag unchanged if the session content is not altered.

        """
        self.session["some key"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertIn("some key", self.session)
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_has_key_async(self):
        """
        Tests asynchronous key existence check in a session.

        Verifies that the has_key method correctly checks for key presence and updates the session's accessed status accordingly, without modifying the session.
        """
        await self.session.aset("some key", 1)
        self.session.modified = False
        self.session.accessed = False
        self.assertIs(await self.session.ahas_key("some key"), True)
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_values(self):
        """
        Tests the basics of session value storage and access tracking.
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

        Test asynchronous session value management.

        Verifies that the session's accessed and modified states are correctly updated
        when setting and retrieving values, and that the values are stored and retrieved
        as expected.

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
        Tests that accessing session keys correctly updates the session's 'accessed' state without modifying the 'modified' state.
        """
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.keys()), ["x"])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_keys_async(self):
        """
        Tests asynchronous retrieval of keys from a session, verifying that the accessed flag is set correctly after accessing the session's keys and that the modified flag remains unchanged.
        """
        await self.session.aset("x", 1)
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(await self.session.akeys()), ["x"])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_items(self):
        """
        Tests that iterating over session items correctly updates the session's accessed flag and leaves the modified flag unchanged.
        """
        self.session["x"] = 1
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(self.session.items()), [("x", 1)])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    async def test_items_async(self):
        """
        Verifies asynchronous session item storage and retrieval, checking that accessing session items correctly updates the session's accessed state.
        """
        await self.session.aset("x", 1)
        self.session.modified = False
        self.session.accessed = False
        self.assertEqual(list(await self.session.aitems()), [("x", 1)])
        self.assertIs(self.session.accessed, True)
        self.assertIs(self.session.modified, False)

    def test_clear(self):
        """
        Tests the clear functionality of a session, verifying that it removes all stored items and correctly updates the session's accessed and modified status.
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
        Tests the flush functionality of the session.

        Verifies that flushing the session removes it from the store, regenerates the session key, 
        and correctly updates the session's modified and accessed status.
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
        Tests asynchronous session flush functionality.

        Verifies that flushing a session removes its data, updates its key, and sets the appropriate flags.\"\"\"
        ```
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
        .Tests that the session key can be safely cycled, ensuring the old key is deleted and the new key has the same session data.
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
        Test that asynchronous session key cycling preserves existing data.

        Verifies that after cycling the session key, the old key is no longer valid,
        a new key is generated, and the stored data remains unchanged.
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
        Tests the cycle_key method of a session with no session cache, 
        ensuring that session data is preserved despite the session key change.
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
        Tests that the session cache is not used when cycling a session key, 
        ensuring data persistence between session creations.
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
        Tests the handling of an invalid session key by attempting to save, retrieve and delete a session with a predefined key, verifying that the session key is updated and that retrieving a non-existent key returns None.
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
        Tests asynchronous session creation and deletion with an invalid key, 
        verifying that the session key is updated and data operations behave as expected.
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
        Tests that a custom session expiry time in seconds is correctly applied and calculated.
        """
        modification = timezone.now()

        self.session.set_expiry(10)

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    async def test_custom_expiry_seconds_async(self):
        """

        Tests that custom expiry seconds are correctly set and retrieved asynchronously.

        Verifies that the expiry date and age calculated from a given modification time
        match the expected values based on the custom expiry seconds.

        """
        modification = timezone.now()

        await self.session.aset_expiry(10)

        date = await self.session.aget_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = await self.session.aget_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    def test_custom_expiry_timedelta(self):
        """
        Verifies that custom expiry timedelta is correctly applied and calculated for a session. Tests the session's expiry date and age based on a manually set modification time and a specified expiry duration.
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
        Tests the custom expiry functionality using a timedelta.

        Verifies that setting an expiry date using a timedelta correctly calculates the expiry date and age based on the provided modification time.
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
        Tests that custom expiry datetime is correctly set and retrieved from the session. Verifies that the expiry date and age are calculated as expected based on the provided modification time.
        """
        modification = timezone.now()

        self.session.set_expiry(modification + timedelta(seconds=10))

        date = self.session.get_expiry_date(modification=modification)
        self.assertEqual(date, modification + timedelta(seconds=10))

        age = self.session.get_expiry_age(modification=modification)
        self.assertEqual(age, 10)

    async def test_custom_expiry_datetime_async(self):
        """
        Tests the functionality of setting a custom expiry date and then retrieving it,
        verifying that the expiry date and age are correctly calculated and stored.
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

        Tests the get_expire_at_browser_close method of the session object.

        Verifies that the method returns the correct value based on the SESSION_EXPIRE_AT_BROWSER_CLOSE setting
        and the session's expiry value. The test covers various scenarios with different expiry values and setting combinations.

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

        Tests the session's expire_at_browser_close setting under different conditions.

        Verifies that the expire_at_browser_close setting is correctly determined based on the session's expiry value and the SESSION_EXPIRE_AT_BROWSER_CLOSE setting.

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
        Checks that decoding failures of session data are logged as security warnings, specifically as \"Session data corrupted\" messages, ensuring that invalid or corrupted session data does not go unnoticed.
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
        Tests that a session expires and its data is deleted after the set expiry time.

        Verifies that setting a session to expire in the past results in the session data being lost and a new session key being generated when accessed.

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
        Tests the actual expiry of a session after setting a negative expiry time.

        Verifies that after the session expires, the session key changes and the expired
        data is no longer available in the new session.
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
        Loading an unknown session key does not create a session record, preventing a potential DOS vulnerability by ensuring session records are not created on load.
        """
        session = self.backend("someunknownkey")
        session.load()

        self.assertIsNone(session.session_key)
        self.assertIs(session.exists(session.session_key), False)
        # provided unknown key was cycled, not reused
        self.assertNotEqual(session.session_key, "someunknownkey")

    async def test_session_load_does_not_create_record_async(self):
        """
        Tests that loading a non-existent session does not create a new record, ensuring the session key remains unknown and the session does not exist in the backend after loading.
        """
        session = self.backend("someunknownkey")
        await session.aload()

        self.assertIsNone(session.session_key)
        self.assertIs(await session.aexists(session.session_key), False)
        # Provided unknown key was cycled, not reused.
        self.assertNotEqual(session.session_key, "someunknownkey")

    def test_session_save_does_not_resurrect_session_logged_out_in_other_context(self):
        """
        Tests that a session is not resurrected by a concurrent request after being logged out in another context, ensuring session deletion persists even if changes were made before deletion.
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
        """
        Tests that a session is not resurrected when it is deleted in another context and 
        then updated concurrently, ensuring that the delete operation takes precedence.
        """
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
        """
        Verifies that the string representation of a session object is equal to its session key, ensuring that the session's identifier is correctly represented as a string.
        """
        self.session["x"] = 1
        self.session.save()

        session_key = self.session.session_key
        s = self.model.objects.get(session_key=session_key)

        self.assertEqual(str(s), session_key)

    def test_session_get_decoded(self):
        """
        Tests the retrieval of stored session data using the Session.get_decoded method, verifying it returns the expected values.
        """
        self.session["x"] = 1
        self.session.save()

        s = self.model.objects.get(session_key=self.session.session_key)

        self.assertEqual(s.get_decoded(), {"x": 1})

    def test_sessionmanager_save(self):
        """
        Tests the proper functioning of the SessionManager's save method, ensuring that changes to session data are correctly persisted.
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

            Tests the clearsessions command to ensure it correctly removes expired sessions from the database.

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

        Tests the removal of expired items from the session using the aclear_expired method.
        Verifies that expired keys are properly cleared and only active keys remain.

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
        Tests that the model properly handles an extra session field, specifically verifying that the value is stored and retrieved correctly, and that it is cleared when the session field is removed.
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
        """
        Tests that a failure to write to the cache does not result in an error being raised, instead logging an error message.
        """
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
        """
        Tests that a non-fatal error occurs when writing to the cache fails, resulting in an error log instead of a raised exception.
        """
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
        Sets up the test environment by creating a temporary session store and setting it as the new session file path, ensuring a clean session store for each test. The original session file path is stored and restored after the test.
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

            Tests the functionality of the clearsessions command, which removes 
            expired sessions from the system to ensure proper session management.

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
        Tests that the session cookie is set as HTTP-only when the SESSION_COOKIE_HTTPONLY setting is enabled, ensuring that JavaScript cannot access the cookie.
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
        Tests if a session cookie is sent without the HttpOnly flag when the SESSION_COOKIE_HTTPONLY setting is disabled.
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
        Tests if session data is saved when a 500 error occurs, ensuring that the session remains untouched in the event of an internal server error.
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
        Tests that session data is not saved when a 5xx response is returned, ensuring that session modifications are discarded in case of server errors, to prevent inconsistent session state.
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
        Tests that a SessionInterrupted exception is raised when a request's session is deleted before the request completes, simulating a concurrent logout.
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

        Tests if a session is correctly deleted at the end of a request, 
        verifying that the session cookie is properly cleared.

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
        Tests that a session deletion response includes a Set-Cookie header with the correct custom domain and path, effectively deleting the session cookie when the session is ended.
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
        Tests that when a session is flushed without setting a session cookie, no cookie is set in the response.
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
        Verifies that an emptied session with a still valid key is properly updated and saved.
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
        Verifies proper functionality of test cookies within a session.

        Ensures a test cookie can be successfully set, checked for, and subsequently deleted,
        confirming the session's ability to manage test cookies correctly.
        """
        self.assertIs(self.session.has_key(self.session.TEST_COOKIE_NAME), False)
        self.session.set_test_cookie()
        self.assertIs(self.session.test_cookie_worked(), True)
        self.session.delete_test_cookie()
        self.assertIs(self.session.has_key(self.session.TEST_COOKIE_NAME), False)

    async def test_atest_cookie(self):
        """
        Verifies the functionality of a test cookie by checking its existence, setting it, testing its effectiveness, and then deleting it, ensuring the session's cookie handling is working correctly.
        """
        self.assertIs(await self.session.ahas_key(self.session.TEST_COOKIE_NAME), False)
        await self.session.aset_test_cookie()
        self.assertIs(await self.session.atest_cookie_worked(), True)
        await self.session.adelete_test_cookie()
        self.assertIs(await self.session.ahas_key(self.session.TEST_COOKIE_NAME), False)

    def test_is_empty(self):
        self.assertIs(self.session.is_empty(), True)
