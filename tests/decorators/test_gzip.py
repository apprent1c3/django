from asgiref.sync import iscoroutinefunction

from django.http import HttpRequest, HttpResponse
from django.test import SimpleTestCase
from django.views.decorators.gzip import gzip_page


class GzipPageTests(SimpleTestCase):
    # Gzip ignores content that is too short.
    content = "Content " * 100

    def test_wrapped_sync_function_is_not_coroutine_function(self):
        """
        Tests that a synchronous function wrapped with gzip_page remains a regular function and not a coroutine function.

        This test ensures that the gzip_page decorator does not inadvertently convert a synchronous view function into a coroutine function, 
        which would affect how the function is handled by asynchronous frameworks and libraries.

        The test verifies that the wrapped view function still behaves as a regular synchronous function, allowing it to be used in 
        non-asynchronous contexts without compatibility issues.
        """
        def sync_view(request):
            return HttpResponse()

        wrapped_view = gzip_page(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        """
        Verifies that wrapping an asynchronous view function with gzip_page results in a coroutine function.

        Tests the gzip_page decorator to ensure it correctly preserves the asynchronous nature
        of the original view function, allowing it to be executed as a coroutine.

        The purpose of this test is to guarantee that the gzip_page wrapper does not inadvertently
        convert the asynchronous view into a synchronous function, which could lead to issues with
        asynchronous code execution and handling.
        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = gzip_page(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_gzip_page_decorator(self):
        @gzip_page
        def sync_view(request):
            return HttpResponse(content=self.content)

        request = HttpRequest()
        request.META["HTTP_ACCEPT_ENCODING"] = "gzip"
        response = sync_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get("Content-Encoding"), "gzip")

    async def test_gzip_page_decorator_async_view(self):
        @gzip_page
        """

        Tests the functionality of the gzip_page decorator when used with an asynchronous view.

        The test verifies that when the gzip_page decorator is applied to an async view,
        the view's response is properly compressed using gzip and that the response's
        Content-Encoding header is correctly set to 'gzip'. The test also checks that the
        response status code is 200, indicating a successful request.

        The test scenario assumes a client that supports gzip compression, as indicated by
        the presence of 'gzip' in the HTTP Accept-Encoding header of the request.

        """
        async def async_view(request):
            return HttpResponse(content=self.content)

        request = HttpRequest()
        request.META["HTTP_ACCEPT_ENCODING"] = "gzip"
        response = await async_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get("Content-Encoding"), "gzip")
