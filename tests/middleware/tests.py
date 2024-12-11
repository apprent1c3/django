import gzip
import random
import re
import struct
from io import BytesIO
from unittest import mock
from urllib.parse import quote

from django.conf import settings
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    HttpResponseNotFound,
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
    StreamingHttpResponse,
)
from django.middleware.clickjacking import XFrameOptionsMiddleware
from django.middleware.common import BrokenLinkEmailsMiddleware, CommonMiddleware
from django.middleware.gzip import GZipMiddleware
from django.middleware.http import ConditionalGetMiddleware
from django.test import RequestFactory, SimpleTestCase, override_settings

int2byte = struct.Struct(">B").pack


def get_response_empty(request):
    return HttpResponse()


def get_response_404(request):
    return HttpResponseNotFound()


@override_settings(ROOT_URLCONF="middleware.urls")
class CommonMiddlewareTest(SimpleTestCase):
    rf = RequestFactory()

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_have_slash(self):
        """
        URLs with slashes should go unmolested.
        """
        request = self.rf.get("/slash/")
        self.assertIsNone(CommonMiddleware(get_response_404).process_request(request))
        self.assertEqual(CommonMiddleware(get_response_404)(request).status_code, 404)

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_slashless_resource(self):
        """
        Matches to explicit slashless URLs should go unmolested.
        """

        def get_response(req):
            return HttpResponse("Here's the text of the web page.")

        request = self.rf.get("/noslash")
        self.assertIsNone(CommonMiddleware(get_response).process_request(request))
        self.assertEqual(
            CommonMiddleware(get_response)(request).content,
            b"Here's the text of the web page.",
        )

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_slashless_unknown(self):
        """
        APPEND_SLASH should not redirect to unknown resources.
        """
        request = self.rf.get("/unknown")
        response = CommonMiddleware(get_response_404)(request)
        self.assertEqual(response.status_code, 404)

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_redirect(self):
        """
        APPEND_SLASH should redirect slashless URLs to a valid pattern.
        """
        request = self.rf.get("/slash")
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertIsNone(r)
        response = HttpResponseNotFound()
        r = CommonMiddleware(get_response_empty).process_response(request, response)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "/slash/")

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_redirect_querystring(self):
        """
        APPEND_SLASH should preserve querystrings when redirecting.
        """
        request = self.rf.get("/slash?test=1")
        resp = CommonMiddleware(get_response_404)(request)
        self.assertEqual(resp.url, "/slash/?test=1")

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_redirect_querystring_have_slash(self):
        """
        APPEND_SLASH should append slash to path when redirecting a request
        with a querystring ending with slash.
        """
        request = self.rf.get("/slash?test=slash/")
        resp = CommonMiddleware(get_response_404)(request)
        self.assertIsInstance(resp, HttpResponsePermanentRedirect)
        self.assertEqual(resp.url, "/slash/?test=slash/")

    @override_settings(APPEND_SLASH=True, DEBUG=True)
    def test_append_slash_no_redirect_in_DEBUG(self):
        """
        While in debug mode, an exception is raised with a warning
        when a failed attempt is made to DELETE, POST, PUT, or PATCH to an URL
        which would normally be redirected to a slashed version.
        """
        msg = "maintaining %s data. Change your form to point to testserver/slash/"
        request = self.rf.get("/slash")
        request.method = "POST"
        with self.assertRaisesMessage(RuntimeError, msg % request.method):
            CommonMiddleware(get_response_404)(request)
        request = self.rf.get("/slash")
        request.method = "PUT"
        with self.assertRaisesMessage(RuntimeError, msg % request.method):
            CommonMiddleware(get_response_404)(request)
        request = self.rf.get("/slash")
        request.method = "PATCH"
        with self.assertRaisesMessage(RuntimeError, msg % request.method):
            CommonMiddleware(get_response_404)(request)
        request = self.rf.delete("/slash")
        with self.assertRaisesMessage(RuntimeError, msg % request.method):
            CommonMiddleware(get_response_404)(request)

    @override_settings(APPEND_SLASH=False)
    def test_append_slash_disabled(self):
        """
        Disabling append slash functionality should leave slashless URLs alone.
        """
        request = self.rf.get("/slash")
        self.assertEqual(CommonMiddleware(get_response_404)(request).status_code, 404)

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_opt_out(self):
        """
        Views marked with @no_append_slash should be left alone.
        """
        request = self.rf.get("/sensitive_fbv")
        self.assertEqual(CommonMiddleware(get_response_404)(request).status_code, 404)

        request = self.rf.get("/sensitive_cbv")
        self.assertEqual(CommonMiddleware(get_response_404)(request).status_code, 404)

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_quoted(self):
        """
        URLs which require quoting should be redirected to their slash version.
        """
        request = self.rf.get(quote("/needsquoting#"))
        r = CommonMiddleware(get_response_404)(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "/needsquoting%23/")

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_leading_slashes(self):
        """
        Paths starting with two slashes are escaped to prevent open redirects.
        If there's a URL pattern that allows paths to start with two slashes, a
        request with path //evil.com must not redirect to //evil.com/ (appended
        slash) which is a schemaless absolute URL. The browser would navigate
        to evil.com/.
        """
        # Use 4 slashes because of RequestFactory behavior.
        request = self.rf.get("////evil.com/security")
        r = CommonMiddleware(get_response_404).process_request(request)
        self.assertIsNone(r)
        response = HttpResponseNotFound()
        r = CommonMiddleware(get_response_404).process_response(request, response)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "/%2Fevil.com/security/")
        r = CommonMiddleware(get_response_404)(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "/%2Fevil.com/security/")

    @override_settings(APPEND_SLASH=False, PREPEND_WWW=True)
    def test_prepend_www(self):
        request = self.rf.get("/path/")
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/path/")

    @override_settings(APPEND_SLASH=True, PREPEND_WWW=True)
    def test_prepend_www_append_slash_have_slash(self):
        request = self.rf.get("/slash/")
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/slash/")

    @override_settings(APPEND_SLASH=True, PREPEND_WWW=True)
    def test_prepend_www_append_slash_slashless(self):
        """
        Tests the application's behavior when both APPEND_SLASH and PREPEND_WWW settings are enabled.
        It verifies that a request to a URL without a trailing slash is redirected to the same URL with a slash appended and the 'www.' subdomain prepended. The expected response is a 301 permanent redirect with the updated URL.
        """
        request = self.rf.get("/slash")
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/slash/")

    # The following tests examine expected behavior given a custom URLconf that
    # overrides the default one through the request object.

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_have_slash_custom_urlconf(self):
        """
        URLs with slashes should go unmolested.
        """
        request = self.rf.get("/customurlconf/slash/")
        request.urlconf = "middleware.extra_urls"
        self.assertIsNone(CommonMiddleware(get_response_404).process_request(request))
        self.assertEqual(CommonMiddleware(get_response_404)(request).status_code, 404)

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_slashless_resource_custom_urlconf(self):
        """
        Matches to explicit slashless URLs should go unmolested.
        """

        def get_response(req):
            return HttpResponse("web content")

        request = self.rf.get("/customurlconf/noslash")
        request.urlconf = "middleware.extra_urls"
        self.assertIsNone(CommonMiddleware(get_response).process_request(request))
        self.assertEqual(
            CommonMiddleware(get_response)(request).content, b"web content"
        )

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_slashless_unknown_custom_urlconf(self):
        """
        APPEND_SLASH should not redirect to unknown resources.
        """
        request = self.rf.get("/customurlconf/unknown")
        request.urlconf = "middleware.extra_urls"
        self.assertIsNone(CommonMiddleware(get_response_404).process_request(request))
        self.assertEqual(CommonMiddleware(get_response_404)(request).status_code, 404)

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_redirect_custom_urlconf(self):
        """
        APPEND_SLASH should redirect slashless URLs to a valid pattern.
        """
        request = self.rf.get("/customurlconf/slash")
        request.urlconf = "middleware.extra_urls"
        r = CommonMiddleware(get_response_404)(request)
        self.assertIsNotNone(
            r,
            "CommonMiddleware failed to return APPEND_SLASH redirect using "
            "request.urlconf",
        )
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "/customurlconf/slash/")

    @override_settings(APPEND_SLASH=True, DEBUG=True)
    def test_append_slash_no_redirect_on_POST_in_DEBUG_custom_urlconf(self):
        """
        While in debug mode, an exception is raised with a warning
        when a failed attempt is made to POST to an URL which would normally be
        redirected to a slashed version.
        """
        request = self.rf.get("/customurlconf/slash")
        request.urlconf = "middleware.extra_urls"
        request.method = "POST"
        with self.assertRaisesMessage(RuntimeError, "end in a slash"):
            CommonMiddleware(get_response_404)(request)

    @override_settings(APPEND_SLASH=False)
    def test_append_slash_disabled_custom_urlconf(self):
        """
        Disabling append slash functionality should leave slashless URLs alone.
        """
        request = self.rf.get("/customurlconf/slash")
        request.urlconf = "middleware.extra_urls"
        self.assertIsNone(CommonMiddleware(get_response_404).process_request(request))
        self.assertEqual(CommonMiddleware(get_response_404)(request).status_code, 404)

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_quoted_custom_urlconf(self):
        """
        URLs which require quoting should be redirected to their slash version.
        """
        request = self.rf.get(quote("/customurlconf/needsquoting#"))
        request.urlconf = "middleware.extra_urls"
        r = CommonMiddleware(get_response_404)(request)
        self.assertIsNotNone(
            r,
            "CommonMiddleware failed to return APPEND_SLASH redirect using "
            "request.urlconf",
        )
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "/customurlconf/needsquoting%23/")

    @override_settings(APPEND_SLASH=False, PREPEND_WWW=True)
    def test_prepend_www_custom_urlconf(self):
        """

        Tests that CommonMiddleware correctly prepends 'www' to a custom URL configuration.

        Verifies that when the PREPEND_WWW setting is enabled, a redirect to the 'www' subdomain is issued for requests with custom URL configurations.

        """
        request = self.rf.get("/customurlconf/path/")
        request.urlconf = "middleware.extra_urls"
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/customurlconf/path/")

    @override_settings(APPEND_SLASH=True, PREPEND_WWW=True)
    def test_prepend_www_append_slash_have_slash_custom_urlconf(self):
        """
        Test that CommonMiddleware correctly prepends 'www' and appends a slash to a custom URLconf when the request URL already ends with a slash.

        The test verifies that the middleware returns a 301 redirect response with the expected URL, demonstrating the proper application of the PREPEND_WWW and APPEND_SLASH settings.

        The test case involves a custom URL configuration, ensuring that the middleware behaves correctly in scenarios where the URL routing is non-standard.

        :raises: AssertionError if the status code or redirect URL does not match the expected values.
        :returns: None
        """
        request = self.rf.get("/customurlconf/slash/")
        request.urlconf = "middleware.extra_urls"
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/customurlconf/slash/")

    @override_settings(APPEND_SLASH=True, PREPEND_WWW=True)
    def test_prepend_www_append_slash_slashless_custom_urlconf(self):
        request = self.rf.get("/customurlconf/slash")
        request.urlconf = "middleware.extra_urls"
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/customurlconf/slash/")

    # Tests for the Content-Length header

    def test_content_length_header_added(self):
        def get_response(req):
            response = HttpResponse("content")
            self.assertNotIn("Content-Length", response)
            return response

        response = CommonMiddleware(get_response)(self.rf.get("/"))
        self.assertEqual(int(response.headers["Content-Length"]), len(response.content))

    def test_content_length_header_not_added_for_streaming_response(self):
        """
        Tests that the Content-Length header is not added to a streaming response by the middleware.

         The test verifies that when a request is made to a view that returns a StreamingHttpResponse,
         the Content-Length header is not included in the response, both before and after passing through
         the CommonMiddleware. This ensures that the middleware does not interfere with the streaming
         response's chunked encoding, which does not require a Content-Length header.
        """
        def get_response(req):
            response = StreamingHttpResponse("content")
            self.assertNotIn("Content-Length", response)
            return response

        response = CommonMiddleware(get_response)(self.rf.get("/"))
        self.assertNotIn("Content-Length", response)

    def test_content_length_header_not_changed(self):
        """
        Tests that the Content-Length header in an HTTP response remains unchanged by the CommonMiddleware when it is manually set. This test ensures that the middleware does not interfere with or modify a predefined Content-Length value, preserving the original header's value in the response.
        """
        bad_content_length = 500

        def get_response(req):
            """

            Generates an HTTP response object.

            This function creates a new HttpResponse object and sets its 'Content-Length' header.
            The 'Content-Length' value is set to a predefined value, which may not accurately reflect the actual content length.

            Returns:
                HttpResponse: An HTTP response object with the 'Content-Length' header set.

            """
            response = HttpResponse()
            response.headers["Content-Length"] = bad_content_length
            return response

        response = CommonMiddleware(get_response)(self.rf.get("/"))
        self.assertEqual(int(response.headers["Content-Length"]), bad_content_length)

    # Other tests

    @override_settings(DISALLOWED_USER_AGENTS=[re.compile(r"foo")])
    def test_disallowed_user_agents(self):
        """
        Test that a request is denied when a disallowed user agent is encountered.

        This test case checks that the CommonMiddleware correctly blocks a request when the user agent matches a disallowed pattern. The test simulates a GET request with a user agent string that matches a compiled regular expression pattern. It then verifies that the request is refused with a \"Forbidden user agent\" error message, which is a PermissionDenied exception.
        """
        request = self.rf.get("/slash")
        request.META["HTTP_USER_AGENT"] = "foo"
        with self.assertRaisesMessage(PermissionDenied, "Forbidden user agent"):
            CommonMiddleware(get_response_empty).process_request(request)

    def test_non_ascii_query_string_does_not_crash(self):
        """Regression test for #15152"""
        request = self.rf.get("/slash")
        request.META["QUERY_STRING"] = "drink=café"
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertIsNone(r)
        response = HttpResponseNotFound()
        r = CommonMiddleware(get_response_empty).process_response(request, response)
        self.assertEqual(r.status_code, 301)

    def test_response_redirect_class(self):
        """
        Tests that the CommonMiddleware class correctly redirects a URL without a trailing slash to its equivalent URL with a trailing slash.

        The test checks that a GET request to a URL without a trailing slash results in a permanent redirect (301 status code) to the same URL with a trailing slash, and that the response object returned is an instance of HttpResponsePermanentRedirect.
        """
        request = self.rf.get("/slash")
        r = CommonMiddleware(get_response_404)(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "/slash/")
        self.assertIsInstance(r, HttpResponsePermanentRedirect)

    def test_response_redirect_class_subclass(self):
        """

        Test the response redirect behavior when using a subclass of CommonMiddleware.

        Verifies that when a request is made to a URL without a trailing slash, the 
        middleware correctly redirects to the URL with a trailing slash using the 
        specified response redirect class.

        The test checks that the redirect response has the expected status code (302), 
        URL, and that the response is an instance of the specified redirect class.

        """
        class MyCommonMiddleware(CommonMiddleware):
            response_redirect_class = HttpResponseRedirect

        request = self.rf.get("/slash")
        r = MyCommonMiddleware(get_response_404)(request)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, "/slash/")
        self.assertIsInstance(r, HttpResponseRedirect)


@override_settings(
    IGNORABLE_404_URLS=[re.compile(r"foo")],
    MANAGERS=[("PHD", "PHB@dilbert.com")],
)
class BrokenLinkEmailsMiddlewareTest(SimpleTestCase):
    rf = RequestFactory()

    def setUp(self):
        self.req = self.rf.get("/regular_url/that/does/not/exist")

    def get_response(self, req):
        return self.client.get(req.path)

    def test_404_error_reporting(self):
        self.req.META["HTTP_REFERER"] = "/another/url/"
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Broken", mail.outbox[0].subject)

    def test_404_error_reporting_no_referer(self):
        """
        Test that a 404 error is not reported via email when there is no referer.

        This test case verifies the functionality of the BrokenLinkEmailsMiddleware 
        when handling 404 errors without a referer. It checks that no email is sent 
        in this scenario, ensuring that the middleware behaves as expected in 
        the absence of a referer header.
        """
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 0)

    def test_404_error_reporting_ignored_url(self):
        """
        Tests that the BrokenLinkEmailsMiddleware correctly ignores reporting 404 errors for specified URLs.

        This test case verifies that when a request is made to a URL that does not exist, and that URL is configured to be ignored by the middleware, no email is sent. The test simulates a request to a non-existent URL, then checks that the email outbox remains empty, confirming that the middleware did not trigger an email to be sent.
        """
        self.req.path = self.req.path_info = "foo_url/that/does/not/exist"
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 0)

    def test_custom_request_checker(self):
        """
        Test customization of the request checker in BrokenLinkEmailsMiddleware.

        This test case verifies that a subclassed middleware can properly ignore
        requests based on custom user-agent patterns. It checks that requests from
        specific user agents, such as spiders or robots, do not trigger email notifications,
        while requests from other user agents do trigger notifications.

        The test covers the following scenarios:

        * A request with a user-agent that matches one of the ignored patterns does not
          trigger an email notification.
        * A request with a user-agent that does not match any ignored patterns does
          trigger an email notification.

        The test ensures that the custom request checker correctly handles different
        user-agent strings and only sends email notifications when necessary.
        """
        class SubclassedMiddleware(BrokenLinkEmailsMiddleware):
            ignored_user_agent_patterns = (
                re.compile(r"Spider.*"),
                re.compile(r"Robot.*"),
            )

            def is_ignorable_request(self, request, uri, domain, referer):
                """Check user-agent in addition to normal checks."""
                if super().is_ignorable_request(request, uri, domain, referer):
                    return True
                user_agent = request.META["HTTP_USER_AGENT"]
                return any(
                    pattern.search(user_agent)
                    for pattern in self.ignored_user_agent_patterns
                )

        self.req.META["HTTP_REFERER"] = "/another/url/"
        self.req.META["HTTP_USER_AGENT"] = "Spider machine 3.4"
        SubclassedMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 0)
        self.req.META["HTTP_USER_AGENT"] = "My user agent"
        SubclassedMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 1)

    def test_referer_equal_to_requested_url(self):
        """
        Some bots set the referer to the current URL to avoid being blocked by
        an referer check (#25302).
        """
        self.req.META["HTTP_REFERER"] = self.req.path
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 0)

        # URL with scheme and domain should also be ignored
        self.req.META["HTTP_REFERER"] = "http://testserver%s" % self.req.path
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 0)

        # URL with a different scheme should be ignored as well because bots
        # tend to use http:// in referers even when browsing HTTPS websites.
        self.req.META["HTTP_X_PROTO"] = "https"
        self.req.META["SERVER_PORT"] = 443
        with self.settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_PROTO", "https")):
            BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 0)

    def test_referer_equal_to_requested_url_on_another_domain(self):
        self.req.META["HTTP_REFERER"] = "http://anotherserver%s" % self.req.path
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(APPEND_SLASH=True)
    def test_referer_equal_to_requested_url_without_trailing_slash_with_append_slash(
        self,
    ):
        self.req.path = self.req.path_info = "/regular_url/that/does/not/exist/"
        self.req.META["HTTP_REFERER"] = self.req.path_info[:-1]
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(APPEND_SLASH=False)
    def test_referer_equal_to_requested_url_without_trailing_slash_with_no_append_slash(
        self,
    ):
        self.req.path = self.req.path_info = "/regular_url/that/does/not/exist/"
        self.req.META["HTTP_REFERER"] = self.req.path_info[:-1]
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 1)


@override_settings(ROOT_URLCONF="middleware.cond_get_urls")
class ConditionalGetMiddlewareTest(SimpleTestCase):
    request_factory = RequestFactory()

    def setUp(self):
        self.req = self.request_factory.get("/")
        self.resp_headers = {}

    def get_response(self, req):
        resp = self.client.get(req.path_info)
        for key, value in self.resp_headers.items():
            resp[key] = value
        return resp

    # Tests for the ETag header

    def test_middleware_calculates_etag(self):
        """
        Tests if the ConditionalGetMiddleware correctly calculates and includes an ETag header in the response.

        The test checks if the middleware returns a successful response (200 status code) and if the ETag header is present and not empty in the response, verifying that the ETag calculation is performed as expected.
        """
        resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual("", resp["ETag"])

    def test_middleware_wont_overwrite_etag(self):
        self.resp_headers["ETag"] = "eggs"
        resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual("eggs", resp["ETag"])

    def test_no_etag_streaming_response(self):
        def get_response(req):
            return StreamingHttpResponse(["content"])

        self.assertFalse(
            ConditionalGetMiddleware(get_response)(self.req).has_header("ETag")
        )

    def test_no_etag_response_empty_content(self):
        def get_response(req):
            return HttpResponse()

        self.assertFalse(
            ConditionalGetMiddleware(get_response)(self.req).has_header("ETag")
        )

    def test_no_etag_no_store_cache(self):
        self.resp_headers["Cache-Control"] = "No-Cache, No-Store, Max-age=0"
        self.assertFalse(
            ConditionalGetMiddleware(self.get_response)(self.req).has_header("ETag")
        )

    def test_etag_extended_cache_control(self):
        """
        Tests that the ConditionalGetMiddleware correctly sets the ETag header
        in the response when the Cache-Control header contains a custom directive.

        This test case covers the scenario where a custom Cache-Control directive
        is specified in the response headers, and verifies that the ETag header
        is still included in the response, as expected.
        """
        self.resp_headers["Cache-Control"] = 'my-directive="my-no-store"'
        self.assertTrue(
            ConditionalGetMiddleware(self.get_response)(self.req).has_header("ETag")
        )

    def test_if_none_match_and_no_etag(self):
        self.req.META["HTTP_IF_NONE_MATCH"] = "spam"
        resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(resp.status_code, 200)

    def test_no_if_none_match_and_etag(self):
        self.resp_headers["ETag"] = "eggs"
        resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(resp.status_code, 200)

    def test_if_none_match_and_same_etag(self):
        self.req.META["HTTP_IF_NONE_MATCH"] = '"spam"'
        self.resp_headers["ETag"] = '"spam"'
        resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(resp.status_code, 304)

    def test_if_none_match_and_different_etag(self):
        self.req.META["HTTP_IF_NONE_MATCH"] = "spam"
        self.resp_headers["ETag"] = "eggs"
        resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(resp.status_code, 200)

    def test_if_none_match_and_redirect(self):
        """
        Tests the ConditionalGetMiddleware when If-None-Match header matches the ETag of a response that redirects to another location.

        The test verifies that the middleware correctly handles a redirect response (301 status code) 
        with a matching ETag, and checks that the status code of the response is set accordingly.
        """
        def get_response(req):
            """
            Return a response object redirecting to the root URL.

            The function creates a redirect response with a status code of 301 (Moved Permanently)
            and includes a Location header pointing to the root URL ('/'). An ETag header is also
            set to a static value, 'spam'. The response is generated based on the provided request
            information.

            Args:
                req: The incoming request object containing path information.

            Returns:
                A response object with a 301 status code and Location header set to '/'.
            """
            resp = self.client.get(req.path_info)
            resp["ETag"] = "spam"
            resp["Location"] = "/"
            resp.status_code = 301
            return resp

        self.req.META["HTTP_IF_NONE_MATCH"] = "spam"
        resp = ConditionalGetMiddleware(get_response)(self.req)
        self.assertEqual(resp.status_code, 301)

    def test_if_none_match_and_client_error(self):
        """
        Tests the behavior of the ConditionalGetMiddleware when the If-None-Match header is set to a value that matches the ETag of the response, but the response from the view is a client error (4xx status code).

        This test verifies that in such cases, the middleware does not intercept the response and returns the original error response from the view, instead of returning a 304 Not Modified response.

        The test case simulates a request with an If-None-Match header that matches the ETag of the response, and checks that the status code of the response returned by the middleware is 400, indicating a client error.
        """
        def get_response(req):
            resp = self.client.get(req.path_info)
            resp["ETag"] = "spam"
            resp.status_code = 400
            return resp

        self.req.META["HTTP_IF_NONE_MATCH"] = "spam"
        resp = ConditionalGetMiddleware(get_response)(self.req)
        self.assertEqual(resp.status_code, 400)

    # Tests for the Last-Modified header

    def test_if_modified_since_and_no_last_modified(self):
        self.req.META["HTTP_IF_MODIFIED_SINCE"] = "Sat, 12 Feb 2011 17:38:44 GMT"
        resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(resp.status_code, 200)

    def test_no_if_modified_since_and_last_modified(self):
        """
        Tests the ConditionalGetMiddleware when the request does not include an \"If-Modified-Since\" header, but the response contains a \"Last-Modified\" header. 
        Verifies that the middleware returns a full response (200 status code) in this scenario.
        """
        self.resp_headers["Last-Modified"] = "Sat, 12 Feb 2011 17:38:44 GMT"
        resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(resp.status_code, 200)

    def test_if_modified_since_and_same_last_modified(self):
        """
        Tests the ConditionalGetMiddleware functionality when the 'If-Modified-Since' header 
        matches the 'Last-Modified' header in the response.

        This test case simulates a scenario where a client requests a resource with a specific 
        'If-Modified-Since' date, which is identical to the 'Last-Modified' date of the resource. 
        It verifies that the middleware returns a 304 status code, indicating that the resource 
        has not been modified since the specified date, and a full response is not necessary.

        The test checks the correct handling of HTTP headers and ensures that the 
        ConditionalGetMiddleware responds correctly to conditional GET requests, 
        promoting efficient use of network resources and reducing unnecessary data transfers.
        """
        self.req.META["HTTP_IF_MODIFIED_SINCE"] = "Sat, 12 Feb 2011 17:38:44 GMT"
        self.resp_headers["Last-Modified"] = "Sat, 12 Feb 2011 17:38:44 GMT"
        self.resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(self.resp.status_code, 304)

    def test_if_modified_since_and_last_modified_in_the_past(self):
        self.req.META["HTTP_IF_MODIFIED_SINCE"] = "Sat, 12 Feb 2011 17:38:44 GMT"
        self.resp_headers["Last-Modified"] = "Sat, 12 Feb 2011 17:35:44 GMT"
        resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(resp.status_code, 304)

    def test_if_modified_since_and_last_modified_in_the_future(self):
        self.req.META["HTTP_IF_MODIFIED_SINCE"] = "Sat, 12 Feb 2011 17:38:44 GMT"
        self.resp_headers["Last-Modified"] = "Sat, 12 Feb 2011 17:41:44 GMT"
        self.resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(self.resp.status_code, 200)

    def test_if_modified_since_and_redirect(self):
        """

        Tests the behavior of the ConditionalGetMiddleware when a request includes an 'If-Modified-Since' header and a redirect response is returned.

        The test verifies that the middleware correctly handles the redirect response (301 status code) when the 'Last-Modified' header of the response matches an earlier time than the 'If-Modified-Since' header of the request.

        The expected outcome is that the middleware returns the redirect response, rather than attempting to follow the redirect or returning a different status code.

        """
        def get_response(req):
            resp = self.client.get(req.path_info)
            resp["Last-Modified"] = "Sat, 12 Feb 2011 17:35:44 GMT"
            resp["Location"] = "/"
            resp.status_code = 301
            return resp

        self.req.META["HTTP_IF_MODIFIED_SINCE"] = "Sat, 12 Feb 2011 17:38:44 GMT"
        resp = ConditionalGetMiddleware(get_response)(self.req)
        self.assertEqual(resp.status_code, 301)

    def test_if_modified_since_and_client_error(self):
        def get_response(req):
            """
            Provides a response to a given HTTP request.

            This function takes an HTTP request object as input and returns a response object.
            The response is generated by sending a GET request to the client using the path information from the input request.
            Additional headers are added to the response, including the 'Last-Modified' date, and a custom status code is set.
            The returned response object can be used for further processing or sent back to the client.

            :returns: A response object containing the result of the HTTP request
            :rtype: Response
            """
            resp = self.client.get(req.path_info)
            resp["Last-Modified"] = "Sat, 12 Feb 2011 17:35:44 GMT"
            resp.status_code = 400
            return resp

        self.req.META["HTTP_IF_MODIFIED_SINCE"] = "Sat, 12 Feb 2011 17:38:44 GMT"
        resp = ConditionalGetMiddleware(get_response)(self.req)
        self.assertEqual(resp.status_code, 400)

    def test_not_modified_headers(self):
        """
        The 304 Not Modified response should include only the headers required
        by RFC 9110 Section 15.4.5, Last-Modified, and the cookies.
        """

        def get_response(req):
            """

            Fetches an HTTP response based on the provided request.

            The retrieved response includes standard HTTP headers such as Date, 
            Last-Modified, Expires, Vary, Cache-Control, Content-Location, 
            Content-Language, and ETag. A cookie is also set on the response.

            The function returns a fully constructed response object that can 
            be used for further processing or sent directly to the client.

            :param req: The request object containing the path information.
            :returns: The constructed HTTP response object.

            """
            resp = self.client.get(req.path_info)
            resp["Date"] = "Sat, 12 Feb 2011 17:35:44 GMT"
            resp["Last-Modified"] = "Sat, 12 Feb 2011 17:35:44 GMT"
            resp["Expires"] = "Sun, 13 Feb 2011 17:35:44 GMT"
            resp["Vary"] = "Cookie"
            resp["Cache-Control"] = "public"
            resp["Content-Location"] = "/alt"
            resp["Content-Language"] = "en"  # shouldn't be preserved
            resp["ETag"] = '"spam"'
            resp.set_cookie("key", "value")
            return resp

        self.req.META["HTTP_IF_NONE_MATCH"] = '"spam"'

        new_response = ConditionalGetMiddleware(get_response)(self.req)
        self.assertEqual(new_response.status_code, 304)
        base_response = get_response(self.req)
        for header in (
            "Cache-Control",
            "Content-Location",
            "Date",
            "ETag",
            "Expires",
            "Last-Modified",
            "Vary",
        ):
            self.assertEqual(
                new_response.headers[header], base_response.headers[header]
            )
        self.assertEqual(new_response.cookies, base_response.cookies)
        self.assertNotIn("Content-Language", new_response)

    def test_no_unsafe(self):
        """
        ConditionalGetMiddleware shouldn't return a conditional response on an
        unsafe request. A response has already been generated by the time
        ConditionalGetMiddleware is called, so it's too late to return a 412
        Precondition Failed.
        """

        def get_200_response(req):
            return HttpResponse(status=200)

        response = ConditionalGetMiddleware(self.get_response)(self.req)
        etag = response.headers["ETag"]
        put_request = self.request_factory.put("/", headers={"if-match": etag})
        conditional_get_response = ConditionalGetMiddleware(get_200_response)(
            put_request
        )
        self.assertEqual(
            conditional_get_response.status_code, 200
        )  # should never be a 412

    def test_no_head(self):
        """
        ConditionalGetMiddleware shouldn't compute and return an ETag on a
        HEAD request since it can't do so accurately without access to the
        response body of the corresponding GET.
        """

        def get_200_response(req):
            return HttpResponse(status=200)

        request = self.request_factory.head("/")
        conditional_get_response = ConditionalGetMiddleware(get_200_response)(request)
        self.assertNotIn("ETag", conditional_get_response)


class XFrameOptionsMiddlewareTest(SimpleTestCase):
    """
    Tests for the X-Frame-Options clickjacking prevention middleware.
    """

    def test_same_origin(self):
        """
        The X_FRAME_OPTIONS setting can be set to SAMEORIGIN to have the
        middleware use that value for the HTTP header.
        """
        with override_settings(X_FRAME_OPTIONS="SAMEORIGIN"):
            r = XFrameOptionsMiddleware(get_response_empty)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "SAMEORIGIN")

        with override_settings(X_FRAME_OPTIONS="sameorigin"):
            r = XFrameOptionsMiddleware(get_response_empty)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "SAMEORIGIN")

    def test_deny(self):
        """
        The X_FRAME_OPTIONS setting can be set to DENY to have the middleware
        use that value for the HTTP header.
        """
        with override_settings(X_FRAME_OPTIONS="DENY"):
            r = XFrameOptionsMiddleware(get_response_empty)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "DENY")

        with override_settings(X_FRAME_OPTIONS="deny"):
            r = XFrameOptionsMiddleware(get_response_empty)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "DENY")

    def test_defaults_sameorigin(self):
        """
        If the X_FRAME_OPTIONS setting is not set then it defaults to
        DENY.
        """
        with override_settings(X_FRAME_OPTIONS=None):
            del settings.X_FRAME_OPTIONS  # restored by override_settings
            r = XFrameOptionsMiddleware(get_response_empty)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "DENY")

    def test_dont_set_if_set(self):
        """
        If the X-Frame-Options header is already set then the middleware does
        not attempt to override it.
        """

        def same_origin_response(request):
            """

            Returns an HTTP response with the X-Frame-Options header set to 'SAMEORIGIN', 
            indicating that the page can only be framed by pages from the same origin.
            This is a security measure to prevent clickjacking attacks.

            :param request: The incoming HTTP request
            :return: An HTTP response with the X-Frame-Options header set

            """
            response = HttpResponse()
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            return response

        def deny_response(request):
            response = HttpResponse()
            response.headers["X-Frame-Options"] = "DENY"
            return response

        with override_settings(X_FRAME_OPTIONS="DENY"):
            r = XFrameOptionsMiddleware(same_origin_response)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "SAMEORIGIN")

        with override_settings(X_FRAME_OPTIONS="SAMEORIGIN"):
            r = XFrameOptionsMiddleware(deny_response)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "DENY")

    def test_response_exempt(self):
        """
        If the response has an xframe_options_exempt attribute set to False
        then it still sets the header, but if it's set to True then it doesn't.
        """

        def xframe_exempt_response(request):
            """

            Exempts the HTTP response from the X-Frame-Options protection.

            This function returns an HttpResponse object that allows the response to be framed by other websites, 
            bypassing the default clickjacking protection.

            Returns:
                HttpResponse: The response object with X-Frame-Options exemption enabled.

            """
            response = HttpResponse()
            response.xframe_options_exempt = True
            return response

        def xframe_not_exempt_response(request):
            response = HttpResponse()
            response.xframe_options_exempt = False
            return response

        with override_settings(X_FRAME_OPTIONS="SAMEORIGIN"):
            r = XFrameOptionsMiddleware(xframe_not_exempt_response)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "SAMEORIGIN")

            r = XFrameOptionsMiddleware(xframe_exempt_response)(HttpRequest())
            self.assertIsNone(r.headers.get("X-Frame-Options"))

    def test_is_extendable(self):
        """
        The XFrameOptionsMiddleware method that determines the X-Frame-Options
        header value can be overridden based on something in the request or
        response.
        """

        class OtherXFrameOptionsMiddleware(XFrameOptionsMiddleware):
            # This is just an example for testing purposes...
            def get_xframe_options_value(self, request, response):
                """

                Determines the X-Frame-Options value for a given request and response.

                The X-Frame-Options header is used to prevent clickjacking attacks by specifying
                whether a page can be iframed by another page. This function checks the request and
                response objects for a 'sameorigin' attribute, and returns 'SAMEORIGIN' if it is
                present, indicating that the page can only be iframed by pages from the same origin.
                If the attribute is not present, it returns 'DENY', indicating that the page cannot
                be iframed by any page.

                Returns:
                    str: The X-Frame-Options value, either 'SAMEORIGIN' or 'DENY'.

                """
                if getattr(request, "sameorigin", False):
                    return "SAMEORIGIN"
                if getattr(response, "sameorigin", False):
                    return "SAMEORIGIN"
                return "DENY"

        def same_origin_response(request):
            """

            Indicates that the current request is from the same origin, 
            enabling the browser to include credentials in the response.

            Returns:
                HttpResponse: A response object with same-origin flag set to True.

            """
            response = HttpResponse()
            response.sameorigin = True
            return response

        with override_settings(X_FRAME_OPTIONS="DENY"):
            r = OtherXFrameOptionsMiddleware(same_origin_response)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "SAMEORIGIN")

            request = HttpRequest()
            request.sameorigin = True
            r = OtherXFrameOptionsMiddleware(get_response_empty)(request)
            self.assertEqual(r.headers["X-Frame-Options"], "SAMEORIGIN")

        with override_settings(X_FRAME_OPTIONS="SAMEORIGIN"):
            r = OtherXFrameOptionsMiddleware(get_response_empty)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "DENY")


class GZipMiddlewareTest(SimpleTestCase):
    """
    Tests the GZipMiddleware.
    """

    short_string = b"This string is too short to be worth compressing."
    compressible_string = b"a" * 500
    incompressible_string = b"".join(
        int2byte(random.randint(0, 255)) for _ in range(500)
    )
    sequence = [b"a" * 500, b"b" * 200, b"a" * 300]
    sequence_unicode = ["a" * 500, "é" * 200, "a" * 300]
    request_factory = RequestFactory()

    def setUp(self):
        """

        Set up test request and response objects for testing purposes.

        This method initializes a test request object with a GET request to the root URL ('/')
        and sets its 'HTTP_ACCEPT_ENCODING' and 'HTTP_USER_AGENT' headers. It also creates
        a test response object with a status code of 200, a content type of 'text/html; charset=UTF-8',
        and a predefined compressible string as its content.

        The resulting request and response objects can be used to test various aspects of
        the application's behavior, such as compression, content rendering, and HTTP header handling.

        """
        self.req = self.request_factory.get("/")
        self.req.META["HTTP_ACCEPT_ENCODING"] = "gzip, deflate"
        self.req.META["HTTP_USER_AGENT"] = (
            "Mozilla/5.0 (Windows NT 5.1; rv:9.0.1) Gecko/20100101 Firefox/9.0.1"
        )
        self.resp = HttpResponse()
        self.resp.status_code = 200
        self.resp.content = self.compressible_string
        self.resp["Content-Type"] = "text/html; charset=UTF-8"

    def get_response(self, request):
        return self.resp

    @staticmethod
    def decompress(gzipped_string):
        """

        Decompress a gzipped string.

        This function takes a gzipped string as input, decompresses it and returns the decompressed bytes.
        It uses the gzip algorithm to achieve this, allowing for efficient and lossless decompression.

        Parameters
        ----------
        gzipped_string : bytes
            The gzipped string to be decompressed.

        Returns
        -------
        bytes
            The decompressed bytes.

        Note
        ----
        This function assumes that the input string is a valid gzipped byte stream. If the input is not a valid gzip file,
        this function may raise an exception or return incorrect results.

        """
        with gzip.GzipFile(mode="rb", fileobj=BytesIO(gzipped_string)) as f:
            return f.read()

    @staticmethod
    def get_mtime(gzipped_string):
        """

        Extract the last modification time from a gzip compressed string.

        This method simulates the retrieval of the last modification time from a gzip file,
        without the need to write the compressed data to disk.

        :arg gzipped_string: A string containing gzip compressed data
        :rtype: int
        :return: The last modification time of the gzip file in seconds since the epoch

        """
        with gzip.GzipFile(mode="rb", fileobj=BytesIO(gzipped_string)) as f:
            f.read()  # must read the data before accessing the header
            return f.mtime

    def test_compress_response(self):
        """
        Compression is performed on responses with compressible content.
        """
        r = GZipMiddleware(self.get_response)(self.req)
        self.assertEqual(self.decompress(r.content), self.compressible_string)
        self.assertEqual(r.get("Content-Encoding"), "gzip")
        self.assertEqual(r.get("Content-Length"), str(len(r.content)))

    def test_compress_streaming_response(self):
        """
        Compression is performed on responses with streaming content.
        """

        def get_stream_response(request):
            """
            Return a server response as a streaming HTTP response.

            This function generates a StreamingHttpResponse object containing the 
            sequence data, which can be used to efficiently handle large or 
            continuously generated content. The response is formatted as HTML text 
            with UTF-8 encoding, making it suitable for displaying dynamic content 
            in a web browser.

            :returns: A StreamingHttpResponse object containing the sequence data.
            :rtype: StreamingHttpResponse
            """
            resp = StreamingHttpResponse(self.sequence)
            resp["Content-Type"] = "text/html; charset=UTF-8"
            return resp

        r = GZipMiddleware(get_stream_response)(self.req)
        self.assertEqual(self.decompress(b"".join(r)), b"".join(self.sequence))
        self.assertEqual(r.get("Content-Encoding"), "gzip")
        self.assertFalse(r.has_header("Content-Length"))

    async def test_compress_async_streaming_response(self):
        """
        Compression is performed on responses with async streaming content.
        """

        async def get_stream_response(request):
            """

            Returns a streaming HTTP response containing the contents of a sequence.

            This function generates a StreamingHttpResponse object that yields the sequence
            in chunks, allowing for efficient transmission of large datasets. The response
            is set to have a Content-Type of 'text/html; charset=UTF-8', indicating that
            the contents are HTML text encoded in UTF-8.

            The function is designed to be used in asynchronous environments and provides
            a convenient way to stream data to clients without having to load the entire
            sequence into memory.

            :param request: The HTTP request object associated with the response.
            :return: A StreamingHttpResponse object containing the sequence.

            """
            async def iterator():
                for chunk in self.sequence:
                    yield chunk

            resp = StreamingHttpResponse(iterator())
            resp["Content-Type"] = "text/html; charset=UTF-8"
            return resp

        r = await GZipMiddleware(get_stream_response)(self.req)
        self.assertEqual(
            self.decompress(b"".join([chunk async for chunk in r])),
            b"".join(self.sequence),
        )
        self.assertEqual(r.get("Content-Encoding"), "gzip")
        self.assertFalse(r.has_header("Content-Length"))

    def test_compress_streaming_response_unicode(self):
        """
        Compression is performed on responses with streaming Unicode content.
        """

        def get_stream_response_unicode(request):
            """

            Returns a response to the given request with a streaming HTTP response of Unicode content.

            The response is generated with a content type of 'text/html' and a character encoding of 'UTF-8', 
            allowing for correct display of Unicode characters in the response.

             Args:
                request: The incoming request to generate a response for.

             Returns:
                A StreamingHttpResponse object containing the Unicode content.

            """
            resp = StreamingHttpResponse(self.sequence_unicode)
            resp["Content-Type"] = "text/html; charset=UTF-8"
            return resp

        r = GZipMiddleware(get_stream_response_unicode)(self.req)
        self.assertEqual(
            self.decompress(b"".join(r)),
            b"".join(x.encode() for x in self.sequence_unicode),
        )
        self.assertEqual(r.get("Content-Encoding"), "gzip")
        self.assertFalse(r.has_header("Content-Length"))

    def test_compress_file_response(self):
        """
        Compression is performed on FileResponse.
        """
        with open(__file__, "rb") as file1:

            def get_response(req):
                """
                Returns a file response containing the contents of a predefined HTML file.

                 This function generates a response to a request, where the response body is the contents of a specific file. 
                 The response is formatted as HTML with UTF-8 character encoding.

                 :param req: The request that triggered this response
                 :return: A file response object containing the HTML file's contents
                """
                file_resp = FileResponse(file1)
                file_resp["Content-Type"] = "text/html; charset=UTF-8"
                return file_resp

            r = GZipMiddleware(get_response)(self.req)
            with open(__file__, "rb") as file2:
                self.assertEqual(self.decompress(b"".join(r)), file2.read())
            self.assertEqual(r.get("Content-Encoding"), "gzip")
            self.assertIsNot(r.file_to_stream, file1)

    def test_compress_non_200_response(self):
        """
        Compression is performed on responses with a status other than 200
        (#10762).
        """
        self.resp.status_code = 404
        r = GZipMiddleware(self.get_response)(self.req)
        self.assertEqual(self.decompress(r.content), self.compressible_string)
        self.assertEqual(r.get("Content-Encoding"), "gzip")

    def test_no_compress_short_response(self):
        """
        Compression isn't performed on responses with short content.
        """
        self.resp.content = self.short_string
        r = GZipMiddleware(self.get_response)(self.req)
        self.assertEqual(r.content, self.short_string)
        self.assertIsNone(r.get("Content-Encoding"))

    def test_no_compress_compressed_response(self):
        """
        Compression isn't performed on responses that are already compressed.
        """
        self.resp["Content-Encoding"] = "deflate"
        r = GZipMiddleware(self.get_response)(self.req)
        self.assertEqual(r.content, self.compressible_string)
        self.assertEqual(r.get("Content-Encoding"), "deflate")

    def test_no_compress_incompressible_response(self):
        """
        Compression isn't performed on responses with incompressible content.
        """
        self.resp.content = self.incompressible_string
        r = GZipMiddleware(self.get_response)(self.req)
        self.assertEqual(r.content, self.incompressible_string)
        self.assertIsNone(r.get("Content-Encoding"))

    def test_compress_deterministic(self):
        """
        Compression results are the same for the same content and don't
        include a modification time (since that would make the results
        of compression non-deterministic and prevent
        ConditionalGetMiddleware from recognizing conditional matches
        on gzipped content).
        """

        class DeterministicGZipMiddleware(GZipMiddleware):
            max_random_bytes = 0

        r1 = DeterministicGZipMiddleware(self.get_response)(self.req)
        r2 = DeterministicGZipMiddleware(self.get_response)(self.req)
        self.assertEqual(r1.content, r2.content)
        self.assertEqual(self.get_mtime(r1.content), 0)
        self.assertEqual(self.get_mtime(r2.content), 0)

    def test_random_bytes(self):
        """A random number of bytes is added to mitigate the BREACH attack."""
        with mock.patch(
            "django.utils.text.secrets.randbelow", autospec=True, return_value=3
        ):
            r = GZipMiddleware(self.get_response)(self.req)
        # The fourth byte of a gzip stream contains flags.
        self.assertEqual(r.content[3], gzip.FNAME)
        # A 3 byte filename "aaa" and a null byte are added.
        self.assertEqual(r.content[10:14], b"aaa\x00")
        self.assertEqual(self.decompress(r.content), self.compressible_string)

    def test_random_bytes_streaming_response(self):
        """A random number of bytes is added to mitigate the BREACH attack."""

        def get_stream_response(request):
            resp = StreamingHttpResponse(self.sequence)
            resp["Content-Type"] = "text/html; charset=UTF-8"
            return resp

        with mock.patch(
            "django.utils.text.secrets.randbelow", autospec=True, return_value=3
        ):
            r = GZipMiddleware(get_stream_response)(self.req)
            content = b"".join(r)
        # The fourth byte of a gzip stream contains flags.
        self.assertEqual(content[3], gzip.FNAME)
        # A 3 byte filename "aaa" and a null byte are added.
        self.assertEqual(content[10:14], b"aaa\x00")
        self.assertEqual(self.decompress(content), b"".join(self.sequence))


class ETagGZipMiddlewareTest(SimpleTestCase):
    """
    ETags are handled properly by GZipMiddleware.
    """

    rf = RequestFactory()
    compressible_string = b"a" * 500

    def test_strong_etag_modified(self):
        """
        GZipMiddleware makes a strong ETag weak.
        """

        def get_response(req):
            """
            Returns an HTTP response object with the specified string as its content and an ETag header set to \"eggs\". The response content is compressed to reduce the size of the data being sent. This function is useful for generating responses to HTTP requests where the content does not change frequently, allowing clients to cache the response and reduce subsequent requests to the server.
            """
            response = HttpResponse(self.compressible_string)
            response.headers["ETag"] = '"eggs"'
            return response

        request = self.rf.get("/", headers={"accept-encoding": "gzip, deflate"})
        gzip_response = GZipMiddleware(get_response)(request)
        self.assertEqual(gzip_response.headers["ETag"], 'W/"eggs"')

    def test_weak_etag_not_modified(self):
        """
        GZipMiddleware doesn't modify a weak ETag.
        """

        def get_response(req):
            response = HttpResponse(self.compressible_string)
            response.headers["ETag"] = 'W/"eggs"'
            return response

        request = self.rf.get("/", headers={"accept-encoding": "gzip, deflate"})
        gzip_response = GZipMiddleware(get_response)(request)
        self.assertEqual(gzip_response.headers["ETag"], 'W/"eggs"')

    def test_etag_match(self):
        """
        GZipMiddleware allows 304 Not Modified responses.
        """

        def get_response(req):
            return HttpResponse(self.compressible_string)

        def get_cond_response(req):
            return ConditionalGetMiddleware(get_response)(req)

        request = self.rf.get("/", headers={"accept-encoding": "gzip, deflate"})
        response = GZipMiddleware(get_cond_response)(request)
        gzip_etag = response.headers["ETag"]
        next_request = self.rf.get(
            "/",
            headers={"accept-encoding": "gzip, deflate", "if-none-match": gzip_etag},
        )
        next_response = ConditionalGetMiddleware(get_response)(next_request)
        self.assertEqual(next_response.status_code, 304)
