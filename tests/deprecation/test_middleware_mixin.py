import threading

from asgiref.sync import async_to_sync, iscoroutinefunction

from django.contrib.admindocs.middleware import XViewMiddleware
from django.contrib.auth.middleware import (
    AuthenticationMiddleware,
    LoginRequiredMiddleware,
    RemoteUserMiddleware,
)
from django.contrib.flatpages.middleware import FlatpageFallbackMiddleware
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.redirects.middleware import RedirectFallbackMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sites.middleware import CurrentSiteMiddleware
from django.db import connection
from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.middleware.cache import (
    CacheMiddleware,
    FetchFromCacheMiddleware,
    UpdateCacheMiddleware,
)
from django.middleware.clickjacking import XFrameOptionsMiddleware
from django.middleware.common import BrokenLinkEmailsMiddleware, CommonMiddleware
from django.middleware.csrf import CsrfViewMiddleware
from django.middleware.gzip import GZipMiddleware
from django.middleware.http import ConditionalGetMiddleware
from django.middleware.locale import LocaleMiddleware
from django.middleware.security import SecurityMiddleware
from django.test import SimpleTestCase
from django.utils.deprecation import MiddlewareMixin


class MiddlewareMixinTests(SimpleTestCase):
    middlewares = [
        AuthenticationMiddleware,
        LoginRequiredMiddleware,
        BrokenLinkEmailsMiddleware,
        CacheMiddleware,
        CommonMiddleware,
        ConditionalGetMiddleware,
        CsrfViewMiddleware,
        CurrentSiteMiddleware,
        FetchFromCacheMiddleware,
        FlatpageFallbackMiddleware,
        GZipMiddleware,
        LocaleMiddleware,
        MessageMiddleware,
        RedirectFallbackMiddleware,
        RemoteUserMiddleware,
        SecurityMiddleware,
        SessionMiddleware,
        UpdateCacheMiddleware,
        XFrameOptionsMiddleware,
        XViewMiddleware,
    ]

    def test_repr(self):
        """
        Tests the string representation of MiddlewareMixin and CsrfViewMiddleware instances.

        Verifies that the repr() method correctly returns a string indicating the class type 
        and the get_response callable, whether it is an instance of a class or a regular function.

        Checks the output for both MiddlewareMixin and CsrfViewMiddleware with different types 
        of get_response callables to ensure consistent string representation across different scenarios.
        """
        class GetResponse:
            def __call__(self):
                return HttpResponse()

        def get_response():
            return HttpResponse()

        self.assertEqual(
            repr(MiddlewareMixin(GetResponse())),
            "<MiddlewareMixin get_response=GetResponse>",
        )
        self.assertEqual(
            repr(MiddlewareMixin(get_response)),
            "<MiddlewareMixin get_response="
            "MiddlewareMixinTests.test_repr.<locals>.get_response>",
        )
        self.assertEqual(
            repr(CsrfViewMiddleware(GetResponse())),
            "<CsrfViewMiddleware get_response=GetResponse>",
        )
        self.assertEqual(
            repr(CsrfViewMiddleware(get_response)),
            "<CsrfViewMiddleware get_response="
            "MiddlewareMixinTests.test_repr.<locals>.get_response>",
        )

    def test_passing_explicit_none(self):
        """
        Tests that each middleware raises a ValueError when get_response is explicitly set to None.

         Verifies that all middlewares in the list enforce the requirement for a valid get_response callback, 
         ensuring they handle invalid input correctly by raising an exception with a meaningful error message.
        """
        msg = "get_response must be provided."
        for middleware in self.middlewares:
            with self.subTest(middleware=middleware):
                with self.assertRaisesMessage(ValueError, msg):
                    middleware(None)

    def test_coroutine(self):
        """

        Tests the behavior of the middlewares with both asynchronous and synchronous response functions.

        This test iterates over each middleware in the list, applying it to both an asynchronous 
        and synchronous response function. It verifies that when applied to an asynchronous function, 
        the middleware returns a coroutine function, and when applied to a synchronous function, 
        it returns a non-coroutine function.

        The test ensures that the middlewares correctly handle both asynchronous and synchronous 
        response functions, maintaining the expected behavior in different scenarios.

        """
        async def async_get_response(request):
            return HttpResponse()

        def sync_get_response(request):
            return HttpResponse()

        for middleware in self.middlewares:
            with self.subTest(middleware=middleware.__qualname__):
                # Middleware appears as coroutine if get_function is
                # a coroutine.
                middleware_instance = middleware(async_get_response)
                self.assertIs(iscoroutinefunction(middleware_instance), True)
                # Middleware doesn't appear as coroutine if get_function is not
                # a coroutine.
                middleware_instance = middleware(sync_get_response)
                self.assertIs(iscoroutinefunction(middleware_instance), False)

    def test_sync_to_async_uses_base_thread_and_connection(self):
        """
        The process_request() and process_response() hooks must be called with
        the sync_to_async thread_sensitive flag enabled, so that database
        operations use the correct thread and connection.
        """

        def request_lifecycle():
            """Fake request_started/request_finished."""
            return (threading.get_ident(), id(connection))

        async def get_response(self):
            return HttpResponse()

        class SimpleMiddleWare(MiddlewareMixin):
            def process_request(self, request):
                request.thread_and_connection = request_lifecycle()

            def process_response(self, request, response):
                """
                Associates the request's lifecycle with the response, capturing thread and connection information.

                This method takes a request and response object as input, and returns the modified response with additional attributes. 
                The response's lifecycle is updated with the thread and connection details from the request, 
                providing context for further processing or analysis.
                """
                response.thread_and_connection = request_lifecycle()
                return response

        threads_and_connections = []
        threads_and_connections.append(request_lifecycle())

        request = HttpRequest()
        response = async_to_sync(SimpleMiddleWare(get_response))(request)
        threads_and_connections.append(request.thread_and_connection)
        threads_and_connections.append(response.thread_and_connection)

        threads_and_connections.append(request_lifecycle())

        self.assertEqual(len(threads_and_connections), 4)
        self.assertEqual(len(set(threads_and_connections)), 1)
