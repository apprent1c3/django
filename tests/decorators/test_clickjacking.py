from asgiref.sync import iscoroutinefunction

from django.http import HttpRequest, HttpResponse
from django.middleware.clickjacking import XFrameOptionsMiddleware
from django.test import SimpleTestCase
from django.views.decorators.clickjacking import (
    xframe_options_deny,
    xframe_options_exempt,
    xframe_options_sameorigin,
)


class XFrameOptionsDenyTests(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        """
        Tests that a synchronous function wrapped with xframe_options_deny is not a coroutine function.

        Verifies that applying the xframe_options_deny decorator to a synchronous view function does not convert it into a coroutine function, ensuring it can still be used in synchronous contexts.

        This check is crucial to maintain compatibility with existing synchronous frameworks and libraries, allowing developers to use the decorator without worrying about introducing asynchronous behavior where it's not expected or supported.
        """
        def sync_view(request):
            return HttpResponse()

        wrapped_view = xframe_options_deny(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        """
        Test that the xframe_options_deny decorator correctly preserves the coroutine function status of an asynchronous view function.

        This test checks that when an async view function is wrapped with the xframe_options_deny decorator, the resulting wrapped view function remains a coroutine function. This ensures that the decorator does not interfere with the asynchronous nature of the original view function.
        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = xframe_options_deny(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_decorator_sets_x_frame_options_to_deny(self):
        @xframe_options_deny
        """
        Tests that the xframe_options_deny decorator correctly sets the X-Frame-Options header to 'DENY' in an HTTP response, preventing the page from being framed by external sites.
        """
        def a_view(request):
            return HttpResponse()

        response = a_view(HttpRequest())
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    async def test_decorator_sets_x_frame_options_to_deny_async_view(self):
        @xframe_options_deny
        async def an_async_view(request):
            return HttpResponse()

        response = await an_async_view(HttpRequest())
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")


class XFrameOptionsSameoriginTests(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        """

        Tests that a synchronous function wrapped with xframe_options_sameorigin decorator 
        does not become a coroutine function.

        This test ensures that the decorator preserves the original function's execution 
        model, allowing it to remain synchronous and return a response directly.

        """
        def sync_view(request):
            return HttpResponse()

        wrapped_view = xframe_options_sameorigin(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        """
        Tests that a wrapped asynchronous view function remains a coroutine function.

        This test verifies that the xframe_options_sameorigin decorator does not alter the
        asynchronous nature of the view function it wraps, ensuring that the decorated
        function can still be used as a coroutine.

        The test case checks if the wrapped view function is identified as a coroutine
        function, confirming that the decorator preserves the original function's type
        and behavior.
        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = xframe_options_sameorigin(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_decorator_sets_x_frame_options_to_sameorigin(self):
        @xframe_options_sameorigin
        """
        Tests the xframe_options_sameorigin decorator by applying it to a view function.

        Verifies that the decorator correctly sets the 'X-Frame-Options' response header to 'SAMEORIGIN', 
        preventing the page from being iframed by external sites, thus enhancing security against clickjacking attacks.

        The test scenario involves defining a view function with the decorator, simulating a request, 
        and asserting the header value in the response matches the expected 'SAMEORIGIN' setting.
        """
        def a_view(request):
            return HttpResponse()

        response = a_view(HttpRequest())
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")

    async def test_decorator_sets_x_frame_options_to_sameorigin_async_view(self):
        @xframe_options_sameorigin
        """
        Tests that the xframe_options_sameorigin decorator correctly sets the X-Frame-Options header to 'SAMEORIGIN' for an asynchronous view.

        This test case verifies that when the xframe_options_sameorigin decorator is applied to an asynchronous view, the view's response will include the X-Frame-Options header with a value of 'SAMEORIGIN', which prevents the page from being iframed by a different origin.

        The test creates an asynchronous view, applies the decorator, and then checks the response headers to ensure the X-Frame-Options header is set correctly.
        """
        async def an_async_view(request):
            return HttpResponse()

        response = await an_async_view(HttpRequest())
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")


class XFrameOptionsExemptTests(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        """
        Tests that a synchronous function remains non-coroutine after being wrapped with xframe_options_exempt decorator.

            Verifies that the wrapped function retains its original synchronous nature and does not become a coroutine function.
            This ensures that the decorator does not unintentionally alter the function's execution type, allowing it to be used as expected in synchronous contexts.
        """
        def sync_view(request):
            return HttpResponse()

        wrapped_view = xframe_options_exempt(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        """
        Tests that a view function wrapped with xframe_options_exempt decorator remains a coroutine function.

        This test ensures that applying the xframe_options_exempt decorator to an asynchronous view function does not alter its coroutine function status, allowing it to continue being executed as an asynchronous function.

        Checking this behavior is crucial for preserving the asynchronous properties of view functions when applying security decorators like xframe_options_exempt, which is used to exempt views from the X-Frame-Options header protection.

        The test verifies that the wrapped view function retains its coroutine function characteristics, ensuring that it can be correctly executed by an asynchronous event loop or framework. If the wrapped view fails to be identified as a coroutine function, it could lead to execution errors or unexpected behavior in asynchronous environments. 
        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = xframe_options_exempt(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_decorator_stops_x_frame_options_being_set(self):
        """
        @xframe_options_exempt instructs the XFrameOptionsMiddleware to NOT set
        the header.
        """

        @xframe_options_exempt
        def a_view(request):
            return HttpResponse()

        request = HttpRequest()
        response = a_view(request)
        self.assertIsNone(response.get("X-Frame-Options", None))
        self.assertIs(response.xframe_options_exempt, True)

        # The real purpose of the exempt decorator is to suppress the
        # middleware's functionality.
        middleware_response = XFrameOptionsMiddleware(a_view)(request)
        self.assertIsNone(middleware_response.get("X-Frame-Options"))

    async def test_exempt_decorator_async_view(self):
        @xframe_options_exempt
        """

        Tests the xframe_options_exempt decorator on an asynchronous view.

        This test case verifies that when the xframe_options_exempt decorator is applied to an asynchronous view,
        the 'X-Frame-Options' header is not added to the response, indicating that the view is exempt from
        X-Frame-Options processing. The test also checks that the xframe_options_exempt attribute of the response
        is set to True, and that the XFrameOptionsMiddleware respects the exemption when applied to the view.

        The test ensures that the decorator correctly modifies the response and interactions with the middleware,
        providing assurance that asynchronous views can be properly exempted from X-Frame-Options restrictions.

        """
        async def an_async_view(request):
            return HttpResponse()

        request = HttpRequest()
        response = await an_async_view(request)
        self.assertIsNone(response.get("X-Frame-Options"))
        self.assertIs(response.xframe_options_exempt, True)

        # The real purpose of the exempt decorator is to suppress the
        # middleware's functionality.
        middleware_response = await XFrameOptionsMiddleware(an_async_view)(request)
        self.assertIsNone(middleware_response.get("X-Frame-Options"))
