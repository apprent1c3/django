"""
Tests for django.core.servers.
"""

import errno
import os
import socket
import threading
import unittest
from http.client import HTTPConnection
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.core.servers.basehttp import ThreadedWSGIServer, WSGIServer
from django.db import DEFAULT_DB_ALIAS, connection, connections
from django.test import LiveServerTestCase, override_settings
from django.test.testcases import LiveServerThread, QuietWSGIRequestHandler

from .models import Person

TEST_ROOT = os.path.dirname(__file__)
TEST_SETTINGS = {
    "MEDIA_URL": "media/",
    "MEDIA_ROOT": os.path.join(TEST_ROOT, "media"),
    "STATIC_URL": "static/",
    "STATIC_ROOT": os.path.join(TEST_ROOT, "static"),
}


@override_settings(ROOT_URLCONF="servers.urls", **TEST_SETTINGS)
class LiveServerBase(LiveServerTestCase):
    available_apps = [
        "servers",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
    ]
    fixtures = ["testdata.json"]

    def urlopen(self, url):
        return urlopen(self.live_server_url + url)


class CloseConnectionTestServer(ThreadedWSGIServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This event is set right after the first time a request closes its
        # database connections.
        self._connections_closed = threading.Event()

    def _close_connections(self):
        """

        Closes all existing connections and signals that the connections are closed.

        This method extends the parent class's connection closure functionality by setting
        an internal flag to indicate that all connections have been successfully closed.

        """
        super()._close_connections()
        self._connections_closed.set()


class CloseConnectionTestLiveServerThread(LiveServerThread):
    server_class = CloseConnectionTestServer

    def _create_server(self, connections_override=None):
        return super()._create_server(connections_override=self.connections_override)


class LiveServerTestCloseConnectionTest(LiveServerBase):
    server_thread_class = CloseConnectionTestLiveServerThread

    @classmethod
    def _make_connections_override(cls):
        conn = connections[DEFAULT_DB_ALIAS]
        cls.conn = conn
        cls.old_conn_max_age = conn.settings_dict["CONN_MAX_AGE"]
        # Set the connection's CONN_MAX_AGE to None to simulate the
        # CONN_MAX_AGE setting being set to None on the server. This prevents
        # Django from closing the connection and allows testing that
        # ThreadedWSGIServer closes connections.
        conn.settings_dict["CONN_MAX_AGE"] = None
        # Pass a database connection through to the server to check it is being
        # closed by ThreadedWSGIServer.
        return {DEFAULT_DB_ALIAS: conn}

    @classmethod
    def tearDownConnectionTest(cls):
        cls.conn.settings_dict["CONN_MAX_AGE"] = cls.old_conn_max_age

    @classmethod
    def tearDownClass(cls):
        cls.tearDownConnectionTest()
        super().tearDownClass()

    def test_closes_connections(self):
        # The server's request thread sets this event after closing
        # its database connections.
        """

        Tests that the connection is properly closed after a request is made.

        This test verifies that the connection to the server is established, 
        a request is successfully made to the '/model_view/' endpoint, 
        and that the connection is subsequently closed. 
        The test checks for the connection status before and after the request, 
        ensuring that the connection is active during the request and inactive afterwards. 
        It also checks that the response from the server contains the expected data.

        """
        closed_event = self.server_thread.httpd._connections_closed
        conn = self.conn
        # Open a connection to the database.
        conn.connect()
        self.assertIsNotNone(conn.connection)
        with self.urlopen("/model_view/") as f:
            # The server can access the database.
            self.assertCountEqual(f.read().splitlines(), [b"jane", b"robert"])
        # Wait for the server's request thread to close the connection.
        # A timeout of 0.1 seconds should be more than enough. If the wait
        # times out, the assertion after should fail.
        closed_event.wait(timeout=0.1)
        self.assertIsNone(conn.connection)


@unittest.skipUnless(connection.vendor == "sqlite", "SQLite specific test.")
class LiveServerInMemoryDatabaseLockTest(LiveServerBase):
    def test_in_memory_database_lock(self):
        """
        With a threaded LiveServer and an in-memory database, an error can
        occur when 2 requests reach the server and try to lock the database
        at the same time, if the requests do not share the same database
        connection.
        """
        conn = self.server_thread.connections_override[DEFAULT_DB_ALIAS]
        source_connection = conn.connection
        # Open a connection to the database.
        conn.connect()
        # Create a transaction to lock the database.
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        try:
            with self.urlopen("/create_model_instance/") as f:
                self.assertEqual(f.status, 200)
        except HTTPError:
            self.fail("Unexpected error due to a database lock.")
        finally:
            # Release the transaction.
            cursor.execute("ROLLBACK")
            source_connection.close()


class FailingLiveServerThread(LiveServerThread):
    def _create_server(self, connections_override=None):
        raise RuntimeError("Error creating server.")


class LiveServerTestCaseSetupTest(LiveServerBase):
    server_thread_class = FailingLiveServerThread

    @classmethod
    def check_allowed_hosts(cls, expected):
        if settings.ALLOWED_HOSTS != expected:
            raise RuntimeError(f"{settings.ALLOWED_HOSTS} != {expected}")

    @classmethod
    def setUpClass(cls):
        """

        Set up the class for testing, handling potential runtime errors and ensuring allowed hosts.

        This method initializes the test environment by checking the allowed hosts and calling the parent class's setup method.
        If a RuntimeError occurs during setup, it cleans up the class and retries checking the allowed hosts.
        The setup process is tracked by the 'set_up_called' flag, which is set to True upon successful execution.
        Note that this method expects the setup to fail, and a RuntimeError is intentionally raised if the setup succeeds.

        """
        cls.check_allowed_hosts(["testserver"])
        try:
            super().setUpClass()
        except RuntimeError:
            # LiveServerTestCase's change to ALLOWED_HOSTS should be reverted.
            cls.doClassCleanups()
            cls.check_allowed_hosts(["testserver"])
        else:
            raise RuntimeError("Server did not fail.")
        cls.set_up_called = True

    def test_set_up_class(self):
        self.assertIs(self.set_up_called, True)


class LiveServerAddress(LiveServerBase):
    @classmethod
    def setUpClass(cls):
        """
        Sets up the class-level test environment, initializing a new class-level attribute with the live server URL for testing purposes.
        """
        super().setUpClass()
        # put it in a list to prevent descriptor lookups in test
        cls.live_server_url_test = [cls.live_server_url]

    def test_live_server_url_is_class_property(self):
        """

        Tests that the live server URL is a class property.

        This function checks that the live server URL is correctly set as a class property by verifying its type and value.
        It ensures that the URL is a string and matches the expected value, confirming that it can be accessed and used as intended.

        """
        self.assertIsInstance(self.live_server_url_test[0], str)
        self.assertEqual(self.live_server_url_test[0], self.live_server_url)


class LiveServerSingleThread(LiveServerThread):
    def _create_server(self, connections_override=None):
        return WSGIServer(
            (self.host, self.port), QuietWSGIRequestHandler, allow_reuse_address=False
        )


class SingleThreadLiveServerTestCase(LiveServerTestCase):
    server_thread_class = LiveServerSingleThread


class LiveServerViews(LiveServerBase):
    def test_protocol(self):
        """Launched server serves with HTTP 1.1."""
        with self.urlopen("/example_view/") as f:
            self.assertEqual(f.version, 11)

    def test_closes_connection_without_content_length(self):
        """
        An HTTP 1.1 server is supposed to support keep-alive. Since our
        development server is rather simple we support it only in cases where
        we can detect a content length from the response. This should be doable
        for all simple views and streaming responses where an iterable with
        length of one is passed. The latter follows as result of `set_content_length`
        from https://github.com/python/cpython/blob/main/Lib/wsgiref/handlers.py.

        If we cannot detect a content length we explicitly set the `Connection`
        header to `close` to notify the client that we do not actually support
        it.
        """
        conn = HTTPConnection(
            LiveServerViews.server_thread.host,
            LiveServerViews.server_thread.port,
            timeout=1,
        )
        try:
            conn.request(
                "GET", "/streaming_example_view/", headers={"Connection": "keep-alive"}
            )
            response = conn.getresponse()
            self.assertTrue(response.will_close)
            self.assertEqual(response.read(), b"Iamastream")
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Connection"), "close")

            conn.request(
                "GET", "/streaming_example_view/", headers={"Connection": "close"}
            )
            response = conn.getresponse()
            self.assertTrue(response.will_close)
            self.assertEqual(response.read(), b"Iamastream")
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Connection"), "close")
        finally:
            conn.close()

    def test_keep_alive_on_connection_with_content_length(self):
        """
        See `test_closes_connection_without_content_length` for details. This
        is a follow up test, which ensure that we do not close the connection
        if not needed, hence allowing us to take advantage of keep-alive.
        """
        conn = HTTPConnection(
            LiveServerViews.server_thread.host, LiveServerViews.server_thread.port
        )
        try:
            conn.request("GET", "/example_view/", headers={"Connection": "keep-alive"})
            response = conn.getresponse()
            self.assertFalse(response.will_close)
            self.assertEqual(response.read(), b"example view")
            self.assertEqual(response.status, 200)
            self.assertIsNone(response.getheader("Connection"))

            conn.request("GET", "/example_view/", headers={"Connection": "close"})
            response = conn.getresponse()
            self.assertFalse(response.will_close)
            self.assertEqual(response.read(), b"example view")
            self.assertEqual(response.status, 200)
            self.assertIsNone(response.getheader("Connection"))
        finally:
            conn.close()

    def test_keep_alive_connection_clears_previous_request_data(self):
        """
        Tests that a keep-alive connection clears previous request data.

        This test case verifies the functionality of a keep-alive connection by sending
        two consecutive POST requests to a live server. It checks that the connection
        remains open after the first request and that the response data from the first
        request does not interfere with the response data of the second request. The
        test also ensures that the connection is properly closed after the test is completed.

        The test covers the following scenarios:

        * Sending a POST request with a keep-alive connection
        * Verifying that the connection remains open after the first request
        * Sending a subsequent POST request
        * Verifying that the response data from the first request does not affect the second request
        * Ensuring that the connection is properly closed after the test

        This test helps to ensure that the keep-alive connection is functioning correctly
        and that previous request data is properly cleared, which is essential for maintaining
        a stable and reliable connection to the server.
        """
        conn = HTTPConnection(
            LiveServerViews.server_thread.host, LiveServerViews.server_thread.port
        )
        try:
            conn.request(
                "POST", "/method_view/", b"{}", headers={"Connection": "keep-alive"}
            )
            response = conn.getresponse()
            self.assertFalse(response.will_close)
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"POST")

            conn.request(
                "POST", "/method_view/", b"{}", headers={"Connection": "close"}
            )
            response = conn.getresponse()
            self.assertFalse(response.will_close)
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"POST")
        finally:
            conn.close()

    def test_404(self):
        """
        Tests that a 404 HTTP error is raised when attempting to access the root URL ('/').

         Verifies that the request fails as expected, with the correct error code and 
         that the error object is properly closed after handling. This ensures the 
         system behaves correctly when encountering a non-existent or unavailable resource.
        """
        with self.assertRaises(HTTPError) as err:
            self.urlopen("/")
        err.exception.close()
        self.assertEqual(err.exception.code, 404, "Expected 404 response")

    def test_view(self):
        """
        Tests the response of the /example_view/ URL by asserting that its content is 'example view'. This test case ensures the view is correctly handled and the expected output is returned.
        """
        with self.urlopen("/example_view/") as f:
            self.assertEqual(f.read(), b"example view")

    def test_static_files(self):
        with self.urlopen("/static/example_static_file.txt") as f:
            self.assertEqual(f.read().rstrip(b"\r\n"), b"example static file")

    def test_no_collectstatic_emulation(self):
        """
        LiveServerTestCase reports a 404 status code when HTTP client
        tries to access a static file that isn't explicitly put under
        STATIC_ROOT.
        """
        with self.assertRaises(HTTPError) as err:
            self.urlopen("/static/another_app/another_app_static_file.txt")
        err.exception.close()
        self.assertEqual(err.exception.code, 404, "Expected 404 response")

    def test_media_files(self):
        """

        Tests the retrieval of a media file.

        This test case verifies that a media file can be successfully fetched and its contents match the expected value.
        The test retrieves a sample media file, reads its contents, and asserts that the contents are as expected.

        """
        with self.urlopen("/media/example_media_file.txt") as f:
            self.assertEqual(f.read().rstrip(b"\r\n"), b"example media file")

    def test_environ(self):
        with self.urlopen("/environ_view/?%s" % urlencode({"q": "тест"})) as f:
            self.assertIn(b"QUERY_STRING: 'q=%D1%82%D0%B5%D1%81%D1%82'", f.read())


@override_settings(ROOT_URLCONF="servers.urls")
class SingleThreadLiveServerViews(SingleThreadLiveServerTestCase):
    available_apps = ["servers"]

    def test_closes_connection_with_content_length(self):
        """
        Contrast to
        LiveServerViews.test_keep_alive_on_connection_with_content_length().
        Persistent connections require threading server.
        """
        conn = HTTPConnection(
            SingleThreadLiveServerViews.server_thread.host,
            SingleThreadLiveServerViews.server_thread.port,
            timeout=1,
        )
        try:
            conn.request("GET", "/example_view/", headers={"Connection": "keep-alive"})
            response = conn.getresponse()
            self.assertTrue(response.will_close)
            self.assertEqual(response.read(), b"example view")
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Connection"), "close")
        finally:
            conn.close()


class LiveServerDatabase(LiveServerBase):
    def test_fixtures_loaded(self):
        """
        Fixtures are properly loaded and visible to the live server thread.
        """
        with self.urlopen("/model_view/") as f:
            self.assertCountEqual(f.read().splitlines(), [b"jane", b"robert"])

    def test_database_writes(self):
        """
        Data written to the database by a view can be read.
        """
        with self.urlopen("/create_model_instance/"):
            pass
        self.assertQuerySetEqual(
            Person.objects.order_by("pk"),
            ["jane", "robert", "emily"],
            lambda b: b.name,
        )


class LiveServerPort(LiveServerBase):
    def test_port_bind(self):
        """
        Each LiveServerTestCase binds to a unique port or fails to start a
        server thread when run concurrently (#26011).
        """
        TestCase = type("TestCase", (LiveServerBase,), {})
        try:
            TestCase._start_server_thread()
        except OSError as e:
            if e.errno == errno.EADDRINUSE:
                # We're out of ports, LiveServerTestCase correctly fails with
                # an OSError.
                return
            # Unexpected error.
            raise
        try:
            self.assertNotEqual(
                self.live_server_url,
                TestCase.live_server_url,
                f"Acquired duplicate server addresses for server threads: "
                f"{self.live_server_url}",
            )
        finally:
            TestCase.doClassCleanups()

    def test_specified_port_bind(self):
        """LiveServerTestCase.port customizes the server's port."""
        TestCase = type("TestCase", (LiveServerBase,), {})
        # Find an open port and tell TestCase to use it.
        s = socket.socket()
        s.bind(("", 0))
        TestCase.port = s.getsockname()[1]
        s.close()
        TestCase._start_server_thread()
        try:
            self.assertEqual(
                TestCase.port,
                TestCase.server_thread.port,
                f"Did not use specified port for LiveServerTestCase thread: "
                f"{TestCase.port}",
            )
        finally:
            TestCase.doClassCleanups()


class LiveServerThreadedTests(LiveServerBase):
    """If LiveServerTestCase isn't threaded, these tests will hang."""

    def test_view_calls_subview(self):
        url = "/subview_calling_view/?%s" % urlencode({"url": self.live_server_url})
        with self.urlopen(url) as f:
            self.assertEqual(f.read(), b"subview calling view: subview")

    def test_check_model_instance_from_subview(self):
        """
        检查模型实例从子视图测试用例。

        此函数测试模型实例是否可以在子视图中正确检索和验证。它通过向指定的URL发送请求并检查响应体中是否包含特定数据来实现此目的。在本例中，函数检查响应体中是否包含字符串\"emily\"，以 доказ明模型实例已被成功检索和渲染。
        """
        url = "/check_model_instance_from_subview/?%s" % urlencode(
            {
                "url": self.live_server_url,
            }
        )
        with self.urlopen(url) as f:
            self.assertIn(b"emily", f.read())
