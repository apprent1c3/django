from datetime import timedelta

from django.core import signing
from django.http import HttpRequest, HttpResponse
from django.test import SimpleTestCase, override_settings
from django.test.utils import freeze_time


class SignedCookieTest(SimpleTestCase):
    def test_can_set_and_read_signed_cookies(self):
        """
        Tests the ability to set and read signed cookies, ensuring that cookies can be securely stored and retrieved with their values intact.
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
        Tests the functionality of setting and retrieving a signed cookie with a specified salt value, ensuring that the signature is validated correctly and that an invalid salt results in a BadSignature error.
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
        Tests that tampering with a signed cookie is properly detected and results in a BadSignature exception being raised.
        """
        response = HttpResponse()
        response.set_signed_cookie("c", "hello")
        request = HttpRequest()
        request.COOKIES["c"] = response.cookies["c"].value[:-2] + "$$"
        with self.assertRaises(signing.BadSignature):
            request.get_signed_cookie("c")

    def test_default_argument_suppresses_exceptions(self):
        """
        Tests that a default value is returned when getting a signed cookie that has been tampered with, instead of raising an exception.
        """
        response = HttpResponse()
        response.set_signed_cookie("c", "hello")
        request = HttpRequest()
        request.COOKIES["c"] = response.cookies["c"].value[:-2] + "$$"
        self.assertIsNone(request.get_signed_cookie("c", default=None))

    def test_max_age_argument(self):
        """
        Tests that the max_age argument of get_signed_cookie works correctly, 
            verifying that the function raises a SignatureExpired exception when 
            the cookie's age exceeds the specified maximum age and returns the 
            cookie's value when the age is within the limit.
        """
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
        Tests that the max_age parameter of set_signed_cookie is correctly set for signed cookies, covering both integer and timedelta inputs.
        """
        response = HttpResponse()
        response.set_signed_cookie("c", "value", max_age=100)
        self.assertEqual(response.cookies["c"]["max-age"], 100)
        response.set_signed_cookie("d", "value", max_age=timedelta(hours=2))
        self.assertEqual(response.cookies["d"]["max-age"], 7200)

    @override_settings(SECRET_KEY=b"\xe7")
    def test_signed_cookies_with_binary_key(self):
        """
        Tests the handling of signed cookies when a binary secret key is used, verifying that session data can be successfully encoded and decoded without errors.
        """
        response = HttpResponse()
        response.set_signed_cookie("c", "hello")

        request = HttpRequest()
        request.COOKIES["c"] = response.cookies["c"].value
        self.assertEqual(request.get_signed_cookie("c"), "hello")
