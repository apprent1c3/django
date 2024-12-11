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

        Tests that the max-age attribute of a cookie is set to an integer value.

        Verifies that when a floating point number is passed to the max-age parameter
        of the set_cookie method, it is truncated to the nearest integer.

        Ensures that the max-age attribute of the resulting cookie is set correctly,
        performing an assertion to confirm the expected behavior.

        """
        response = HttpResponse()
        response.set_cookie("max_age", max_age=10.6)
        self.assertEqual(response.cookies["max_age"]["max-age"], 10)

    def test_max_age_timedelta(self):
        """
        Tests that the max-age attribute of a cookie is correctly set to the equivalent number of seconds when using a timedelta object for the max_age parameter.

            This test case verifies that the max-age value in the cookie is calculated
            correctly from the provided timedelta object, ensuring that the cookie
            expiration time is set as expected. The test checks for the correct
            conversion of the timedelta object into seconds, which is essential for
            proper cookie expiration handling.
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

        Test the Samesite attribute of an HTTP response cookie.

        This test case verifies that the Samesite attribute of a cookie can be successfully set to different values ('None', 'Lax', 'Strict') and retrieved correctly.

        The test covers the basic functionality of setting and getting the Samesite attribute, ensuring that it behaves as expected and returns the correct values.

        """
        response = HttpResponse()
        response.set_cookie("example", samesite="None")
        self.assertEqual(response.cookies["example"]["samesite"], "None")
        response.set_cookie("example", samesite="Lax")
        self.assertEqual(response.cookies["example"]["samesite"], "Lax")
        response.set_cookie("example", samesite="strict")
        self.assertEqual(response.cookies["example"]["samesite"], "strict")

    def test_invalid_samesite(self):
        """
        Tests that setting an invalid 'samesite' attribute for a cookie raises a ValueError.

        The 'samesite' attribute of a cookie must have one of the following values: 'lax', 'none', or 'strict'.
        Any other value will result in a ValueError being raised, with a message indicating the allowed values.

        This test ensures that the set_cookie method of an HttpResponse object correctly validates the 'samesite' attribute and raises an error for invalid values.
        """
        msg = 'samesite must be "lax", "none", or "strict".'
        with self.assertRaisesMessage(ValueError, msg):
            HttpResponse().set_cookie("example", samesite="invalid")


class DeleteCookieTests(SimpleTestCase):
    def test_default(self):
        """

        Tests that deleting a cookie using HttpResponse results in the expected cookie attributes.

        Specifically, this test verifies that the 'c' cookie's attributes are set as follows:
        - 'expires' is set to the Unix epoch (January 1, 1970, 00:00:00 GMT) to immediately expire the cookie.
        - 'max-age' is set to 0, indicating that the cookie should be deleted.
        - 'path' is set to '/', which is the root path of the domain.
        - 'secure', 'domain', and 'samesite' attributes are not specified.

        The test ensures that deleting a cookie using the HttpResponse object correctly sets these attributes to delete the cookie.

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
        response = HttpResponse()
        response.delete_cookie("c", samesite="none")
        self.assertIs(response.cookies["c"]["secure"], True)

    def test_delete_cookie_samesite(self):
        """
        Tests that deleting a cookie with the samesite attribute set to 'lax' correctly sets the samesite value in the response's cookie. This ensures that cookies marked with the samesite='lax' flag are properly deleted and their attributes are updated accordingly, verifying the expected behavior of the delete_cookie method.
        """
        response = HttpResponse()
        response.delete_cookie("c", samesite="lax")
        self.assertEqual(response.cookies["c"]["samesite"], "lax")
