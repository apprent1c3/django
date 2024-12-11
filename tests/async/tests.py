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
        async def async_cache():
            return caches[DEFAULT_CACHE_ALIAS]

        cache_1 = async_cache()
        cache_2 = async_cache()
        self.assertIs(cache_1, cache_2)


class DatabaseConnectionTest(SimpleTestCase):
    """A database connection cannot be used in an async context."""

    async def test_get_async_connection(self):
        """
        Tests that attempting to retrieve an asynchronous connection results in a SynchronousOnlyOperation exception.

        This test ensures that the asynchronous connection retrieval is properly handled and 
        raises the expected exception when attempting to use synchronous operations.

        Raises:
            SynchronousOnlyOperation: When trying to retrieve an asynchronous connection synchronously.
        """
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
        Tests that views are correctly marked as asynchronous or synchronous.

        This test case checks if the `view_is_async` attribute of a view class and the 
        resulting view function from `as_view()` match the expected asynchronous 
        behavior. It verifies this for both synchronous and asynchronous view classes.

        The test iterates over a series of view classes, each with an expected 
        asynchronous behavior, and asserts that the `view_is_async` attribute and the 
        view function's coroutine status are consistent with the expected behavior.
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

        Tests that a view class with a mix of synchronous and asynchronous HTTP handlers raises an error.

        This test case checks that the view class must have either all synchronous or all asynchronous handlers.
        If a mix of both is used, it raises an ImproperlyConfigured exception with a descriptive error message.

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
        Tests the OPTIONS handler in different view classes to ensure it responds correctly.

        This test function verifies that the OPTIONS handler in both synchronous and asynchronous views 
        returns the correct type of response. It checks that asynchronous views return a coroutine and 
        synchronous views return a response directly. The response is also verified to be an instance of 
        HttpResponse.

        The test covers two scenarios: one for synchronous views and one for asynchronous views, 
        providing a comprehensive check of the OPTIONS handler's behavior in different contexts.
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

        Tests if views correctly handle HTTP method not allowed requests.

        The function verifies that SyncView and AsyncView instances return the 
        correct response type when an HTTP method not allowed request is made.
        It checks if the response is a coroutine for AsyncView and not for SyncView.
        The response is then evaluated to ensure it is an instance of HttpResponseNotAllowed.

        This test covers both synchronous and asynchronous views, providing assurance
        that the application handles invalid HTTP methods as expected.

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
