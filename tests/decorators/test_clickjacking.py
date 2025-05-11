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
        def sync_view(request):
            return HttpResponse()

        wrapped_view = xframe_options_deny(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = xframe_options_deny(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_decorator_sets_x_frame_options_to_deny(self):
        @xframe_options_deny
        """
        Tests that the xframe_options_deny decorator correctly sets the X-Frame-Options header to 'DENY' in the HTTP response.
        """
        def a_view(request):
            return HttpResponse()

        response = a_view(HttpRequest())
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    async def test_decorator_sets_x_frame_options_to_deny_async_view(self):
        @xframe_options_deny
        """
        Tests that the xframe_options_deny decorator correctly sets the X-Frame-Options header to 'DENY' for an asynchronous view.
        """
        async def an_async_view(request):
            return HttpResponse()

        response = await an_async_view(HttpRequest())
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")


class XFrameOptionsSameoriginTests(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        def sync_view(request):
            return HttpResponse()

        wrapped_view = xframe_options_sameorigin(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = xframe_options_sameorigin(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_decorator_sets_x_frame_options_to_sameorigin(self):
        @xframe_options_sameorigin
        """
        Test that the xframe_options_sameorigin decorator correctly sets the X-Frame-Options header to SAMEORIGIN in HTTP responses.
        """
        def a_view(request):
            return HttpResponse()

        response = a_view(HttpRequest())
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")

    async def test_decorator_sets_x_frame_options_to_sameorigin_async_view(self):
        @xframe_options_sameorigin
        """
        Tests that the xframe_options_sameorigin decorator sets the X-Frame-Options header to 'SAMEORIGIN' for an asynchronous view.
        """
        async def an_async_view(request):
            return HttpResponse()

        response = await an_async_view(HttpRequest())
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")


class XFrameOptionsExemptTests(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        def sync_view(request):
            return HttpResponse()

        wrapped_view = xframe_options_exempt(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = xframe_options_exempt(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_decorator_stops_x_frame_options_being_set(self):
        """
        Tests that the @xframe_options_exempt decorator correctly prevents 
        X-Frame-Options headers from being set on a view's response.
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
        Tests the functionality of the xframe_options_exempt decorator when applied to an asynchronous view, ensuring it correctly sets the X-Frame-Options header to None and the xframe_options_exempt attribute to True, both with and without the XFrameOptionsMiddleware.
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
