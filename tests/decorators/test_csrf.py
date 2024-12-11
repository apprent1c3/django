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

        Verifies that a wrapped asynchronous function remains a coroutine function.

        This test checks that when an asynchronous view function is wrapped with CSRF protection,
        the resulting function is still recognizable as a coroutine function.

        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = csrf_protect(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_csrf_protect_decorator(self):
        @csrf_protect
        """

        Tests the functionality of the csrf_protect decorator.

        The csrf_protect decorator is used to protect views from Cross-Site Request Forgery (CSRF) attacks.
        This test case checks that the decorator correctly handles valid and invalid CSRF tokens.

        In a valid scenario, the test ensures that the view returns a successful response (200 status code)
        and that the CSRF processing is marked as done.

        In an invalid scenario, where the CSRF token is missing, the test verifies that the view returns
        a Forbidden response (403 status code) and that a warning is logged by the django.security.csrf module.

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
        Tests the csrf_protect decorator functionality for asynchronous views.

         This function verifies that the csrf_protect decorator correctly handles CSRF protection for async views.
         It checks that a successful request with a valid token results in a 200 status code and the request's CSRF processing is marked as done.
         Additionally, it tests that a request without a token elicits a 403 status code and a warning log message from the django.security.csrf module, demonstrating proper error handling for invalid or missing tokens.
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
        Tests the functionality of the requires_csrf_token decorator by applying it to a synchronous view.
        The test ensures that the decorator allows views to process requests correctly, setting the csrf_processing_done flag to True and returning a successful response (200 status code) when a valid CSRF token is present.
        Additionally, the test verifies that the decorator does not log any warnings when no CSRF token is provided in the request.
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
        """

        Tests the ensure_csrf_cookie decorator to verify its functionality.

        The ensure_csrf_cookie decorator is used to ensure that a CSRF cookie is set on
        the client's browser. This test checks that the decorator correctly sets the
        cookie and handles cases where the CSRF token is not provided in the request.

        It validates the following scenarios:
        - The response status code is 200 (OK) after decorating a view function.
        - The CSRF processing is marked as done after the view function is called.
        - The view function handles requests without a CSRF token without logging any warnings.

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
        """
        Tests that a synchronous function wrapped with csrf_exempt is not treated as a coroutine function.

        Verifies that the wrapper does not modify the function's coroutine status, ensuring its behavior remains consistent with its synchronous implementation.

        Args:
            None

        Returns:
            None

        Notes:
            This test is crucial in maintaining the correctness of synchronous views, as treating them as coroutines could lead to unexpected behavior or errors in the application.
        """
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

        Tests the functionality of the csrf_exempt decorator.

        This test case checks if the csrf_exempt decorator correctly exempts a view from
        requiring a CSRF token and verifies that the decorated view returns an HttpResponse
        object.

        The test ensures that the csrf_exempt attribute of the decorated view is set to True,
        indicating that the view is exempt from CSRF checks, and that the view handles an HttpRequest
        and returns an HttpResponse instance.

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
