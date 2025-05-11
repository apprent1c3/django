from datetime import timedelta

from django.core import signing
from django.http import HttpRequest, HttpResponse
from django.test import SimpleTestCase, override_settings
from django.test.utils import freeze_time


class SignedCookieTest(SimpleTestCase):
    def test_can_set_and_read_signed_cookies(self):
        """
        Tests setting and reading of signed cookies to ensure data integrity.

        Verifies that a cookie can be set with a signature, and subsequently read with the signature verified,
        returning the original cookie value if the signature is valid.
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

        Tests the functionality of signed cookies, specifically the usage of salt values.
        Verifies that a signed cookie can be set and retrieved correctly when using the same salt,
        and that attempting to retrieve the cookie with a different salt results in a BadSignature error.

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
        Tests that a tampered signed cookie raises a BadSignature exception when retrieved.
        """
        response = HttpResponse()
        response.set_signed_cookie("c", "hello")
        request = HttpRequest()
        request.COOKIES["c"] = response.cookies["c"].value[:-2] + "$$"
        with self.assertRaises(signing.BadSignature):
            request.get_signed_cookie("c")

    def test_default_argument_suppresses_exceptions(self):
        """
        Tests that setting a default value for get_signed_cookie suppresses raised exceptions when the cookie signature is invalid.
        """
        response = HttpResponse()
        response.set_signed_cookie("c", "hello")
        request = HttpRequest()
        request.COOKIES["c"] = response.cookies["c"].value[:-2] + "$$"
        self.assertIsNone(request.get_signed_cookie("c", default=None))

    def test_max_age_argument(self):
        """
        Tests the get_signed_cookie function's max_age argument, verifying that it correctly validates the age of a signed cookie and raises a SignatureExpired exception when the cookie is older than the specified maximum age.
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
        Tests the set_signed_cookie method to ensure it correctly sets the max-age attribute of a signed cookie when provided with either an integer or a timedelta object.
        """
        response = HttpResponse()
        response.set_signed_cookie("c", "value", max_age=100)
        self.assertEqual(response.cookies["c"]["max-age"], 100)
        response.set_signed_cookie("d", "value", max_age=timedelta(hours=2))
        self.assertEqual(response.cookies["d"]["max-age"], 7200)

    @override_settings(SECRET_KEY=b"\xe7")
    def test_signed_cookies_with_binary_key(self):
        """

        Tests the functionality of setting and getting signed cookies with a binary secret key.

        Verifies that a cookie can be successfully signed and verified using a binary secret key.

        """
        response = HttpResponse()
        response.set_signed_cookie("c", "hello")

        request = HttpRequest()
        request.COOKIES["c"] = response.cookies["c"].value
        self.assertEqual(request.get_signed_cookie("c"), "hello")
