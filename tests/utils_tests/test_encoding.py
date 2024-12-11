import datetime
import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import quote, quote_plus

from django.test import SimpleTestCase
from django.utils.encoding import (
    DjangoUnicodeDecodeError,
    escape_uri_path,
    filepath_to_uri,
    force_bytes,
    force_str,
    get_system_encoding,
    iri_to_uri,
    repercent_broken_unicode,
    smart_bytes,
    smart_str,
    uri_to_iri,
)
from django.utils.functional import SimpleLazyObject
from django.utils.translation import gettext_lazy
from django.utils.version import PYPY


class TestEncodingUtils(SimpleTestCase):
    def test_force_str_exception(self):
        """
        Broken __str__ actually raises an error.
        """

        class MyString:
            def __str__(self):
                return b"\xc3\xb6\xc3\xa4\xc3\xbc"

        # str(s) raises a TypeError if the result is not a text type.
        with self.assertRaises(TypeError):
            force_str(MyString())

    def test_force_str_lazy(self):
        """
        Tests that the force_str function correctly converts a SimpleLazyObject to a string.

        Verifies that the type of the returned value is a string, ensuring that the 
        force_str function can handle lazy objects and force their evaluation to a 
        string representation.
        """
        s = SimpleLazyObject(lambda: "x")
        self.assertIs(type(force_str(s)), str)

    def test_force_str_DjangoUnicodeDecodeError(self):
        """
        Tests that force_str correctly raises a DjangoUnicodeDecodeError when 
        given a bytes object that cannot be decoded to a string using UTF-8 encoding.

        Specifically, this test checks that the error message raised by 
        force_str contains the expected details about the decoding failure, 
        including the reason for the failure and the invalid byte that caused it.
        """
        reason = "unexpected end of data" if PYPY else "invalid start byte"
        msg = (
            f"'utf-8' codec can't decode byte 0xff in position 0: {reason}. "
            "You passed in b'\\xff' (<class 'bytes'>)"
        )
        with self.assertRaisesMessage(DjangoUnicodeDecodeError, msg):
            force_str(b"\xff")

    def test_force_bytes_exception(self):
        """
        force_bytes knows how to convert to bytes an exception
        containing non-ASCII characters in its args.
        """
        error_msg = "This is an exception, voilà"
        exc = ValueError(error_msg)
        self.assertEqual(force_bytes(exc), error_msg.encode())
        self.assertEqual(
            force_bytes(exc, encoding="ascii", errors="ignore"),
            b"This is an exception, voil",
        )

    def test_force_bytes_strings_only(self):
        today = datetime.date.today()
        self.assertEqual(force_bytes(today, strings_only=True), today)

    def test_force_bytes_encoding(self):
        """

        Tests the force_bytes function's handling of encoding errors.

        This test case verifies that the function correctly encodes a bytes object with non-ASCII characters, ignoring unencodable characters.

        """
        error_msg = "This is an exception, voilà".encode()
        result = force_bytes(error_msg, encoding="ascii", errors="ignore")
        self.assertEqual(result, b"This is an exception, voil")

    def test_force_bytes_memory_view(self):
        """

        Tests the functionality of the force_bytes function when passed a memory view object.

        This test case verifies that when a memory view of a bytes object is passed to the force_bytes function,
        it correctly returns a bytes object that matches the original data.

        The test confirms that the returned result is of type bytes and is equal to the original bytes data,
        ensuring the force_bytes function behaves as expected with memory view inputs.

        """
        data = b"abc"
        result = force_bytes(memoryview(data))
        # Type check is needed because memoryview(bytes) == bytes.
        self.assertIs(type(result), bytes)
        self.assertEqual(result, data)

    def test_smart_bytes(self):
        """

        Converts the input object to bytes, handling various types and encodings.

        Handles the conversion of different data types, including lazy gettext objects,
        custom objects with a string representation, integers, and strings, to bytes.

        The conversion process ensures that the output remains consistent with the input,
        preserving the original data when possible, while applying the necessary encoding
        for string-based inputs.

        The function is particularly useful when working with international characters and
        mixed data types, providing a reliable way to obtain byte representations of the
        input objects.

        """
        class Test:
            def __str__(self):
                return "ŠĐĆŽćžšđ"

        lazy_func = gettext_lazy("x")
        self.assertIs(smart_bytes(lazy_func), lazy_func)
        self.assertEqual(
            smart_bytes(Test()),
            b"\xc5\xa0\xc4\x90\xc4\x86\xc5\xbd\xc4\x87\xc5\xbe\xc5\xa1\xc4\x91",
        )
        self.assertEqual(smart_bytes(1), b"1")
        self.assertEqual(smart_bytes("foo"), b"foo")

    def test_smart_str(self):
        """

        Checks the functionality of the smart_str function.

        The smart_str function is designed to handle the conversion of different data types to strings.
        It is tested with various inputs, including a lazy function, a custom class instance with a defined __str__ method,
        an integer, and a string. The function should return the original object when it is a lazy function,
        and a string representation of the object for other input types, handling non-ASCII characters correctly.

        """
        class Test:
            def __str__(self):
                return "ŠĐĆŽćžšđ"

        lazy_func = gettext_lazy("x")
        self.assertIs(smart_str(lazy_func), lazy_func)
        self.assertEqual(
            smart_str(Test()), "\u0160\u0110\u0106\u017d\u0107\u017e\u0161\u0111"
        )
        self.assertEqual(smart_str(1), "1")
        self.assertEqual(smart_str("foo"), "foo")

    def test_get_default_encoding(self):
        """
        Tests the get_system_encoding function to ensure it returns 'ascii' when locale.getlocale raises an exception, effectively handling failure to retrieve the system's default encoding.
        """
        with mock.patch("locale.getlocale", side_effect=Exception):
            self.assertEqual(get_system_encoding(), "ascii")

    def test_repercent_broken_unicode_recursion_error(self):
        # Prepare a string long enough to force a recursion error if the tested
        # function uses recursion.
        data = b"\xfc" * sys.getrecursionlimit()
        try:
            self.assertEqual(
                repercent_broken_unicode(data), b"%FC" * sys.getrecursionlimit()
            )
        except RecursionError:
            self.fail("Unexpected RecursionError raised.")

    def test_repercent_broken_unicode_small_fragments(self):
        data = b"test\xfctest\xfctest\xfc"
        decoded_paths = []

        def mock_quote(*args, **kwargs):
            # The second frame is the call to repercent_broken_unicode().
            decoded_paths.append(inspect.currentframe().f_back.f_locals["path"])
            return quote(*args, **kwargs)

        with mock.patch("django.utils.encoding.quote", mock_quote):
            self.assertEqual(repercent_broken_unicode(data), b"test%FCtest%FCtest%FC")

        # decode() is called on smaller fragment of the path each time.
        self.assertEqual(
            decoded_paths,
            [b"test\xfctest\xfctest\xfc", b"test\xfctest\xfc", b"test\xfc"],
        )


class TestRFC3987IEncodingUtils(unittest.TestCase):
    def test_filepath_to_uri(self):
        """

        Convert a file path to a valid URI.

        This function takes a file path as input and returns its equivalent URI representation.
        It handles both string and Path object inputs, and properly encodes non-ASCII characters.
        The resulting URI is suitable for use in URLs and other contexts where a valid URI is required.

        The function supports various input formats, including Windows-style backslashes and POSIX-style forward slashes.
        It also correctly handles null input, returning None in such cases.

        """
        self.assertIsNone(filepath_to_uri(None))
        self.assertEqual(
            filepath_to_uri("upload\\чубака.mp4"),
            "upload/%D1%87%D1%83%D0%B1%D0%B0%D0%BA%D0%B0.mp4",
        )
        self.assertEqual(filepath_to_uri(Path("upload/test.png")), "upload/test.png")
        self.assertEqual(filepath_to_uri(Path("upload\\test.png")), "upload/test.png")

    def test_iri_to_uri(self):
        """
        Tests the conversion of Internationalized Resource Identifiers (IRIs) to Uniform Resource Identifiers (URIs).

        The test covers various cases, including IRIs with Unicode characters, URL encoded characters, and non-ASCII characters.

        Each test case checks that the IRI is correctly converted to a URI, and that re-converting the resulting URI does not alter its value.
        """
        cases = [
            # Valid UTF-8 sequences are encoded.
            ("red%09rosé#red", "red%09ros%C3%A9#red"),
            ("/blog/for/Jürgen Münster/", "/blog/for/J%C3%BCrgen%20M%C3%BCnster/"),
            (
                "locations/%s" % quote_plus("Paris & Orléans"),
                "locations/Paris+%26+Orl%C3%A9ans",
            ),
            # Reserved chars remain unescaped.
            ("%&", "%&"),
            ("red&♥ros%#red", "red&%E2%99%A5ros%#red"),
            (gettext_lazy("red&♥ros%#red"), "red&%E2%99%A5ros%#red"),
        ]

        for iri, uri in cases:
            with self.subTest(iri):
                self.assertEqual(iri_to_uri(iri), uri)

                # Test idempotency.
                self.assertEqual(iri_to_uri(iri_to_uri(iri)), uri)

    def test_uri_to_iri(self):
        """

        Tests the conversion of a URI to an IRI.

        This test case covers various input scenarios, including URIs with encoded characters,
        to ensure the correctness of the uri_to_iri function. It verifies that the conversion
        produces the expected IRI output and also checks the idempotence of the function,
        i.e., applying the conversion twice yields the same result as applying it once.

        """
        cases = [
            (None, None),
            # Valid UTF-8 sequences are decoded.
            ("/%e2%89%Ab%E2%99%a5%E2%89%aB/", "/≫♥≫/"),
            ("/%E2%99%A5%E2%99%A5/?utf8=%E2%9C%93", "/♥♥/?utf8=✓"),
            ("/%41%5a%6B/", "/AZk/"),
            # Reserved and non-URL valid ASCII chars are not decoded.
            ("/%25%20%02%41%7b/", "/%25%20%02A%7b/"),
            # Broken UTF-8 sequences remain escaped.
            ("/%AAd%AAj%AAa%AAn%AAg%AAo%AA/", "/%AAd%AAj%AAa%AAn%AAg%AAo%AA/"),
            ("/%E2%99%A5%E2%E2%99%A5/", "/♥%E2♥/"),
            ("/%E2%99%A5%E2%99%E2%99%A5/", "/♥%E2%99♥/"),
            ("/%E2%E2%99%A5%E2%99%A5%99/", "/%E2♥♥%99/"),
            (
                "/%E2%99%A5%E2%99%A5/?utf8=%9C%93%E2%9C%93%9C%93",
                "/♥♥/?utf8=%9C%93✓%9C%93",
            ),
        ]

        for uri, iri in cases:
            with self.subTest(uri):
                self.assertEqual(uri_to_iri(uri), iri)

                # Test idempotency.
                self.assertEqual(uri_to_iri(uri_to_iri(uri)), iri)

    def test_complementarity(self):
        """
        Test the complementarity of the URI to IRI and IRI to URI conversion functions by verifying that a round-trip conversion between the two formats results in the original input.

        This test case checks the conversion for a variety of URI and IRI inputs, including those containing non-ASCII characters, percent-encoded characters, and edge cases. The test ensures that the conversion functions are working correctly by comparing the results of the round-trip conversions with the original inputs.
        """
        cases = [
            (
                "/blog/for/J%C3%BCrgen%20M%C3%BCnster/",
                "/blog/for/J\xfcrgen%20M\xfcnster/",
            ),
            ("%&", "%&"),
            ("red&%E2%99%A5ros%#red", "red&♥ros%#red"),
            ("/%E2%99%A5%E2%99%A5/", "/♥♥/"),
            ("/%E2%99%A5%E2%99%A5/?utf8=%E2%9C%93", "/♥♥/?utf8=✓"),
            ("/%25%20%02%7b/", "/%25%20%02%7b/"),
            ("/%AAd%AAj%AAa%AAn%AAg%AAo%AA/", "/%AAd%AAj%AAa%AAn%AAg%AAo%AA/"),
            ("/%E2%99%A5%E2%E2%99%A5/", "/♥%E2♥/"),
            ("/%E2%99%A5%E2%99%E2%99%A5/", "/♥%E2%99♥/"),
            ("/%E2%E2%99%A5%E2%99%A5%99/", "/%E2♥♥%99/"),
            (
                "/%E2%99%A5%E2%99%A5/?utf8=%9C%93%E2%9C%93%9C%93",
                "/♥♥/?utf8=%9C%93✓%9C%93",
            ),
        ]

        for uri, iri in cases:
            with self.subTest(uri):
                self.assertEqual(iri_to_uri(uri_to_iri(uri)), uri)
                self.assertEqual(uri_to_iri(iri_to_uri(iri)), iri)

    def test_escape_uri_path(self):
        cases = [
            (
                "/;some/=awful/?path/:with/@lots/&of/+awful/chars",
                "/%3Bsome/%3Dawful/%3Fpath/:with/@lots/&of/+awful/chars",
            ),
            ("/foo#bar", "/foo%23bar"),
            ("/foo?bar", "/foo%3Fbar"),
        ]
        for uri, expected in cases:
            with self.subTest(uri):
                self.assertEqual(escape_uri_path(uri), expected)
