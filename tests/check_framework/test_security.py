from django.conf import settings
from django.core.checks.messages import Error, Warning
from django.core.checks.security import base, csrf, sessions
from django.core.management.utils import get_random_secret_key
from django.test import SimpleTestCase
from django.test.utils import override_settings
from django.views.generic import View


class CheckSessionCookieSecureTest(SimpleTestCase):
    @override_settings(
        SESSION_COOKIE_SECURE=False,
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=[],
    )
    def test_session_cookie_secure_with_installed_app(self):
        """
        Warn if SESSION_COOKIE_SECURE is off and "django.contrib.sessions" is
        in INSTALLED_APPS.
        """
        self.assertEqual(sessions.check_session_cookie_secure(None), [sessions.W010])

    @override_settings(
        SESSION_COOKIE_SECURE="1",
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=[],
    )
    def test_session_cookie_secure_with_installed_app_truthy(self):
        """SESSION_COOKIE_SECURE must be boolean."""
        self.assertEqual(sessions.check_session_cookie_secure(None), [sessions.W010])

    @override_settings(
        SESSION_COOKIE_SECURE=False,
        INSTALLED_APPS=[],
        MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware"],
    )
    def test_session_cookie_secure_with_middleware(self):
        """
        Warn if SESSION_COOKIE_SECURE is off and
        "django.contrib.sessions.middleware.SessionMiddleware" is in
        MIDDLEWARE.
        """
        self.assertEqual(sessions.check_session_cookie_secure(None), [sessions.W011])

    @override_settings(
        SESSION_COOKIE_SECURE=False,
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware"],
    )
    def test_session_cookie_secure_both(self):
        """
        If SESSION_COOKIE_SECURE is off and we find both the session app and
        the middleware, provide one common warning.
        """
        self.assertEqual(sessions.check_session_cookie_secure(None), [sessions.W012])

    @override_settings(
        SESSION_COOKIE_SECURE=True,
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware"],
    )
    def test_session_cookie_secure_true(self):
        """
        If SESSION_COOKIE_SECURE is on, there's no warning about it.
        """
        self.assertEqual(sessions.check_session_cookie_secure(None), [])


class CheckSessionCookieHttpOnlyTest(SimpleTestCase):
    @override_settings(
        SESSION_COOKIE_HTTPONLY=False,
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=[],
    )
    def test_session_cookie_httponly_with_installed_app(self):
        """
        Warn if SESSION_COOKIE_HTTPONLY is off and "django.contrib.sessions"
        is in INSTALLED_APPS.
        """
        self.assertEqual(sessions.check_session_cookie_httponly(None), [sessions.W013])

    @override_settings(
        SESSION_COOKIE_HTTPONLY="1",
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=[],
    )
    def test_session_cookie_httponly_with_installed_app_truthy(self):
        """SESSION_COOKIE_HTTPONLY must be boolean."""
        self.assertEqual(sessions.check_session_cookie_httponly(None), [sessions.W013])

    @override_settings(
        SESSION_COOKIE_HTTPONLY=False,
        INSTALLED_APPS=[],
        MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware"],
    )
    def test_session_cookie_httponly_with_middleware(self):
        """
        Warn if SESSION_COOKIE_HTTPONLY is off and
        "django.contrib.sessions.middleware.SessionMiddleware" is in
        MIDDLEWARE.
        """
        self.assertEqual(sessions.check_session_cookie_httponly(None), [sessions.W014])

    @override_settings(
        SESSION_COOKIE_HTTPONLY=False,
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware"],
    )
    def test_session_cookie_httponly_both(self):
        """
        If SESSION_COOKIE_HTTPONLY is off and we find both the session app and
        the middleware, provide one common warning.
        """
        self.assertEqual(sessions.check_session_cookie_httponly(None), [sessions.W015])

    @override_settings(
        SESSION_COOKIE_HTTPONLY=True,
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware"],
    )
    def test_session_cookie_httponly_true(self):
        """
        If SESSION_COOKIE_HTTPONLY is on, there's no warning about it.
        """
        self.assertEqual(sessions.check_session_cookie_httponly(None), [])


class CheckCSRFMiddlewareTest(SimpleTestCase):
    @override_settings(MIDDLEWARE=[])
    def test_no_csrf_middleware(self):
        """
        Warn if CsrfViewMiddleware isn't in MIDDLEWARE.
        """
        self.assertEqual(csrf.check_csrf_middleware(None), [csrf.W003])

    @override_settings(MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"])
    def test_with_csrf_middleware(self):
        self.assertEqual(csrf.check_csrf_middleware(None), [])


class CheckCSRFCookieSecureTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"],
        CSRF_COOKIE_SECURE=False,
    )
    def test_with_csrf_cookie_secure_false(self):
        """
        Warn if CsrfViewMiddleware is in MIDDLEWARE but
        CSRF_COOKIE_SECURE isn't True.
        """
        self.assertEqual(csrf.check_csrf_cookie_secure(None), [csrf.W016])

    @override_settings(
        MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"],
        CSRF_COOKIE_SECURE="1",
    )
    def test_with_csrf_cookie_secure_truthy(self):
        """CSRF_COOKIE_SECURE must be boolean."""
        self.assertEqual(csrf.check_csrf_cookie_secure(None), [csrf.W016])

    @override_settings(
        MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"],
        CSRF_USE_SESSIONS=True,
        CSRF_COOKIE_SECURE=False,
    )
    def test_use_sessions_with_csrf_cookie_secure_false(self):
        """
        No warning if CSRF_COOKIE_SECURE isn't True while CSRF_USE_SESSIONS
        is True.
        """
        self.assertEqual(csrf.check_csrf_cookie_secure(None), [])

    @override_settings(MIDDLEWARE=[], CSRF_COOKIE_SECURE=False)
    def test_with_csrf_cookie_secure_false_no_middleware(self):
        """
        No warning if CsrfViewMiddleware isn't in MIDDLEWARE, even if
        CSRF_COOKIE_SECURE is False.
        """
        self.assertEqual(csrf.check_csrf_cookie_secure(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"],
        CSRF_COOKIE_SECURE=True,
    )
    def test_with_csrf_cookie_secure_true(self):
        self.assertEqual(csrf.check_csrf_cookie_secure(None), [])


class CheckSecurityMiddlewareTest(SimpleTestCase):
    @override_settings(MIDDLEWARE=[])
    def test_no_security_middleware(self):
        """
        Warn if SecurityMiddleware isn't in MIDDLEWARE.
        """
        self.assertEqual(base.check_security_middleware(None), [base.W001])

    @override_settings(MIDDLEWARE=["django.middleware.security.SecurityMiddleware"])
    def test_with_security_middleware(self):
        self.assertEqual(base.check_security_middleware(None), [])


class CheckStrictTransportSecurityTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_HSTS_SECONDS=0,
    )
    def test_no_sts(self):
        """
        Warn if SECURE_HSTS_SECONDS isn't > 0.
        """
        self.assertEqual(base.check_sts(None), [base.W004])

    @override_settings(MIDDLEWARE=[], SECURE_HSTS_SECONDS=0)
    def test_no_sts_no_middleware(self):
        """
        Don't warn if SECURE_HSTS_SECONDS isn't > 0 and SecurityMiddleware isn't
        installed.
        """
        self.assertEqual(base.check_sts(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_HSTS_SECONDS=3600,
    )
    def test_with_sts(self):
        self.assertEqual(base.check_sts(None), [])


class CheckStrictTransportSecuritySubdomainsTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_SECONDS=3600,
    )
    def test_no_sts_subdomains(self):
        """
        Warn if SECURE_HSTS_INCLUDE_SUBDOMAINS isn't True.
        """
        self.assertEqual(base.check_sts_include_subdomains(None), [base.W005])

    @override_settings(
        MIDDLEWARE=[],
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_SECONDS=3600,
    )
    def test_no_sts_subdomains_no_middleware(self):
        """
        Don't warn if SecurityMiddleware isn't installed.
        """
        self.assertEqual(base.check_sts_include_subdomains(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_SSL_REDIRECT=False,
        SECURE_HSTS_SECONDS=None,
    )
    def test_no_sts_subdomains_no_seconds(self):
        """
        Don't warn if SECURE_HSTS_SECONDS isn't set.
        """
        self.assertEqual(base.check_sts_include_subdomains(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_SECONDS=3600,
    )
    def test_with_sts_subdomains(self):
        self.assertEqual(base.check_sts_include_subdomains(None), [])


class CheckStrictTransportSecurityPreloadTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_HSTS_PRELOAD=False,
        SECURE_HSTS_SECONDS=3600,
    )
    def test_no_sts_preload(self):
        """
        Warn if SECURE_HSTS_PRELOAD isn't True.
        """
        self.assertEqual(base.check_sts_preload(None), [base.W021])

    @override_settings(
        MIDDLEWARE=[], SECURE_HSTS_PRELOAD=False, SECURE_HSTS_SECONDS=3600
    )
    def test_no_sts_preload_no_middleware(self):
        """
        Don't warn if SecurityMiddleware isn't installed.
        """
        self.assertEqual(base.check_sts_preload(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_SSL_REDIRECT=False,
        SECURE_HSTS_SECONDS=None,
    )
    def test_no_sts_preload_no_seconds(self):
        """
        Don't warn if SECURE_HSTS_SECONDS isn't set.
        """
        self.assertEqual(base.check_sts_preload(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_HSTS_PRELOAD=True,
        SECURE_HSTS_SECONDS=3600,
    )
    def test_with_sts_preload(self):
        self.assertEqual(base.check_sts_preload(None), [])


class CheckXFrameOptionsMiddlewareTest(SimpleTestCase):
    @override_settings(MIDDLEWARE=[])
    def test_middleware_not_installed(self):
        """
        Warn if XFrameOptionsMiddleware isn't in MIDDLEWARE.
        """
        self.assertEqual(base.check_xframe_options_middleware(None), [base.W002])

    @override_settings(
        MIDDLEWARE=["django.middleware.clickjacking.XFrameOptionsMiddleware"]
    )
    def test_middleware_installed(self):
        self.assertEqual(base.check_xframe_options_middleware(None), [])


class CheckXFrameOptionsDenyTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.clickjacking.XFrameOptionsMiddleware"],
        X_FRAME_OPTIONS="SAMEORIGIN",
    )
    def test_x_frame_options_not_deny(self):
        """
        Warn if XFrameOptionsMiddleware is in MIDDLEWARE but
        X_FRAME_OPTIONS isn't 'DENY'.
        """
        self.assertEqual(base.check_xframe_deny(None), [base.W019])

    @override_settings(MIDDLEWARE=[], X_FRAME_OPTIONS="SAMEORIGIN")
    def test_middleware_not_installed(self):
        """
        No error if XFrameOptionsMiddleware isn't in MIDDLEWARE even if
        X_FRAME_OPTIONS isn't 'DENY'.
        """
        self.assertEqual(base.check_xframe_deny(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.clickjacking.XFrameOptionsMiddleware"],
        X_FRAME_OPTIONS="DENY",
    )
    def test_xframe_deny(self):
        self.assertEqual(base.check_xframe_deny(None), [])


class CheckContentTypeNosniffTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_CONTENT_TYPE_NOSNIFF=False,
    )
    def test_no_content_type_nosniff(self):
        """
        Warn if SECURE_CONTENT_TYPE_NOSNIFF isn't True.
        """
        self.assertEqual(base.check_content_type_nosniff(None), [base.W006])

    @override_settings(MIDDLEWARE=[], SECURE_CONTENT_TYPE_NOSNIFF=False)
    def test_no_content_type_nosniff_no_middleware(self):
        """
        Don't warn if SECURE_CONTENT_TYPE_NOSNIFF isn't True and
        SecurityMiddleware isn't in MIDDLEWARE.
        """
        self.assertEqual(base.check_content_type_nosniff(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_CONTENT_TYPE_NOSNIFF=True,
    )
    def test_with_content_type_nosniff(self):
        self.assertEqual(base.check_content_type_nosniff(None), [])


class CheckSSLRedirectTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_SSL_REDIRECT=False,
    )
    def test_no_ssl_redirect(self):
        """
        Warn if SECURE_SSL_REDIRECT isn't True.
        """
        self.assertEqual(base.check_ssl_redirect(None), [base.W008])

    @override_settings(MIDDLEWARE=[], SECURE_SSL_REDIRECT=False)
    def test_no_ssl_redirect_no_middleware(self):
        """
        Don't warn if SECURE_SSL_REDIRECT is False and SecurityMiddleware isn't
        installed.
        """
        self.assertEqual(base.check_ssl_redirect(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_SSL_REDIRECT=True,
    )
    def test_with_ssl_redirect(self):
        self.assertEqual(base.check_ssl_redirect(None), [])


class CheckSecretKeyTest(SimpleTestCase):
    @override_settings(SECRET_KEY=("abcdefghijklmnopqrstuvwx" * 2) + "ab")
    def test_okay_secret_key(self):
        """
        Tests that the SECRET_KEY setting is valid.

        The SECRET_KEY is checked to ensure it meets the minimum length requirement and contains a sufficient number of unique characters.
        If the SECRET_KEY is valid, the function should not return any errors.

        Checks performed:
            - Minimum length of SECRET_KEY
            - Minimum number of unique characters in SECRET_KEY

        This test is useful to ensure the SECRET_KEY is properly configured and secure, helping to prevent potential security issues in the application.
        """
        self.assertEqual(len(settings.SECRET_KEY), base.SECRET_KEY_MIN_LENGTH)
        self.assertGreater(
            len(set(settings.SECRET_KEY)), base.SECRET_KEY_MIN_UNIQUE_CHARACTERS
        )
        self.assertEqual(base.check_secret_key(None), [])

    @override_settings(SECRET_KEY="")
    def test_empty_secret_key(self):
        self.assertEqual(base.check_secret_key(None), [base.W009])

    @override_settings(SECRET_KEY=None)
    def test_missing_secret_key(self):
        del settings.SECRET_KEY
        self.assertEqual(base.check_secret_key(None), [base.W009])

    @override_settings(SECRET_KEY=None)
    def test_none_secret_key(self):
        self.assertEqual(base.check_secret_key(None), [base.W009])

    @override_settings(
        SECRET_KEY=base.SECRET_KEY_INSECURE_PREFIX + get_random_secret_key()
    )
    def test_insecure_secret_key(self):
        self.assertEqual(base.check_secret_key(None), [base.W009])

    @override_settings(SECRET_KEY=("abcdefghijklmnopqrstuvwx" * 2) + "a")
    def test_low_length_secret_key(self):
        """
        Tests the behavior of the application when the SECRET_KEY setting is shorter than the minimum allowed length. 
        Verifies that the SECRET_KEY is correctly identified as being too short by the check_secret_key function. 
        Specifically, it checks that the function returns the W009 warning message, indicating a secret key that is too short.
        """
        self.assertEqual(len(settings.SECRET_KEY), base.SECRET_KEY_MIN_LENGTH - 1)
        self.assertEqual(base.check_secret_key(None), [base.W009])

    @override_settings(SECRET_KEY="abcd" * 20)
    def test_low_entropy_secret_key(self):
        """

        Tests that a secret key with low entropy triggers the corresponding warning.

        This test case checks that a secret key with insufficient unique characters, 
        although it meets the minimum length requirement, correctly raises a warning.
        The secret key used in this test has a low entropy due to repetition of the same characters.

        """
        self.assertGreater(len(settings.SECRET_KEY), base.SECRET_KEY_MIN_LENGTH)
        self.assertLess(
            len(set(settings.SECRET_KEY)), base.SECRET_KEY_MIN_UNIQUE_CHARACTERS
        )
        self.assertEqual(base.check_secret_key(None), [base.W009])


class CheckSecretKeyFallbacksTest(SimpleTestCase):
    @override_settings(SECRET_KEY_FALLBACKS=[("abcdefghijklmnopqrstuvwx" * 2) + "ab"])
    def test_okay_secret_key_fallbacks(self):
        """
        Tests the use of secret key fallbacks with a valid key.

        This test case verifies that when a valid secret key fallback is provided, 
        it meets the minimum length and uniqueness requirements. It also checks 
        that no errors are raised when checking the secret key fallbacks.

        The test confirms that the length of the secret key fallback is at least 
        as long as the minimum required, and that it contains a minimum number 
        of unique characters. Additionally, it ensures that the function 
        responsible for checking secret key fallbacks returns an empty list, 
        indicating no errors or warnings, when a valid key is used.
        """
        self.assertEqual(
            len(settings.SECRET_KEY_FALLBACKS[0]),
            base.SECRET_KEY_MIN_LENGTH,
        )
        self.assertGreater(
            len(set(settings.SECRET_KEY_FALLBACKS[0])),
            base.SECRET_KEY_MIN_UNIQUE_CHARACTERS,
        )
        self.assertEqual(base.check_secret_key_fallbacks(None), [])

    def test_no_secret_key_fallbacks(self):
        """
        Tests the behavior of the secret key fallback system when no fallbacks are configured.

        This test case verifies that the system correctly handles the absence of secret key fallbacks and returns the expected warning message.

        The test checks that the :func:`base.check_secret_key_fallbacks` function returns a list containing a single warning when no fallbacks are provided. The warning includes a message indicating that the 'SECRET_KEY_FALLBACKS' setting is not configured, along with a unique warning ID (:const:`base.W025.id`).
        """
        with self.settings(SECRET_KEY_FALLBACKS=None):
            del settings.SECRET_KEY_FALLBACKS
            self.assertEqual(
                base.check_secret_key_fallbacks(None),
                [
                    Warning(base.W025.msg % "SECRET_KEY_FALLBACKS", id=base.W025.id),
                ],
            )

    @override_settings(
        SECRET_KEY_FALLBACKS=[base.SECRET_KEY_INSECURE_PREFIX + get_random_secret_key()]
    )
    def test_insecure_secret_key_fallbacks(self):
        self.assertEqual(
            base.check_secret_key_fallbacks(None),
            [
                Warning(base.W025.msg % "SECRET_KEY_FALLBACKS[0]", id=base.W025.id),
            ],
        )

    @override_settings(SECRET_KEY_FALLBACKS=[("abcdefghijklmnopqrstuvwx" * 2) + "a"])
    def test_low_length_secret_key_fallbacks(self):
        """
        Tests the functionality of secret key fallbacks when the length is less than the minimum required.

         This test case checks if the provided secret key fallback has a length that is less than the minimum length allowed. 
         It verifies that a warning is generated when the secret key fallback's length is insufficient, specifically one character less than the minimum length. 
         The test ensures that the warning message correctly identifies the problematic setting and provides the relevant warning id.
        """
        self.assertEqual(
            len(settings.SECRET_KEY_FALLBACKS[0]),
            base.SECRET_KEY_MIN_LENGTH - 1,
        )
        self.assertEqual(
            base.check_secret_key_fallbacks(None),
            [
                Warning(base.W025.msg % "SECRET_KEY_FALLBACKS[0]", id=base.W025.id),
            ],
        )

    @override_settings(SECRET_KEY_FALLBACKS=["abcd" * 20])
    def test_low_entropy_secret_key_fallbacks(self):
        self.assertGreater(
            len(settings.SECRET_KEY_FALLBACKS[0]),
            base.SECRET_KEY_MIN_LENGTH,
        )
        self.assertLess(
            len(set(settings.SECRET_KEY_FALLBACKS[0])),
            base.SECRET_KEY_MIN_UNIQUE_CHARACTERS,
        )
        self.assertEqual(
            base.check_secret_key_fallbacks(None),
            [
                Warning(base.W025.msg % "SECRET_KEY_FALLBACKS[0]", id=base.W025.id),
            ],
        )

    @override_settings(
        SECRET_KEY_FALLBACKS=[
            ("abcdefghijklmnopqrstuvwx" * 2) + "ab",
            "badkey",
        ]
    )
    def test_multiple_keys(self):
        self.assertEqual(
            base.check_secret_key_fallbacks(None),
            [
                Warning(base.W025.msg % "SECRET_KEY_FALLBACKS[1]", id=base.W025.id),
            ],
        )

    @override_settings(
        SECRET_KEY_FALLBACKS=[
            ("abcdefghijklmnopqrstuvwx" * 2) + "ab",
            "badkey1",
            "badkey2",
        ]
    )
    def test_multiple_bad_keys(self):
        self.assertEqual(
            base.check_secret_key_fallbacks(None),
            [
                Warning(base.W025.msg % "SECRET_KEY_FALLBACKS[1]", id=base.W025.id),
                Warning(base.W025.msg % "SECRET_KEY_FALLBACKS[2]", id=base.W025.id),
            ],
        )


class CheckDebugTest(SimpleTestCase):
    @override_settings(DEBUG=True)
    def test_debug_true(self):
        """
        Warn if DEBUG is True.
        """
        self.assertEqual(base.check_debug(None), [base.W018])

    @override_settings(DEBUG=False)
    def test_debug_false(self):
        self.assertEqual(base.check_debug(None), [])


class CheckAllowedHostsTest(SimpleTestCase):
    @override_settings(ALLOWED_HOSTS=[])
    def test_allowed_hosts_empty(self):
        self.assertEqual(base.check_allowed_hosts(None), [base.W020])

    @override_settings(ALLOWED_HOSTS=[".example.com"])
    def test_allowed_hosts_set(self):
        self.assertEqual(base.check_allowed_hosts(None), [])


class CheckReferrerPolicyTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_REFERRER_POLICY=None,
    )
    def test_no_referrer_policy(self):
        self.assertEqual(base.check_referrer_policy(None), [base.W022])

    @override_settings(MIDDLEWARE=[], SECURE_REFERRER_POLICY=None)
    def test_no_referrer_policy_no_middleware(self):
        """
        Don't warn if SECURE_REFERRER_POLICY is None and SecurityMiddleware
        isn't in MIDDLEWARE.
        """
        self.assertEqual(base.check_referrer_policy(None), [])

    @override_settings(MIDDLEWARE=["django.middleware.security.SecurityMiddleware"])
    def test_with_referrer_policy(self):
        """

        Test the check_referrer_policy function with various referrer policies.

        The function verifies that the check_referrer_policy function returns an empty list
        for different types of referrer policy values, including strings and iterable
        objects. The tests cover various valid formats for the SECURE_REFERRER_POLICY setting.

        The test cases include policies with single and multiple values, with and without
        whitespace, and as strings, tuples, and lists. The function ensures that the
        check_referrer_policy function behaves correctly under different settings.

        """
        tests = (
            "strict-origin",
            "strict-origin,origin",
            "strict-origin, origin",
            ["strict-origin", "origin"],
            ("strict-origin", "origin"),
        )
        for value in tests:
            with (
                self.subTest(value=value),
                override_settings(SECURE_REFERRER_POLICY=value),
            ):
                self.assertEqual(base.check_referrer_policy(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_REFERRER_POLICY="invalid-value",
    )
    def test_with_invalid_referrer_policy(self):
        self.assertEqual(base.check_referrer_policy(None), [base.E023])


def failure_view_with_invalid_signature():
    pass


good_class_based_csrf_failure_view = View.as_view()


class CSRFFailureViewTest(SimpleTestCase):
    @override_settings(CSRF_FAILURE_VIEW="")
    def test_failure_view_import_error(self):
        self.assertEqual(
            csrf.check_csrf_failure_view(None),
            [
                Error(
                    "The CSRF failure view '' could not be imported.",
                    id="security.E102",
                )
            ],
        )

    @override_settings(
        CSRF_FAILURE_VIEW=(
            "check_framework.test_security.failure_view_with_invalid_signature"
        ),
    )
    def test_failure_view_invalid_signature(self):
        msg = (
            "The CSRF failure view "
            "'check_framework.test_security.failure_view_with_invalid_signature' "
            "does not take the correct number of arguments."
        )
        self.assertEqual(
            csrf.check_csrf_failure_view(None),
            [Error(msg, id="security.E101")],
        )

    @override_settings(
        CSRF_FAILURE_VIEW=(
            "check_framework.test_security.good_class_based_csrf_failure_view"
        ),
    )
    def test_failure_view_valid_class_based(self):
        self.assertEqual(csrf.check_csrf_failure_view(None), [])


class CheckCrossOriginOpenerPolicyTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_CROSS_ORIGIN_OPENER_POLICY=None,
    )
    def test_no_coop(self):
        self.assertEqual(base.check_cross_origin_opener_policy(None), [])

    @override_settings(MIDDLEWARE=["django.middleware.security.SecurityMiddleware"])
    def test_with_coop(self):
        tests = ["same-origin", "same-origin-allow-popups", "unsafe-none"]
        for value in tests:
            with (
                self.subTest(value=value),
                override_settings(
                    SECURE_CROSS_ORIGIN_OPENER_POLICY=value,
                ),
            ):
                self.assertEqual(base.check_cross_origin_opener_policy(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_CROSS_ORIGIN_OPENER_POLICY="invalid-value",
    )
    def test_with_invalid_coop(self):
        self.assertEqual(base.check_cross_origin_opener_policy(None), [base.E024])
