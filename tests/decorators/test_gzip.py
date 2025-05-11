from asgiref.sync import iscoroutinefunction

from django.http import HttpRequest, HttpResponse
from django.test import SimpleTestCase
from django.views.decorators.gzip import gzip_page


class GzipPageTests(SimpleTestCase):
    # Gzip ignores content that is too short.
    content = "Content " * 100

    def test_wrapped_sync_function_is_not_coroutine_function(self):
        def sync_view(request):
            return HttpResponse()

        wrapped_view = gzip_page(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = gzip_page(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_gzip_page_decorator(self):
        @gzip_page
        """
        Tests the gzip_page decorator to ensure it correctly gzips responses to HTTP requests 
        that specify gzip encoding in the Accept-Encoding header.
        """
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
        Tests that the gzip_page decorator correctly compresses an asynchronous view's response when the client supports gzip encoding.
        """
        async def async_view(request):
            return HttpResponse(content=self.content)

        request = HttpRequest()
        request.META["HTTP_ACCEPT_ENCODING"] = "gzip"
        response = await async_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get("Content-Encoding"), "gzip")
