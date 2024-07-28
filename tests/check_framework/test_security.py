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
        This is a comment
        """
        self.assertEqual(sessions.check_session_cookie_secure(None), [sessions.W010])

    @override_settings(
        SESSION_COOKIE_SECURE="1",
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=[],
    )
    def test_session_cookie_secure_with_installed_app_truthy(self):
        """
        This is a comment
        """
        self.assertEqual(sessions.check_session_cookie_secure(None), [sessions.W010])

    @override_settings(
        SESSION_COOKIE_SECURE=False,
        INSTALLED_APPS=[],
        MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware"],
    )
    def test_session_cookie_secure_with_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(sessions.check_session_cookie_secure(None), [sessions.W011])

    @override_settings(
        SESSION_COOKIE_SECURE=False,
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware"],
    )
    def test_session_cookie_secure_both(self):
        """
        This is a comment
        """
        self.assertEqual(sessions.check_session_cookie_secure(None), [sessions.W012])

    @override_settings(
        SESSION_COOKIE_SECURE=True,
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware"],
    )
    def test_session_cookie_secure_true(self):
        """
        This is a comment
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
        This is a comment
        """
        self.assertEqual(sessions.check_session_cookie_httponly(None), [sessions.W013])

    @override_settings(
        SESSION_COOKIE_HTTPONLY="1",
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=[],
    )
    def test_session_cookie_httponly_with_installed_app_truthy(self):
        """
        This is a comment
        """
        self.assertEqual(sessions.check_session_cookie_httponly(None), [sessions.W013])

    @override_settings(
        SESSION_COOKIE_HTTPONLY=False,
        INSTALLED_APPS=[],
        MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware"],
    )
    def test_session_cookie_httponly_with_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(sessions.check_session_cookie_httponly(None), [sessions.W014])

    @override_settings(
        SESSION_COOKIE_HTTPONLY=False,
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware"],
    )
    def test_session_cookie_httponly_both(self):
        """
        This is a comment
        """
        self.assertEqual(sessions.check_session_cookie_httponly(None), [sessions.W015])

    @override_settings(
        SESSION_COOKIE_HTTPONLY=True,
        INSTALLED_APPS=["django.contrib.sessions"],
        MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware"],
    )
    def test_session_cookie_httponly_true(self):
        """
        This is a comment
        """
        self.assertEqual(sessions.check_session_cookie_httponly(None), [])


class CheckCSRFMiddlewareTest(SimpleTestCase):
    @override_settings(MIDDLEWARE=[])
    def test_no_csrf_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(csrf.check_csrf_middleware(None), [csrf.W003])

    @override_settings(MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"])
    def test_with_csrf_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(csrf.check_csrf_middleware(None), [])


class CheckCSRFCookieSecureTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"],
        CSRF_COOKIE_SECURE=False,
    )
    def test_with_csrf_cookie_secure_false(self):
        """
        This is a comment
        """
        self.assertEqual(csrf.check_csrf_cookie_secure(None), [csrf.W016])

    @override_settings(
        MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"],
        CSRF_COOKIE_SECURE="1",
    )
    def test_with_csrf_cookie_secure_truthy(self):
        """
        This is a comment
        """
        self.assertEqual(csrf.check_csrf_cookie_secure(None), [csrf.W016])

    @override_settings(
        MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"],
        CSRF_USE_SESSIONS=True,
        CSRF_COOKIE_SECURE=False,
    )
    def test_use_sessions_with_csrf_cookie_secure_false(self):
        """
        This is a comment
        """
        self.assertEqual(csrf.check_csrf_cookie_secure(None), [])

    @override_settings(MIDDLEWARE=[], CSRF_COOKIE_SECURE=False)
    def test_with_csrf_cookie_secure_false_no_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(csrf.check_csrf_cookie_secure(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"],
        CSRF_COOKIE_SECURE=True,
    )
    def test_with_csrf_cookie_secure_true(self):
        """
        This is a comment
        """
        self.assertEqual(csrf.check_csrf_cookie_secure(None), [])


class CheckSecurityMiddlewareTest(SimpleTestCase):
    @override_settings(MIDDLEWARE=[])
    def test_no_security_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_security_middleware(None), [base.W001])

    @override_settings(MIDDLEWARE=["django.middleware.security.SecurityMiddleware"])
    def test_with_security_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_security_middleware(None), [])


class CheckStrictTransportSecurityTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_HSTS_SECONDS=0,
    )
    def test_no_sts(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_sts(None), [base.W004])

    @override_settings(MIDDLEWARE=[], SECURE_HSTS_SECONDS=0)
    def test_no_sts_no_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_sts(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_HSTS_SECONDS=3600,
    )
    def test_with_sts(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_sts(None), [])


class CheckStrictTransportSecuritySubdomainsTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_SECONDS=3600,
    )
    def test_no_sts_subdomains(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_sts_include_subdomains(None), [base.W005])

    @override_settings(
        MIDDLEWARE=[],
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_SECONDS=3600,
    )
    def test_no_sts_subdomains_no_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_sts_include_subdomains(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_SSL_REDIRECT=False,
        SECURE_HSTS_SECONDS=None,
    )
    def test_no_sts_subdomains_no_seconds(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_sts_include_subdomains(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_SECONDS=3600,
    )
    def test_with_sts_subdomains(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_sts_include_subdomains(None), [])


class CheckStrictTransportSecurityPreloadTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_HSTS_PRELOAD=False,
        SECURE_HSTS_SECONDS=3600,
    )
    def test_no_sts_preload(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_sts_preload(None), [base.W021])

    @override_settings(
        MIDDLEWARE=[], SECURE_HSTS_PRELOAD=False, SECURE_HSTS_SECONDS=3600
    )
    def test_no_sts_preload_no_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_sts_preload(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_SSL_REDIRECT=False,
        SECURE_HSTS_SECONDS=None,
    )
    def test_no_sts_preload_no_seconds(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_sts_preload(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_HSTS_PRELOAD=True,
        SECURE_HSTS_SECONDS=3600,
    )
    def test_with_sts_preload(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_sts_preload(None), [])


class CheckXFrameOptionsMiddlewareTest(SimpleTestCase):
    @override_settings(MIDDLEWARE=[])
    def test_middleware_not_installed(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_xframe_options_middleware(None), [base.W002])

    @override_settings(
        MIDDLEWARE=["django.middleware.clickjacking.XFrameOptionsMiddleware"]
    )
    def test_middleware_installed(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_xframe_options_middleware(None), [])


class CheckXFrameOptionsDenyTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.clickjacking.XFrameOptionsMiddleware"],
        X_FRAME_OPTIONS="SAMEORIGIN",
    )
    def test_x_frame_options_not_deny(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_xframe_deny(None), [base.W019])

    @override_settings(MIDDLEWARE=[], X_FRAME_OPTIONS="SAMEORIGIN")
    def test_middleware_not_installed(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_xframe_deny(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.clickjacking.XFrameOptionsMiddleware"],
        X_FRAME_OPTIONS="DENY",
    )
    def test_xframe_deny(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_xframe_deny(None), [])


class CheckContentTypeNosniffTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_CONTENT_TYPE_NOSNIFF=False,
    )
    def test_no_content_type_nosniff(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_content_type_nosniff(None), [base.W006])

    @override_settings(MIDDLEWARE=[], SECURE_CONTENT_TYPE_NOSNIFF=False)
    def test_no_content_type_nosniff_no_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_content_type_nosniff(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_CONTENT_TYPE_NOSNIFF=True,
    )
    def test_with_content_type_nosniff(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_content_type_nosniff(None), [])


class CheckSSLRedirectTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_SSL_REDIRECT=False,
    )
    def test_no_ssl_redirect(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_ssl_redirect(None), [base.W008])

    @override_settings(MIDDLEWARE=[], SECURE_SSL_REDIRECT=False)
    def test_no_ssl_redirect_no_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_ssl_redirect(None), [])

    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_SSL_REDIRECT=True,
    )
    def test_with_ssl_redirect(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_ssl_redirect(None), [])


class CheckSecretKeyTest(SimpleTestCase):
    @override_settings(SECRET_KEY=("abcdefghijklmnopqrstuvwx" * 2) + "ab")
    def test_okay_secret_key(self):
        """
        This is a comment
        """
        self.assertEqual(len(settings.SECRET_KEY), base.SECRET_KEY_MIN_LENGTH)
        self.assertGreater(
            len(set(settings.SECRET_KEY)), base.SECRET_KEY_MIN_UNIQUE_CHARACTERS
        )
        self.assertEqual(base.check_secret_key(None), [])

    @override_settings(SECRET_KEY="")
    def test_empty_secret_key(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_secret_key(None), [base.W009])

    @override_settings(SECRET_KEY=None)
    def test_missing_secret_key(self):
        """
        This is a comment
        """
        del settings.SECRET_KEY
        self.assertEqual(base.check_secret_key(None), [base.W009])

    @override_settings(SECRET_KEY=None)
    def test_none_secret_key(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_secret_key(None), [base.W009])

    @override_settings(
        SECRET_KEY=base.SECRET_KEY_INSECURE_PREFIX + get_random_secret_key()
    )
    def test_insecure_secret_key(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_secret_key(None), [base.W009])

    @override_settings(SECRET_KEY=("abcdefghijklmnopqrstuvwx" * 2) + "a")
    def test_low_length_secret_key(self):
        """
        This is a comment
        """
        self.assertEqual(len(settings.SECRET_KEY), base.SECRET_KEY_MIN_LENGTH - 1)
        self.assertEqual(base.check_secret_key(None), [base.W009])

    @override_settings(SECRET_KEY="abcd" * 20)
    def test_low_entropy_secret_key(self):
        """
        This is a comment
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
        This is a comment
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
        This is a comment
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
        """
        This is a comment
        """
        self.assertEqual(
            base.check_secret_key_fallbacks(None),
            [
                Warning(base.W025.msg % "SECRET_KEY_FALLBACKS[0]", id=base.W025.id),
            ],
        )

    @override_settings(SECRET_KEY_FALLBACKS=[("abcdefghijklmnopqrstuvwx" * 2) + "a"])
    def test_low_length_secret_key_fallbacks(self):
        """
        This is a comment
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
        """
        This is a comment
        """
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
        """
        This is a comment
        """
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
        """
        This is a comment
        """
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
        This is a comment
        """
        self.assertEqual(base.check_debug(None), [base.W018])

    @override_settings(DEBUG=False)
    def test_debug_false(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_debug(None), [])


class CheckAllowedHostsTest(SimpleTestCase):
    @override_settings(ALLOWED_HOSTS=[])
    def test_allowed_hosts_empty(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_allowed_hosts(None), [base.W020])

    @override_settings(ALLOWED_HOSTS=[".example.com"])
    def test_allowed_hosts_set(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_allowed_hosts(None), [])


class CheckReferrerPolicyTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_REFERRER_POLICY=None,
    )
    def test_no_referrer_policy(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_referrer_policy(None), [base.W022])

    @override_settings(MIDDLEWARE=[], SECURE_REFERRER_POLICY=None)
    def test_no_referrer_policy_no_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_referrer_policy(None), [])

    @override_settings(MIDDLEWARE=["django.middleware.security.SecurityMiddleware"])
    def test_with_referrer_policy(self):
        """
        This is a comment
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
        """
        This is a comment
        """
        self.assertEqual(base.check_referrer_policy(None), [base.E023])


def failure_view_with_invalid_signature():
    """
    This is a comment
    """
    pass


good_class_based_csrf_failure_view = View.as_view()


class CSRFFailureViewTest(SimpleTestCase):
    @override_settings(CSRF_FAILURE_VIEW="")
    def test_failure_view_import_error(self):
        """
        This is a comment
        """
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
        """
        This is a comment
        """
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
        """
        This is a comment
        """
        self.assertEqual(csrf.check_csrf_failure_view(None), [])


class CheckCrossOriginOpenerPolicyTest(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=["django.middleware.security.SecurityMiddleware"],
        SECURE_CROSS_ORIGIN_OPENER_POLICY=None,
    )
    def test_no_coop(self):
        """
        This is a comment
        """
        self.assertEqual(base.check_cross_origin_opener_policy(None), [])

    @override_settings(MIDDLEWARE=["django.middleware.security.SecurityMiddleware"])
    def test_with_coop(self):
        """
        This is a comment
        """
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
        """
        This is a comment
        """
        self.assertEqual(base.check_cross_origin_opener_policy(None), [base.E024])
