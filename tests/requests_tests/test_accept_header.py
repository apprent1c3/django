from unittest import TestCase

from django.http import HttpRequest
from django.http.request import MediaType


class MediaTypeTests(TestCase):
    def test_empty(self):
        for empty_media_type in (None, ""):
            with self.subTest(media_type=empty_media_type):
                media_type = MediaType(empty_media_type)
                self.assertIs(media_type.is_all_types, False)
                self.assertEqual(str(media_type), "")
                self.assertEqual(repr(media_type), "<MediaType: >")

    def test_str(self):
        self.assertEqual(str(MediaType("*/*; q=0.8")), "*/*; q=0.8")
        self.assertEqual(str(MediaType("application/xml")), "application/xml")

    def test_repr(self):
        """

        Tests the string representation of a MediaType object.

        This function verifies that the repr() method of a MediaType object returns a string
        in the expected format, which includes the media type and any associated parameters.

        """
        self.assertEqual(repr(MediaType("*/*; q=0.8")), "<MediaType: */*; q=0.8>")
        self.assertEqual(
            repr(MediaType("application/xml")),
            "<MediaType: application/xml>",
        )

    def test_is_all_types(self):
        self.assertIs(MediaType("*/*").is_all_types, True)
        self.assertIs(MediaType("*/*; q=0.8").is_all_types, True)
        self.assertIs(MediaType("text/*").is_all_types, False)
        self.assertIs(MediaType("application/xml").is_all_types, False)

    def test_match(self):
        """

        Tests the MediaType.match method to ensure correct matching of accepted types and MIME types.

        The function verifies that the MediaType class can properly match different accepted types 
        against corresponding MIME types, including cases with varying levels of specificity and 
        whitespace. The test suite includes a range of scenarios, from generic accepted types 
        (e.g., '*/*') to more specific ones (e.g., 'application/xml'), covering different 
        quality values and whitespace handling.

        """
        tests = [
            ("*/*; q=0.8", "*/*"),
            ("*/*", "application/json"),
            (" */* ", "application/json"),
            ("application/*", "application/json"),
            ("application/xml", "application/xml"),
            (" application/xml ", "application/xml"),
            ("application/xml", " application/xml "),
        ]
        for accepted_type, mime_type in tests:
            with self.subTest(accepted_type, mime_type=mime_type):
                self.assertIs(MediaType(accepted_type).match(mime_type), True)

    def test_no_match(self):
        """

        Checks that the MediaType class correctly identifies non-matching MIME types.

        This function tests the match method of the MediaType class with various
        accepted types and MIME types, ensuring that it returns False when no match
        is found. The test cases cover different edge cases, including None and empty
        accepted types, as well as MIME types with and without quality parameters.

        """
        tests = [
            (None, "*/*"),
            ("", "*/*"),
            ("; q=0.8", "*/*"),
            ("application/xml", "application/html"),
            ("application/xml", "*/*"),
        ]
        for accepted_type, mime_type in tests:
            with self.subTest(accepted_type, mime_type=mime_type):
                self.assertIs(MediaType(accepted_type).match(mime_type), False)


class AcceptHeaderTests(TestCase):
    def test_no_headers(self):
        """Absence of Accept header defaults to '*/*'."""
        request = HttpRequest()
        self.assertEqual(
            [str(accepted_type) for accepted_type in request.accepted_types],
            ["*/*"],
        )

    def test_accept_headers(self):
        """

        Tests that the accepted types from the ACCEPT HTTP header are properly parsed.

        The function verifies that the HttpRequest object correctly interprets the HTTP_ACCEPT header, 
        which specifies the MIME types that the client can handle, along with their respective quality values.
        It checks that the accepted_types attribute of the HttpRequest object returns a list of accepted types 
        in the correct order, including their quality values if specified.

        """
        request = HttpRequest()
        request.META["HTTP_ACCEPT"] = (
            "text/html, application/xhtml+xml,application/xml ;q=0.9,*/*;q=0.8"
        )
        self.assertEqual(
            [str(accepted_type) for accepted_type in request.accepted_types],
            [
                "text/html",
                "application/xhtml+xml",
                "application/xml; q=0.9",
                "*/*; q=0.8",
            ],
        )

    def test_request_accepts_any(self):
        request = HttpRequest()
        request.META["HTTP_ACCEPT"] = "*/*"
        self.assertIs(request.accepts("application/json"), True)

    def test_request_accepts_none(self):
        request = HttpRequest()
        request.META["HTTP_ACCEPT"] = ""
        self.assertIs(request.accepts("application/json"), False)
        self.assertEqual(request.accepted_types, [])

    def test_request_accepts_some(self):
        """

        Tests whether a request correctly identifies the accepted content types.

        The function verifies that the :meth:`~HttpRequest.accepts` method accurately
        reflects the \"Accept\" header in the request's metadata. It checks if the method
        correctly returns True for accepted content types (text/html, application/xhtml+xml,
        application/xml) and False for unaccepted content types (application/json).

        """
        request = HttpRequest()
        request.META["HTTP_ACCEPT"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9"
        )
        self.assertIs(request.accepts("text/html"), True)
        self.assertIs(request.accepts("application/xhtml+xml"), True)
        self.assertIs(request.accepts("application/xml"), True)
        self.assertIs(request.accepts("application/json"), False)
