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
        def sync_view(request):
            return HttpResponse()

        wrapped_view = cache_control()(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = cache_control()(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_cache_control_decorator_http_request(self):
        """

        Tests that the cache_control decorator correctly raises a TypeError when used
        with an object that is not an instance of HttpRequest, or when used with a 
        decorated class method without the method_decorator wrapper.

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
        Tests the cache control decorator with an asynchronous HTTP request view.

        Verifies that the decorator correctly handles an asynchronous view function
        and raises a TypeError when not used with a proper HttpRequest object.
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
        """
        Tests the application of the cache control decorator to an HTTP request via a proxy, ensuring that the Cache-Control header is correctly set in the response.
        """
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
        Tests that the cache_control decorator, when used without arguments, sets the Cache-Control header of an HttpResponse to an empty string.
        """
        def a_view(request):
            return HttpResponse()

        response = a_view(HttpRequest())
        self.assertEqual(response.get("Cache-Control"), "")

    async def test_cache_control_empty_decorator_async_view(self):
        @cache_control()
        """
        Tests that applying the cache_control decorator to an asynchronous view without any parameters results in an empty Cache-Control header being set in the response.
        """
        async def async_view(request):
            return HttpResponse()

        response = await async_view(HttpRequest())
        self.assertEqual(response.get("Cache-Control"), "")

    def test_cache_control_full_decorator(self):
        @cache_control(max_age=123, private=True, public=True, custom=456)
        """
        Tests the cache control decorator with all possible parameters, verifying it sets the correct Cache-Control headers in the response.
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
        Tests the application of the cache control decorator to an asynchronous view, ensuring the cache control headers are correctly set in the response.
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
        """
        Tests the cache_page decorator functionality.

        Verifies that the cache_page decorator correctly caches and returns the response
        from a view function, both with and without a custom key prefix.
        """
        def my_view(request):
            return "response"

        my_view_cached = cache_page(123)(my_view)
        self.assertEqual(my_view_cached(HttpRequest()), "response")
        my_view_cached2 = cache_page(123, key_prefix="test")(my_view)
        self.assertEqual(my_view_cached2(HttpRequest()), "response")


class NeverCacheDecoratorTest(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
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
        Tests the never_cache decorator by verifying that it sets the appropriate HTTP headers to prevent caching, 
        including Expires and Cache-Control headers, for a given view function.
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

        Tests the behavior of the never_cache decorator when applied to an asynchronous view.
        Ensures that the decorator correctly sets the Cache-Control and Expires headers to prevent caching.

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
        Tests that the never_cache decorator does not override the Expires header if it is already set.
        """
        def a_view(request):
            return HttpResponse(headers={"Expires": "tomorrow"})

        response = a_view(HttpRequest())
        self.assertEqual(response.headers["Expires"], "tomorrow")

    async def test_never_cache_decorator_expires_not_overridden_async_view(self):
        @never_cache
        """
        Tests that the never_cache decorator does not override the Expires header when set explicitly in an asynchronous view.
        """
        async def async_view(request):
            return HttpResponse(headers={"Expires": "tomorrow"})

        response = await async_view(HttpRequest())
        self.assertEqual(response.headers["Expires"], "tomorrow")

    def test_never_cache_decorator_http_request(self):
        """
        Tests that the never_cache decorator raises a TypeError when applied to an instance method that takes an HttpRequest, to ensure proper usage as a method decorator rather than a function decorator.
        """
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
        Tests the never_cache decorator's behavior when applied to an asynchronous view function, verifying it raises a TypeError when called without proper decorator usage.
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
        """
        Tests that the never_cache decorator sets cache control headers in the response of an HTTP request when proxied through HttpRequestProxy.
        """
        class MyClass:
            @method_decorator(never_cache)
            def a_view(self, request):
                return HttpResponse()

        request = HttpRequest()
        response = MyClass().a_view(HttpRequestProxy(request))
        self.assertIn("Cache-Control", response.headers)
        self.assertIn("Expires", response.headers)
