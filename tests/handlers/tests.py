from django.core.exceptions import ImproperlyConfigured
from django.core.handlers.wsgi import WSGIHandler, WSGIRequest, get_script_name
from django.core.signals import request_finished, request_started
from django.db import close_old_connections, connection
from django.test import (
    AsyncRequestFactory,
    RequestFactory,
    SimpleTestCase,
    TransactionTestCase,
    override_settings,
)


class HandlerTests(SimpleTestCase):
    request_factory = RequestFactory()

    def setUp(self):
        request_started.disconnect(close_old_connections)
        self.addCleanup(request_started.connect, close_old_connections)

    def test_middleware_initialized(self):
        """

        Checks that the middleware chain for the WSGIHandler is properly initialized.

        Verifies that the _middleware_chain attribute of the WSGIHandler instance is not None after initialization, 
        indicating that the middleware setup is ready for use.

        """
        handler = WSGIHandler()
        self.assertIsNotNone(handler._middleware_chain)

    def test_bad_path_info(self):
        """
        A non-UTF-8 path populates PATH_INFO with an URL-encoded path and
        produces a 404.
        """
        environ = self.request_factory.get("/").environ
        environ["PATH_INFO"] = "\xed"
        handler = WSGIHandler()
        response = handler(environ, lambda *a, **k: None)
        # The path of the request will be encoded to '/%ED'.
        self.assertEqual(response.status_code, 404)

    def test_non_ascii_query_string(self):
        """
        Non-ASCII query strings are properly decoded (#20530, #22996).
        """
        environ = self.request_factory.get("/").environ
        raw_query_strings = [
            b"want=caf%C3%A9",  # This is the proper way to encode 'café'
            b"want=caf\xc3\xa9",  # UA forgot to quote bytes
            b"want=caf%E9",  # UA quoted, but not in UTF-8
            # UA forgot to convert Latin-1 to UTF-8 and to quote (typical of
            # MSIE).
            b"want=caf\xe9",
        ]
        got = []
        for raw_query_string in raw_query_strings:
            # Simulate http.server.BaseHTTPRequestHandler.parse_request
            # handling of raw request.
            environ["QUERY_STRING"] = str(raw_query_string, "iso-8859-1")
            request = WSGIRequest(environ)
            got.append(request.GET["want"])
        # %E9 is converted to the Unicode replacement character by parse_qsl
        self.assertEqual(got, ["café", "café", "caf\ufffd", "café"])

    def test_non_ascii_cookie(self):
        """Non-ASCII cookies set in JavaScript are properly decoded (#20557)."""
        environ = self.request_factory.get("/").environ
        raw_cookie = 'want="café"'.encode("utf-8").decode("iso-8859-1")
        environ["HTTP_COOKIE"] = raw_cookie
        request = WSGIRequest(environ)
        self.assertEqual(request.COOKIES["want"], "café")

    def test_invalid_unicode_cookie(self):
        """
        Invalid cookie content should result in an absent cookie, but not in a
        crash while trying to decode it (#23638).
        """
        environ = self.request_factory.get("/").environ
        environ["HTTP_COOKIE"] = "x=W\x03c(h]\x8e"
        request = WSGIRequest(environ)
        # We don't test COOKIES content, as the result might differ between
        # Python version because parsing invalid content became stricter in
        # latest versions.
        self.assertIsInstance(request.COOKIES, dict)

    @override_settings(ROOT_URLCONF="handlers.urls")
    def test_invalid_multipart_boundary(self):
        """
        Invalid boundary string should produce a "Bad Request" response, not a
        server error (#23887).
        """
        environ = self.request_factory.post("/malformed_post/").environ
        environ["CONTENT_TYPE"] = "multipart/form-data; boundary=WRONG\x07"
        handler = WSGIHandler()
        response = handler(environ, lambda *a, **k: None)
        # Expect "bad request" response
        self.assertEqual(response.status_code, 400)


@override_settings(ROOT_URLCONF="handlers.urls", MIDDLEWARE=[])
class TransactionsPerRequestTests(TransactionTestCase):
    available_apps = []

    def test_no_transaction(self):
        """
        Tests that the '/in_transaction/' endpoint correctly reports when no transaction is in progress.

        The test sends a GET request to the endpoint and verifies that the response contains 'False', indicating that no transaction is currently being processed.
        """
        response = self.client.get("/in_transaction/")
        self.assertContains(response, "False")

    def test_auto_transaction(self):
        """

        Tests that the auto transaction feature is functioning as expected.

        This test case checks the behavior of a view when atomic requests are enabled.
        It sets atomic requests to True, makes a GET request to a specific view, 
        and then verifies that the response contains an indication that the 
        request was indeed handled within a transaction.

        """
        old_atomic_requests = connection.settings_dict["ATOMIC_REQUESTS"]
        try:
            connection.settings_dict["ATOMIC_REQUESTS"] = True
            response = self.client.get("/in_transaction/")
        finally:
            connection.settings_dict["ATOMIC_REQUESTS"] = old_atomic_requests
        self.assertContains(response, "True")

    async def test_auto_transaction_async_view(self):
        old_atomic_requests = connection.settings_dict["ATOMIC_REQUESTS"]
        try:
            connection.settings_dict["ATOMIC_REQUESTS"] = True
            msg = "You cannot use ATOMIC_REQUESTS with async views."
            with self.assertRaisesMessage(RuntimeError, msg):
                await self.async_client.get("/async_regular/")
        finally:
            connection.settings_dict["ATOMIC_REQUESTS"] = old_atomic_requests

    def test_no_auto_transaction(self):
        """
        ..: 
            Tests whether automatic transaction handling works as expected.

            This test case checks the behavior of views that are not using transactions
            when atomic requests are enabled. It tests three different scenarios:
            - A view that does not use transactions and returns a boolean value.
            - A view that does not use transactions and returns None.
            - A view that does not use transactions and returns a text value.

            In each case, the test enables atomic requests, sends a GET request to the view,
            and then checks the response to ensure that it matches the expected output.
            The atomic requests setting is restored to its original value after each test.
        """
        old_atomic_requests = connection.settings_dict["ATOMIC_REQUESTS"]
        try:
            connection.settings_dict["ATOMIC_REQUESTS"] = True
            response = self.client.get("/not_in_transaction/")
        finally:
            connection.settings_dict["ATOMIC_REQUESTS"] = old_atomic_requests
        self.assertContains(response, "False")
        try:
            connection.settings_dict["ATOMIC_REQUESTS"] = True
            response = self.client.get("/not_in_transaction_using_none/")
        finally:
            connection.settings_dict["ATOMIC_REQUESTS"] = old_atomic_requests
        self.assertContains(response, "False")
        try:
            connection.settings_dict["ATOMIC_REQUESTS"] = True
            response = self.client.get("/not_in_transaction_using_text/")
        finally:
            connection.settings_dict["ATOMIC_REQUESTS"] = old_atomic_requests
        # The non_atomic_requests decorator is used for an incorrect table.
        self.assertContains(response, "True")


@override_settings(ROOT_URLCONF="handlers.urls")
class SignalsTests(SimpleTestCase):
    def setUp(self):
        self.signals = []
        self.signaled_environ = None
        request_started.connect(self.register_started)
        self.addCleanup(request_started.disconnect, self.register_started)
        request_finished.connect(self.register_finished)
        self.addCleanup(request_finished.disconnect, self.register_finished)

    def register_started(self, **kwargs):
        self.signals.append("started")
        self.signaled_environ = kwargs.get("environ")

    def register_finished(self, **kwargs):
        self.signals.append("finished")

    def test_request_signals(self):
        response = self.client.get("/regular/")
        self.assertEqual(self.signals, ["started", "finished"])
        self.assertEqual(response.content, b"regular content")
        self.assertEqual(self.signaled_environ, response.wsgi_request.environ)

    def test_request_signals_streaming_response(self):
        response = self.client.get("/streaming/")
        self.assertEqual(self.signals, ["started"])
        self.assertEqual(b"".join(list(response)), b"streaming content")
        self.assertEqual(self.signals, ["started", "finished"])


def empty_middleware(get_response):
    pass


@override_settings(ROOT_URLCONF="handlers.urls")
class HandlerRequestTests(SimpleTestCase):
    request_factory = RequestFactory()

    def test_async_view(self):
        """Calling an async view down the normal synchronous path."""
        response = self.client.get("/async_regular/")
        self.assertEqual(response.status_code, 200)

    def test_suspiciousop_in_view_returns_400(self):
        response = self.client.get("/suspicious/")
        self.assertEqual(response.status_code, 400)

    def test_bad_request_in_view_returns_400(self):
        """
        Tests that a HTTP request to the '/bad_request/' view endpoint returns a 400 status code, 
        indicating a Bad Request response, to verify proper error handling.
        """
        response = self.client.get("/bad_request/")
        self.assertEqual(response.status_code, 400)

    def test_invalid_urls(self):
        response = self.client.get("~%A9helloworld")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.context["request_path"], "/~%25A9helloworld")

        response = self.client.get("d%aao%aaw%aan%aal%aao%aaa%aad%aa/")
        self.assertEqual(
            response.context["request_path"],
            "/d%25AAo%25AAw%25AAn%25AAl%25AAo%25AAa%25AAd%25AA",
        )

        response = self.client.get("/%E2%99%E2%99%A5/")
        self.assertEqual(response.context["request_path"], "/%25E2%2599%E2%99%A5/")

        response = self.client.get("/%E2%98%8E%E2%A9%E2%99%A5/")
        self.assertEqual(
            response.context["request_path"], "/%E2%98%8E%25E2%25A9%E2%99%A5/"
        )

    def test_environ_path_info_type(self):
        environ = self.request_factory.get("/%E2%A8%87%87%A5%E2%A8%A0").environ
        self.assertIsInstance(environ["PATH_INFO"], str)

    def test_handle_accepts_httpstatus_enum_value(self):
        def start_response(status, headers):
            start_response.status = status

        environ = self.request_factory.get("/httpstatus_enum/").environ
        WSGIHandler()(environ, start_response)
        self.assertEqual(start_response.status, "200 OK")

    @override_settings(MIDDLEWARE=["handlers.tests.empty_middleware"])
    def test_middleware_returns_none(self):
        """
        Tests that an ImproperlyConfigured exception is raised when a middleware factory returns None.

        This test case verifies the behavior of the system when a middleware factory fails to return a valid middleware instance.
        It checks that the expected error message is raised, ensuring that the system correctly handles invalid middleware configurations.

        :raises: ImproperlyConfigured
        """
        msg = "Middleware factory handlers.tests.empty_middleware returned None."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/")

    def test_no_response(self):
        msg = (
            "The view %s didn't return an HttpResponse object. It returned None "
            "instead."
        )
        tests = (
            ("/no_response_fbv/", "handlers.views.no_response"),
            ("/no_response_cbv/", "handlers.views.NoResponse.__call__"),
        )
        for url, view in tests:
            with (
                self.subTest(url=url),
                self.assertRaisesMessage(ValueError, msg % view),
            ):
                self.client.get(url)

    def test_streaming(self):
        response = self.client.get("/streaming/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(list(response)), b"streaming content")

    def test_async_streaming(self):
        response = self.client.get("/async_streaming/")
        self.assertEqual(response.status_code, 200)
        msg = (
            "StreamingHttpResponse must consume asynchronous iterators in order to "
            "serve them synchronously. Use a synchronous iterator instead."
        )
        with self.assertWarnsMessage(Warning, msg):
            self.assertEqual(b"".join(list(response)), b"streaming content")


class ScriptNameTests(SimpleTestCase):
    def test_get_script_name(self):
        # Regression test for #23173
        # Test first without PATH_INFO
        script_name = get_script_name({"SCRIPT_URL": "/foobar/"})
        self.assertEqual(script_name, "/foobar/")

        script_name = get_script_name({"SCRIPT_URL": "/foobar/", "PATH_INFO": "/"})
        self.assertEqual(script_name, "/foobar")

    def test_get_script_name_double_slashes(self):
        """
        WSGI squashes multiple successive slashes in PATH_INFO, get_script_name
        should take that into account when forming SCRIPT_NAME (#17133).
        """
        script_name = get_script_name(
            {
                "SCRIPT_URL": "/mst/milestones//accounts/login//help",
                "PATH_INFO": "/milestones/accounts/login/help",
            }
        )
        self.assertEqual(script_name, "/mst")


@override_settings(ROOT_URLCONF="handlers.urls")
class AsyncHandlerRequestTests(SimpleTestCase):
    """Async variants of the normal handler request tests."""

    async def test_sync_view(self):
        """Calling a sync view down the asynchronous path."""
        response = await self.async_client.get("/regular/")
        self.assertEqual(response.status_code, 200)

    async def test_async_view(self):
        """Calling an async view down the asynchronous path."""
        response = await self.async_client.get("/async_regular/")
        self.assertEqual(response.status_code, 200)

    async def test_suspiciousop_in_view_returns_400(self):
        response = await self.async_client.get("/suspicious/")
        self.assertEqual(response.status_code, 400)

    async def test_bad_request_in_view_returns_400(self):
        response = await self.async_client.get("/bad_request/")
        self.assertEqual(response.status_code, 400)

    async def test_no_response(self):
        msg = (
            "The view handlers.views.no_response didn't return an "
            "HttpResponse object. It returned None instead."
        )
        with self.assertRaisesMessage(ValueError, msg):
            await self.async_client.get("/no_response_fbv/")

    async def test_unawaited_response(self):
        """
        Checks if an unawaited coroutine in a view handler correctly raises a ValueError.

        This test case verifies that the framework properly handles the situation when a view returns an unawaited coroutine instead of an expected HttpResponse object. It ensures that the correct error message is raised when this occurs, providing a clear indication of the issue to the developer.
        """
        msg = (
            "The view handlers.views.CoroutineClearingView.__call__ didn't"
            " return an HttpResponse object. It returned an unawaited"
            " coroutine instead. You may need to add an 'await'"
            " into your view."
        )
        with self.assertRaisesMessage(ValueError, msg):
            await self.async_client.get("/unawaited/")

    def test_root_path(self):
        """

        Tests that the root path of an asynchronous request is correctly handled.

        Verifies that the request path, script name, and path info are properly set when
        a request is made with a root path. The test checks that the absolute path
        of the request, the root path prefix, and the relative path after the root
        are accurately extracted and stored in the request object.

        """
        async_request_factory = AsyncRequestFactory()
        request = async_request_factory.request(
            **{"path": "/root/somepath/", "root_path": "/root"}
        )
        self.assertEqual(request.path, "/root/somepath/")
        self.assertEqual(request.script_name, "/root")
        self.assertEqual(request.path_info, "/somepath/")

    @override_settings(FORCE_SCRIPT_NAME="/FORCED_PREFIX")
    def test_force_script_name(self):
        async_request_factory = AsyncRequestFactory()
        request = async_request_factory.request(**{"path": "/FORCED_PREFIX/somepath/"})
        self.assertEqual(request.path, "/FORCED_PREFIX/somepath/")
        self.assertEqual(request.script_name, "/FORCED_PREFIX")
        self.assertEqual(request.path_info, "/somepath/")

    async def test_sync_streaming(self):
        """
        Tests the synchronous streaming functionality of the async client.

        Verifies that a GET request to the '/streaming/' endpoint returns a 200 status code and
        that the response content is correctly streamed. Also checks that a warning is raised
        when attempting to consume a synchronous iterator in an asynchronous context, as this
        can cause performance issues.

        The test validates that the async client can handle streaming responses and that the
        Warning message is properly raised when using a synchronous iterator, ensuring that
        users are notified to use asynchronous iterators instead for optimal performance.
        """
        response = await self.async_client.get("/streaming/")
        self.assertEqual(response.status_code, 200)
        msg = (
            "StreamingHttpResponse must consume synchronous iterators in order to "
            "serve them asynchronously. Use an asynchronous iterator instead."
        )
        with self.assertWarnsMessage(Warning, msg):
            self.assertEqual(
                b"".join([chunk async for chunk in response]), b"streaming content"
            )

    async def test_async_streaming(self):
        """
        Tests asynchronous streaming functionality by sending a GET request to the '/async_streaming/' endpoint.

        This test case verifies that the response status code is 200 (OK) and that the streamed content is correctly received and decoded.

        The test uses the async_client to send the request and then joins the streamed chunks into a single bytes object for comparison with the expected content.

        Successful execution of this test indicates that the asynchronous streaming functionality is working as expected, allowing for efficient handling of large or continuous data streams.
        """
        response = await self.async_client.get("/async_streaming/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            b"".join([chunk async for chunk in response]), b"streaming content"
        )
