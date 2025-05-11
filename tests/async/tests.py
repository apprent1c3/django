import asyncio
import os
from unittest import mock

from asgiref.sync import async_to_sync, iscoroutinefunction

from django.core.cache import DEFAULT_CACHE_ALIAS, caches
from django.core.exceptions import ImproperlyConfigured, SynchronousOnlyOperation
from django.http import HttpResponse, HttpResponseNotAllowed
from django.test import RequestFactory, SimpleTestCase
from django.utils.asyncio import async_unsafe
from django.views.generic.base import View

from .models import SimpleModel


class CacheTest(SimpleTestCase):
    def test_caches_local(self):
        @async_to_sync
        """
        Tests whether the local cache is shared across multiple synchronous accesses.
        """
        async def async_cache():
            return caches[DEFAULT_CACHE_ALIAS]

        cache_1 = async_cache()
        cache_2 = async_cache()
        self.assertIs(cache_1, cache_2)


class DatabaseConnectionTest(SimpleTestCase):
    """A database connection cannot be used in an async context."""

    async def test_get_async_connection(self):
        with self.assertRaises(SynchronousOnlyOperation):
            list(SimpleModel.objects.all())


class AsyncUnsafeTest(SimpleTestCase):
    """
    async_unsafe decorator should work correctly and returns the correct
    message.
    """

    @async_unsafe
    def dangerous_method(self):
        return True

    async def test_async_unsafe(self):
        # async_unsafe decorator catches bad access and returns the right
        # message.
        msg = (
            "You cannot call this from an async context - use a thread or "
            "sync_to_async."
        )
        with self.assertRaisesMessage(SynchronousOnlyOperation, msg):
            self.dangerous_method()

    @mock.patch.dict(os.environ, {"DJANGO_ALLOW_ASYNC_UNSAFE": "true"})
    @async_to_sync  # mock.patch() is not async-aware.
    async def test_async_unsafe_suppressed(self):
        # Decorator doesn't trigger check when the environment variable to
        # suppress it is set.
        try:
            self.dangerous_method()
        except SynchronousOnlyOperation:
            self.fail("SynchronousOnlyOperation should not be raised.")


class SyncView(View):
    def get(self, request, *args, **kwargs):
        return HttpResponse("Hello (sync) world!")


class AsyncView(View):
    async def get(self, request, *args, **kwargs):
        return HttpResponse("Hello (async) world!")


class ViewTests(SimpleTestCase):
    def test_views_are_correctly_marked(self):
        """
        Tests whether view classes are correctly identified as synchronous or asynchronous.
        """
        tests = [
            (SyncView, False),
            (AsyncView, True),
        ]
        for view_cls, is_async in tests:
            with self.subTest(view_cls=view_cls, is_async=is_async):
                self.assertIs(view_cls.view_is_async, is_async)
                callback = view_cls.as_view()
                self.assertIs(iscoroutinefunction(callback), is_async)

    def test_mixed_views_raise_error(self):
        """
        Tests that a view with mixed synchronous and asynchronous HTTP handlers raises an error.
        """
        class MixedView(View):
            def get(self, request, *args, **kwargs):
                return HttpResponse("Hello (mixed) world!")

            async def post(self, request, *args, **kwargs):
                return HttpResponse("Hello (mixed) world!")

        msg = (
            f"{MixedView.__qualname__} HTTP handlers must either be all sync or all "
            "async."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            MixedView.as_view()

    def test_options_handler_responds_correctly(self):
        """
        Tests that the options handler of SyncView and AsyncView responds correctly, verifying if the response is a coroutine or not, and that it returns an HttpResponse instance.
        """
        tests = [
            (SyncView, False),
            (AsyncView, True),
        ]
        for view_cls, is_coroutine in tests:
            with self.subTest(view_cls=view_cls, is_coroutine=is_coroutine):
                instance = view_cls()
                response = instance.options(None)
                self.assertIs(
                    asyncio.iscoroutine(response),
                    is_coroutine,
                )
                if is_coroutine:
                    response = asyncio.run(response)

                self.assertIsInstance(response, HttpResponse)

    def test_http_method_not_allowed_responds_correctly(self):
        """
        Tests that views respond correctly when receiving an HTTP method that is not allowed.

        Checks both synchronous and asynchronous views, verifying that the response is an
        instance of HttpResponseNotAllowed and that the response is a coroutine if the view is
        asynchronous.
        """
        request_factory = RequestFactory()
        tests = [
            (SyncView, False),
            (AsyncView, True),
        ]
        for view_cls, is_coroutine in tests:
            with self.subTest(view_cls=view_cls, is_coroutine=is_coroutine):
                instance = view_cls()
                response = instance.http_method_not_allowed(request_factory.post("/"))
                self.assertIs(
                    asyncio.iscoroutine(response),
                    is_coroutine,
                )
                if is_coroutine:
                    response = asyncio.run(response)

                self.assertIsInstance(response, HttpResponseNotAllowed)

    def test_base_view_class_is_sync(self):
        """
        View and by extension any subclasses that don't define handlers are
        sync.
        """
        self.assertIs(View.view_is_async, False)
