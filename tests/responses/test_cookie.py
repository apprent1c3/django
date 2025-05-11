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
        """
        Tests that a cookie's expiration time is set correctly when a near expiration time is provided.
        """
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
        """
        Tests that the set_cookie method correctly handles an aware datetime object as the expiration time, verifying that the resulting cookie's max-age is set to the expected value.
        """
        response = HttpResponse()
        expires = datetime.now(tz=timezone.utc) + timedelta(seconds=10)
        time.sleep(0.001)
        response.set_cookie("datetime", expires=expires)
        datetime_cookie = response.cookies["datetime"]
        self.assertEqual(datetime_cookie["max-age"], 10)

    def test_create_cookie_after_deleting_cookie(self):
        """
        Verifies that setting a cookie after it has been deleted results in the expiry date being cleared.
        """
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
        """
        Tests that a cookie is correctly set to expire at a distant future time. Verifies the cookie's expiration time matches the provided future datetime in the HTTP response.
        """
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
        """
        Tests that setting a cookie's max-age attribute causes it to expire after the specified time.
        """
        response = HttpResponse()
        set_cookie_time = time.time()
        with freeze_time(set_cookie_time):
            response.set_cookie("max_age", max_age=10)
        max_age_cookie = response.cookies["max_age"]
        self.assertEqual(max_age_cookie["max-age"], 10)
        self.assertEqual(max_age_cookie["expires"], http_date(set_cookie_time + 10))

    def test_max_age_int(self):
        response = HttpResponse()
        response.set_cookie("max_age", max_age=10.6)
        self.assertEqual(response.cookies["max_age"]["max-age"], 10)

    def test_max_age_timedelta(self):
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
        Verifies that an HttpOnly cookie is correctly set and configured in an HttpResponse.\"\"\"
        ```
        """
        response = HttpResponse()
        response.set_cookie("example", httponly=True)
        example_cookie = response.cookies["example"]
        self.assertIn(
            "; %s" % cookies.Morsel._reserved["httponly"], str(example_cookie)
        )
        self.assertIs(example_cookie["httponly"], True)

    def test_unicode_cookie(self):
        """
        Tests that HttpResponse.set_cookie() can handle Unicode values, ensuring cookies can be set with non-ASCII characters.
        """
        response = HttpResponse()
        cookie_value = "清風"
        response.set_cookie("test", cookie_value)
        self.assertEqual(response.cookies["test"].value, cookie_value)

    def test_samesite(self):
        """

        Tests the functionality of setting the SameSite attribute of a cookie in an HTTP response.
        Verifies that the attribute can be successfully set to 'None', 'Lax', and 'Strict' values.

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
        Tests the default behavior of deleting a cookie in an HTTP response.

        Verifies that the deleted cookie has its expiration date set to the past,
        a zero max-age, and default settings for path, security, domain, and same-site attributes.
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
        Tests that the delete_cookie method sets the secure flag for cookies with names prefixed with '__Host-' or '__Secure-'.
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
        response = HttpResponse()
        response.delete_cookie("c", samesite="lax")
        self.assertEqual(response.cookies["c"]["samesite"], "lax")
