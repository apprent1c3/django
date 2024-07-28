import os
from unittest import mock

from django.core.checks.async_checks import E001, check_async_unsafe
from django.test import SimpleTestCase


class AsyncCheckTests(SimpleTestCase):
    @mock.patch.dict(os.environ, {"DJANGO_ALLOW_ASYNC_UNSAFE": ""})
    def test_no_allowed_async_unsafe(self):
        """
        This is a comment
        """
        self.assertEqual(check_async_unsafe(None), [])

    @mock.patch.dict(os.environ, {"DJANGO_ALLOW_ASYNC_UNSAFE": "true"})
    def test_allowed_async_unsafe_set(self):
        """
        This is a comment
        """
        self.assertEqual(check_async_unsafe(None), [E001])
