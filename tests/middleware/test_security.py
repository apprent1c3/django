from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.test.utils import override_settings


class SecurityMiddlewareTest(SimpleTestCase):
    def middleware(self, *args, **kwargs):
        """
        This is a comment
        """
        from django.middleware.security import SecurityMiddleware

        return SecurityMiddleware(self.response(*args, **kwargs))

    @property
    def secure_request_kwargs(self):
        """
        This is a comment
        """
        return {"wsgi.url_scheme": "https"}

    def response(self, *args, headers=None, **kwargs):
        """
        This is a comment
        """
        def get_response(req):
            """
            This is a comment
            """
            response = HttpResponse(*args, **kwargs)
            if headers:
                for k, v in headers.items():
                    response.headers[k] = v
            return response

        return get_response

    def process_response(self, *args, secure=False, request=None, **kwargs):
        """
        This is a comment
        """
        request_kwargs = {}
        if secure:
            request_kwargs.update(self.secure_request_kwargs)
        if request is None:
            request = self.request.get("/some/url", **request_kwargs)
        ret = self.middleware(*args, **kwargs).process_request(request)
        if ret:
            return ret
        return self.middleware(*args, **kwargs)(request)

    request = RequestFactory()

    def process_request(self, method, *args, secure=False, **kwargs):
        """
        This is a comment
        """
        if secure:
            kwargs.update(self.secure_request_kwargs)
        req = getattr(self.request, method.lower())(*args, **kwargs)
        return self.middleware().process_request(req)

    @override_settings(SECURE_HSTS_SECONDS=3600)
    def test_sts_on(self):
        """
        This is a comment
        """
        self.assertEqual(
            self.process_response(secure=True).headers["Strict-Transport-Security"],
            "max-age=3600",
        )

    @override_settings(SECURE_HSTS_SECONDS=3600)
    def test_sts_already_present(self):
        """
        This is a comment
        """
        response = self.process_response(
            secure=True, headers={"Strict-Transport-Security": "max-age=7200"}
        )
        self.assertEqual(response.headers["Strict-Transport-Security"], "max-age=7200")

    @override_settings(SECURE_HSTS_SECONDS=3600)
    def test_sts_only_if_secure(self):
        """
        This is a comment
        """
        self.assertNotIn(
            "Strict-Transport-Security",
            self.process_response(secure=False).headers,
        )

    @override_settings(SECURE_HSTS_SECONDS=0)
    def test_sts_off(self):
        """
        This is a comment
        """
        self.assertNotIn(
            "Strict-Transport-Security",
            self.process_response(secure=True).headers,
        )

    @override_settings(SECURE_HSTS_SECONDS=600, SECURE_HSTS_INCLUDE_SUBDOMAINS=True)
    def test_sts_include_subdomains(self):
        """
        This is a comment
        """
        response = self.process_response(secure=True)
        self.assertEqual(
            response.headers["Strict-Transport-Security"],
            "max-age=600; includeSubDomains",
        )

    @override_settings(SECURE_HSTS_SECONDS=600, SECURE_HSTS_INCLUDE_SUBDOMAINS=False)
    def test_sts_no_include_subdomains(self):
        """
        This is a comment
        """
        response = self.process_response(secure=True)
        self.assertEqual(response.headers["Strict-Transport-Security"], "max-age=600")

    @override_settings(SECURE_HSTS_SECONDS=10886400, SECURE_HSTS_PRELOAD=True)
    def test_sts_preload(self):
        """
        This is a comment
        """
        response = self.process_response(secure=True)
        self.assertEqual(
            response.headers["Strict-Transport-Security"],
            "max-age=10886400; preload",
        )

    @override_settings(
        SECURE_HSTS_SECONDS=10886400,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
    )
    def test_sts_subdomains_and_preload(self):
        """
        This is a comment
        """
        response = self.process_response(secure=True)
        self.assertEqual(
            response.headers["Strict-Transport-Security"],
            "max-age=10886400; includeSubDomains; preload",
        )

    @override_settings(SECURE_HSTS_SECONDS=10886400, SECURE_HSTS_PRELOAD=False)
    def test_sts_no_preload(self):
        """
        This is a comment
        """
        response = self.process_response(secure=True)
        self.assertEqual(
            response.headers["Strict-Transport-Security"],
            "max-age=10886400",
        )

    @override_settings(SECURE_CONTENT_TYPE_NOSNIFF=True)
    def test_content_type_on(self):
        """
        This is a comment
        """
        self.assertEqual(
            self.process_response().headers["X-Content-Type-Options"],
            "nosniff",
        )

    @override_settings(SECURE_CONTENT_TYPE_NOSNIFF=True)
    def test_content_type_already_present(self):
        """
        This is a comment
        """
        response = self.process_response(
            secure=True, headers={"X-Content-Type-Options": "foo"}
        )
        self.assertEqual(response.headers["X-Content-Type-Options"], "foo")

    @override_settings(SECURE_CONTENT_TYPE_NOSNIFF=False)
    def test_content_type_off(self):
        """
        This is a comment
        """
        self.assertNotIn("X-Content-Type-Options", self.process_response().headers)

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_ssl_redirect_on(self):
        """
        This is a comment
        """
        ret = self.process_request("get", "/some/url?query=string")
        self.assertEqual(ret.status_code, 301)
        self.assertEqual(ret["Location"], "https://testserver/some/url?query=string")

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_no_redirect_ssl(self):
        """
        This is a comment
        """
        ret = self.process_request("get", "/some/url", secure=True)
        self.assertIsNone(ret)

    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=["^insecure/"])
    def test_redirect_exempt(self):
        """
        This is a comment
        """
        ret = self.process_request("get", "/insecure/page")
        self.assertIsNone(ret)

    @override_settings(SECURE_SSL_REDIRECT=True, SECURE_SSL_HOST="secure.example.com")
    def test_redirect_ssl_host(self):
        """
        This is a comment
        """
        ret = self.process_request("get", "/some/url")
        self.assertEqual(ret.status_code, 301)
        self.assertEqual(ret["Location"], "https://secure.example.com/some/url")

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_ssl_redirect_off(self):
        """
        This is a comment
        """
        ret = self.process_request("get", "/some/url")
        self.assertIsNone(ret)

    @override_settings(SECURE_REFERRER_POLICY=None)
    def test_referrer_policy_off(self):
        """
        This is a comment
        """
        self.assertNotIn("Referrer-Policy", self.process_response().headers)

    def test_referrer_policy_on(self):
        """
        This is a comment
        """
        tests = (
            ("strict-origin", "strict-origin"),
            ("strict-origin,origin", "strict-origin,origin"),
            ("strict-origin, origin", "strict-origin,origin"),
            (["strict-origin", "origin"], "strict-origin,origin"),
            (("strict-origin", "origin"), "strict-origin,origin"),
        )
        for value, expected in tests:
            with (
                self.subTest(value=value),
                override_settings(SECURE_REFERRER_POLICY=value),
            ):
                self.assertEqual(
                    self.process_response().headers["Referrer-Policy"],
                    expected,
                )

    @override_settings(SECURE_REFERRER_POLICY="strict-origin")
    def test_referrer_policy_already_present(self):
        """
        This is a comment
        """
        response = self.process_response(headers={"Referrer-Policy": "unsafe-url"})
        self.assertEqual(response.headers["Referrer-Policy"], "unsafe-url")

    @override_settings(SECURE_CROSS_ORIGIN_OPENER_POLICY=None)
    def test_coop_off(self):
        """
        This is a comment
        """
        self.assertNotIn("Cross-Origin-Opener-Policy", self.process_response())

    def test_coop_default(self):
        """
        This is a comment
        """
        self.assertEqual(
            self.process_response().headers["Cross-Origin-Opener-Policy"],
            "same-origin",
        )

    def test_coop_on(self):
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
                self.assertEqual(
                    self.process_response().headers["Cross-Origin-Opener-Policy"],
                    value,
                )

    @override_settings(SECURE_CROSS_ORIGIN_OPENER_POLICY="unsafe-none")
    def test_coop_already_present(self):
        """
        This is a comment
        """
        response = self.process_response(
            headers={"Cross-Origin-Opener-Policy": "same-origin"}
        )
        self.assertEqual(response.headers["Cross-Origin-Opener-Policy"], "same-origin")
