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
        This is a comment
        """
        class GetResponse:
            def __call__(self):
                """
                This is a comment
                """
                return HttpResponse()

        def get_response():
            """
            This is a comment
            """
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
        This is a comment
        """
        msg = "get_response must be provided."
        for middleware in self.middlewares:
            with self.subTest(middleware=middleware):
                with self.assertRaisesMessage(ValueError, msg):
                    middleware(None)

    def test_coroutine(self):
        """
        This is a comment
        """
        async def async_get_response(request):
            return HttpResponse()

        def sync_get_response(request):
            """
            This is a comment
            """
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
        This is a comment
        """

        def request_lifecycle():
            """
            This is a comment
            """
            return (threading.get_ident(), id(connection))

        async def get_response(self):
            return HttpResponse()

        class SimpleMiddleWare(MiddlewareMixin):
            def process_request(self, request):
                """
                This is a comment
                """
                request.thread_and_connection = request_lifecycle()

            def process_response(self, request, response):
                """
                This is a comment
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
