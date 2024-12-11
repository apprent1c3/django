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
        self.assertEqual(repr(MediaType("*/*; q=0.8")), "<MediaType: */*; q=0.8>")
        self.assertEqual(
            repr(MediaType("application/xml")),
            "<MediaType: application/xml>",
        )

    def test_is_all_types(self):
        """
        Tests whether a MediaType represents all types, i.e., its type is \"*/*\". 
        A MediaType is considered to represent all types if its type matches this pattern, 
        regardless of any additional parameters, such as quality (q) values.
        """
        self.assertIs(MediaType("*/*").is_all_types, True)
        self.assertIs(MediaType("*/*; q=0.8").is_all_types, True)
        self.assertIs(MediaType("text/*").is_all_types, False)
        self.assertIs(MediaType("application/xml").is_all_types, False)

    def test_match(self):
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
        Test that the HttpRequest object properly handles HTTP Accept headers.

        This test checks that the accepts method of the HttpRequest object correctly
        identifies the MIME types that the client has indicated it can handle, based on
        the Accept header of the HTTP request. It verifies that the method returns True
        for MIME types that are explicitly listed in the Accept header and False for
        MIME types that are not listed.

        The Accept header is used by clients to specify the types of content that they
        are capable of handling. The test covers cases where the Accept header lists
        multiple MIME types, with and without quality values (q-values), and where it
        does not list a particular MIME type. The method should return True for MIME
        types with the highest q-value and False for MIME types that are not listed or
        have a lower q-value.
        """
        request = HttpRequest()
        request.META["HTTP_ACCEPT"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9"
        )
        self.assertIs(request.accepts("text/html"), True)
        self.assertIs(request.accepts("application/xhtml+xml"), True)
        self.assertIs(request.accepts("application/xml"), True)
        self.assertIs(request.accepts("application/json"), False)
