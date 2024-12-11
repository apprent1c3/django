from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.handlers.asgi import ASGIHandler
from django.test import AsyncRequestFactory

from .cases import StaticFilesTestCase


class MockApplication:
    """ASGI application that returns a string indicating that it was called."""

    async def __call__(self, scope, receive, send):
        return "Application called"


class TestASGIStaticFilesHandler(StaticFilesTestCase):
    async_request_factory = AsyncRequestFactory()

    async def test_get_async_response(self):
        request = self.async_request_factory.get("/static/test/file.txt")
        handler = ASGIStaticFilesHandler(ASGIHandler())
        response = await handler.get_response_async(request)
        response.close()
        self.assertEqual(response.status_code, 200)

    async def test_get_async_response_not_found(self):
        request = self.async_request_factory.get("/static/test/not-found.txt")
        handler = ASGIStaticFilesHandler(ASGIHandler())
        response = await handler.get_response_async(request)
        self.assertEqual(response.status_code, 404)

    async def test_non_http_requests_passed_to_the_wrapped_application(self):
        """

        Tests that non-HTTP requests are properly passed to the wrapped application.

        This test verifies that when a non-HTTP request (in this case, a WebSocket request)
        is made to a path, the request is correctly handled by the wrapped application,
        rather than being intercepted by the static file handler.

        The test checks this behavior for both static and non-static paths, to ensure
        that the wrapped application receives all non-HTTP requests as expected.

        """
        tests = [
            "/static/path.txt",
            "/non-static/path.txt",
        ]
        for path in tests:
            with self.subTest(path=path):
                scope = {"type": "websocket", "path": path}
                handler = ASGIStaticFilesHandler(MockApplication())
                response = await handler(scope, None, None)
                self.assertEqual(response, "Application called")
