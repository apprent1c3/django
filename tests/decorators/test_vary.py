from asgiref.sync import iscoroutinefunction

from django.http import HttpRequest, HttpResponse
from django.test import SimpleTestCase
from django.views.decorators.vary import vary_on_cookie, vary_on_headers


class VaryOnHeadersTests(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        """
        Tests that a synchronous function wrapped with vary_on_headers decorator remains a non-coroutine function.

        This test ensures that applying the vary_on_headers decorator to a synchronous view function does not convert it into a coroutine function, thus preserving its original execution behavior. The outcome verifies that the decorator can be safely used with synchronous views without introducing asynchronous execution. 
        """
        def sync_view(request):
            return HttpResponse()

        wrapped_view = vary_on_headers()(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = vary_on_headers()(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_vary_on_headers_decorator(self):
        @vary_on_headers("Header", "Another-header")
        def sync_view(request):
            return HttpResponse()

        response = sync_view(HttpRequest())
        self.assertEqual(response.get("Vary"), "Header, Another-header")

    async def test_vary_on_headers_decorator_async_view(self):
        @vary_on_headers("Header", "Another-header")
        """

        Tests the usage of the vary_on_headers decorator with an asynchronous view.

        The vary_on_headers decorator is used to specify the request headers that 
        should be taken into account when determining the cache validity of a response.
        This test ensures that the decorator correctly sets the Vary header in the response.

        The test case verifies that the response from the decorated async view includes 
        the Vary header with the specified headers.

        """
        async def async_view(request):
            return HttpResponse()

        response = await async_view(HttpRequest())
        self.assertEqual(response.get("Vary"), "Header, Another-header")


class VaryOnCookieTests(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        def sync_view(request):
            return HttpResponse()

        wrapped_view = vary_on_cookie(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        """
        Tests that an async function wrapped with vary_on_cookie decorator remains a coroutine function.

        This test ensures that the vary_on_cookie decorator does not alter the asynchronous nature of the original function,
        allowing it to be treated as a coroutine function after decoration. This is crucial for maintaining compatibility
        with async/await syntax and asynchronous frameworks. The test checks that the wrapped function is indeed a coroutine
        function, verifying the decorator's behavior in this regard.
        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = vary_on_cookie(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_vary_on_cookie_decorator(self):
        @vary_on_cookie
        def sync_view(request):
            return HttpResponse()

        response = sync_view(HttpRequest())
        self.assertEqual(response.get("Vary"), "Cookie")

    async def test_vary_on_cookie_decorator_async_view(self):
        @vary_on_cookie
        """
        Tests the vary_on_cookie_decorator_async_view functionality to ensure it correctly sets the 'Vary' response header to 'Cookie' when decorating an asynchronous view. This test verifies that the decorator properly handles asynchronous requests and sets the required header for caching purposes, allowing caching systems to vary their storage based on the Cookie request header.
        """
        async def async_view(request):
            return HttpResponse()

        response = await async_view(HttpRequest())
        self.assertEqual(response.get("Vary"), "Cookie")
