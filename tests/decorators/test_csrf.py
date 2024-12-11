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
        """
        Tests that an async view function wrapped with CSRF protection remains a coroutine function.

        Verifies that applying CSRF protection to an asynchronous view function does not alter its coroutine status, ensuring it can still be properly handled by the asynchronous request-response cycle.

        This test ensures compatibility between async views and CSRF protection, allowing developers to securely handle asynchronous requests without compromising the coroutine functionality of the view function. 
        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = csrf_protect(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_csrf_protect_decorator(self):
        @csrf_protect
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
        """

        Tests that a synchronous function wrapped with CSRF token protection remains non-async.

        This function verifies that applying CSRF token requirements to a synchronous view
        does not transform it into a coroutine function, ensuring that the function's behavior
        remains consistent with its original synchronous implementation.

        """
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

        Tests the functionality of the requires_csrf_token decorator in synchronous views.

        Verifies that when the decorator is applied to a view, the view can handle requests 
        with and without a valid CSRF token. The test checks for the following conditions:

        * The view returns a successful response (200 status code) when a valid CSRF token is provided.
        * The CSRF token is marked as processed after the view has handled the request.
        * The view returns a successful response (200 status code) even when no CSRF token is provided, 
          without logging any warnings related to CSRF token verification.

        Ensures that the requires_csrf_token decorator functions correctly in synchronous views, 
        allowing them to handle requests with or without CSRF tokens without interrupting the request flow.

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

        Checks the functionality of the csrf_exempt decorator.

        This test verifies that the csrf_exempt decorator correctly flags a view as 
        CSRF exempt and ensures the view returns the expected HTTP response.

        The test case checks if the view is properly marked as CSRF exempt and 
        confirms that the view returns an HttpResponse object when it is called with 
        an HttpRequest object. 

        Returns:
            None

        """
        def sync_view(request):
            return HttpResponse()

        self.assertIs(sync_view.csrf_exempt, True)
        self.assertIsInstance(sync_view(HttpRequest()), HttpResponse)

    async def test_csrf_exempt_decorator_async_view(self):
        @csrf_exempt
        async def async_view(request):
            return HttpResponse()

        self.assertIs(async_view.csrf_exempt, True)
        self.assertIsInstance(await async_view(HttpRequest()), HttpResponse)
