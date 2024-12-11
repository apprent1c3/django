from unittest import TestCase

from django.http import HttpRequest
from django.http.request import MediaType


class MediaTypeTests(TestCase):
    def test_empty(self):
        """
        Tests the construction and properties of a MediaType object when initialized with an empty media type.

        Verifies that an empty media type (represented by None or an empty string) results in a MediaType object that:
        - does not match all media types
        - has an empty string representation
        - has a specific repr() output indicating an empty media type
        """
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
        """
        disciple the function's purpose and behavior 

         Test that an HTTP request accepts any content type.

         This test case verifies that when the 'Accept' header in the HTTP request is set to '*/*', 
         the request object correctly identifies that it can accept any content type, 
         including 'application/json'.
        """
        request = HttpRequest()
        request.META["HTTP_ACCEPT"] = "*/*"
        self.assertIs(request.accepts("application/json"), True)

    def test_request_accepts_none(self):
        """
        Tests that an HttpRequest object correctly handles a request with no Accept header set.

        This test case checks if the request object behaves as expected when the HTTP Accept header is empty.
        Specifically, it verifies that the :meth:`accepts` method returns False for 'application/json' and 
        the :attr:`accepted_types` attribute returns an empty list, indicating no accepted content types.
        """
        request = HttpRequest()
        request.META["HTTP_ACCEPT"] = ""
        self.assertIs(request.accepts("application/json"), False)
        self.assertEqual(request.accepted_types, [])

    def test_request_accepts_some(self):
        """

        Tests that an HttpRequest object correctly interprets the HTTP Accept header.

        The function checks that the request accepts various MIME types based on their
        presence and priority in the Accept header. This includes testing for types
        that are explicitly listed, as well as those that are implicitly accepted due
        to a wildcard or default priority.

        """
        request = HttpRequest()
        request.META["HTTP_ACCEPT"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9"
        )
        self.assertIs(request.accepts("text/html"), True)
        self.assertIs(request.accepts("application/xhtml+xml"), True)
        self.assertIs(request.accepts("application/xml"), True)
        self.assertIs(request.accepts("application/json"), False)
