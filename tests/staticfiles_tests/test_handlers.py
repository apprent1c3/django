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
        """

        Tests the retrieval of an asynchronous response from a static file.

        This function verifies that an ASGIStaticFilesHandler can successfully handle
        a GET request for a static file and return a response with a status code of 200.

        """
        request = self.async_request_factory.get("/static/test/file.txt")
        handler = ASGIStaticFilesHandler(ASGIHandler())
        response = await handler.get_response_async(request)
        response.close()
        self.assertEqual(response.status_code, 200)

    async def test_get_async_response_not_found(self):
        """

        Tests the ASGIStaticFilesHandler's ability to handle asynchronous GET requests for non-existent files.

        This test case verifies that when a request is made for a static file that does not exist, the handler returns a 404 status code, indicating that the requested resource was not found.

        The test simulates an asynchronous request to retrieve a non-existent static file and checks the status code of the response to ensure it matches the expected \"Not Found\" status.

        """
        request = self.async_request_factory.get("/static/test/not-found.txt")
        handler = ASGIStaticFilesHandler(ASGIHandler())
        response = await handler.get_response_async(request)
        self.assertEqual(response.status_code, 404)

    async def test_non_http_requests_passed_to_the_wrapped_application(self):
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
