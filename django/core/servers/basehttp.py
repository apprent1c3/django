"""
HTTP server that implements the Python WSGI protocol (PEP 333, rev 1.21).

Based on wsgiref.simple_server which is part of the standard library since 2.5.

This is a simple server for use in testing or debugging Django apps. It hasn't
been reviewed for security issues. DON'T USE IT FOR PRODUCTION USE!
"""

import logging
import socket
import socketserver
import sys
from collections import deque
from wsgiref import simple_server

from django.core.exceptions import ImproperlyConfigured
from django.core.handlers.wsgi import LimitedStream
from django.core.wsgi import get_wsgi_application
from django.db import connections
from django.utils.module_loading import import_string

__all__ = ("WSGIServer", "WSGIRequestHandler")

logger = logging.getLogger("django.server")


def get_internal_wsgi_application():
    """

    Loads and returns the WSGI application configured by the user in settings.

    This function is used by Django's internal server and returns the application object
    specified in settings.WSGI_APPLICATION, or the default application if the setting is not configured.

    """
    from django.conf import settings

    app_path = getattr(settings, "WSGI_APPLICATION")
    if app_path is None:
        return get_wsgi_application()

    try:
        return import_string(app_path)
    except ImportError as err:
        raise ImproperlyConfigured(
            "WSGI application '%s' could not be loaded; "
            "Error importing module." % app_path
        ) from err


def is_broken_pipe_error():
    exc_type, _, _ = sys.exc_info()
    return issubclass(
        exc_type,
        (
            BrokenPipeError,
            ConnectionAbortedError,
            ConnectionResetError,
        ),
    )


class WSGIServer(simple_server.WSGIServer):
    """BaseHTTPServer that implements the Python WSGI protocol"""

    request_queue_size = 10

    def __init__(self, *args, ipv6=False, allow_reuse_address=True, **kwargs):
        if ipv6:
            self.address_family = socket.AF_INET6
        self.allow_reuse_address = allow_reuse_address
        super().__init__(*args, **kwargs)

    def handle_error(self, request, client_address):
        if is_broken_pipe_error():
            logger.info("- Broken pipe from %s", client_address)
        else:
            super().handle_error(request, client_address)


class ThreadedWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
    """A threaded version of the WSGIServer"""

    daemon_threads = True

    def __init__(self, *args, connections_override=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.connections_override = connections_override

    # socketserver.ThreadingMixIn.process_request() passes this method as
    # the target to a new Thread object.
    def process_request_thread(self, request, client_address):
        if self.connections_override:
            # Override this thread's database connections with the ones
            # provided by the parent thread.
            for alias, conn in self.connections_override.items():
                connections[alias] = conn
        super().process_request_thread(request, client_address)

    def _close_connections(self):
        # Used for mocking in tests.
        connections.close_all()

    def close_request(self, request):
        self._close_connections()
        super().close_request(request)


class ServerHandler(simple_server.ServerHandler):
    http_version = "1.1"

    def __init__(self, stdin, stdout, stderr, environ, **kwargs):
        """
        Initializes a WSGI request object, using a LimitedStream to handle request data and prevent unread data from being discarded, specifically designed for use with the test server or runserver.
        """
        try:
            content_length = int(environ.get("CONTENT_LENGTH"))
        except (ValueError, TypeError):
            content_length = 0
        super().__init__(
            LimitedStream(stdin, content_length), stdout, stderr, environ, **kwargs
        )

    def cleanup_headers(self):
        """
        Adjusts HTTP response headers based on the request method and connection handling.

        This function ensures proper handling of 'Content-Length' and 'Connection' headers
        for HTTP HEAD requests and requests where connection closing is required.

        It also updates the request handler to close the connection if necessary.
        """
        super().cleanup_headers()
        if (
            self.environ["REQUEST_METHOD"] == "HEAD"
            and "Content-Length" in self.headers
            and str(self.headers["Content-Length"]) == "0"
        ):
            del self.headers["Content-Length"]
        # HTTP/1.1 requires support for persistent connections. Send 'close' if
        # the content length is unknown to prevent clients from reusing the
        # connection.
        if (
            self.environ["REQUEST_METHOD"] != "HEAD"
            and "Content-Length" not in self.headers
        ):
            self.headers["Connection"] = "close"
        # Persistent connections require threading server.
        elif not isinstance(self.request_handler.server, socketserver.ThreadingMixIn):
            self.headers["Connection"] = "close"
        # Mark the connection for closing if it's set as such above or if the
        # application sent the header.
        if self.headers.get("Connection") == "close":
            self.request_handler.close_connection = True

    def close(self):
        self.get_stdin().read()
        super().close()

    def finish_response(self):
        """
        Finishes the HTTP response, handling the specific case where the request method is 'HEAD'. In such cases, it discards the response body, sends the headers if not already sent, and closes the connection. For other request methods, it delegates to the parent class implementation.
        """
        if self.environ["REQUEST_METHOD"] == "HEAD":
            try:
                deque(self.result, maxlen=0)  # Consume iterator.
                # Don't call self.finish_content() as, if the headers have not
                # been sent and Content-Length isn't set, it'll default to "0"
                # which will prevent omission of the Content-Length header with
                # HEAD requests as permitted by RFC 9110 Section 9.3.2.
                # Instead, send the headers, if not sent yet.
                if not self.headers_sent:
                    self.send_headers()
            finally:
                self.close()
        else:
            super().finish_response()


class WSGIRequestHandler(simple_server.WSGIRequestHandler):
    protocol_version = "HTTP/1.1"

    def address_string(self):
        # Short-circuit parent method to not call socket.getfqdn
        return self.client_address[0]

    def log_message(self, format, *args):
        """
        Logs a message with the given format and arguments, adding extra context including the current request and server time.

        The log level is determined based on the HTTP status code, if present, with error levels for 500+, warning for 400+, and info otherwise.

        Optional extra handling is performed when accessing the development server over HTTPS, which is not supported and will be logged as an error with a 500 status code.
        """
        extra = {
            "request": self.request,
            "server_time": self.log_date_time_string(),
        }
        if args[1][0] == "4":
            # 0x16 = Handshake, 0x03 = SSL 3.0 or TLS 1.x
            if args[0].startswith("\x16\x03"):
                extra["status_code"] = 500
                logger.error(
                    "You're accessing the development server over HTTPS, but "
                    "it only supports HTTP.",
                    extra=extra,
                )
                return

        if args[1].isdigit() and len(args[1]) == 3:
            status_code = int(args[1])
            extra["status_code"] = status_code

            if status_code >= 500:
                level = logger.error
            elif status_code >= 400:
                level = logger.warning
            else:
                level = logger.info
        else:
            level = logger.info

        level(format, *args, extra=extra)

    def get_environ(self):
        # Strip all headers with underscores in the name before constructing
        # the WSGI environ. This prevents header-spoofing based on ambiguity
        # between underscores and dashes both normalized to underscores in WSGI
        # env vars. Nginx and Apache 2.4+ both do this as well.
        for k in self.headers:
            if "_" in k:
                del self.headers[k]

        return super().get_environ()

    def handle(self):
        """
        Handles incoming HTTP requests on a connection, processing requests until 
        the connection is closed. Once all requests have been handled, the connection 
        is shut down to prevent further communication.
        """
        self.close_connection = True
        self.handle_one_request()
        while not self.close_connection:
            self.handle_one_request()
        try:
            self.connection.shutdown(socket.SHUT_WR)
        except (AttributeError, OSError):
            pass

    def handle_one_request(self):
        """
        Handles a single HTTP request, reading the request line, parsing the request, and invoking the request handler to process the request and send a response back to the client.
        """
        self.raw_requestline = self.rfile.readline(65537)
        if len(self.raw_requestline) > 65536:
            self.requestline = ""
            self.request_version = ""
            self.command = ""
            self.send_error(414)
            return

        if not self.parse_request():  # An error code has been sent, just exit
            return

        handler = ServerHandler(
            self.rfile, self.wfile, self.get_stderr(), self.get_environ()
        )
        handler.request_handler = self  # backpointer for logging & connection closing
        handler.run(self.server.get_app())


def run(
    addr,
    port,
    wsgi_handler,
    ipv6=False,
    threading=False,
    on_bind=None,
    server_cls=WSGIServer,
):
    """

    Run a WSGI server.

    This function creates and starts a WSGI server, listening on the specified address and port.
    It supports optional features such as IPv6, threading, and custom server classes.

    Parameters
    ----------
    addr : str
        The address to bind the server to.
    port : int
        The port to bind the server to.
    wsgi_handler : callable
        The WSGI application to handle requests.
    ipv6 : bool, optional
        Whether to use IPv6 (default is False).
    threading : bool, optional
        Whether to use threading (default is False).
    on_bind : callable, optional
        A callback function to call when the server is bound.
    server_cls : class, optional
        The server class to use (default is WSGIServer).

    Note
    ----
    The server will run indefinitely until it is manually stopped.

    """
    server_address = (addr, port)
    if threading:
        httpd_cls = type("WSGIServer", (socketserver.ThreadingMixIn, server_cls), {})
    else:
        httpd_cls = server_cls
    httpd = httpd_cls(server_address, WSGIRequestHandler, ipv6=ipv6)
    if on_bind is not None:
        on_bind(getattr(httpd, "server_port", port))
    if threading:
        # ThreadingMixIn.daemon_threads indicates how threads will behave on an
        # abrupt shutdown; like quitting the server by the user or restarting
        # by the auto-reloader. True means the server will not wait for thread
        # termination before it quits. This will make auto-reloader faster
        # and will prevent the need to kill the server manually if a thread
        # isn't terminating correctly.
        httpd.daemon_threads = True
    httpd.set_app(wsgi_handler)
    httpd.serve_forever()
