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
        """
        ..:nodoc:
        Checks the string representation of MediaType objects to ensure they match their initialization values.

        The test covers different scenarios, including media types with and without quality parameters.
        It verifies that the string representation accurately reflects the media type's attributes, such as type and subtype, as well as any additional parameters like quality (q) values.
        """
        self.assertEqual(str(MediaType("*/*; q=0.8")), "*/*; q=0.8")
        self.assertEqual(str(MediaType("application/xml")), "application/xml")

    def test_repr(self):
        """
        :return: Tests the representation of MediaType objects to ensure correct string output.

         The function verifies that the repr function returns a string in the expected format: 
         '<MediaType: type/subtype; parameters>' for MediaTypes with parameters 
         and '<MediaType: type/subtype>' for those without. 

         This test checks for the proper formatting of the string representation in both 
         cases, including when quality factor parameter (q) is present and when it is not.

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
        Tests that the MediaType class correctly identifies non-matching media types.

        This function verifies that the MediaType match method returns False for various
        combinations of accepted types and MIME types, ensuring that the class behaves
        as expected when no match is found. The test cases cover a range of scenarios,
        including empty or null accepted types, and mismatched MIME types.
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
        Tests the parsing of Accept headers in an HttpRequest object.

        This function verifies that the accepted_types attribute of an HttpRequest object
        is correctly populated based on the HTTP Accept header. It checks that the
        accepted types are parsed and ordered correctly, and that the quality values
        (q-values) are preserved.

        The test case covers a typical Accept header with multiple MIME types and q-values,
        ensuring that the HttpRequest object accurately represents the client's preferences.


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
        """
        ..: meth:: test_request_accepts_any
            Verifies that an HttpRequest object accepts any media type when the 'Accept' header is set to '*/*'.

            Checks if the :meth:`accepts` method of the HttpRequest object returns True for 'application/json' when the 'Accept' header is set to '*/*', confirming that the object accepts all media types.
        """
        request = HttpRequest()
        request.META["HTTP_ACCEPT"] = "*/*"
        self.assertIs(request.accepts("application/json"), True)

    def test_request_accepts_none(self):
        request = HttpRequest()
        request.META["HTTP_ACCEPT"] = ""
        self.assertIs(request.accepts("application/json"), False)
        self.assertEqual(request.accepted_types, [])

    def test_request_accepts_some(self):
        request = HttpRequest()
        request.META["HTTP_ACCEPT"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9"
        )
        self.assertIs(request.accepts("text/html"), True)
        self.assertIs(request.accepts("application/xhtml+xml"), True)
        self.assertIs(request.accepts("application/xml"), True)
        self.assertIs(request.accepts("application/json"), False)
