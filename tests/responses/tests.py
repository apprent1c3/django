import io

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.http.response import HttpResponseBase
from django.test import SimpleTestCase

UTF8 = "utf-8"
ISO88591 = "iso-8859-1"


class HttpResponseBaseTests(SimpleTestCase):
    def test_closed(self):
        """

        Tests that an HttpResponseBase object is initially not closed and can be successfully closed.

        The test case checks the initial state of the 'closed' attribute and then verifies that it is correctly updated after calling the close method.

        """
        r = HttpResponseBase()
        self.assertIs(r.closed, False)

        r.close()
        self.assertIs(r.closed, True)

    def test_write(self):
        """
        Verifies the behavior of HttpResponseBase instances when attempting to write to them.

        This test checks that HttpResponseBase objects are not writable by default and that attempting to call write() or writelines() methods on such instances raises an OSError with a descriptive message, indicating that the instance is not writable.

        The test covers both single write operations and batch write operations using writelines(), ensuring that both scenarios raise the expected exception and error message, thus validating the non-writable nature of HttpResponseBase objects.
        """
        r = HttpResponseBase()
        self.assertIs(r.writable(), False)

        with self.assertRaisesMessage(
            OSError, "This HttpResponseBase instance is not writable"
        ):
            r.write("asdf")
        with self.assertRaisesMessage(
            OSError, "This HttpResponseBase instance is not writable"
        ):
            r.writelines(["asdf\n", "qwer\n"])

    def test_tell(self):
        """
        Tests that attempting to determine the position of an HttpResponseBase instance raises an OSError.

        This test case verifies that the tell method, which is used to get the current position of a file or stream, 
        is not supported by the HttpResponseBase class and correctly raises an exception with a descriptive message.

        Args: None

        Returns: None

        Raises: 
            OSError: If an attempt is made to call the tell method on an HttpResponseBase instance.

        """
        r = HttpResponseBase()
        with self.assertRaisesMessage(
            OSError, "This HttpResponseBase instance cannot tell its position"
        ):
            r.tell()

    def test_setdefault(self):
        """
        HttpResponseBase.setdefault() should not change an existing header
        and should be case insensitive.
        """
        r = HttpResponseBase()

        r.headers["Header"] = "Value"
        r.setdefault("header", "changed")
        self.assertEqual(r.headers["header"], "Value")

        r.setdefault("x-header", "DefaultValue")
        self.assertEqual(r.headers["X-Header"], "DefaultValue")

    def test_charset_setter(self):
        """

        Tests the_thread safety and functionality of setting the charset property 
        in an HttpResponseBase object, verifying that it can be successfully set 
        and retrieved with the expected value.

        """
        r = HttpResponseBase()
        r.charset = "utf-8"
        self.assertEqual(r.charset, "utf-8")

    def test_reason_phrase_setter(self):
        """
        Test that the reason phrase setter updates the HttpResponseBase object correctly.

        This test verifies that setting the reason phrase attribute of an HttpResponseBase
        object successfully updates its internal state, allowing the updated phrase to be
        retrieved accurately. It ensures that the reason phrase setter functions as expected,
        providing a valid test case for the HttpResponseBase class's reason phrase property.

        """
        r = HttpResponseBase()
        r.reason_phrase = "test"
        self.assertEqual(r.reason_phrase, "test")


class HttpResponseTests(SimpleTestCase):
    def test_status_code(self):
        resp = HttpResponse(status=503)
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.reason_phrase, "Service Unavailable")

    def test_change_status_code(self):
        resp = HttpResponse()
        resp.status_code = 503
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.reason_phrase, "Service Unavailable")

    def test_valid_status_code_string(self):
        """
        Tests that the HttpResponse status code is correctly set when provided as a string.

        This test case verifies that the status_code attribute of an HttpResponse object
        is properly updated when a string representation of the status code is passed to
        the HttpResponse constructor. It covers a range of valid status codes, including
        informational (1xx), client error (4xx), and server error (5xx) responses.

        The test ensures that the status_code attribute is correctly assigned the integer
        value corresponding to the input string, allowing for proper handling and
        interpretation of HTTP response codes in the application.
        """
        resp = HttpResponse(status="100")
        self.assertEqual(resp.status_code, 100)
        resp = HttpResponse(status="404")
        self.assertEqual(resp.status_code, 404)
        resp = HttpResponse(status="599")
        self.assertEqual(resp.status_code, 599)

    def test_invalid_status_code(self):
        """
        Tests that the HttpResponse constructor raises the correct errors for invalid HTTP status codes.

        The function checks that a TypeError is raised if the status code is not an integer, and that a ValueError is raised if the status code is an integer outside the valid range of 100 to 599.

        Raises:
            TypeError: If the status code is not an integer.
            ValueError: If the status code is an integer outside the valid range.

        Notes:
            This test is designed to ensure that the HttpResponse constructor correctly validates the status code, preventing the creation of responses with invalid or malformed status codes.

        """
        must_be_integer = "HTTP status code must be an integer."
        must_be_integer_in_range = (
            "HTTP status code must be an integer from 100 to 599."
        )
        with self.assertRaisesMessage(TypeError, must_be_integer):
            HttpResponse(status=object())
        with self.assertRaisesMessage(TypeError, must_be_integer):
            HttpResponse(status="J'attendrai")
        with self.assertRaisesMessage(ValueError, must_be_integer_in_range):
            HttpResponse(status=99)
        with self.assertRaisesMessage(ValueError, must_be_integer_in_range):
            HttpResponse(status=600)

    def test_reason_phrase(self):
        reason = "I'm an anarchist coffee pot on crack."
        resp = HttpResponse(status=419, reason=reason)
        self.assertEqual(resp.status_code, 419)
        self.assertEqual(resp.reason_phrase, reason)

    def test_charset_detection(self):
        """HttpResponse should parse charset from content_type."""
        response = HttpResponse("ok")
        self.assertEqual(response.charset, settings.DEFAULT_CHARSET)

        response = HttpResponse(charset=ISO88591)
        self.assertEqual(response.charset, ISO88591)
        self.assertEqual(
            response.headers["Content-Type"], "text/html; charset=%s" % ISO88591
        )

        response = HttpResponse(
            content_type="text/plain; charset=%s" % UTF8, charset=ISO88591
        )
        self.assertEqual(response.charset, ISO88591)

        response = HttpResponse(content_type="text/plain; charset=%s" % ISO88591)
        self.assertEqual(response.charset, ISO88591)

        response = HttpResponse(content_type='text/plain; charset="%s"' % ISO88591)
        self.assertEqual(response.charset, ISO88591)

        response = HttpResponse(content_type="text/plain; charset=")
        self.assertEqual(response.charset, settings.DEFAULT_CHARSET)

        response = HttpResponse(content_type="text/plain")
        self.assertEqual(response.charset, settings.DEFAULT_CHARSET)

    def test_response_content_charset(self):
        """HttpResponse should encode based on charset."""
        content = "Café :)"
        utf8_content = content.encode(UTF8)
        iso_content = content.encode(ISO88591)

        response = HttpResponse(utf8_content)
        self.assertContains(response, utf8_content)

        response = HttpResponse(
            iso_content, content_type="text/plain; charset=%s" % ISO88591
        )
        self.assertContains(response, iso_content)

        response = HttpResponse(iso_content)
        self.assertContains(response, iso_content)

        response = HttpResponse(iso_content, content_type="text/plain")
        self.assertContains(response, iso_content)

    def test_repr(self):
        response = HttpResponse(content="Café :)".encode(UTF8), status=201)
        expected = '<HttpResponse status_code=201, "text/html; charset=utf-8">'
        self.assertEqual(repr(response), expected)

    def test_repr_no_content_type(self):
        response = HttpResponse(status=204)
        del response.headers["Content-Type"]
        self.assertEqual(repr(response), "<HttpResponse status_code=204>")

    def test_wrap_textiowrapper(self):
        """
        Tests that writing to an HttpResponse object using a TextIOWrapper correctly encodes the content as UTF-8. 

        This test case checks that the content written to the TextIOWrapper is properly encoded and matches the expected output, ensuring compatibility with Unicode characters.
        """
        content = "Café :)"
        r = HttpResponse()
        with io.TextIOWrapper(r, UTF8) as buf:
            buf.write(content)
        self.assertEqual(r.content, content.encode(UTF8))

    def test_generator_cache(self):
        """

        Tests the caching behavior of HttpResponse objects that contain generator content.

        This test case ensures that the HttpResponse content is correctly generated and 
        stored in the cache, as well as verifying that the generator is properly 
        exhausted and cannot be iterated over again after its content has been consumed.

        It checks that the cached response matches the original response content and 
        that attempting to retrieve the next item from the exhausted generator raises 
        a StopIteration exception. 

        The test scenario involves creating a generator that yields string representations 
        of numbers from 0 to 9, wrapping it in an HttpResponse object, and caching the 
        response. The test then verifies the cached response content and the state of 
        the generator.

        """
        generator = (str(i) for i in range(10))
        response = HttpResponse(content=generator)
        self.assertEqual(response.content, b"0123456789")
        with self.assertRaises(StopIteration):
            next(generator)

        cache.set("my-response-key", response)
        response = cache.get("my-response-key")
        self.assertEqual(response.content, b"0123456789")
