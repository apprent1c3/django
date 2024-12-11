import asyncio
import sys
import threading
import time
from pathlib import Path

from asgiref.sync import sync_to_async
from asgiref.testing import ApplicationCommunicator

from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application
from django.core.exceptions import RequestDataTooBig
from django.core.handlers.asgi import ASGIHandler, ASGIRequest
from django.core.signals import request_finished, request_started
from django.db import close_old_connections
from django.http import HttpResponse, StreamingHttpResponse
from django.test import (
    AsyncRequestFactory,
    SimpleTestCase,
    ignore_warnings,
    modify_settings,
    override_settings,
)
from django.urls import path
from django.utils.http import http_date
from django.views.decorators.csrf import csrf_exempt

from .urls import sync_waiter, test_filename

TEST_STATIC_ROOT = Path(__file__).parent / "project" / "static"


class SignalHandler:
    """Helper class to track threads and kwargs when signals are dispatched."""

    def __init__(self):
        """
        Initializes a new instance of the class.

        This method is called when an object is created from the class and it sets up the basic state of the object.
        It inherits the initialization behavior from its parent class and initializes an empty list to store calls made by the object.

        :raises: No specific exceptions are raised by this method.
        :note: This is a special method in Python classes, known as a constructor, and is not intended to be called directly.
        """
        super().__init__()
        self.calls = []

    def __call__(self, signal, **kwargs):
        self.calls.append({"thread": threading.current_thread(), "kwargs": kwargs})


@override_settings(ROOT_URLCONF="asgi.urls")
class ASGITest(SimpleTestCase):
    async_request_factory = AsyncRequestFactory()

    def setUp(self):
        """
        Sets up the test environment by temporarily unregistering the database connection closer.

        This method ensures that old database connections are not closed at the start of each request during the test. 
        Instead, it delays the re-registration of the connection closer until the test is cleaned up, 
        preventing any potential issues with connections being closed prematurely. 

        This setup is necessary for tests that require a stable database connection throughout their execution.

        Note: This method is typically used in a testing context, such as in a TestCase subclass.
        """
        request_started.disconnect(close_old_connections)
        self.addCleanup(request_started.connect, close_old_connections)

    async def test_get_asgi_application(self):
        """
        get_asgi_application() returns a functioning ASGI callable.
        """
        application = get_asgi_application()
        # Construct HTTP request.
        scope = self.async_request_factory._base_scope(path="/")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        # Read the response.
        response_start = await communicator.receive_output()
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 200)
        self.assertEqual(
            set(response_start["headers"]),
            {
                (b"Content-Length", b"12"),
                (b"Content-Type", b"text/html; charset=utf-8"),
            },
        )
        response_body = await communicator.receive_output()
        self.assertEqual(response_body["type"], "http.response.body")
        self.assertEqual(response_body["body"], b"Hello World!")
        # Allow response.close() to finish.
        await communicator.wait()

    # Python's file API is not async compatible. A third-party library such
    # as https://github.com/Tinche/aiofiles allows passing the file to
    # FileResponse as an async iterator. With a sync iterator
    # StreamingHTTPResponse triggers a warning when iterating the file.
    # assertWarnsMessage is not async compatible, so ignore_warnings for the
    # test.
    @ignore_warnings(module="django.http.response")
    async def test_file_response(self):
        """
        Makes sure that FileResponse works over ASGI.
        """
        application = get_asgi_application()
        # Construct HTTP request.
        scope = self.async_request_factory._base_scope(path="/file/")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        # Get the file content.
        with open(test_filename, "rb") as test_file:
            test_file_contents = test_file.read()
        # Read the response.
        response_start = await communicator.receive_output()
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 200)
        headers = response_start["headers"]
        self.assertEqual(len(headers), 3)
        expected_headers = {
            b"Content-Length": str(len(test_file_contents)).encode("ascii"),
            b"Content-Type": b"text/x-python",
            b"Content-Disposition": b'inline; filename="urls.py"',
        }
        for key, value in headers:
            try:
                self.assertEqual(value, expected_headers[key])
            except AssertionError:
                # Windows registry may not be configured with correct
                # mimetypes.
                if sys.platform == "win32" and key == b"Content-Type":
                    self.assertEqual(value, b"text/plain")
                else:
                    raise

        # Warning ignored here.
        response_body = await communicator.receive_output()
        self.assertEqual(response_body["type"], "http.response.body")
        self.assertEqual(response_body["body"], test_file_contents)
        # Allow response.close() to finish.
        await communicator.wait()

    @modify_settings(INSTALLED_APPS={"append": "django.contrib.staticfiles"})
    @override_settings(
        STATIC_URL="static/",
        STATIC_ROOT=TEST_STATIC_ROOT,
        STATICFILES_DIRS=[TEST_STATIC_ROOT],
        STATICFILES_FINDERS=[
            "django.contrib.staticfiles.finders.FileSystemFinder",
        ],
    )
    async def test_static_file_response(self):
        """
        ..:async:
            Tests the response of a static file served by the ASGIStaticFilesHandler.

            This test checks if the handler correctly serves a static file, verifying the 
            HTTP response status, headers, and body. It also ensures that the response 
            contains the correct 'Content-Length', 'Content-Type', 'Content-Disposition', 
            and 'Last-Modified' headers. 

            The test uses the ApplicationCommunicator to simulate an HTTP request and 
            verify the response sent by the ASGIStaticFilesHandler. The test case covers 
            the entire lifecycle of the request, from sending the request to receiving the 
            response body.
        """
        application = ASGIStaticFilesHandler(get_asgi_application())
        # Construct HTTP request.
        scope = self.async_request_factory._base_scope(path="/static/file.txt")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        # Get the file content.
        file_path = TEST_STATIC_ROOT / "file.txt"
        with open(file_path, "rb") as test_file:
            test_file_contents = test_file.read()
        # Read the response.
        stat = file_path.stat()
        response_start = await communicator.receive_output()
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 200)
        self.assertEqual(
            set(response_start["headers"]),
            {
                (b"Content-Length", str(len(test_file_contents)).encode("ascii")),
                (b"Content-Type", b"text/plain"),
                (b"Content-Disposition", b'inline; filename="file.txt"'),
                (b"Last-Modified", http_date(stat.st_mtime).encode("ascii")),
            },
        )
        response_body = await communicator.receive_output()
        self.assertEqual(response_body["type"], "http.response.body")
        self.assertEqual(response_body["body"], test_file_contents)
        # Allow response.close() to finish.
        await communicator.wait()

    async def test_headers(self):
        """

        Test the handling of HTTP headers in an ASGI application.

        Verifies that the application correctly processes and responds to HTTP requests
        with multiple headers of the same name. Specifically, it checks that the response
        status is 200, the Content-Type and Content-Length headers are correctly set,
        and the response body contains the expected data. The test also ensures that
        the application handles multiple 'Referer' headers correctly, by concatenating
        their values in the response body.

        """
        application = get_asgi_application()
        communicator = ApplicationCommunicator(
            application,
            self.async_request_factory._base_scope(
                path="/meta/",
                headers=[
                    [b"content-type", b"text/plain; charset=utf-8"],
                    [b"content-length", b"77"],
                    [b"referer", b"Scotland"],
                    [b"referer", b"Wales"],
                ],
            ),
        )
        await communicator.send_input({"type": "http.request"})
        response_start = await communicator.receive_output()
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 200)
        self.assertEqual(
            set(response_start["headers"]),
            {
                (b"Content-Length", b"19"),
                (b"Content-Type", b"text/plain; charset=utf-8"),
            },
        )
        response_body = await communicator.receive_output()
        self.assertEqual(response_body["type"], "http.response.body")
        self.assertEqual(response_body["body"], b"From Scotland,Wales")
        # Allow response.close() to finish
        await communicator.wait()

    async def test_post_body(self):
        """

        Tests the handling of a POST request body.

        This test checks that the application correctly echoes the body of a POST request.
        It uses the ASGI application and a test request factory to simulate a POST request
        to the '/post/' endpoint, then verifies that the response has a status code of 200
        and a body that matches the original request body.

        """
        application = get_asgi_application()
        scope = self.async_request_factory._base_scope(
            method="POST",
            path="/post/",
            query_string="echo=1",
        )
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request", "body": b"Echo!"})
        response_start = await communicator.receive_output()
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 200)
        response_body = await communicator.receive_output()
        self.assertEqual(response_body["type"], "http.response.body")
        self.assertEqual(response_body["body"], b"Echo!")

    async def test_create_request_error(self):
        # Track request_finished signal.
        """

        Tests the error handling for creating a request when the request data is too large.

        Verifies that the signal handler correctly captures the request finished signal when a 
        RequestDataTooBig exception is raised during request creation, and confirms that the 
        signal is not received by the same thread that initiated the request.

        Ensures that the application correctly handles the request error by checking the 
        number of calls to the signal handler and the thread in which the signal was received. 

        """
        signal_handler = SignalHandler()
        request_finished.connect(signal_handler)
        self.addCleanup(request_finished.disconnect, signal_handler)

        # Request class that always fails creation with RequestDataTooBig.
        class TestASGIRequest(ASGIRequest):

            def __init__(self, scope, body_file):
                """
                Initializes an instance of the class, inheriting from a parent class.

                Parameters
                ----------
                scope : 
                    The scope of the instance.
                body_file : 
                    The body file associated with the instance.

                Raises
                ------
                RequestDataTooBig
                    The instance initialization always raises a RequestDataTooBig exception, indicating that the request data exceeds the allowed limit.

                """
                super().__init__(scope, body_file)
                raise RequestDataTooBig()

        # Handler to use the custom request class.
        class TestASGIHandler(ASGIHandler):
            request_class = TestASGIRequest

        application = TestASGIHandler()
        scope = self.async_request_factory._base_scope(path="/not-important/")
        communicator = ApplicationCommunicator(application, scope)

        # Initiate request.
        await communicator.send_input({"type": "http.request"})
        # Give response.close() time to finish.
        await communicator.wait()

        self.assertEqual(len(signal_handler.calls), 1)
        self.assertNotEqual(
            signal_handler.calls[0]["thread"], threading.current_thread()
        )

    async def test_cancel_post_request_with_sync_processing(self):
        """
        The request.body object should be available and readable in view
        code, even if the ASGIHandler cancels processing part way through.
        """
        loop = asyncio.get_event_loop()
        # Events to monitor the view processing from the parent test code.
        view_started_event = asyncio.Event()
        view_finished_event = asyncio.Event()
        # Record received request body or exceptions raised in the test view
        outcome = []

        # This view will run in a new thread because it is wrapped in
        # sync_to_async. The view consumes the POST body data after a short
        # delay. The test will cancel the request using http.disconnect during
        # the delay, but because this is a sync view the code runs to
        # completion. There should be no exceptions raised inside the view
        # code.
        @csrf_exempt
        @sync_to_async
        def post_view(request):
            """

            Handles an incoming HTTP POST request asynchronously.

            This view processes the request, records its body, and returns a successful response.
            In case of an exception, it captures the error and continues execution.
            The view also triggers events to signal the start and completion of its processing.

            The recorded request body and any exceptions that occur are stored for further analysis.
            The response is always 'ok', unless an exception prevents it from being sent.

            Events are triggered to notify other parts of the system when the view starts and finishes processing.
            These events can be used to coordinate other tasks or monitor the view's execution.

            :return: An HttpResponse object with the status 'ok'

            """
            try:
                loop.call_soon_threadsafe(view_started_event.set)
                time.sleep(0.1)
                # Do something to read request.body after pause
                outcome.append({"request_body": request.body})
                return HttpResponse("ok")
            except Exception as e:
                outcome.append({"exception": e})
            finally:
                loop.call_soon_threadsafe(view_finished_event.set)

        # Request class to use the view.
        class TestASGIRequest(ASGIRequest):
            urlconf = (path("post/", post_view),)

        # Handler to use request class.
        class TestASGIHandler(ASGIHandler):
            request_class = TestASGIRequest

        application = TestASGIHandler()
        scope = self.async_request_factory._base_scope(
            method="POST",
            path="/post/",
        )
        communicator = ApplicationCommunicator(application, scope)

        await communicator.send_input({"type": "http.request", "body": b"Body data!"})

        # Wait until the view code has started, then send http.disconnect.
        await view_started_event.wait()
        await communicator.send_input({"type": "http.disconnect"})
        # Wait until view code has finished.
        await view_finished_event.wait()
        with self.assertRaises(asyncio.TimeoutError):
            await communicator.receive_output()

        self.assertEqual(outcome, [{"request_body": b"Body data!"}])

    async def test_untouched_request_body_gets_closed(self):
        application = get_asgi_application()
        scope = self.async_request_factory._base_scope(method="POST", path="/post/")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        response_start = await communicator.receive_output()
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 204)
        response_body = await communicator.receive_output()
        self.assertEqual(response_body["type"], "http.response.body")
        self.assertEqual(response_body["body"], b"")
        # Allow response.close() to finish
        await communicator.wait()

    async def test_get_query_string(self):
        """
        Tests the get query string functionality by sending an HTTP request with a query string.

        This test ensures that the application correctly handles query strings, 
        both in bytes and string formats, and returns the expected response.
        The expected response is a 200 status code with a body of 'Hello Andrew!'.

        The test covers the following scenarios:

        * Query string in bytes format
        * Query string in string format

        It verifies that the application responds correctly to both scenarios.

        """
        application = get_asgi_application()
        for query_string in (b"name=Andrew", "name=Andrew"):
            with self.subTest(query_string=query_string):
                scope = self.async_request_factory._base_scope(
                    path="/",
                    query_string=query_string,
                )
                communicator = ApplicationCommunicator(application, scope)
                await communicator.send_input({"type": "http.request"})
                response_start = await communicator.receive_output()
                self.assertEqual(response_start["type"], "http.response.start")
                self.assertEqual(response_start["status"], 200)
                response_body = await communicator.receive_output()
                self.assertEqual(response_body["type"], "http.response.body")
                self.assertEqual(response_body["body"], b"Hello Andrew!")
                # Allow response.close() to finish
                await communicator.wait()

    async def test_disconnect(self):
        """

        Tests the disconnection of an ASGI application by sending an HTTP disconnect event.

        This method simulates a disconnection scenario by creating an ApplicationCommunicator
        instance with the ASGI application and a pre-defined scope. It then sends an HTTP
        disconnect event to the communicator and verifies that a TimeoutError is raised
        when attempting to receive output, indicating that the application has been
        successfully disconnected.

        """
        application = get_asgi_application()
        scope = self.async_request_factory._base_scope(path="/")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.disconnect"})
        with self.assertRaises(asyncio.TimeoutError):
            await communicator.receive_output()

    async def test_disconnect_both_return(self):
        # Force both the disconnect listener and the task that sends the
        # response to finish at the same time.
        application = get_asgi_application()
        scope = self.async_request_factory._base_scope(path="/")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request", "body": b"some body"})
        # Fetch response headers (this yields to asyncio and causes
        # ASGHandler.send_response() to dump the body of the response in the
        # queue).
        await communicator.receive_output()
        # Fetch response body (there's already some data queued up, so this
        # doesn't actually yield to the event loop, it just succeeds
        # instantly).
        await communicator.receive_output()
        # Send disconnect at the same time that response finishes (this just
        # puts some info in a queue, it doesn't have to yield to the event
        # loop).
        await communicator.send_input({"type": "http.disconnect"})
        # Waiting for the communicator _does_ yield to the event loop, since
        # ASGIHandler.send_response() is still waiting to do response.close().
        # It so happens that there are enough remaining yield points in both
        # tasks that they both finish while the loop is running.
        await communicator.wait()

    async def test_disconnect_with_body(self):
        """

        Test that an ASGI application correctly handles a disconnect event when a request body has been sent.

        This test verifies that the application raises an asyncio.TimeoutError when a disconnect event is received after
        sending a request body. This ensures that the application properly handles disconnections and timeouts in
        conjunction with request bodies, preventing potential issues with request processing and resource management.

        """
        application = get_asgi_application()
        scope = self.async_request_factory._base_scope(path="/")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request", "body": b"some body"})
        await communicator.send_input({"type": "http.disconnect"})
        with self.assertRaises(asyncio.TimeoutError):
            await communicator.receive_output()

    async def test_assert_in_listen_for_disconnect(self):
        application = get_asgi_application()
        scope = self.async_request_factory._base_scope(path="/")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        await communicator.send_input({"type": "http.not_a_real_message"})
        msg = "Invalid ASGI message after request body: http.not_a_real_message"
        with self.assertRaisesMessage(AssertionError, msg):
            await communicator.wait()

    async def test_delayed_disconnect_with_body(self):
        """
        Tests that a server handles a delayed disconnect with a request body correctly, ensuring it raises an asyncio.TimeoutError when attempting to receive output after the client has disconnected.
        """
        application = get_asgi_application()
        scope = self.async_request_factory._base_scope(path="/delayed_hello/")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request", "body": b"some body"})
        await communicator.send_input({"type": "http.disconnect"})
        with self.assertRaises(asyncio.TimeoutError):
            await communicator.receive_output()

    async def test_wrong_connection_type(self):
        """
        Tests the behavior of the application when a wrong connection type is provided.

        Verifies that attempting to establish a connection with a type other than ASGI/HTTP
        results in a ValueError being raised, as Django only supports ASGI/HTTP connections.

        The expected error message is 'Django can only handle ASGI/HTTP connections, not other.'
        """
        application = get_asgi_application()
        scope = self.async_request_factory._base_scope(path="/", type="other")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        msg = "Django can only handle ASGI/HTTP connections, not other."
        with self.assertRaisesMessage(ValueError, msg):
            await communicator.receive_output()

    async def test_non_unicode_query_string(self):
        application = get_asgi_application()
        scope = self.async_request_factory._base_scope(path="/", query_string=b"\xff")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        response_start = await communicator.receive_output()
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 400)
        response_body = await communicator.receive_output()
        self.assertEqual(response_body["type"], "http.response.body")
        self.assertEqual(response_body["body"], b"")

    async def test_request_lifecycle_signals_dispatched_with_thread_sensitive(self):
        # Track request_started and request_finished signals.
        """
        Tests whether the request lifecycle signals are dispatched properly with thread sensitivity.

        This test case verifies that the request_started and request_finished signals are 
        sent during the lifecycle of an ASGI request. It checks that these signals are 
        dispatched from the same thread and that the correct number of signals are sent.

        The test simulates an HTTP request, sending the request and receiving the response, 
        then verifies that the expected signals were dispatched. It ensures that the 
        request_started signal is sent before the response is generated and that the 
        request_finished signal is sent after the response has been sent.

        It also checks that the thread on which the request_started and request_finished 
        signals are dispatched is the same, which is an important aspect of thread 
        sensitivity in the ASGI request lifecycle. 

        This test case provides a way to validate the correct functioning of the signal 
        dispatching mechanism in the context of ASGI requests.
        """
        signal_handler = SignalHandler()
        request_started.connect(signal_handler)
        self.addCleanup(request_started.disconnect, signal_handler)
        request_finished.connect(signal_handler)
        self.addCleanup(request_finished.disconnect, signal_handler)

        # Perform a basic request.
        application = get_asgi_application()
        scope = self.async_request_factory._base_scope(path="/")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        response_start = await communicator.receive_output()
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 200)
        response_body = await communicator.receive_output()
        self.assertEqual(response_body["type"], "http.response.body")
        self.assertEqual(response_body["body"], b"Hello World!")
        # Give response.close() time to finish.
        await communicator.wait()

        # AsyncToSync should have executed the signals in the same thread.
        self.assertEqual(len(signal_handler.calls), 2)
        request_started_call, request_finished_call = signal_handler.calls
        self.assertEqual(
            request_started_call["thread"], request_finished_call["thread"]
        )

    async def test_concurrent_async_uses_multiple_thread_pools(self):
        """

        Tests that concurrent asynchronous requests utilize multiple thread pools.

        This function sends two concurrent HTTP requests to an ASGI application and verifies 
        that the requests are handled by separate thread pools. The test ensures that each 
        request receives a successful response with the expected status code and response body.

        The test uses the ApplicationCommunicator to send and receive messages to the ASGI 
        application, and checks that the response messages have the correct type and content.

        Finally, the test verifies that two separate threads were used to handle the requests, 
        by checking the length of the active threads list.

        """
        sync_waiter.active_threads.clear()

        # Send 2 requests concurrently
        application = get_asgi_application()
        scope = self.async_request_factory._base_scope(path="/wait/")
        communicators = []
        for _ in range(2):
            communicators.append(ApplicationCommunicator(application, scope))
            await communicators[-1].send_input({"type": "http.request"})

        # Each request must complete with a status code of 200
        # If requests aren't scheduled concurrently, the barrier in the
        # sync_wait view will time out, resulting in a 500 status code.
        for communicator in communicators:
            response_start = await communicator.receive_output()
            self.assertEqual(response_start["type"], "http.response.start")
            self.assertEqual(response_start["status"], 200)
            response_body = await communicator.receive_output()
            self.assertEqual(response_body["type"], "http.response.body")
            self.assertEqual(response_body["body"], b"Hello World!")
            # Give response.close() time to finish.
            await communicator.wait()

        # The requests should have scheduled on different threads. Note
        # active_threads is a set (a thread can only appear once), therefore
        # length is a sufficient check.
        self.assertEqual(len(sync_waiter.active_threads), 2)

        sync_waiter.active_threads.clear()

    async def test_asyncio_cancel_error(self):
        """
        Tests the asyncio cancel error behavior in an ASGI application.

        This test case covers the scenario where an asynchronous view is cancelled
        due to a client disconnect. It verifies that the view's `asyncio.CancelledError`
        exception is properly raised and handled, and that the request is terminated
        correctly. Additionally, it checks that the signal handler is called with the
        correct arguments and from a different thread.

        The test consists of two parts: the first part tests a successful request where
        the view completes without cancellation, and the second part tests a cancelled
        request where the client disconnects before the view completes.
        """
        view_started = asyncio.Event()
        # Flag to check if the view was cancelled.
        view_did_cancel = False
        # Track request_finished signal.
        signal_handler = SignalHandler()
        request_finished.connect(signal_handler)
        self.addCleanup(request_finished.disconnect, signal_handler)

        # A view that will listen for the cancelled error.
        async def view(request):
            nonlocal view_started, view_did_cancel
            view_started.set()
            try:
                await asyncio.sleep(0.1)
                return HttpResponse("Hello World!")
            except asyncio.CancelledError:
                # Set the flag.
                view_did_cancel = True
                raise

        # Request class to use the view.
        class TestASGIRequest(ASGIRequest):
            urlconf = (path("cancel/", view),)

        # Handler to use request class.
        class TestASGIHandler(ASGIHandler):
            request_class = TestASGIRequest

        # Request cycle should complete since no disconnect was sent.
        application = TestASGIHandler()
        scope = self.async_request_factory._base_scope(path="/cancel/")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        response_start = await communicator.receive_output()
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 200)
        response_body = await communicator.receive_output()
        self.assertEqual(response_body["type"], "http.response.body")
        self.assertEqual(response_body["body"], b"Hello World!")
        # Give response.close() time to finish.
        await communicator.wait()
        self.assertIs(view_did_cancel, False)
        # Exactly one call to request_finished handler.
        self.assertEqual(len(signal_handler.calls), 1)
        handler_call = signal_handler.calls.pop()
        # It was NOT on the async thread.
        self.assertNotEqual(handler_call["thread"], threading.current_thread())
        # The signal sender is the handler class.
        self.assertEqual(handler_call["kwargs"], {"sender": TestASGIHandler})
        view_started.clear()

        # Request cycle with a disconnect before the view can respond.
        application = TestASGIHandler()
        scope = self.async_request_factory._base_scope(path="/cancel/")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        # Let the view actually start.
        await view_started.wait()
        # Disconnect the client.
        await communicator.send_input({"type": "http.disconnect"})
        # The handler should not send a response.
        with self.assertRaises(asyncio.TimeoutError):
            await communicator.receive_output()
        await communicator.wait()
        self.assertIs(view_did_cancel, True)
        # Exactly one call to request_finished handler.
        self.assertEqual(len(signal_handler.calls), 1)
        handler_call = signal_handler.calls.pop()
        # It was NOT on the async thread.
        self.assertNotEqual(handler_call["thread"], threading.current_thread())
        # The signal sender is the handler class.
        self.assertEqual(handler_call["kwargs"], {"sender": TestASGIHandler})

    async def test_asyncio_streaming_cancel_error(self):
        # Similar to test_asyncio_cancel_error(), but during a streaming
        # response.
        """
        Tests the cancellation of an asynchronous streaming response by an HTTP disconnect request.

        The test checks two scenarios:

        1. A successful streaming response where the client receives the full response body.
        2. An interrupted streaming response where the client disconnects before receiving the full response body, triggering a `asyncio.CancelledError` exception.

        Verifies that in both cases the `view_did_cancel` flag is updated correctly, the request finished signal is fired with the correct sender, and the signal handler is called with the expected arguments.
        """
        view_did_cancel = False
        # Track request_finished signals.
        signal_handler = SignalHandler()
        request_finished.connect(signal_handler)
        self.addCleanup(request_finished.disconnect, signal_handler)

        async def streaming_response():
            """
            Return a streaming response that yields a simple message.

            This function is designed to be used in asynchronous contexts, providing a basic
            example of how to generate a stream of data. The response will pause for a short
            period of time before yielding the message 'Hello World!' as a bytes object.

            In the event that the operation is cancelled, the function will set an internal
            flag to indicate that cancellation occurred and then re-raise the cancellation
            exception to propagate the error to the caller.

            The returned response can be used directly in asynchronous views or other
            contexts that support streaming data, providing a simple way to test or
            demonstrate streaming functionality. 
            """
            nonlocal view_did_cancel
            try:
                await asyncio.sleep(0.2)
                yield b"Hello World!"
            except asyncio.CancelledError:
                # Set the flag.
                view_did_cancel = True
                raise

        async def view(request):
            return StreamingHttpResponse(streaming_response())

        class TestASGIRequest(ASGIRequest):
            urlconf = (path("cancel/", view),)

        class TestASGIHandler(ASGIHandler):
            request_class = TestASGIRequest

        # With no disconnect, the request cycle should complete in the same
        # manner as the non-streaming response.
        application = TestASGIHandler()
        scope = self.async_request_factory._base_scope(path="/cancel/")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        response_start = await communicator.receive_output()
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 200)
        response_body = await communicator.receive_output()
        self.assertEqual(response_body["type"], "http.response.body")
        self.assertEqual(response_body["body"], b"Hello World!")
        await communicator.wait()
        self.assertIs(view_did_cancel, False)
        # Exactly one call to request_finished handler.
        self.assertEqual(len(signal_handler.calls), 1)
        handler_call = signal_handler.calls.pop()
        # It was NOT on the async thread.
        self.assertNotEqual(handler_call["thread"], threading.current_thread())
        # The signal sender is the handler class.
        self.assertEqual(handler_call["kwargs"], {"sender": TestASGIHandler})

        # Request cycle with a disconnect.
        application = TestASGIHandler()
        scope = self.async_request_factory._base_scope(path="/cancel/")
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        response_start = await communicator.receive_output()
        # Fetch the start of response so streaming can begin
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 200)
        await asyncio.sleep(0.1)
        # Now disconnect the client.
        await communicator.send_input({"type": "http.disconnect"})
        # This time the handler should not send a response.
        with self.assertRaises(asyncio.TimeoutError):
            await communicator.receive_output()
        await communicator.wait()
        self.assertIs(view_did_cancel, True)
        # Exactly one call to request_finished handler.
        self.assertEqual(len(signal_handler.calls), 1)
        handler_call = signal_handler.calls.pop()
        # It was NOT on the async thread.
        self.assertNotEqual(handler_call["thread"], threading.current_thread())
        # The signal sender is the handler class.
        self.assertEqual(handler_call["kwargs"], {"sender": TestASGIHandler})

    async def test_streaming(self):
        """

        Tests the streaming functionality of the application.

        This test case simulates an HTTP request to the '/streaming/' endpoint with a query string parameter 'sleep=0.001'.
        It then verifies that the application sends a streaming response in the correct order, with the expected body content.
        The test checks for the receipt of two messages, 'first' and 'last', followed by a timeout, indicating the end of the stream.

        """
        scope = self.async_request_factory._base_scope(
            path="/streaming/", query_string=b"sleep=0.001"
        )
        application = get_asgi_application()
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        # Fetch http.response.start.
        await communicator.receive_output(timeout=1)
        # Fetch the 'first' and 'last'.
        first_response = await communicator.receive_output(timeout=1)
        self.assertEqual(first_response["body"], b"first\n")
        second_response = await communicator.receive_output(timeout=1)
        self.assertEqual(second_response["body"], b"last\n")
        # Fetch the rest of the response so that coroutines are cleaned up.
        await communicator.receive_output(timeout=1)
        with self.assertRaises(asyncio.TimeoutError):
            await communicator.receive_output(timeout=1)

    async def test_streaming_disconnect(self):
        """

        Tests the disconnection of a streaming request.

        This test case simulates a streaming request and verifies that the connection is properly closed when a disconnect message is sent.
        It checks that the server sends the initial response and then closes the connection after receiving the disconnect message.
        The test uses the ASGI application and a communicator to send and receive messages, and it asserts that the expected responses are received and that the connection is closed as expected.

        :raises: AssertionError if the test fails

        """
        scope = self.async_request_factory._base_scope(
            path="/streaming/", query_string=b"sleep=0.1"
        )
        application = get_asgi_application()
        communicator = ApplicationCommunicator(application, scope)
        await communicator.send_input({"type": "http.request"})
        await communicator.receive_output(timeout=1)
        first_response = await communicator.receive_output(timeout=1)
        self.assertEqual(first_response["body"], b"first\n")
        # Disconnect the client.
        await communicator.send_input({"type": "http.disconnect"})
        # 'last\n' isn't sent.
        with self.assertRaises(asyncio.TimeoutError):
            await communicator.receive_output(timeout=0.2)
