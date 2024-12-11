import sys
import traceback
from io import BytesIO
from unittest import TestCase, mock
from wsgiref import simple_server

from django.core.servers.basehttp import get_internal_wsgi_application
from django.core.signals import request_finished
from django.test import RequestFactory, override_settings

from .views import FILE_RESPONSE_HOLDER

# If data is too large, socket will choke, so write chunks no larger than 32MB
# at a time. The rationale behind the 32MB can be found in #5596#comment:4.
MAX_SOCKET_CHUNK_SIZE = 32 * 1024 * 1024  # 32 MB


class ServerHandler(simple_server.ServerHandler):
    error_status = "500 INTERNAL SERVER ERROR"

    def write(self, data):
        """'write()' callable as specified by PEP 3333"""

        assert isinstance(data, bytes), "write() argument must be bytestring"

        if not self.status:
            raise AssertionError("write() before start_response()")

        elif not self.headers_sent:
            # Before the first output, send the stored headers
            self.bytes_sent = len(data)  # make sure we know content-length
            self.send_headers()
        else:
            self.bytes_sent += len(data)

        # XXX check Content-Length and truncate if too many bytes written?
        data = BytesIO(data)
        for chunk in iter(lambda: data.read(MAX_SOCKET_CHUNK_SIZE), b""):
            self._write(chunk)
            self._flush()

    def error_output(self, environ, start_response):
        """
        Generates an error response, including the traceback information for the current exception.

        This method extends the error handling behavior of its parent class by appending the formatted exception traceback to the response output. The resulting error message provides detailed information about the exception that occurred, including the type, value, and stack trace, which can be useful for debugging purposes.

        :param environ: The WSGI environment dictionary.
        :param start_response: The WSGI start response callable.
        :return: A list containing the formatted exception traceback as a string, terminated by a newline character.

        """
        super().error_output(environ, start_response)
        return ["\n".join(traceback.format_exception(*sys.exc_info()))]


class DummyHandler:
    def log_request(self, *args, **kwargs):
        pass


class FileWrapperHandler(ServerHandler):
    def __init__(self, *args, **kwargs):
        """
        Initializes the object.

        This constructor sets up the basic state of the object, calling the parent class's 
        initializer and establishing a request handler. It also tracks whether the sendfile 
        method has been used.

        :param args: Variable number of non-keyword arguments to be passed to the parent class
        :param kwargs: Variable number of keyword arguments to be passed to the parent class
        """
        super().__init__(*args, **kwargs)
        self.request_handler = DummyHandler()
        self._used_sendfile = False

    def sendfile(self):
        self._used_sendfile = True
        return True


def wsgi_app(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"Hello World!"]


def wsgi_app_file_wrapper(environ, start_response):
    """

    Handles serving a file wrapped in a WSGI-compatible response.

    This function acts as a wrapper for serving a file through a WSGI interface,
    utilizing the provided environment to construct a proper response. The
    file wrapper is typically provided by the WSGI server implementation and is
    used to manage the file serving process.

    Accepts a standard WSGI environment dictionary and a start response callable.
    Returns a file wrapper object containing the served content, in this case,
    a simple text/plain response containing 'foo'.

    Use this function to create a simple, WSGI-compliant file server that can be
    integrated into a larger application or framework.

    """
    start_response("200 OK", [("Content-Type", "text/plain")])
    return environ["wsgi.file_wrapper"](BytesIO(b"foo"))


class WSGIFileWrapperTests(TestCase):
    """
    The wsgi.file_wrapper works for the builtin server.

    Tests for #9659: wsgi.file_wrapper in the builtin server.
    We need to mock a couple of handlers and keep track of what
    gets called when using a couple kinds of WSGI apps.
    """

    def test_file_wrapper_uses_sendfile(self):
        """
        Tests if the file wrapper component of the WSGI application uses the sendfile system call when handling a file request.

        This test case evaluates the behavior of the WSGI application under an HTTP/1.0 protocol environment, verifying that sendfile is utilized during the execution of the test application, and confirms that no output is generated on the standard output and standard error streams.
        """
        env = {"SERVER_PROTOCOL": "HTTP/1.0"}
        handler = FileWrapperHandler(BytesIO(), BytesIO(), BytesIO(), env)
        handler.run(wsgi_app_file_wrapper)
        self.assertTrue(handler._used_sendfile)
        self.assertEqual(handler.stdout.getvalue(), b"")
        self.assertEqual(handler.stderr.getvalue(), b"")

    def test_file_wrapper_no_sendfile(self):
        """

        Tests the FileWrapperHandler functionality when the sendfile operation is not utilized.

        This test case simulates a scenario where the server protocol is HTTP/1.0 and verifies that 
        the handler does not use the sendfile method. It also checks the correctness of the output 
        by comparing the last line of the standard output with the expected 'Hello World!' message 
        and ensures that there are no error messages in the standard error output.

        """
        env = {"SERVER_PROTOCOL": "HTTP/1.0"}
        handler = FileWrapperHandler(BytesIO(), BytesIO(), BytesIO(), env)
        handler.run(wsgi_app)
        self.assertFalse(handler._used_sendfile)
        self.assertEqual(handler.stdout.getvalue().splitlines()[-1], b"Hello World!")
        self.assertEqual(handler.stderr.getvalue(), b"")

    @override_settings(ROOT_URLCONF="builtin_server.urls")
    def test_file_response_closing(self):
        """
        View returning a FileResponse properly closes the file and http
        response when file_wrapper is used.
        """
        env = RequestFactory().get("/fileresponse/").environ
        handler = FileWrapperHandler(BytesIO(), BytesIO(), BytesIO(), env)
        handler.run(get_internal_wsgi_application())
        # Sendfile is used only when file_wrapper has been used.
        self.assertTrue(handler._used_sendfile)
        # Fetch the original response object.
        self.assertIn("response", FILE_RESPONSE_HOLDER)
        response = FILE_RESPONSE_HOLDER["response"]
        # The response and file buffers are closed.
        self.assertIs(response.closed, True)
        buf1, buf2 = FILE_RESPONSE_HOLDER["buffers"]
        self.assertIs(buf1.closed, True)
        self.assertIs(buf2.closed, True)
        FILE_RESPONSE_HOLDER.clear()

    @override_settings(ROOT_URLCONF="builtin_server.urls")
    def test_file_response_call_request_finished(self):
        """
        Tests that the file response handlers correctly send a signal when a request is finished, 
        verifying that the request_finished signal is emitted once during the handling of a file response request.
        """
        env = RequestFactory().get("/fileresponse/").environ
        handler = FileWrapperHandler(BytesIO(), BytesIO(), BytesIO(), env)
        with mock.MagicMock() as signal_handler:
            request_finished.connect(signal_handler)
            handler.run(get_internal_wsgi_application())
            self.assertEqual(signal_handler.call_count, 1)


class WriteChunkCounterHandler(ServerHandler):
    """
    Server handler that counts the number of chunks written after headers were
    sent. Used to make sure large response body chunking works properly.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes a new instance of the class.

        This method is responsible for setting up the internal state of the object, 
        including the request handler and tracking variables for headers and chunk writing.
        It takes any number of positional and keyword arguments, which are passed to the 
        parent class's initializer.

        The object's request handler is set to a DummyHandler instance by default.
        Additionally, flags are initialized to track whether headers have been written 
        and the number of chunks that have been written.\"\"\"

        """
        super().__init__(*args, **kwargs)
        self.request_handler = DummyHandler()
        self.headers_written = False
        self.write_chunk_counter = 0

    def send_headers(self):
        """
        Sends HTTP headers to the client and marks them as written.

        This method extends the base class functionality by also setting a flag to indicate that headers have been sent. 

        Once this method is called, it is assumed that the headers are transmitted and cannot be modified or sent again.

        """
        super().send_headers()
        self.headers_written = True

    def _write(self, data):
        """
        Writes data to the standard output.

        If headers have already been written, increments the chunk counter before writing the data.
        The actual writing operation is performed using the stdout interface, which sends the data to the standard output stream.

        :raises: None
        :returns: None
        """
        if self.headers_written:
            self.write_chunk_counter += 1
        self.stdout.write(data)


def send_big_data_app(environ, start_response):
    """
    Sends a large amount of data in response to an HTTP request.

    This function generates a response with a 200 OK status code and a Content-Type of text/plain.
    It returns a single chunk of data, consisting of a repeated character ('x'), with a size that exceeds the maximum socket chunk size by half of the maximum chunk size.
    This is typically used for testing purposes, such as verifying the HTTP server's ability to handle large responses.
    """
    start_response("200 OK", [("Content-Type", "text/plain")])
    # Return a blob of data that is 1.5 times the maximum chunk size.
    return [b"x" * (MAX_SOCKET_CHUNK_SIZE + MAX_SOCKET_CHUNK_SIZE // 2)]


class ServerHandlerChunksProperly(TestCase):
    """
    The ServerHandler chunks data properly.

    Tests for #18972: The logic that performs the math to break data into
    32MB (MAX_SOCKET_CHUNK_SIZE) chunks was flawed, BUT it didn't actually
    cause any problems.
    """

    def test_chunked_data(self):
        """

        Test that chunked data is properly handled by verifying the write chunk counter.

        This test case simulates an HTTP/1.0 request and sends a large amount of data
        using the send_big_data_app function. It then asserts that the write chunk
        counter is correctly incremented, indicating that the data was successfully
        chunked and written.

        Parameters: None
        Returns: None
        Raises: AssertionError if the write chunk counter does not match the expected value.

        """
        env = {"SERVER_PROTOCOL": "HTTP/1.0"}
        handler = WriteChunkCounterHandler(None, BytesIO(), BytesIO(), env)
        handler.run(send_big_data_app)
        self.assertEqual(handler.write_chunk_counter, 2)
