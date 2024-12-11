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
        Gets an HTTP request object configured for a POST request with optional CSRF token.

        :param token: The CSRF token to include in the request, defaults to CSRF_TOKEN
        :return: An HttpRequest object with the specified token and POST method
        :note: The request's CSRF cookie and POST data will be set to the provided token, if specified.
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
        """

        Tests that wrapping an asynchronous view function with csrf_protect still results in a coroutine function.

        Verifies that the csrf_protect decorator preserves the asynchronous nature of the original view function,
        allowing it to be properly handled in an asynchronous context.

        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = csrf_protect(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_csrf_protect_decorator(self):
        @csrf_protect
        """

        Tests the functionality of the csrf_protect decorator.

        This test case verifies that the csrf_protect decorator correctly handles
        CSRF protection for synchronous views. It checks that the decorator allows
        requests with a valid CSRF token to pass through and returns a successful
        response, while requests without a valid token are blocked and return a 403
        Forbidden response. Additionally, it ensures that the csrf_processing_done
        flag is set correctly after the request has been processed.

        The test covers the following scenarios:
        - A request with a valid CSRF token
        - A request without a valid CSRF token, which is expected to trigger a
          warning log message

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

        Tests the functionality of the csrf_protect decorator when applied to an asynchronous view.

        The test case verifies that the decorator correctly processes the CSRF token in the request, 
        allowing valid requests to proceed while rejecting those with missing or invalid tokens. 

        It checks for the following conditions:

        * A request with a valid CSRF token receives a successful response (200 status code).
        * The CSRF processing is marked as done for the request.
        * A request without a CSRF token or with an invalid token receives a forbidden response (403 status code) and logs a warning.

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

        Tests the requires_csrf_token decorator to ensure it functions correctly.

        The test verifies that when the decorator is applied to a view, it successfully
        processes the CSRF token and allows the view to respond with a 200 status code.
        It also checks that when no CSRF token is provided in the request, the view still
        responds with a 200 status code without logging any warnings about CSRF token
        processing.

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
        """
        Tests that a wrapped synchronous function is not a coroutine function.

        This test case verifies the behavior of the ensure_csrf_cookie function when 
        applied to a synchronous view function. It checks that the resulting wrapped 
        view function does not become a coroutine function, ensuring that it can be 
        used in synchronous contexts without any issues related to asynchronous 
        execution.

        The test has implications for the proper handling of CSRF cookies in 
        synchronous views, confirming that the ensure_csrf_cookie decorator does not 
        inadvertently convert synchronous functions into coroutines, which could 
        introduce unexpected asynchronous behavior. 
        """
        def sync_view(request):
            return HttpResponse()

        wrapped_view = ensure_csrf_cookie(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        """
        Tests that the ensure_csrf_cookie decorator correctly wraps asynchronous functions, preserving their coroutine status.

        The function ensures that the decorated view remains a coroutine function, allowing it to be properly handled by asynchronous frameworks and libraries.

        This test case verifies that the ensure_csrf_cookie decorator does not modify the asynchronous nature of the wrapped function, maintaining its original functionality and behavior.

        Parameters: None
        Returns: None
        Raises: Assertion failure if the wrapped view is not a coroutine function.
        """
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
        """

        Tests the functionality of the ensure_csrf_cookie decorator when used with asynchronous views.

        Ensures that the decorator sets the CSRF cookie correctly and allows the view to proceed 
        without logging any warnings when the CSRF token is missing from the request.

        Verifies that the CSRF processing is marked as done after the view has been executed and 
        that the response has a status code of 200, indicating a successful execution.

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
        """
        Tests that an asynchronous view function remains a coroutine function after being wrapped with csrf_exempt decorator.

        Verifies that the wrapped view function can still be identified as a coroutine function using the iscoroutinefunction check, ensuring that its asynchronous nature is preserved after the wrapping process.
        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = csrf_exempt(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_csrf_exempt_decorator(self):
        @csrf_exempt
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
