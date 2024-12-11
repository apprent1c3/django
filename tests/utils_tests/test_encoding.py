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
        s = SimpleLazyObject(lambda: "x")
        self.assertIs(type(force_str(s)), str)

    def test_force_str_DjangoUnicodeDecodeError(self):
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
        error_msg = "This is an exception, voilà".encode()
        result = force_bytes(error_msg, encoding="ascii", errors="ignore")
        self.assertEqual(result, b"This is an exception, voil")

    def test_force_bytes_memory_view(self):
        data = b"abc"
        result = force_bytes(memoryview(data))
        # Type check is needed because memoryview(bytes) == bytes.
        self.assertIs(type(result), bytes)
        self.assertEqual(result, data)

    def test_smart_bytes(self):
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
        Tests the functionality of the smart_str function, which is designed to handle different types of input and return a string representation.

        The function checks that the smart_str function correctly handles various types of input, including lazy translation functions, custom objects with a defined string representation, integers, and strings. It verifies that the output is as expected in each case, ensuring that the function behaves consistently and correctly across different input types.

        The tests cover the following scenarios:
        - Lazy translation functions are left unchanged.
        - Custom objects with a defined string representation return the expected string.
        - Integers and strings are converted to their string representations.
        The purpose of this test is to ensure that the smart_str function works as intended, providing a reliable way to obtain a string representation from different types of input, which is essential for tasks such as internationalization and logging.
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
        """
        Tests the repercent_broken_unicode function to ensure it correctly handles broken Unicode characters.

        This test case verifies the function's ability to properly quote Unicode characters
        in small fragments of data. The expected output is a bytes object where all broken
        Unicode characters are correctly percent-encoded.

        Additionally, the test checks the quotation paths of the function by mocking the quote
        function and verifying the decoded paths that are being quoted. This ensures the
        function is correctly handling the data as it is being processed.

        :returns: None
        :raises: AssertionError if the function does not produce the expected output or quotation paths
        """
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

        Converts a filepath to a URI.

        This function takes a filepath as input, which can be a string or a Path object, 
        and returns a URI string. The filepath is url-encoded to ensure that special 
        characters are properly escaped.

        If the input is None, the function returns None. The function also handles 
        both Unix and Windows-style path separators, and will always return a URI 
        with Unix-style path separators.

        The resulting URI is suitable for use in a URL or other context where a 
        normalized filepath is required. 

        """
        self.assertIsNone(filepath_to_uri(None))
        self.assertEqual(
            filepath_to_uri("upload\\чубака.mp4"),
            "upload/%D1%87%D1%83%D0%B1%D0%B0%D0%BA%D0%B0.mp4",
        )
        self.assertEqual(filepath_to_uri(Path("upload/test.png")), "upload/test.png")
        self.assertEqual(filepath_to_uri(Path("upload\\test.png")), "upload/test.png")

    def test_iri_to_uri(self):
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
