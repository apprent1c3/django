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
        """
        Tests the initialization of an HttpRequest object to ensure it has the expected default state.

        The test covers the following aspects:
            * That all HTTP request dictionaries (GET, POST, COOKIES, META) are empty.
            * That the urlencode() method of the GET and POST dictionaries returns an empty string.
            * That the FILES dictionary is empty.
            * That the content_type and content_params attributes are None.

        This test case verifies that a newly created HttpRequest object has a clean and predictable state, 
        which is essential for ensuring the correctness of subsequent operations that rely on this object.
        """
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
        Tests the construction of a full HTTP request path.

        This test case verifies that the get_full_path and get_full_path_info methods
        correctly handle a request with a full path and query string, including
        special characters and prefix.

        The test checks that the methods properly escape and concatenate the path,
        query string, and prefix to form the expected full path and path info.

        """
        request = HttpRequest()
        request.path = "/;some/?awful/=path/foo:bar/"
        request.path_info = "/prefix" + request.path
        request.META["QUERY_STRING"] = ";some=query&+query=string"
        expected = "/%3Bsome/%3Fawful/%3Dpath/foo:bar/?;some=query&+query=string"
        self.assertEqual(request.get_full_path(), expected)
        self.assertEqual(request.get_full_path_info(), "/prefix" + expected)

    def test_httprequest_full_path_with_query_string_and_fragment(self):
        request = HttpRequest()
        request.path = "/foo#bar"
        request.path_info = "/prefix" + request.path
        request.META["QUERY_STRING"] = "baz#quux"
        self.assertEqual(request.get_full_path(), "/foo%23bar?baz#quux")
        self.assertEqual(request.get_full_path_info(), "/prefix/foo%23bar?baz#quux")

    def test_httprequest_repr(self):
        """

        Tests the string representation of an HTTP request object.

        Verifies that the repr function returns a string in the expected format,
        including the HTTP method and path, for a given HttpRequest object.

        """
        request = HttpRequest()
        request.path = "/somepath/"
        request.method = "GET"
        request.GET = {"get-key": "get-value"}
        request.POST = {"post-key": "post-value"}
        request.COOKIES = {"post-key": "post-value"}
        request.META = {"post-key": "post-value"}
        self.assertEqual(repr(request), "<HttpRequest: GET '/somepath/'>")

    def test_httprequest_repr_invalid_method_and_path(self):
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
        def wsgi_str(path_info, encoding="utf-8"):
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
        """
        Tests the readline method of WSGIRequest object to ensure it correctly reads lines from the HTTP request body.

        This test verifies that the readline method returns each line of the request body separately, without including the remaining content, 
        when the request body contains multiple lines of form-encoded data.

        The test covers a basic scenario where the request body contains two lines of data, 
        each line representing a key-value pair in the format 'key=value'. 

        The test passes if the readline method returns each line of the request body as expected, 
        which is essential for correctly parsing and processing HTTP requests with form-encoded data.
        """
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
        Test that a POST request with a non-UTF8 charset in the 'application/x-www-form-urlencoded' content type raises a BadRequest exception.

        This test case verifies that the framework correctly handles POST requests with a character encoding other than UTF-8, such as ISO-8859-1, and returns an error message indicating that UTF-8 encoding is required. The test checks that both the request's POST data and FILES are inaccessible due to the invalid encoding.
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
        """

        Tests the handling of multipart/form-data requests by the custom file upload handler.

        This test case simulates a POST request with a multipart/form-data payload, 
        containing a single form field. It verifies that the request's POST data and 
        FILES are correctly parsed by the custom file upload handler.

        The test uses a fake payload to mimic the structure of a multipart/form-data 
        request, with a boundary marker and a single form field. The custom file upload 
        handler should correctly extract the form field's value and store it in the 
        request's POST data.

        The test asserts that the request's POST data and FILES are correctly populated 
        after parsing the multipart/form-data payload.

        """
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

        Tests handling of POST requests with form data containing JSON payload.

        This test verifies that a POST request with a multipart/form-data body containing
        a JSON payload is correctly parsed and the JSON data is available in the request object.

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
        Tests a POST request with a multipart form, containing both form data and a file upload.

        The function verifies that the request object correctly parses the form data and file from the multipart payload.

        It checks that the request's POST dictionary contains the expected form data, and that the request's FILES dictionary contains a single uploaded file, which is an instance of InMemoryUploadedFile.
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
        """

        Tests that a WSGI request can be read line by line when the request body contains form data.

        Verifies that the request object correctly reads the input data from the request body
        and returns it as a list of lines, in this case a single line containing the form data.

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

        Tests that a MultiPartParserError is raised when the Content-Type header of a 
        multipart/form-data request contains non-ASCII characters in its boundary string.

        This test case verifies that the request parser correctly identifies and rejects 
        invalid Content-Type headers, ensuring that only valid ASCII characters are 
        allowed in the boundary string definition.

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
        Tests that a MultiPartParserError is raised when a multipart/form-data request has header fields that exceed the maximum total header size. The test verifies that the request is rejected and an error message is returned, indicating that the request's total header size limit has been exceeded.
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

        Tests whether setting the encoding of a request clears the POST data.

        This test case verifies that when the encoding of a request is set to a non-unicode
        encoding, the POST data is properly cleared to ensure data consistency.

        The test assumes a WSGIRequest with a multipart content type and a payload
        containing form data. It checks that the POST data is correctly populated before
        setting the encoding to a non-unicode encoding (in this case, 'iso-8859-16').

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

        Tests the deepcopy functionality of the Request object to ensure that modifying 
        the session of the original request does not affect the session of the copied request.

        This test verifies that the session attribute of the copied request remains unchanged
        after the original request's session is modified, confirming that a deep copy was successfully 
        made and the copied request is independent of the original request.

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
        request = HttpRequest()
        url = "https://www.example.com/asdf"
        self.assertEqual(request.build_absolute_uri(location=url), url)

    def test_host_retrieval(self):
        """

        Tests the retrieval of absolute URIs for a given host.

        This test ensures that the build_absolute_uri method correctly constructs an absolute URI
        by combining the host and the provided location. It verifies that the resulting URI is 
        correctly formatted, including the scheme, host, and path.

        The test covers a scenario where the location path contains special characters, such as colons.

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
        """
        Test that :meth:`build_absolute_uri` correctly handles a request path starting with two slashes.

        This test case verifies that the function correctly resolves absolute and relative URLs,
         HandlesPaths that start with '/./' or '/../' and returns a URL as per the RFC 3986.

        Multiple test scenarios are covered including paths with query parameters, paths that start with '//' and absolute paths, 
         to ensure the function handles different edge cases as expected.

        The expected output URLs are compared against the actual output of :meth:`build_absolute_uri` to ensure correctness.
        """
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

        Tests WSGI request headers by creating a WSGIRequest object from a predefined environment and verifying its headers.

        The function checks if the headers contain the expected keys and values, including 'Content-Type', 'Content-Length', 'Accept', 'Host', and 'User-Agent', 
        to ensure they match the predefined environment settings.

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
        """

        Tests access to WSGI request headers using dictionary-style access.

        Verifies that the 'headers' attribute of a WSGIRequest object behaves as expected,
        allowing retrieval of HTTP request headers in a case-insensitive manner and
        handles different cases (e.g. 'User-Agent', 'user-agent', 'user_agent').

        Ensures correct retrieval of various headers, including 'User-Agent', 'Content-Type',
        and 'Content-Length', demonstrating that headers are properly parsed and made
        available for inspection.

        """
        request = WSGIRequest(self.ENVIRON)
        self.assertEqual(request.headers["User-Agent"], "python-requests/1.2.0")
        self.assertEqual(request.headers["user-agent"], "python-requests/1.2.0")
        self.assertEqual(request.headers["user_agent"], "python-requests/1.2.0")
        self.assertEqual(request.headers["Content-Type"], "text/html")
        self.assertEqual(request.headers["Content-Length"], "100")

    def test_wsgi_request_headers_get(self):
        request = WSGIRequest(self.ENVIRON)
        self.assertEqual(request.headers.get("User-Agent"), "python-requests/1.2.0")
        self.assertEqual(request.headers.get("user-agent"), "python-requests/1.2.0")
        self.assertEqual(request.headers.get("Content-Type"), "text/html")
        self.assertEqual(request.headers.get("Content-Length"), "100")


class HttpHeadersTests(SimpleTestCase):
    def test_basic(self):
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
