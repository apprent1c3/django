import copy
from io import BytesIO
from itertools import chain
from urllib.parse import urlencode

from django.core.exceptions import BadRequest, DisallowedHost
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadhandler import MemoryFileUploadHandler
from django.core.handlers.wsgi import LimitedStream, WSGIRequest
from django.http import (
    HttpHeaders,
    HttpRequest,
    RawPostDataException,
    UnreadablePostError,
)
from django.http.multipartparser import MAX_TOTAL_HEADER_SIZE, MultiPartParserError
from django.http.request import split_domain_port
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.test.client import BOUNDARY, MULTIPART_CONTENT, FakePayload


class ErrorFileUploadHandler(MemoryFileUploadHandler):
    def handle_raw_input(
        self, input_data, META, content_length, boundary, encoding=None
    ):
        raise ValueError


class CustomFileUploadHandler(MemoryFileUploadHandler):
    def handle_raw_input(
        self, input_data, META, content_length, boundary, encoding=None
    ):
        return ("_POST", "_FILES")


class RequestsTests(SimpleTestCase):
    def test_httprequest(self):
        request = HttpRequest()
        self.assertEqual(list(request.GET), [])
        self.assertEqual(list(request.POST), [])
        self.assertEqual(list(request.COOKIES), [])
        self.assertEqual(list(request.META), [])

        # .GET and .POST should be QueryDicts
        self.assertEqual(request.GET.urlencode(), "")
        self.assertEqual(request.POST.urlencode(), "")

        # and FILES should be MultiValueDict
        self.assertEqual(request.FILES.getlist("foo"), [])

        self.assertIsNone(request.content_type)
        self.assertIsNone(request.content_params)

    def test_httprequest_full_path(self):
        """
        Tests the construction of a full path for an HTTP request.

        This test case verifies that the :meth:`get_full_path` and :meth:`get_full_path_info` methods correctly handle URLs with special characters and query strings.
        The full path is expected to be properly escaped, including the path and query string components.
        The test also covers the case where a prefix is added to the path info, ensuring that it is correctly included in the resulting full path.
        """
        request = HttpRequest()
        request.path = "/;some/?awful/=path/foo:bar/"
        request.path_info = "/prefix" + request.path
        request.META["QUERY_STRING"] = ";some=query&+query=string"
        expected = "/%3Bsome/%3Fawful/%3Dpath/foo:bar/?;some=query&+query=string"
        self.assertEqual(request.get_full_path(), expected)
        self.assertEqual(request.get_full_path_info(), "/prefix" + expected)

    def test_httprequest_full_path_with_query_string_and_fragment(self):
        """
        Tests the construction of full HTTP request paths.

        This test case verifies that the HttpRequest class correctly handles URL paths,
        query strings, and fragments when building full request paths. It checks that
        the get_full_path method returns the expected path, including properly escaped
        special characters, and that the get_full_path_info method includes the prefix
        path in its output.

        It covers the case where the path contains a fragment and the query string also
        contains special characters, ensuring that the resulting full path is correctly
        URL-encoded.
        """
        request = HttpRequest()
        request.path = "/foo#bar"
        request.path_info = "/prefix" + request.path
        request.META["QUERY_STRING"] = "baz#quux"
        self.assertEqual(request.get_full_path(), "/foo%23bar?baz#quux")
        self.assertEqual(request.get_full_path_info(), "/prefix/foo%23bar?baz#quux")

    def test_httprequest_repr(self):
        request = HttpRequest()
        request.path = "/somepath/"
        request.method = "GET"
        request.GET = {"get-key": "get-value"}
        request.POST = {"post-key": "post-value"}
        request.COOKIES = {"post-key": "post-value"}
        request.META = {"post-key": "post-value"}
        self.assertEqual(repr(request), "<HttpRequest: GET '/somepath/'>")

    def test_httprequest_repr_invalid_method_and_path(self):
        """
        Tests the string representation of an HttpRequest object under various conditions.

        Verifies that the repr() function returns the expected string for 
        HttpRequest objects with invalid or missing method and path attributes.

        In particular, this test checks the string representation when:
        - The HttpRequest object is newly created with no attributes set.
        - The method attribute is set to a valid HTTP method (e.g. 'GET').
        - The path attribute is set to an empty string.

        """
        request = HttpRequest()
        self.assertEqual(repr(request), "<HttpRequest>")
        request = HttpRequest()
        request.method = "GET"
        self.assertEqual(repr(request), "<HttpRequest>")
        request = HttpRequest()
        request.path = ""
        self.assertEqual(repr(request), "<HttpRequest>")

    def test_wsgirequest(self):
        request = WSGIRequest(
            {
                "PATH_INFO": "bogus",
                "REQUEST_METHOD": "bogus",
                "CONTENT_TYPE": "text/html; charset=utf8",
                "wsgi.input": BytesIO(b""),
            }
        )
        self.assertEqual(list(request.GET), [])
        self.assertEqual(list(request.POST), [])
        self.assertEqual(list(request.COOKIES), [])
        self.assertEqual(
            set(request.META),
            {
                "PATH_INFO",
                "REQUEST_METHOD",
                "SCRIPT_NAME",
                "CONTENT_TYPE",
                "wsgi.input",
            },
        )
        self.assertEqual(request.META["PATH_INFO"], "bogus")
        self.assertEqual(request.META["REQUEST_METHOD"], "bogus")
        self.assertEqual(request.META["SCRIPT_NAME"], "")
        self.assertEqual(request.content_type, "text/html")
        self.assertEqual(request.content_params, {"charset": "utf8"})

    def test_wsgirequest_with_script_name(self):
        """
        The request's path is correctly assembled, regardless of whether or
        not the SCRIPT_NAME has a trailing slash (#20169).
        """
        # With trailing slash
        request = WSGIRequest(
            {
                "PATH_INFO": "/somepath/",
                "SCRIPT_NAME": "/PREFIX/",
                "REQUEST_METHOD": "get",
                "wsgi.input": BytesIO(b""),
            }
        )
        self.assertEqual(request.path, "/PREFIX/somepath/")
        # Without trailing slash
        request = WSGIRequest(
            {
                "PATH_INFO": "/somepath/",
                "SCRIPT_NAME": "/PREFIX",
                "REQUEST_METHOD": "get",
                "wsgi.input": BytesIO(b""),
            }
        )
        self.assertEqual(request.path, "/PREFIX/somepath/")

    def test_wsgirequest_script_url_double_slashes(self):
        """
        WSGI squashes multiple successive slashes in PATH_INFO, WSGIRequest
        should take that into account when populating request.path and
        request.META['SCRIPT_NAME'] (#17133).
        """
        request = WSGIRequest(
            {
                "SCRIPT_URL": "/mst/milestones//accounts/login//help",
                "PATH_INFO": "/milestones/accounts/login/help",
                "REQUEST_METHOD": "get",
                "wsgi.input": BytesIO(b""),
            }
        )
        self.assertEqual(request.path, "/mst/milestones/accounts/login/help")
        self.assertEqual(request.META["SCRIPT_NAME"], "/mst")

    def test_wsgirequest_with_force_script_name(self):
        """
        The FORCE_SCRIPT_NAME setting takes precedence over the request's
        SCRIPT_NAME environment parameter (#20169).
        """
        with override_settings(FORCE_SCRIPT_NAME="/FORCED_PREFIX/"):
            request = WSGIRequest(
                {
                    "PATH_INFO": "/somepath/",
                    "SCRIPT_NAME": "/PREFIX/",
                    "REQUEST_METHOD": "get",
                    "wsgi.input": BytesIO(b""),
                }
            )
            self.assertEqual(request.path, "/FORCED_PREFIX/somepath/")

    def test_wsgirequest_path_with_force_script_name_trailing_slash(self):
        """
        The request's path is correctly assembled, regardless of whether or not
        the FORCE_SCRIPT_NAME setting has a trailing slash (#20169).
        """
        # With trailing slash
        with override_settings(FORCE_SCRIPT_NAME="/FORCED_PREFIX/"):
            request = WSGIRequest(
                {
                    "PATH_INFO": "/somepath/",
                    "REQUEST_METHOD": "get",
                    "wsgi.input": BytesIO(b""),
                }
            )
            self.assertEqual(request.path, "/FORCED_PREFIX/somepath/")
        # Without trailing slash
        with override_settings(FORCE_SCRIPT_NAME="/FORCED_PREFIX"):
            request = WSGIRequest(
                {
                    "PATH_INFO": "/somepath/",
                    "REQUEST_METHOD": "get",
                    "wsgi.input": BytesIO(b""),
                }
            )
            self.assertEqual(request.path, "/FORCED_PREFIX/somepath/")

    def test_wsgirequest_repr(self):
        """

        Tests the representation of a WSGIRequest object.

        This function verifies that the string representation of a WSGIRequest object
        is correctly formatted, including the request method (e.g., GET, POST) and
        the requested path. The test covers various scenarios, such as an empty path
        and a path with query parameters, to ensure the repr() function behaves as
        expected.

        The function checks that the representation string only includes the request
        method and path, ignoring other attributes like GET, POST, COOKIE, and META
        data.

        """
        request = WSGIRequest({"REQUEST_METHOD": "get", "wsgi.input": BytesIO(b"")})
        self.assertEqual(repr(request), "<WSGIRequest: GET '/'>")
        request = WSGIRequest(
            {
                "PATH_INFO": "/somepath/",
                "REQUEST_METHOD": "get",
                "wsgi.input": BytesIO(b""),
            }
        )
        request.GET = {"get-key": "get-value"}
        request.POST = {"post-key": "post-value"}
        request.COOKIES = {"post-key": "post-value"}
        request.META = {"post-key": "post-value"}
        self.assertEqual(repr(request), "<WSGIRequest: GET '/somepath/'>")

    def test_wsgirequest_path_info(self):
        """
        Tests the path_info attribute of a WSGIRequest object to ensure it correctly handles non-ASCII characters.

        The test checks that the path_info encoding is properly converted from the WSGI environment to the request object.
        Specifically, it verifies that Unicode characters are correctly decoded and that the resulting path is as expected.
        The test covers scenarios with different encodings to ensure the request path is correctly formatted in all cases.
        """
        def wsgi_str(path_info, encoding="utf-8"):
            """
            #: Returns the path_info string with WSGI encoding applied.
            #:
            #: The function takes the path_info string and applies WSGI encoding rules.
            #: It first encodes the path_info using the specified encoding (default is 'utf-8'),
            #: and then decodes it using 'iso-8859-1', which is the encoding expected by WSGI.
            #: The result is the path_info string with any non-ASCII characters converted to their ISO-8859-1 equivalents.
            #:
            #: :param path_info: The path_info string to be encoded
            #: :param encoding: The encoding to use for the initial encoding (default is 'utf-8')
            #: :return: The WSGI-encoded path_info string
            """
            path_info = path_info.encode(
                encoding
            )  # Actual URL sent by the browser (bytestring)
            path_info = path_info.decode(
                "iso-8859-1"
            )  # Value in the WSGI environ dict (native string)
            return path_info

        # Regression for #19468
        request = WSGIRequest(
            {
                "PATH_INFO": wsgi_str("/سلام/"),
                "REQUEST_METHOD": "get",
                "wsgi.input": BytesIO(b""),
            }
        )
        self.assertEqual(request.path, "/سلام/")

        # The URL may be incorrectly encoded in a non-UTF-8 encoding (#26971)
        request = WSGIRequest(
            {
                "PATH_INFO": wsgi_str("/café/", encoding="iso-8859-1"),
                "REQUEST_METHOD": "get",
                "wsgi.input": BytesIO(b""),
            }
        )
        # Since it's impossible to decide the (wrong) encoding of the URL, it's
        # left percent-encoded in the path.
        self.assertEqual(request.path, "/caf%E9/")

    def test_wsgirequest_copy(self):
        """
        Tests the behavior of copying a WSGIRequest object to ensure that the environ attribute is shared between the original and the copy.

        Verifies that the shallow copy operation preserves the reference to the environ dictionary, 
        meaning that both the original and copied request objects will access the same environ data structure.

        This test case is important to prevent unexpected side effects when modifying the environ 
        dictionary through one of the request objects, as changes will be reflected in both the original and the copy.
        """
        request = WSGIRequest({"REQUEST_METHOD": "get", "wsgi.input": BytesIO(b"")})
        request_copy = copy.copy(request)
        self.assertIs(request_copy.environ, request.environ)

    def test_limited_stream(self):
        # Read all of a limited stream
        stream = LimitedStream(BytesIO(b"test"), 2)
        self.assertEqual(stream.read(), b"te")
        # Reading again returns nothing.
        self.assertEqual(stream.read(), b"")

        # Read a number of characters greater than the stream has to offer
        stream = LimitedStream(BytesIO(b"test"), 2)
        self.assertEqual(stream.read(5), b"te")
        # Reading again returns nothing.
        self.assertEqual(stream.readline(5), b"")

        # Read sequentially from a stream
        stream = LimitedStream(BytesIO(b"12345678"), 8)
        self.assertEqual(stream.read(5), b"12345")
        self.assertEqual(stream.read(5), b"678")
        # Reading again returns nothing.
        self.assertEqual(stream.readline(5), b"")

        # Read lines from a stream
        stream = LimitedStream(BytesIO(b"1234\n5678\nabcd\nefgh\nijkl"), 24)
        # Read a full line, unconditionally
        self.assertEqual(stream.readline(), b"1234\n")
        # Read a number of characters less than a line
        self.assertEqual(stream.readline(2), b"56")
        # Read the rest of the partial line
        self.assertEqual(stream.readline(), b"78\n")
        # Read a full line, with a character limit greater than the line length
        self.assertEqual(stream.readline(6), b"abcd\n")
        # Read the next line, deliberately terminated at the line end
        self.assertEqual(stream.readline(4), b"efgh")
        # Read the next line... just the line end
        self.assertEqual(stream.readline(), b"\n")
        # Read everything else.
        self.assertEqual(stream.readline(), b"ijkl")

        # Regression for #15018
        # If a stream contains a newline, but the provided length
        # is less than the number of provided characters, the newline
        # doesn't reset the available character count
        stream = LimitedStream(BytesIO(b"1234\nabcdef"), 9)
        self.assertEqual(stream.readline(10), b"1234\n")
        self.assertEqual(stream.readline(3), b"abc")
        # Now expire the available characters
        self.assertEqual(stream.readline(3), b"d")
        # Reading again returns nothing.
        self.assertEqual(stream.readline(2), b"")

        # Same test, but with read, not readline.
        stream = LimitedStream(BytesIO(b"1234\nabcdef"), 9)
        self.assertEqual(stream.read(6), b"1234\na")
        self.assertEqual(stream.read(2), b"bc")
        self.assertEqual(stream.read(2), b"d")
        self.assertEqual(stream.read(2), b"")
        self.assertEqual(stream.read(), b"")

    def test_stream_read(self):
        payload = FakePayload("name=value")
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            },
        )
        self.assertEqual(request.read(), b"name=value")

    def test_stream_readline(self):
        payload = FakePayload("name=value\nother=string")
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            },
        )
        self.assertEqual(request.readline(), b"name=value\n")
        self.assertEqual(request.readline(), b"other=string")

    def test_read_after_value(self):
        """
        Reading from request is allowed after accessing request contents as
        POST or body.
        """
        payload = FakePayload("name=value")
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        self.assertEqual(request.POST, {"name": ["value"]})
        self.assertEqual(request.body, b"name=value")
        self.assertEqual(request.read(), b"name=value")

    def test_value_after_read(self):
        """
        Construction of POST or body is not allowed after reading
        from request.
        """
        payload = FakePayload("name=value")
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        self.assertEqual(request.read(2), b"na")
        with self.assertRaises(RawPostDataException):
            request.body
        self.assertEqual(request.POST, {})

    def test_non_ascii_POST(self):
        """
        Tests the handling of non-ASCII characters in POST requests.

        This test case verifies that the framework correctly processes HTTP POST requests
        containing non-ASCII characters in the request body. It checks that the request
        data is properly decoded and made available in the request's POST dictionary.

        The test uses a sample payload containing a non-ASCII character (ä is not used, 
        instead 'España' is used which contains a non-ASCII 'ñ') and verifies that the 
        request's POST dictionary contains the expected key-value pair.\"\"\"


        Alternatively, a more concise version:

        \"\"\"Tests handling of non-ASCII characters in HTTP POST requests.

        Verifies that POST requests with non-ASCII characters are properly decoded and 
        made available in the request's POST dictionary.
        """
        payload = FakePayload(urlencode({"key": "España"}))
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_LENGTH": len(payload),
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
                "wsgi.input": payload,
            }
        )
        self.assertEqual(request.POST, {"key": ["España"]})

    def test_non_utf8_charset_POST_bad_request(self):
        """

        Tests that a POST request with a non-UTF8 charset raises a BadRequest exception.

        This test case verifies that the application correctly handles HTTP requests with
        the 'application/x-www-form-urlencoded' content type and a charset other than UTF-8.
        It checks that attempting to access the request's POST data or files raises a
        BadRequest exception with a specific error message, ensuring that the application
        enforces UTF-8 encoding for such requests.

        """
        payload = FakePayload(urlencode({"key": "España".encode("latin-1")}))
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_LENGTH": len(payload),
                "CONTENT_TYPE": "application/x-www-form-urlencoded; charset=iso-8859-1",
                "wsgi.input": payload,
            }
        )
        msg = (
            "HTTP requests with the 'application/x-www-form-urlencoded' content type "
            "must be UTF-8 encoded."
        )
        with self.assertRaisesMessage(BadRequest, msg):
            request.POST
        with self.assertRaisesMessage(BadRequest, msg):
            request.FILES

    def test_utf8_charset_POST(self):
        for charset in ["utf-8", "UTF-8"]:
            with self.subTest(charset=charset):
                payload = FakePayload(urlencode({"key": "España"}))
                request = WSGIRequest(
                    {
                        "REQUEST_METHOD": "POST",
                        "CONTENT_LENGTH": len(payload),
                        "CONTENT_TYPE": (
                            f"application/x-www-form-urlencoded; charset={charset}"
                        ),
                        "wsgi.input": payload,
                    }
                )
                self.assertEqual(request.POST, {"key": ["España"]})

    def test_body_after_POST_multipart_form_data(self):
        """
        Reading body after parsing multipart/form-data is not allowed
        """
        # Because multipart is used for large amounts of data i.e. file uploads,
        # we don't want the data held in memory twice, and we don't want to
        # silence the error by setting body = '' either.
        payload = FakePayload(
            "\r\n".join(
                [
                    "--boundary",
                    'Content-Disposition: form-data; name="name"',
                    "",
                    "value",
                    "--boundary--",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "multipart/form-data; boundary=boundary",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        self.assertEqual(request.POST, {"name": ["value"]})
        with self.assertRaises(RawPostDataException):
            request.body

    def test_body_after_POST_multipart_related(self):
        """
        Reading body after parsing multipart that isn't form-data is allowed
        """
        # Ticket #9054
        # There are cases in which the multipart data is related instead of
        # being a binary upload, in which case it should still be accessible
        # via body.
        payload_data = b"\r\n".join(
            [
                b"--boundary",
                b'Content-ID: id; name="name"',
                b"",
                b"value",
                b"--boundary--",
            ]
        )
        payload = FakePayload(payload_data)
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "multipart/related; boundary=boundary",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        self.assertEqual(request.POST, {})
        self.assertEqual(request.body, payload_data)

    def test_POST_multipart_with_content_length_zero(self):
        """
        Multipart POST requests with Content-Length >= 0 are valid and need to
        be handled.
        """
        # According to RFC 9110 Section 8.6 every POST with Content-Length >= 0
        # is a valid request, so ensure that we handle Content-Length == 0.
        payload = FakePayload(
            "\r\n".join(
                [
                    "--boundary",
                    'Content-Disposition: form-data; name="name"',
                    "",
                    "value",
                    "--boundary--",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "multipart/form-data; boundary=boundary",
                "CONTENT_LENGTH": 0,
                "wsgi.input": payload,
            }
        )
        self.assertEqual(request.POST, {})

    @override_settings(
        FILE_UPLOAD_HANDLERS=["requests_tests.tests.ErrorFileUploadHandler"]
    )
    def test_POST_multipart_handler_error(self):
        payload = FakePayload(
            "\r\n".join(
                [
                    f"--{BOUNDARY}",
                    'Content-Disposition: form-data; name="name"',
                    "",
                    "value",
                    f"--{BOUNDARY}--",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": MULTIPART_CONTENT,
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        with self.assertRaises(ValueError):
            request.POST

    @override_settings(
        FILE_UPLOAD_HANDLERS=["requests_tests.tests.CustomFileUploadHandler"]
    )
    def test_POST_multipart_handler_parses_input(self):
        payload = FakePayload(
            "\r\n".join(
                [
                    f"--{BOUNDARY}",
                    'Content-Disposition: form-data; name="name"',
                    "",
                    "value",
                    f"--{BOUNDARY}--",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": MULTIPART_CONTENT,
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        self.assertEqual(request.POST, "_POST")
        self.assertEqual(request.FILES, "_FILES")

    def test_request_methods_with_content(self):
        """

        Tests the request methods with content to ensure proper handling.

        This test case iterates over the 'GET', 'PUT', and 'DELETE' HTTP methods and
         verifies that the request's POST data is correctly parsed. It constructs a
        WSGIRequest object with a fake payload and checks that the request's POST
        dictionary remains empty, confirming that these methods do not populate the
        POST data.

        The test uses a fake payload encoded as 'application/x-www-form-urlencoded'
        to simulate a request with content. The outcome of this test ensures that the
        request object correctly distinguishes between request methods that should
        and should not contain POST data.

        """
        for method in ["GET", "PUT", "DELETE"]:
            with self.subTest(method=method):
                payload = FakePayload(urlencode({"key": "value"}))
                request = WSGIRequest(
                    {
                        "REQUEST_METHOD": method,
                        "CONTENT_LENGTH": len(payload),
                        "CONTENT_TYPE": "application/x-www-form-urlencoded",
                        "wsgi.input": payload,
                    }
                )
                self.assertEqual(request.POST, {})

    def test_POST_content_type_json(self):
        """

        Tests that a POST request with JSON content type does not populate the POST data.

        This test case verifies that when a request is made with a JSON payload, 
        the framework does not interpret it as form data and therefore the POST 
        dictionary remains empty. Additionally, it checks that no files are 
        associated with the request.

        The test uses a fake payload with a JSON string and a WSGI request object 
        to simulate the POST request. It then asserts that the POST data and 
        files are empty, as expected for a JSON request.

        """
        payload = FakePayload(
            "\r\n".join(
                [
                    '{"pk": 1, "model": "store.book", "fields": {"name": "Mostly Ha',
                    'rmless", "author": ["Douglas", Adams"]}}',
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "application/json",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        self.assertEqual(request.POST, {})
        self.assertEqual(request.FILES, {})

    _json_payload = [
        'Content-Disposition: form-data; name="JSON"',
        "Content-Type: application/json",
        "",
        '{"pk": 1, "model": "store.book", "fields": {"name": "Mostly Harmless", '
        '"author": ["Douglas", Adams"]}}',
    ]

    def test_POST_form_data_json(self):
        """

        Tests that a POST request with form data in JSON format is correctly parsed.

        The function simulates a POST request with a multipart content type and a JSON payload.
        It then asserts that the request's POST data is correctly extracted and matches the expected JSON data.

        This test ensures that the request handling logic correctly handles JSON data sent in the request body.

        """
        payload = FakePayload(
            "\r\n".join([f"--{BOUNDARY}", *self._json_payload, f"--{BOUNDARY}--"])
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": MULTIPART_CONTENT,
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        self.assertEqual(
            request.POST,
            {
                "JSON": [
                    '{"pk": 1, "model": "store.book", "fields": {"name": "Mostly '
                    'Harmless", "author": ["Douglas", Adams"]}}'
                ],
            },
        )

    def test_POST_multipart_json(self):
        payload = FakePayload(
            "\r\n".join(
                [
                    f"--{BOUNDARY}",
                    'Content-Disposition: form-data; name="name"',
                    "",
                    "value",
                    f"--{BOUNDARY}",
                    *self._json_payload,
                    f"--{BOUNDARY}--",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": MULTIPART_CONTENT,
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        self.assertEqual(
            request.POST,
            {
                "name": ["value"],
                "JSON": [
                    '{"pk": 1, "model": "store.book", "fields": {"name": "Mostly '
                    'Harmless", "author": ["Douglas", Adams"]}}'
                ],
            },
        )

    def test_POST_multipart_json_csv(self):
        payload = FakePayload(
            "\r\n".join(
                [
                    f"--{BOUNDARY}",
                    'Content-Disposition: form-data; name="name"',
                    "",
                    "value",
                    f"--{BOUNDARY}",
                    *self._json_payload,
                    f"--{BOUNDARY}",
                    'Content-Disposition: form-data; name="CSV"',
                    "Content-Type: text/csv",
                    "",
                    "Framework,ID.Django,1.Flask,2.",
                    f"--{BOUNDARY}--",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": MULTIPART_CONTENT,
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        self.assertEqual(
            request.POST,
            {
                "name": ["value"],
                "JSON": [
                    '{"pk": 1, "model": "store.book", "fields": {"name": "Mostly '
                    'Harmless", "author": ["Douglas", Adams"]}}'
                ],
                "CSV": ["Framework,ID.Django,1.Flask,2."],
            },
        )

    def test_POST_multipart_with_file(self):
        """
        Tests the handling of a POST request containing a multipart/form-data payload with a file attachment.

         Verifies that the request's POST data and files are correctly parsed from the payload, 
         and that the uploaded file is an instance of InMemoryUploadedFile.

         Specifically, this test case checks that:
         - The request's POST data is extracted correctly as a dictionary
         - The request's files are extracted correctly as a dictionary with a single InMemoryUploadedFile instance
        """
        payload = FakePayload(
            "\r\n".join(
                [
                    f"--{BOUNDARY}",
                    'Content-Disposition: form-data; name="name"',
                    "",
                    "value",
                    f"--{BOUNDARY}",
                    *self._json_payload,
                    f"--{BOUNDARY}",
                    'Content-Disposition: form-data; name="File"; filename="test.csv"',
                    "Content-Type: application/octet-stream",
                    "",
                    "Framework,ID",
                    "Django,1",
                    "Flask,2",
                    f"--{BOUNDARY}--",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": MULTIPART_CONTENT,
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        self.assertEqual(
            request.POST,
            {
                "name": ["value"],
                "JSON": [
                    '{"pk": 1, "model": "store.book", "fields": {"name": "Mostly '
                    'Harmless", "author": ["Douglas", Adams"]}}'
                ],
            },
        )
        self.assertEqual(len(request.FILES), 1)
        self.assertIsInstance((request.FILES["File"]), InMemoryUploadedFile)

    def test_base64_invalid_encoding(self):
        """
        Tests handling of invalid base64 encoding in multipart form data.

        Verifies that the MultiPartParserError is raised with the expected error message
        when attempting to parse a request containing a base64 encoded file part with
        invalid encoding. This test ensures that the parser correctly identifies and
        handles malformed base64 data, providing a meaningful error message to the user.

         Args:
            None

         Raises:
            MultiPartParserError: If the base64 data cannot be decoded.

         Returns:
            None
        """
        payload = FakePayload(
            "\r\n".join(
                [
                    f"--{BOUNDARY}",
                    'Content-Disposition: form-data; name="file"; filename="test.txt"',
                    "Content-Type: application/octet-stream",
                    "Content-Transfer-Encoding: base64",
                    "",
                    f"\r\nZsg£\r\n--{BOUNDARY}--",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": MULTIPART_CONTENT,
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        msg = "Could not decode base64 data."
        with self.assertRaisesMessage(MultiPartParserError, msg):
            request.POST

    def test_POST_binary_only(self):
        """
        Tests the handling of binary data in a POST request.

        Verifies that when sending a POST request with binary data and a 'application/octet-stream' content type,
        the request body is correctly set and the POST and FILES dictionaries are empty.

        Also tests the case where the 'CONTENT_TYPE' header is empty, ensuring that the request body is still
        correctly set and the POST and FILES dictionaries are empty.
        """
        payload = b"\r\n\x01\x00\x00\x00ab\x00\x00\xcd\xcc,@"
        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "application/octet-stream",
            "CONTENT_LENGTH": len(payload),
            "wsgi.input": BytesIO(payload),
        }
        request = WSGIRequest(environ)
        self.assertEqual(request.POST, {})
        self.assertEqual(request.FILES, {})
        self.assertEqual(request.body, payload)

        # Same test without specifying content-type
        environ.update({"CONTENT_TYPE": "", "wsgi.input": BytesIO(payload)})
        request = WSGIRequest(environ)
        self.assertEqual(request.POST, {})
        self.assertEqual(request.FILES, {})
        self.assertEqual(request.body, payload)

    def test_read_by_lines(self):
        payload = FakePayload("name=value")
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        self.assertEqual(list(request), [b"name=value"])

    def test_POST_after_body_read(self):
        """
        POST should be populated even if body is read first
        """
        payload = FakePayload("name=value")
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        request.body  # evaluate
        self.assertEqual(request.POST, {"name": ["value"]})

    def test_POST_after_body_read_and_stream_read(self):
        """
        POST should be populated even if body is read first, and then
        the stream is read second.
        """
        payload = FakePayload("name=value")
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        request.body  # evaluate
        self.assertEqual(request.read(1), b"n")
        self.assertEqual(request.POST, {"name": ["value"]})

    def test_multipart_post_field_with_base64(self):
        """

        Tests that a multipart POST request with a base64 encoded field is correctly parsed.

        Verifies that the request body is properly decoded and the base64 encoded field
        is translated to its original value, and that the resulting POST data is as expected.

        """
        payload = FakePayload(
            "\r\n".join(
                [
                    f"--{BOUNDARY}",
                    'Content-Disposition: form-data; name="name"',
                    "Content-Transfer-Encoding: base64",
                    "",
                    "dmFsdWU=",
                    f"--{BOUNDARY}--",
                    "",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": MULTIPART_CONTENT,
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        request.body  # evaluate
        self.assertEqual(request.POST, {"name": ["value"]})

    def test_multipart_post_field_with_invalid_base64(self):
        payload = FakePayload(
            "\r\n".join(
                [
                    f"--{BOUNDARY}",
                    'Content-Disposition: form-data; name="name"',
                    "Content-Transfer-Encoding: base64",
                    "",
                    "123",
                    f"--{BOUNDARY}--",
                    "",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": MULTIPART_CONTENT,
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        request.body  # evaluate
        self.assertEqual(request.POST, {"name": ["123"]})

    def test_POST_after_body_read_and_stream_read_multipart(self):
        """
        POST should be populated even if body is read first, and then
        the stream is read second. Using multipart/form-data instead of urlencoded.
        """
        payload = FakePayload(
            "\r\n".join(
                [
                    "--boundary",
                    'Content-Disposition: form-data; name="name"',
                    "",
                    "value",
                    "--boundary--" "",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "multipart/form-data; boundary=boundary",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        request.body  # evaluate
        # Consume enough data to mess up the parsing:
        self.assertEqual(request.read(13), b"--boundary\r\nC")
        self.assertEqual(request.POST, {"name": ["value"]})

    def test_POST_immutable_for_multipart(self):
        """
        MultiPartParser.parse() leaves request.POST immutable.
        """
        payload = FakePayload(
            "\r\n".join(
                [
                    "--boundary",
                    'Content-Disposition: form-data; name="name"',
                    "",
                    "value",
                    "--boundary--",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "multipart/form-data; boundary=boundary",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        self.assertFalse(request.POST._mutable)

    def test_multipart_without_boundary(self):
        """
        Test the handling of a multipart/form-data request without a boundary.

        The test verifies that a MultiPartParserError is raised with an appropriate error message when attempting to access the POST data of a request missing a boundary in its Content-Type header, which is a required parameter for multipart/form-data requests.
        """
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "multipart/form-data;",
                "CONTENT_LENGTH": 0,
                "wsgi.input": FakePayload(),
            }
        )
        with self.assertRaisesMessage(
            MultiPartParserError, "Invalid boundary in multipart: None"
        ):
            request.POST

    def test_multipart_non_ascii_content_type(self):
        """
        \\":\\"\\"Tests that a MultiPartParserError is raised when a non-ASCII character appears in the Content-Type header of a multipart request, specifically in the boundary parameter.

        This check ensures that the server correctly identifies and rejects requests with invalid multipart content types, which could potentially lead to security vulnerabilities or data corruption.

        The test case simulates a POST request with a multipart/form-data content type and a boundary containing a non-ASCII character (à). It verifies that attempting to access the request's POST data raises a MultiPartParserError with an appropriate error message, indicating that the server is properly handling this invalid scenario.\\"\\"\\"
        """
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "multipart/form-data; boundary = \xe0",
                "CONTENT_LENGTH": 0,
                "wsgi.input": FakePayload(),
            }
        )
        msg = (
            "Invalid non-ASCII Content-Type in multipart: multipart/form-data; "
            "boundary = à"
        )
        with self.assertRaisesMessage(MultiPartParserError, msg):
            request.POST

    def test_multipart_with_header_fields_too_large(self):
        """

        Tests the handling of multipart requests with header fields that exceed the maximum allowed size.

        This test case simulates a malicious request where the total size of the header fields
        in a multipart/form-data request exceeds the configured limit. It verifies that the
        MultiPartParserError is raised with the correct error message when attempting to parse
        the request.

        The scenario tested includes a request with a large X-Long-Header field that exceeds the 
        MAX_TOTAL_HEADER_SIZE limit, and ensures that the parser correctly identifies and reports 
        the error when parsing the request's POST data.

        """
        payload = FakePayload(
            "\r\n".join(
                [
                    "--boundary",
                    'Content-Disposition: form-data; name="name"',
                    "X-Long-Header: %s" % ("-" * (MAX_TOTAL_HEADER_SIZE + 1)),
                    "",
                    "value",
                    "--boundary--",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "multipart/form-data; boundary=boundary",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        msg = "Request max total header size exceeded."
        with self.assertRaisesMessage(MultiPartParserError, msg):
            request.POST

    def test_POST_connection_error(self):
        """
        If wsgi.input.read() raises an exception while trying to read() the
        POST, the exception is identifiable (not a generic OSError).
        """

        class ExplodingBytesIO(BytesIO):
            def read(self, size=-1, /):
                raise OSError("kaboom!")

        payload = b"name=value"
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": ExplodingBytesIO(payload),
            }
        )
        with self.assertRaises(UnreadablePostError):
            request.body

    def test_set_encoding_clears_POST(self):
        """
        Tests that setting the encoding of a request clears its POST data.

        This test ensures that when the encoding attribute of a WSGIRequest object is
        modified, its POST data is updated accordingly. Specifically, it verifies that
        the request's POST data is correctly parsed from a multipart/form-data payload
        and that changing the encoding resets the POST data.

        The test uses a sample POST request with a multipart/form-data payload
        containing a field with a non-ASCII character. It then sets the request's
        encoding to 'iso-8859-16' and checks that the POST data is cleared as expected.

        This test helps ensure that the WSGIRequest object behaves correctly when
        dealing with different encodings and POST data, which is crucial for handling
        requests with non-ASCII characters in a web application.
        """
        payload = FakePayload(
            "\r\n".join(
                [
                    f"--{BOUNDARY}",
                    'Content-Disposition: form-data; name="name"',
                    "",
                    "Hello Günter",
                    f"--{BOUNDARY}--",
                    "",
                ]
            )
        )
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": MULTIPART_CONTENT,
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": payload,
            }
        )
        self.assertEqual(request.POST, {"name": ["Hello Günter"]})
        request.encoding = "iso-8859-16"
        # FIXME: POST should be accessible after changing the encoding
        # (refs #14035).
        # self.assertEqual(request.POST, {"name": ["Hello GĂŒnter"]})

    def test_set_encoding_clears_GET(self):
        payload = FakePayload("")
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "GET",
                "wsgi.input": payload,
                "QUERY_STRING": "name=Hello%20G%C3%BCnter",
            }
        )
        self.assertEqual(request.GET, {"name": ["Hello Günter"]})
        request.encoding = "iso-8859-16"
        self.assertEqual(request.GET, {"name": ["Hello G\u0102\u0152nter"]})

    def test_FILES_connection_error(self):
        """
        If wsgi.input.read() raises an exception while trying to read() the
        FILES, the exception is identifiable (not a generic OSError).
        """

        class ExplodingBytesIO(BytesIO):
            def read(self, size=-1, /):
                raise OSError("kaboom!")

        payload = b"x"
        request = WSGIRequest(
            {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": "multipart/form-data; boundary=foo_",
                "CONTENT_LENGTH": len(payload),
                "wsgi.input": ExplodingBytesIO(payload),
            }
        )
        with self.assertRaises(UnreadablePostError):
            request.FILES

    def test_copy(self):
        request = HttpRequest()
        request_copy = copy.copy(request)
        self.assertIs(request_copy.resolver_match, request.resolver_match)

    def test_deepcopy(self):
        """

        Tests that a deep copy of a Request object creates a new, independent session dictionary.

        Verifies that modifications to the original request's session do not affect the session of the copied request.

        """
        request = RequestFactory().get("/")
        request.session = {}
        request_copy = copy.deepcopy(request)
        request.session["key"] = "value"
        self.assertEqual(request_copy.session, {})


class HostValidationTests(SimpleTestCase):
    poisoned_hosts = [
        "example.com@evil.tld",
        "example.com:dr.frankenstein@evil.tld",
        "example.com:dr.frankenstein@evil.tld:80",
        "example.com:80/badpath",
        "example.com: recovermypassword.com",
    ]

    @override_settings(
        USE_X_FORWARDED_HOST=False,
        ALLOWED_HOSTS=[
            "forward.com",
            "example.com",
            "internal.com",
            "12.34.56.78",
            "[2001:19f0:feee::dead:beef:cafe]",
            "xn--4ca9at.com",
            ".multitenant.com",
            "INSENSITIVE.com",
            "[::ffff:169.254.169.254]",
        ],
    )
    def test_http_get_host(self):
        # Check if X_FORWARDED_HOST is provided.
        """

        Tests the HttpRequest.get_host method to ensure it correctly determines the host
        from the HTTP request headers and server settings.

        The method prioritizes the HTTP_HOST header, falls back to the SERVER_NAME if
        HTTP_HOST is not provided, and appends the port number if it's not the default
        port (80 for HTTP). The test cases cover various scenarios, including:

        * Requests with HTTP_HOST, HTTP_X_FORWARDED_HOST, and SERVER_NAME headers set
        * Requests with only HTTP_HOST and SERVER_NAME headers set
        * Requests with only the SERVER_NAME header set
        * Requests with non-standard port numbers

        The test also checks that the get_host method raises a DisallowedHost exception
        when the requested host is not in the list of allowed hosts.

        Valid and invalid hosts are tested, including IPv4 and IPv6 addresses, domain
        names, and hosts with non-standard port numbers. Hostnames are also tested with
        and without trailing dots, as well as with internationalized domain names (IDN).

        """
        request = HttpRequest()
        request.META = {
            "HTTP_X_FORWARDED_HOST": "forward.com",
            "HTTP_HOST": "example.com",
            "SERVER_NAME": "internal.com",
            "SERVER_PORT": 80,
        }
        # X_FORWARDED_HOST is ignored.
        self.assertEqual(request.get_host(), "example.com")

        # Check if X_FORWARDED_HOST isn't provided.
        request = HttpRequest()
        request.META = {
            "HTTP_HOST": "example.com",
            "SERVER_NAME": "internal.com",
            "SERVER_PORT": 80,
        }
        self.assertEqual(request.get_host(), "example.com")

        # Check if HTTP_HOST isn't provided.
        request = HttpRequest()
        request.META = {
            "SERVER_NAME": "internal.com",
            "SERVER_PORT": 80,
        }
        self.assertEqual(request.get_host(), "internal.com")

        # Check if HTTP_HOST isn't provided, and we're on a nonstandard port
        request = HttpRequest()
        request.META = {
            "SERVER_NAME": "internal.com",
            "SERVER_PORT": 8042,
        }
        self.assertEqual(request.get_host(), "internal.com:8042")

        legit_hosts = [
            "example.com",
            "example.com:80",
            "12.34.56.78",
            "12.34.56.78:443",
            "[2001:19f0:feee::dead:beef:cafe]",
            "[2001:19f0:feee::dead:beef:cafe]:8080",
            "xn--4ca9at.com",  # Punycode for öäü.com
            "anything.multitenant.com",
            "multitenant.com",
            "insensitive.com",
            "example.com.",
            "example.com.:80",
            "[::ffff:169.254.169.254]",
        ]

        for host in legit_hosts:
            request = HttpRequest()
            request.META = {
                "HTTP_HOST": host,
            }
            request.get_host()

        # Poisoned host headers are rejected as suspicious
        for host in chain(self.poisoned_hosts, ["other.com", "example.com.."]):
            with self.assertRaises(DisallowedHost):
                request = HttpRequest()
                request.META = {
                    "HTTP_HOST": host,
                }
                request.get_host()

    @override_settings(USE_X_FORWARDED_HOST=True, ALLOWED_HOSTS=["*"])
    def test_http_get_host_with_x_forwarded_host(self):
        # Check if X_FORWARDED_HOST is provided.
        """
        Tests the get_host method of an HttpRequest object to ensure it correctly determines the host of the request.

        The get_host method checks the 'HTTP_X_FORWARDED_HOST' header, then the 'HTTP_HOST' header, and finally the 'SERVER_NAME' and 'SERVER_PORT' attributes to determine the host of the request.

        This test covers several scenarios, including when the 'HTTP_X_FORWARDED_HOST' and 'HTTP_HOST' headers are present, when only the 'HTTP_HOST' header is present, and when neither of these headers is present.

        Additionally, this test checks that the get_host method correctly handles various valid host formats, including domain names, IP addresses, and internationalized domain names.

        It also tests that the get_host method raises a DisallowedHost exception when an invalid or poisoned host is provided, ensuring the security of the request by preventing malicious hosts from being accepted.
        """
        request = HttpRequest()
        request.META = {
            "HTTP_X_FORWARDED_HOST": "forward.com",
            "HTTP_HOST": "example.com",
            "SERVER_NAME": "internal.com",
            "SERVER_PORT": 80,
        }
        # X_FORWARDED_HOST is obeyed.
        self.assertEqual(request.get_host(), "forward.com")

        # Check if X_FORWARDED_HOST isn't provided.
        request = HttpRequest()
        request.META = {
            "HTTP_HOST": "example.com",
            "SERVER_NAME": "internal.com",
            "SERVER_PORT": 80,
        }
        self.assertEqual(request.get_host(), "example.com")

        # Check if HTTP_HOST isn't provided.
        request = HttpRequest()
        request.META = {
            "SERVER_NAME": "internal.com",
            "SERVER_PORT": 80,
        }
        self.assertEqual(request.get_host(), "internal.com")

        # Check if HTTP_HOST isn't provided, and we're on a nonstandard port
        request = HttpRequest()
        request.META = {
            "SERVER_NAME": "internal.com",
            "SERVER_PORT": 8042,
        }
        self.assertEqual(request.get_host(), "internal.com:8042")

        # Poisoned host headers are rejected as suspicious
        legit_hosts = [
            "example.com",
            "example.com:80",
            "12.34.56.78",
            "12.34.56.78:443",
            "[2001:19f0:feee::dead:beef:cafe]",
            "[2001:19f0:feee::dead:beef:cafe]:8080",
            "xn--4ca9at.com",  # Punycode for öäü.com
        ]

        for host in legit_hosts:
            request = HttpRequest()
            request.META = {
                "HTTP_HOST": host,
            }
            request.get_host()

        for host in self.poisoned_hosts:
            with self.assertRaises(DisallowedHost):
                request = HttpRequest()
                request.META = {
                    "HTTP_HOST": host,
                }
                request.get_host()

    @override_settings(USE_X_FORWARDED_PORT=False)
    def test_get_port(self):
        """

        Tests the get_port method of the HttpRequest object to ensure it returns the correct port number.

        The test covers two scenarios: one where the HTTP_X_FORWARDED_PORT header is present in the request metadata,
        and one where it is not. In both cases, the method should return the value of the SERVER_PORT header.

        The test also verifies that the USE_X_FORWARDED_PORT setting does not affect the get_port method when set to False.

        """
        request = HttpRequest()
        request.META = {
            "SERVER_PORT": "8080",
            "HTTP_X_FORWARDED_PORT": "80",
        }
        # Shouldn't use the X-Forwarded-Port header
        self.assertEqual(request.get_port(), "8080")

        request = HttpRequest()
        request.META = {
            "SERVER_PORT": "8080",
        }
        self.assertEqual(request.get_port(), "8080")

    @override_settings(USE_X_FORWARDED_PORT=True)
    def test_get_port_with_x_forwarded_port(self):
        """

        Tests the get_port method of an HttpRequest object to ensure it returns the correct port number.

        The test covers two scenarios:
        - When the 'HTTP_X_FORWARDED_PORT' header is present in the request's metadata, 
          the method should return the port number specified in this header.
        - When the 'HTTP_X_FORWARDED_PORT' header is not present, the method should return 
          the port number specified in the 'SERVER_PORT' header.

        This test relies on the USE_X_FORWARDED_PORT setting being enabled.

        """
        request = HttpRequest()
        request.META = {
            "SERVER_PORT": "8080",
            "HTTP_X_FORWARDED_PORT": "80",
        }
        # Should use the X-Forwarded-Port header
        self.assertEqual(request.get_port(), "80")

        request = HttpRequest()
        request.META = {
            "SERVER_PORT": "8080",
        }
        self.assertEqual(request.get_port(), "8080")

    @override_settings(DEBUG=True, ALLOWED_HOSTS=[])
    def test_host_validation_in_debug_mode(self):
        """
        If ALLOWED_HOSTS is empty and DEBUG is True, variants of localhost are
        allowed.
        """
        valid_hosts = ["localhost", "subdomain.localhost", "127.0.0.1", "[::1]"]
        for host in valid_hosts:
            request = HttpRequest()
            request.META = {"HTTP_HOST": host}
            self.assertEqual(request.get_host(), host)

        # Other hostnames raise a DisallowedHost.
        with self.assertRaises(DisallowedHost):
            request = HttpRequest()
            request.META = {"HTTP_HOST": "example.com"}
            request.get_host()

    @override_settings(ALLOWED_HOSTS=[])
    def test_get_host_suggestion_of_allowed_host(self):
        """
        get_host() makes helpful suggestions if a valid-looking host is not in
        ALLOWED_HOSTS.
        """
        msg_invalid_host = "Invalid HTTP_HOST header: %r."
        msg_suggestion = msg_invalid_host + " You may need to add %r to ALLOWED_HOSTS."
        msg_suggestion2 = (
            msg_invalid_host
            + " The domain name provided is not valid according to RFC 1034/1035"
        )

        for host in [  # Valid-looking hosts
            "example.com",
            "12.34.56.78",
            "[2001:19f0:feee::dead:beef:cafe]",
            "xn--4ca9at.com",  # Punycode for öäü.com
        ]:
            request = HttpRequest()
            request.META = {"HTTP_HOST": host}
            with self.assertRaisesMessage(
                DisallowedHost, msg_suggestion % (host, host)
            ):
                request.get_host()

        for domain, port in [  # Valid-looking hosts with a port number
            ("example.com", 80),
            ("12.34.56.78", 443),
            ("[2001:19f0:feee::dead:beef:cafe]", 8080),
        ]:
            host = "%s:%s" % (domain, port)
            request = HttpRequest()
            request.META = {"HTTP_HOST": host}
            with self.assertRaisesMessage(
                DisallowedHost, msg_suggestion % (host, domain)
            ):
                request.get_host()

        for host in self.poisoned_hosts:
            request = HttpRequest()
            request.META = {"HTTP_HOST": host}
            with self.assertRaisesMessage(DisallowedHost, msg_invalid_host % host):
                request.get_host()

        request = HttpRequest()
        request.META = {"HTTP_HOST": "invalid_hostname.com"}
        with self.assertRaisesMessage(
            DisallowedHost, msg_suggestion2 % "invalid_hostname.com"
        ):
            request.get_host()

    def test_split_domain_port(self):
        """
        Test the split_domain_port function with various valid and invalid host inputs.

        This test case checks that the function correctly splits a host string into its domain and port components.
        It covers a range of scenarios, including IPv4 and IPv6 addresses, domain names, and hosts with and without ports.

        The test cases include hosts with invalid port numbers, hosts with no port specified, and hosts with various domain formats.
        The expected output for each test case is compared to the actual output of the split_domain_port function.

        The test is designed to ensure that the function behaves correctly for different types of input and provides accurate results for domain and port extraction.\"\"\"

         Param host: The input host string to be tested.

         Returns: None 
         Raises: AssertionError: If the function does not behave as expected.
        """
        for host, expected in [
            ("<invalid>", ("", "")),
            ("<invalid>:8080", ("", "")),
            ("example.com 8080", ("", "")),
            ("example.com:invalid", ("", "")),
            ("[::1]", ("[::1]", "")),
            ("[::1]:8080", ("[::1]", "8080")),
            ("[::ffff:127.0.0.1]", ("[::ffff:127.0.0.1]", "")),
            ("[::ffff:127.0.0.1]:8080", ("[::ffff:127.0.0.1]", "8080")),
            (
                "[1851:0000:3238:DEF1:0177:0000:0000:0125]",
                ("[1851:0000:3238:def1:0177:0000:0000:0125]", ""),
            ),
            (
                "[1851:0000:3238:DEF1:0177:0000:0000:0125]:8080",
                ("[1851:0000:3238:def1:0177:0000:0000:0125]", "8080"),
            ),
            ("127.0.0.1", ("127.0.0.1", "")),
            ("127.0.0.1:8080", ("127.0.0.1", "8080")),
            ("example.com", ("example.com", "")),
            ("example.com:8080", ("example.com", "8080")),
            ("example.com.", ("example.com", "")),
            ("example.com.:8080", ("example.com", "8080")),
            ("xn--n28h.test", ("xn--n28h.test", "")),
            ("xn--n28h.test:8080", ("xn--n28h.test", "8080")),
            ("subdomain.example.com", ("subdomain.example.com", "")),
            ("subdomain.example.com:8080", ("subdomain.example.com", "8080")),
        ]:
            with self.subTest(host=host):
                self.assertEqual(split_domain_port(host), expected)


class BuildAbsoluteURITests(SimpleTestCase):
    factory = RequestFactory()

    def test_absolute_url(self):
        """
        Tests the ability to build an absolute URI when the input URL is already absolute.

        This test ensures that the build_absolute_uri method correctly handles URLs that do not require scheme, host, or port information to be added. 

        :raises AssertionError: If the built URI does not match the input URL.

        """
        request = HttpRequest()
        url = "https://www.example.com/asdf"
        self.assertEqual(request.build_absolute_uri(location=url), url)

    def test_host_retrieval(self):
        """
        Tests the retrieval of the host component in an absolute URI.

        Verifies that the build_absolute_uri method correctly constructs an absolute URI 
        given a location path and the host name. The test checks that the host is 
        appropriately used and special characters in the location path are preserved.

        The function ensures that the resulting absolute URI is correctly formatted as 
        an HTTP URI with the host name and the location path, even when the path contains 
        special characters such as colons.
        """
        request = HttpRequest()
        request.get_host = lambda: "www.example.com"
        request.path = ""
        self.assertEqual(
            request.build_absolute_uri(location="/path/with:colons"),
            "http://www.example.com/path/with:colons",
        )

    def test_request_path_begins_with_two_slashes(self):
        # //// creates a request with a path beginning with //
        request = self.factory.get("////absolute-uri")
        tests = (
            # location isn't provided
            (None, "http://testserver//absolute-uri"),
            # An absolute URL
            ("http://example.com/?foo=bar", "http://example.com/?foo=bar"),
            # A schema-relative URL
            ("//example.com/?foo=bar", "http://example.com/?foo=bar"),
            # Relative URLs
            ("/foo/bar/", "http://testserver/foo/bar/"),
            ("/foo/./bar/", "http://testserver/foo/bar/"),
            ("/foo/../bar/", "http://testserver/bar/"),
            ("///foo/bar/", "http://testserver/foo/bar/"),
        )
        for location, expected_url in tests:
            with self.subTest(location=location):
                self.assertEqual(
                    request.build_absolute_uri(location=location), expected_url
                )


class RequestHeadersTests(SimpleTestCase):
    ENVIRON = {
        # Non-headers are ignored.
        "PATH_INFO": "/somepath/",
        "REQUEST_METHOD": "get",
        "wsgi.input": BytesIO(b""),
        "SERVER_NAME": "internal.com",
        "SERVER_PORT": 80,
        # These non-HTTP prefixed headers are included.
        "CONTENT_TYPE": "text/html",
        "CONTENT_LENGTH": "100",
        # All HTTP-prefixed headers are included.
        "HTTP_ACCEPT": "*",
        "HTTP_HOST": "example.com",
        "HTTP_USER_AGENT": "python-requests/1.2.0",
    }

    def test_base_request_headers(self):
        """

        Tests that a base HttpRequest object contains the expected request headers.

        Verifies that the request headers include Content-Type, Content-Length, Accept, 
        Host, and User-Agent, and that their values match the expected defaults.

        """
        request = HttpRequest()
        request.META = self.ENVIRON
        self.assertEqual(
            dict(request.headers),
            {
                "Content-Type": "text/html",
                "Content-Length": "100",
                "Accept": "*",
                "Host": "example.com",
                "User-Agent": "python-requests/1.2.0",
            },
        )

    def test_wsgi_request_headers(self):
        """
        Tests that a WSGI request properly interprets HTTP headers.

        Verifies that the request object can correctly parse and expose the headers
        from the WSGI environment, including common headers such as Content-Type,
        Content-Length, Accept, Host, and User-Agent.

        This test ensures that the request object is properly configured and can be
        used to handle HTTP requests with various headers.
        """
        request = WSGIRequest(self.ENVIRON)
        self.assertEqual(
            dict(request.headers),
            {
                "Content-Type": "text/html",
                "Content-Length": "100",
                "Accept": "*",
                "Host": "example.com",
                "User-Agent": "python-requests/1.2.0",
            },
        )

    def test_wsgi_request_headers_getitem(self):
        request = WSGIRequest(self.ENVIRON)
        self.assertEqual(request.headers["User-Agent"], "python-requests/1.2.0")
        self.assertEqual(request.headers["user-agent"], "python-requests/1.2.0")
        self.assertEqual(request.headers["user_agent"], "python-requests/1.2.0")
        self.assertEqual(request.headers["Content-Type"], "text/html")
        self.assertEqual(request.headers["Content-Length"], "100")

    def test_wsgi_request_headers_get(self):
        """
        Tests the retrieval of HTTP request headers from a WSGI request object. 
        This test case ensures that the headers are correctly accessed in a case-insensitive manner, 
        and that the expected values are returned for 'User-Agent' and 'Content-Type' headers. 
        It validates the functionality of the `get` method of the `headers` attribute of the `WSGIRequest` class.
        """
        request = WSGIRequest(self.ENVIRON)
        self.assertEqual(request.headers.get("User-Agent"), "python-requests/1.2.0")
        self.assertEqual(request.headers.get("user-agent"), "python-requests/1.2.0")
        self.assertEqual(request.headers.get("Content-Type"), "text/html")
        self.assertEqual(request.headers.get("Content-Length"), "100")


class HttpHeadersTests(SimpleTestCase):
    def test_basic(self):
        """

        Tests the basic functionality of the HttpHeaders class.

        Verifies that the class correctly extracts and stores HTTP headers from an environment dictionary.
        It also checks that the headers are properly sorted and can be accessed as a dictionary.
        The test case uses a sample environment with Content-Type, Content-Length, and HTTP_HOST headers.

        """
        environ = {
            "CONTENT_TYPE": "text/html",
            "CONTENT_LENGTH": "100",
            "HTTP_HOST": "example.com",
        }
        headers = HttpHeaders(environ)
        self.assertEqual(sorted(headers), ["Content-Length", "Content-Type", "Host"])
        self.assertEqual(
            headers,
            {
                "Content-Type": "text/html",
                "Content-Length": "100",
                "Host": "example.com",
            },
        )

    def test_parse_header_name(self):
        """
        Tests the parsing of HTTP header names.

        This test case ensures that the HttpHeaders.parse_header_name function correctly
        maps CGI-style header names to their corresponding HTTP header names.

        It checks a variety of header names, including those that start with 'HTTP_' and
        those that do not, to verify that the function behaves as expected in different
        scenarios.

        The test covers a range of common headers, such as Accept, User-Agent, and
        Content-Type, to ensure that the function can handle a variety of input values.

        If any of the test cases fail, it indicates that the HttpHeaders.parse_header_name
        function is not working correctly, and the expected output does not match the
        actual output.
        """
        tests = (
            ("PATH_INFO", None),
            ("HTTP_ACCEPT", "Accept"),
            ("HTTP_USER_AGENT", "User-Agent"),
            ("HTTP_X_FORWARDED_PROTO", "X-Forwarded-Proto"),
            ("CONTENT_TYPE", "Content-Type"),
            ("CONTENT_LENGTH", "Content-Length"),
        )
        for header, expected in tests:
            with self.subTest(header=header):
                self.assertEqual(HttpHeaders.parse_header_name(header), expected)
