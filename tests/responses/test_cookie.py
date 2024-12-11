import time
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime as format_datetime_rfc5322
from http import cookies

from django.http import HttpResponse
from django.test import SimpleTestCase
from django.test.utils import freeze_time
from django.utils.http import http_date


class SetCookieTests(SimpleTestCase):
    def test_near_expiration(self):
        """Cookie will expire when a near expiration time is provided."""
        response = HttpResponse()
        # There's a timing weakness in this test; The expected result for
        # max-age requires that there be a very slight difference between the
        # evaluated expiration time and the time evaluated in set_cookie(). If
        # this difference doesn't exist, the cookie time will be 1 second
        # larger. The sleep guarantees that there will be a time difference.
        expires = datetime.now(tz=timezone.utc).replace(tzinfo=None) + timedelta(
            seconds=10
        )
        time.sleep(0.001)
        response.set_cookie("datetime", expires=expires)
        datetime_cookie = response.cookies["datetime"]
        self.assertEqual(datetime_cookie["max-age"], 10)

    def test_aware_expiration(self):
        """set_cookie() accepts an aware datetime as expiration time."""
        response = HttpResponse()
        expires = datetime.now(tz=timezone.utc) + timedelta(seconds=10)
        time.sleep(0.001)
        response.set_cookie("datetime", expires=expires)
        datetime_cookie = response.cookies["datetime"]
        self.assertEqual(datetime_cookie["max-age"], 10)

    def test_create_cookie_after_deleting_cookie(self):
        """Setting a cookie after deletion clears the expiry date."""
        response = HttpResponse()
        response.set_cookie("c", "old-value")
        self.assertEqual(response.cookies["c"]["expires"], "")
        response.delete_cookie("c")
        self.assertEqual(
            response.cookies["c"]["expires"], "Thu, 01 Jan 1970 00:00:00 GMT"
        )
        response.set_cookie("c", "new-value")
        self.assertEqual(response.cookies["c"]["expires"], "")

    def test_far_expiration(self):
        """Cookie will expire when a distant expiration time is provided."""
        response = HttpResponse()
        future_datetime = datetime(
            date.today().year + 2, 1, 1, 4, 5, 6, tzinfo=timezone.utc
        )
        response.set_cookie("datetime", expires=future_datetime)
        datetime_cookie = response.cookies["datetime"]
        self.assertIn(
            datetime_cookie["expires"],
            # assertIn accounts for slight time dependency (#23450)
            (
                format_datetime_rfc5322(future_datetime, usegmt=True),
                format_datetime_rfc5322(future_datetime.replace(second=7), usegmt=True),
            ),
        )

    def test_max_age_expiration(self):
        """Cookie will expire if max_age is provided."""
        response = HttpResponse()
        set_cookie_time = time.time()
        with freeze_time(set_cookie_time):
            response.set_cookie("max_age", max_age=10)
        max_age_cookie = response.cookies["max_age"]
        self.assertEqual(max_age_cookie["max-age"], 10)
        self.assertEqual(max_age_cookie["expires"], http_date(set_cookie_time + 10))

    def test_max_age_int(self):
        """
        Tests that the 'max-age' attribute of a cookie is set to an integer value.

        Verifies that a floating-point value passed to the 'max_age' parameter of set_cookie
        is truncated to the nearest integer when constructing the 'Set-Cookie' header.

        This ensures that the resulting cookie is sent with a valid 'max-age' directive,
        as required by the HTTP cookie specification.
        """
        response = HttpResponse()
        response.set_cookie("max_age", max_age=10.6)
        self.assertEqual(response.cookies["max_age"]["max-age"], 10)

    def test_max_age_timedelta(self):
        """
        Tests that the max-age attribute of a cookie is correctly converted to seconds when a timedelta object is used.

        The function verifies that setting a cookie with a max-age of 1 hour results in a 'max-age' value of 3600 seconds in the cookie.

        """
        response = HttpResponse()
        response.set_cookie("max_age", max_age=timedelta(hours=1))
        self.assertEqual(response.cookies["max_age"]["max-age"], 3600)

    def test_max_age_with_expires(self):
        response = HttpResponse()
        msg = "'expires' and 'max_age' can't be used together."
        with self.assertRaisesMessage(ValueError, msg):
            response.set_cookie(
                "max_age", expires=datetime(2000, 1, 1), max_age=timedelta(hours=1)
            )

    def test_httponly_cookie(self):
        """
        Tests that an HTTP-only cookie is correctly set in an HTTP response.

        This function verifies that a cookie with the 'httponly' flag is properly included in an HttpResponse object.
        It checks that the 'httponly' attribute is correctly added to the cookie and that its value is set to True.
        The purpose of this test is to ensure that the 'httponly' flag is set as expected, which is a security feature that helps prevent JavaScript access to sensitive cookies.
        """
        response = HttpResponse()
        response.set_cookie("example", httponly=True)
        example_cookie = response.cookies["example"]
        self.assertIn(
            "; %s" % cookies.Morsel._reserved["httponly"], str(example_cookie)
        )
        self.assertIs(example_cookie["httponly"], True)

    def test_unicode_cookie(self):
        """HttpResponse.set_cookie() works with Unicode data."""
        response = HttpResponse()
        cookie_value = "清風"
        response.set_cookie("test", cookie_value)
        self.assertEqual(response.cookies["test"].value, cookie_value)

    def test_samesite(self):
        """

        Tests setting the 'SameSite' attribute of a cookie in an HTTP response.

        The 'SameSite' attribute is used to declare whether a cookie should be restricted
        to a first-party or same-site context. This test covers the three possible values
        of the 'SameSite' attribute: 'None', 'Lax', and 'Strict'.

        Verifies that each of these values can be successfully set on a cookie and that
        the resulting cookie attribute matches the expected value.

        """
        response = HttpResponse()
        response.set_cookie("example", samesite="None")
        self.assertEqual(response.cookies["example"]["samesite"], "None")
        response.set_cookie("example", samesite="Lax")
        self.assertEqual(response.cookies["example"]["samesite"], "Lax")
        response.set_cookie("example", samesite="strict")
        self.assertEqual(response.cookies["example"]["samesite"], "strict")

    def test_invalid_samesite(self):
        msg = 'samesite must be "lax", "none", or "strict".'
        with self.assertRaisesMessage(ValueError, msg):
            HttpResponse().set_cookie("example", samesite="invalid")


class DeleteCookieTests(SimpleTestCase):
    def test_default(self):
        """

        Tests the behavior of deleting a cookie using the HttpResponse object.

        Specifically, this test verifies that when a cookie is deleted, its attributes
        are set to the expected values, including the expiration date, maximum age,
        path, security, domain, and same-site policy. The test ensures that the
        deleted cookie is properly configured to be removed by the client.

        """
        response = HttpResponse()
        response.delete_cookie("c")
        cookie = response.cookies["c"]
        self.assertEqual(cookie["expires"], "Thu, 01 Jan 1970 00:00:00 GMT")
        self.assertEqual(cookie["max-age"], 0)
        self.assertEqual(cookie["path"], "/")
        self.assertEqual(cookie["secure"], "")
        self.assertEqual(cookie["domain"], "")
        self.assertEqual(cookie["samesite"], "")

    def test_delete_cookie_secure_prefix(self):
        """
        delete_cookie() sets the secure flag if the cookie name starts with
        __Host- or __Secure- (without that, browsers ignore cookies with those
        prefixes).
        """
        response = HttpResponse()
        for prefix in ("Secure", "Host"):
            with self.subTest(prefix=prefix):
                cookie_name = "__%s-c" % prefix
                response.delete_cookie(cookie_name)
                self.assertIs(response.cookies[cookie_name]["secure"], True)

    def test_delete_cookie_secure_samesite_none(self):
        # delete_cookie() sets the secure flag if samesite='none'.
        """

        Tests that deleting a cookie with SameSite=None sets the Secure attribute.

        This test case verifies that when a cookie is deleted with the SameSite attribute set to 'none', 
        the Secure attribute is automatically set to True to maintain the cookie's security.

        """
        response = HttpResponse()
        response.delete_cookie("c", samesite="none")
        self.assertIs(response.cookies["c"]["secure"], True)

    def test_delete_cookie_samesite(self):
        response = HttpResponse()
        response.delete_cookie("c", samesite="lax")
        self.assertEqual(response.cookies["c"]["samesite"], "lax")
