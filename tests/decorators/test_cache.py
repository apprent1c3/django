from unittest import mock

from asgiref.sync import iscoroutinefunction

from django.http import HttpRequest, HttpResponse
from django.test import SimpleTestCase
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control, cache_page, never_cache


class HttpRequestProxy:
    def __init__(self, request):
        self._request = request

    def __getattr__(self, attr):
        """Proxy to the underlying HttpRequest object."""
        return getattr(self._request, attr)


class CacheControlDecoratorTest(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        """
        Tests that a wrapped synchronous function remains a non-coroutine function after applying cache control.

        This test case verifies that the cache control decorator does not convert a synchronous view function into a coroutine function, ensuring that the original function's characteristics are preserved.
        """
        def sync_view(request):
            return HttpResponse()

        wrapped_view = cache_control()(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        """
        Tests that an async view function wrapped with cache control decorator remains a coroutine function.

        Verifies that the cache control decorator does not alter the asynchronous nature of the view function,
        allowing it to be properly handled as a coroutine.
        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = cache_control()(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_cache_control_decorator_http_request(self):
        """
        Tests the cache control decorator's behavior when used to decorate an instance method that accepts an HttpRequest.

        The purpose of this test is to ensure that the cache control decorator correctly raises a TypeError when it does not receive an HttpRequest as its first argument, which can occur when using the decorator without the method_decorator on a classmethod. It also checks this behavior with a proxy request.
        """
        class MyClass:
            @cache_control(a="b")
            def a_view(self, request):
                return HttpResponse()

        msg = (
            "cache_control didn't receive an HttpRequest. If you are "
            "decorating a classmethod, be sure to use @method_decorator."
        )
        request = HttpRequest()
        with self.assertRaisesMessage(TypeError, msg):
            MyClass().a_view(request)
        with self.assertRaisesMessage(TypeError, msg):
            MyClass().a_view(HttpRequestProxy(request))

    async def test_cache_control_decorator_http_request_async_view(self):
        """

        Tests the behavior of the cache control decorator when applied to an asynchronous view function.

        The cache control decorator is expected to raise a TypeError when it does not receive an HttpRequest object.
        This test case verifies this behavior for both a direct HttpRequest and a wrapped HttpRequestProxy object.

        It checks that the decorator correctly identifies the object type and raises the expected error message.

        """
        class MyClass:
            @cache_control(a="b")
            async def async_view(self, request):
                return HttpResponse()

        msg = (
            "cache_control didn't receive an HttpRequest. If you are decorating a "
            "classmethod, be sure to use @method_decorator."
        )
        request = HttpRequest()
        with self.assertRaisesMessage(TypeError, msg):
            await MyClass().async_view(request)
        with self.assertRaisesMessage(TypeError, msg):
            await MyClass().async_view(HttpRequestProxy(request))

    def test_cache_control_decorator_http_request_proxy(self):
        class MyClass:
            @method_decorator(cache_control(a="b"))
            def a_view(self, request):
                return HttpResponse()

        request = HttpRequest()
        response = MyClass().a_view(HttpRequestProxy(request))
        self.assertEqual(response.headers["Cache-Control"], "a=b")

    def test_cache_control_empty_decorator(self):
        @cache_control()
        """
        Tests that applying the cache_control decorator with no arguments results in an empty Cache-Control header in the HTTP response.

        Verifies that when a view function is decorated with @cache_control(), the Cache-Control header in the response is set to an empty string, indicating that no caching directives are specified.

        This test ensures that the cache_control decorator behaves as expected when no caching parameters are provided, allowing for fine-grained control over caching behavior in HTTP responses.
        """
        def a_view(request):
            return HttpResponse()

        response = a_view(HttpRequest())
        self.assertEqual(response.get("Cache-Control"), "")

    async def test_cache_control_empty_decorator_async_view(self):
        @cache_control()
        async def async_view(request):
            return HttpResponse()

        response = await async_view(HttpRequest())
        self.assertEqual(response.get("Cache-Control"), "")

    def test_cache_control_full_decorator(self):
        @cache_control(max_age=123, private=True, public=True, custom=456)
        """

        Tests the cache_control decorator with all available options.

        This function checks that when the cache_control decorator is applied to a view
        with the max-age, private, public, and custom parameters, the resulting HTTP
        response includes the expected Cache-Control headers.

        The test verifies that the Cache-Control header is correctly formatted and
        contains all the specified directives. 

        :raises AssertionError: if the Cache-Control header does not match the expected output.

        """
        def a_view(request):
            return HttpResponse()

        response = a_view(HttpRequest())
        cache_control_items = response.get("Cache-Control").split(", ")
        self.assertEqual(
            set(cache_control_items), {"max-age=123", "private", "public", "custom=456"}
        )

    async def test_cache_control_full_decorator_async_view(self):
        @cache_control(max_age=123, private=True, public=True, custom=456)
        """
        Tests that the cache_control decorator correctly sets Cache-Control headers on an asynchronous view.

        This test case verifies that the cache_control decorator applies the specified options 
        (max-age, private, public, and custom) to the Cache-Control header of an HTTP response 
        generated by an asynchronous view. It checks that the resulting Cache-Control header 
        contains all the specified options with their correct values.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the Cache-Control header does not match the expected values.

        """
        async def async_view(request):
            return HttpResponse()

        response = await async_view(HttpRequest())
        cache_control_items = response.get("Cache-Control").split(", ")
        self.assertEqual(
            set(cache_control_items), {"max-age=123", "private", "public", "custom=456"}
        )


class CachePageDecoratorTest(SimpleTestCase):
    def test_cache_page(self):
        def my_view(request):
            return "response"

        my_view_cached = cache_page(123)(my_view)
        self.assertEqual(my_view_cached(HttpRequest()), "response")
        my_view_cached2 = cache_page(123, key_prefix="test")(my_view)
        self.assertEqual(my_view_cached2(HttpRequest()), "response")


class NeverCacheDecoratorTest(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        """

        Tests that a wrapped synchronous function is not treated as a coroutine function.

        This test case verifies that when a synchronous function is wrapped using the
        never_cache decorator, the resulting wrapped function does not become a coroutine
        function. This ensures that the decorator does not inadvertently alter the 
        function's type or behavior, allowing it to be used as expected in synchronous
        contexts.

        """
        def sync_view(request):
            return HttpResponse()

        wrapped_view = never_cache(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = never_cache(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    @mock.patch("time.time")
    def test_never_cache_decorator_headers(self, mocked_time):
        @never_cache
        """

        Tests the never_cache decorator to ensure it correctly sets HTTP headers to prevent caching.

        The decorator is expected to set the 'Expires' header to a date in the past and the 'Cache-Control'
        header to instruct the browser and any intermediate caches to never cache the response. This test
        verifies that the decorator behaves correctly by checking the values of these headers in the response.

        """
        def a_view(request):
            return HttpResponse()

        mocked_time.return_value = 1167616461.0
        response = a_view(HttpRequest())
        self.assertEqual(
            response.headers["Expires"],
            "Mon, 01 Jan 2007 01:54:21 GMT",
        )
        self.assertEqual(
            response.headers["Cache-Control"],
            "max-age=0, no-cache, no-store, must-revalidate, private",
        )

    @mock.patch("time.time")
    async def test_never_cache_decorator_headers_async_view(self, mocked_time):
        @never_cache
        """

        Tests the never_cache decorator when applied to an asynchronous view function.

        This test case verifies that the never_cache decorator properly sets the
        Cache-Control and Expires headers in the HTTP response to prevent caching.
        The Expires header is set to a specific date in the past, and the Cache-Control
        header is set to instruct the client to not cache the response.

        The test function uses mocking to simulate a specific current time and then
        calls the decorated view function, checking the resulting HTTP response
        headers for the expected values.

        """
        async def async_view(request):
            return HttpResponse()

        mocked_time.return_value = 1167616461.0
        response = await async_view(HttpRequest())
        self.assertEqual(response.headers["Expires"], "Mon, 01 Jan 2007 01:54:21 GMT")
        self.assertEqual(
            response.headers["Cache-Control"],
            "max-age=0, no-cache, no-store, must-revalidate, private",
        )

    def test_never_cache_decorator_expires_not_overridden(self):
        @never_cache
        """
        Tests that the never_cache decorator does not override the Expires header if it is explicitly set.

        Verifies that when a view function decorated with never_cache is called, the Expires header
        in the response is not modified if it has been explicitly set by the view. This ensures that
        the view has control over the caching behavior of its responses, even when the never_cache
        decorator is applied.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the Expires header in the response does not match the expected value.

        """
        def a_view(request):
            return HttpResponse(headers={"Expires": "tomorrow"})

        response = a_view(HttpRequest())
        self.assertEqual(response.headers["Expires"], "tomorrow")

    async def test_never_cache_decorator_expires_not_overridden_async_view(self):
        @never_cache
        """

        Tests that the never_cache decorator does not override the Expires header 
        set in an asynchronous view.

        This test ensures that when the never_cache decorator is applied to an 
        asynchronous view, it does not modify any existing Expires header 
        specified in the view's response. The test verifies this by checking 
        that the response from the decorated view still contains the original 
        Expires header value.

        """
        async def async_view(request):
            return HttpResponse(headers={"Expires": "tomorrow"})

        response = await async_view(HttpRequest())
        self.assertEqual(response.headers["Expires"], "tomorrow")

    def test_never_cache_decorator_http_request(self):
        class MyClass:
            @never_cache
            def a_view(self, request):
                return HttpResponse()

        request = HttpRequest()
        msg = (
            "never_cache didn't receive an HttpRequest. If you are decorating "
            "a classmethod, be sure to use @method_decorator."
        )
        with self.assertRaisesMessage(TypeError, msg):
            MyClass().a_view(request)
        with self.assertRaisesMessage(TypeError, msg):
            MyClass().a_view(HttpRequestProxy(request))

    async def test_never_cache_decorator_http_request_async_view(self):
        """

        Tests the functionality of the never_cache decorator when applied to an asynchronous view function.

        This test case checks that the never_cache decorator correctly raises a TypeError when an HttpRequest object is not received, 
        indicating improper decorator usage, such as decorating a class method without applying the method_decorator. 

        The test provides assurance that the decorator behaves as expected in asynchronous views, ensuring proper error handling and notification.

        """
        class MyClass:
            @never_cache
            async def async_view(self, request):
                return HttpResponse()

        request = HttpRequest()
        msg = (
            "never_cache didn't receive an HttpRequest. If you are decorating "
            "a classmethod, be sure to use @method_decorator."
        )
        with self.assertRaisesMessage(TypeError, msg):
            await MyClass().async_view(request)
        with self.assertRaisesMessage(TypeError, msg):
            await MyClass().async_view(HttpRequestProxy(request))

    def test_never_cache_decorator_http_request_proxy(self):
        class MyClass:
            @method_decorator(never_cache)
            def a_view(self, request):
                return HttpResponse()

        request = HttpRequest()
        response = MyClass().a_view(HttpRequestProxy(request))
        self.assertIn("Cache-Control", response.headers)
        self.assertIn("Expires", response.headers)
