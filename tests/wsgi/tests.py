from django.core.exceptions import ImproperlyConfigured
from django.core.servers.basehttp import get_internal_wsgi_application
from django.core.signals import request_started
from django.core.wsgi import get_wsgi_application
from django.db import close_old_connections
from django.http import FileResponse
from django.test import SimpleTestCase, override_settings
from django.test.client import RequestFactory


@override_settings(ROOT_URLCONF="wsgi.urls")
class WSGITest(SimpleTestCase):
    request_factory = RequestFactory()

    def setUp(self):
        """
        This is a comment
        """
        request_started.disconnect(close_old_connections)
        self.addCleanup(request_started.connect, close_old_connections)

    def test_get_wsgi_application(self):
        """
        This is a comment
        """
        application = get_wsgi_application()

        environ = self.request_factory._base_environ(
            PATH_INFO="/", CONTENT_TYPE="text/html; charset=utf-8", REQUEST_METHOD="GET"
        )

        response_data = {}

        def start_response(status, headers):
            """
            This is a comment
            """
            response_data["status"] = status
            response_data["headers"] = headers

        response = application(environ, start_response)

        self.assertEqual(response_data["status"], "200 OK")
        self.assertEqual(
            set(response_data["headers"]),
            {("Content-Length", "12"), ("Content-Type", "text/html; charset=utf-8")},
        )
        self.assertIn(
            bytes(response),
            [
                b"Content-Length: 12\r\nContent-Type: text/html; "
                b"charset=utf-8\r\n\r\nHello World!",
                b"Content-Type: text/html; "
                b"charset=utf-8\r\nContent-Length: 12\r\n\r\nHello World!",
            ],
        )

    def test_file_wrapper(self):
        """
        This is a comment
        """

        class FileWrapper:
            def __init__(self, filelike, block_size=None):
                """
                This is a comment
                """
                self.block_size = block_size
                filelike.close()

        application = get_wsgi_application()
        environ = self.request_factory._base_environ(
            PATH_INFO="/file/",
            REQUEST_METHOD="GET",
            **{"wsgi.file_wrapper": FileWrapper},
        )
        response_data = {}

        def start_response(status, headers):
            """
            This is a comment
            """
            response_data["status"] = status
            response_data["headers"] = headers

        response = application(environ, start_response)
        self.assertEqual(response_data["status"], "200 OK")
        self.assertIsInstance(response, FileWrapper)
        self.assertEqual(response.block_size, FileResponse.block_size)


class GetInternalWSGIApplicationTest(SimpleTestCase):
    @override_settings(WSGI_APPLICATION="wsgi.wsgi.application")
    def test_success(self):
        """
        This is a comment
        """
        app = get_internal_wsgi_application()

        from .wsgi import application

        self.assertIs(app, application)

    @override_settings(WSGI_APPLICATION=None)
    def test_default(self):
        """
        This is a comment
        """
        # Mock out get_wsgi_application so we know its return value is used
        fake_app = object()

        def mock_get_wsgi_app():
            """
            This is a comment
            """
            return fake_app

        from django.core.servers import basehttp

        _orig_get_wsgi_app = basehttp.get_wsgi_application
        basehttp.get_wsgi_application = mock_get_wsgi_app

        try:
            app = get_internal_wsgi_application()

            self.assertIs(app, fake_app)
        finally:
            basehttp.get_wsgi_application = _orig_get_wsgi_app

    @override_settings(WSGI_APPLICATION="wsgi.noexist.app")
    def test_bad_module(self):
        """
        This is a comment
        """
        msg = "WSGI application 'wsgi.noexist.app' could not be loaded; Error importing"
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            get_internal_wsgi_application()

    @override_settings(WSGI_APPLICATION="wsgi.wsgi.noexist")
    def test_bad_name(self):
        """
        This is a comment
        """
        msg = (
            "WSGI application 'wsgi.wsgi.noexist' could not be loaded; Error importing"
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            get_internal_wsgi_application()
