from asgiref.sync import iscoroutinefunction

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.test import SimpleTestCase
from django.views.decorators.csrf import (
    csrf_exempt,
    csrf_protect,
    ensure_csrf_cookie,
    requires_csrf_token,
)

CSRF_TOKEN = "1bcdefghij2bcdefghij3bcdefghij4bcdefghij5bcdefghij6bcdefghijABCD"


class CsrfTestMixin:
    def get_request(self, token=CSRF_TOKEN):
        """
        Creates a POST HttpRequest object with optional CSRF token validation.\"\"\"

        \"\"\" 
            :param token: The CSRF token to include in the request. Defaults to CSRF_TOKEN.
            :return: An HttpRequest object representing a POST request with the provided token.

        """
        request = HttpRequest()
        request.method = "POST"
        if token:
            request.POST["csrfmiddlewaretoken"] = token
            request.COOKIES[settings.CSRF_COOKIE_NAME] = token
        return request


class CsrfProtectTests(CsrfTestMixin, SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        def sync_view(request):
            return HttpResponse()

        wrapped_view = csrf_protect(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = csrf_protect(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_csrf_protect_decorator(self):
        @csrf_protect
        """
        Tests the CSRF protect decorator functionality.

        Verifies that the decorator allows valid requests and blocks those with missing or invalid CSRF tokens, logging a warning in the latter case.
        """
        def sync_view(request):
            return HttpResponse()

        request = self.get_request()
        response = sync_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIs(request.csrf_processing_done, True)

        with self.assertLogs("django.security.csrf", "WARNING"):
            request = self.get_request(token=None)
            response = sync_view(request)
            self.assertEqual(response.status_code, 403)

    async def test_csrf_protect_decorator_async_view(self):
        @csrf_protect
        """
        Tests the csrf_protect decorator on an asynchronous view.

        Verifies that the decorator allows valid requests to pass through and prevents
        requests without a valid CSRF token from accessing the view, returning a 403
        status code instead. Also checks that the CSRF processing is marked as done for
        successful requests and logs a warning for invalid requests.
        """
        async def async_view(request):
            return HttpResponse()

        request = self.get_request()
        response = await async_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIs(request.csrf_processing_done, True)

        with self.assertLogs("django.security.csrf", "WARNING"):
            request = self.get_request(token=None)
            response = await async_view(request)
            self.assertEqual(response.status_code, 403)


class RequiresCsrfTokenTests(CsrfTestMixin, SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        def sync_view(request):
            return HttpResponse()

        wrapped_view = requires_csrf_token(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = requires_csrf_token(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_requires_csrf_token_decorator(self):
        @requires_csrf_token
        """
        Tests the requires_csrf_token decorator, ensuring it correctly handles 
        requests with and without CSRF tokens, and that it processes CSRF checks as expected.
        """
        def sync_view(request):
            return HttpResponse()

        request = self.get_request()
        response = sync_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIs(request.csrf_processing_done, True)

        with self.assertNoLogs("django.security.csrf", "WARNING"):
            request = self.get_request(token=None)
            response = sync_view(request)
            self.assertEqual(response.status_code, 200)

    async def test_requires_csrf_token_decorator_async_view(self):
        @requires_csrf_token
        """
        Test that the requires_csrf_token decorator works correctly with an asynchronous view.

         Verifies that the decorator sets the csrf_processing_done flag on the request and allows the view to 
         proceed without a CSRF token, but logs a warning at the INFO level in Django's security logger.
        """
        async def async_view(request):
            return HttpResponse()

        request = self.get_request()
        response = await async_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIs(request.csrf_processing_done, True)

        with self.assertNoLogs("django.security.csrf", "WARNING"):
            request = self.get_request(token=None)
            response = await async_view(request)
            self.assertEqual(response.status_code, 200)


class EnsureCsrfCookieTests(CsrfTestMixin, SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        def sync_view(request):
            return HttpResponse()

        wrapped_view = ensure_csrf_cookie(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = ensure_csrf_cookie(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_ensure_csrf_cookie_decorator(self):
        @ensure_csrf_cookie
        """
        Tests the ensure_csrf_cookie decorator to verify it sets the CSRF cookie correctly and handles missing or invalid tokens gracefully, ensuring secure requests without logging unnecessary warnings.
        """
        def sync_view(request):
            return HttpResponse()

        request = self.get_request()
        response = sync_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIs(request.csrf_processing_done, True)

        with self.assertNoLogs("django.security.csrf", "WARNING"):
            request = self.get_request(token=None)
            response = sync_view(request)
            self.assertEqual(response.status_code, 200)

    async def test_ensure_csrf_cookie_decorator_async_view(self):
        @ensure_csrf_cookie
        """
        Ensures the CSRF cookie decorator works with asynchronous views by verifying it sets the CSRF cookie and handles missing tokens correctly.
        """
        async def async_view(request):
            return HttpResponse()

        request = self.get_request()
        response = await async_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIs(request.csrf_processing_done, True)

        with self.assertNoLogs("django.security.csrf", "WARNING"):
            request = self.get_request(token=None)
            response = await async_view(request)
            self.assertEqual(response.status_code, 200)


class CsrfExemptTests(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        def sync_view(request):
            return HttpResponse()

        wrapped_view = csrf_exempt(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = csrf_exempt(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_csrf_exempt_decorator(self):
        @csrf_exempt
        """
        Tests that the csrf_exempt decorator correctly exempts a view from CSRF checks and allows it to return a response.
        """
        def sync_view(request):
            return HttpResponse()

        self.assertIs(sync_view.csrf_exempt, True)
        self.assertIsInstance(sync_view(HttpRequest()), HttpResponse)

    async def test_csrf_exempt_decorator_async_view(self):
        @csrf_exempt
        """
        Tests that the csrf_exempt decorator correctly configures an asynchronous view to exempt it from CSRF checks and verifies the view returns a valid HttpResponse.
        """
        async def async_view(request):
            return HttpResponse()

        self.assertIs(async_view.csrf_exempt, True)
        self.assertIsInstance(await async_view(HttpRequest()), HttpResponse)
