from datetime import timedelta

from django.core import signing
from django.http import HttpRequest, HttpResponse
from django.test import SimpleTestCase, override_settings
from django.test.utils import freeze_time


class SignedCookieTest(SimpleTestCase):
    def test_can_set_and_read_signed_cookies(self):
        """
        Tests the functionality of setting and reading signed cookies.

            This test case verifies that a signed cookie can be set in an HTTP response
            and then successfully retrieved from an HTTP request. It checks that the 
            signed cookie is properly formatted and that its value can be correctly 
            decrypted and returned. The goal is to ensure the integrity and security 
            of cookie data by validating the signing and verification process.

        """
        response = HttpResponse()
        response.set_signed_cookie("c", "hello")
        self.assertIn("c", response.cookies)
        self.assertTrue(response.cookies["c"].value.startswith("hello:"))
        request = HttpRequest()
        request.COOKIES["c"] = response.cookies["c"].value
        value = request.get_signed_cookie("c")
        self.assertEqual(value, "hello")

    def test_can_use_salt(self):
        """
        Tests the functionality of using a salt value when setting and retrieving signed cookies.

        Verifies that a signed cookie set with a specific salt value can be successfully retrieved using the same salt value, 
        and that attempting to retrieve the cookie with a different salt value results in a BadSignature exception.
        """
        response = HttpResponse()
        response.set_signed_cookie("a", "hello", salt="one")
        request = HttpRequest()
        request.COOKIES["a"] = response.cookies["a"].value
        value = request.get_signed_cookie("a", salt="one")
        self.assertEqual(value, "hello")
        with self.assertRaises(signing.BadSignature):
            request.get_signed_cookie("a", salt="two")

    def test_detects_tampering(self):
        """
        Checks if the function correctly detects tampering with a signed cookie. 
        Verifies that a request with a tampered signed cookie raises a BadSignature exception, ensuring the security of signed cookies by preventing the use of altered cookie values.
        """
        response = HttpResponse()
        response.set_signed_cookie("c", "hello")
        request = HttpRequest()
        request.COOKIES["c"] = response.cookies["c"].value[:-2] + "$$"
        with self.assertRaises(signing.BadSignature):
            request.get_signed_cookie("c")

    def test_default_argument_suppresses_exceptions(self):
        response = HttpResponse()
        response.set_signed_cookie("c", "hello")
        request = HttpRequest()
        request.COOKIES["c"] = response.cookies["c"].value[:-2] + "$$"
        self.assertIsNone(request.get_signed_cookie("c", default=None))

    def test_max_age_argument(self):
        value = "hello"
        with freeze_time(123456789):
            response = HttpResponse()
            response.set_signed_cookie("c", value)
            request = HttpRequest()
            request.COOKIES["c"] = response.cookies["c"].value
            self.assertEqual(request.get_signed_cookie("c"), value)

        with freeze_time(123456800):
            self.assertEqual(request.get_signed_cookie("c", max_age=12), value)
            self.assertEqual(request.get_signed_cookie("c", max_age=11), value)
            self.assertEqual(
                request.get_signed_cookie("c", max_age=timedelta(seconds=11)), value
            )
            with self.assertRaises(signing.SignatureExpired):
                request.get_signed_cookie("c", max_age=10)
            with self.assertRaises(signing.SignatureExpired):
                request.get_signed_cookie("c", max_age=timedelta(seconds=10))

    def test_set_signed_cookie_max_age_argument(self):
        """
        Tests the set_signed_cookie method to verify that the max_age argument is correctly applied to a signed cookie.

        The function checks the max-age attribute of the cookie after setting it with both an integer value, representing seconds, and a timedelta object, representing a duration. It ensures that the max-age is correctly calculated and set in the response cookies.
        """
        response = HttpResponse()
        response.set_signed_cookie("c", "value", max_age=100)
        self.assertEqual(response.cookies["c"]["max-age"], 100)
        response.set_signed_cookie("d", "value", max_age=timedelta(hours=2))
        self.assertEqual(response.cookies["d"]["max-age"], 7200)

    @override_settings(SECRET_KEY=b"\xe7")
    def test_signed_cookies_with_binary_key(self):
        """

        Tests the functionality of signed cookies when using a binary secret key.

        This test case verifies that cookies can be successfully signed and verified
        when the SECRET_KEY setting is a binary value. It checks that a cookie signed
        with this key can be correctly decrypted and its original value retrieved.

        The test covers the full cycle of cookie signing and verification, including
        setting a signed cookie in an HttpResponse object, and then retrieving its
        value from an HttpRequest object.

        """
        response = HttpResponse()
        response.set_signed_cookie("c", "hello")

        request = HttpRequest()
        request.COOKIES["c"] = response.cookies["c"].value
        self.assertEqual(request.get_signed_cookie("c"), "hello")
