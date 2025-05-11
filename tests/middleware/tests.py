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
        Tests that a slashless URL is not modified when APPEND_SLASH is True, ensuring the developers' explicit routing decisions are respected.
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
        Tests whether the APPEND_SLASH setting correctly redirects URLs without a trailing slash to their canonical URL with a slash.
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
        Tests that the APPEND_SLASH setting correctly appends a slash to a URL path when redirecting a request with a query string that ends with a slash.
        """
        request = self.rf.get("/slash?test=slash/")
        resp = CommonMiddleware(get_response_404)(request)
        self.assertIsInstance(resp, HttpResponsePermanentRedirect)
        self.assertEqual(resp.url, "/slash/?test=slash/")

    @override_settings(APPEND_SLASH=True, DEBUG=True)
    def test_append_slash_no_redirect_in_DEBUG(self):
        """
        Tests that the CommonMiddleware raises an exception when attempting to make a POST, PUT, PATCH, or DELETE request to a URL without a trailing slash in debug mode, instead of silently redirecting to the slashed version.
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
        Tests that views marked with a decorator to opt out of the APPEND_SLASH feature are not modified.
        """
        request = self.rf.get("/sensitive_fbv")
        self.assertEqual(CommonMiddleware(get_response_404)(request).status_code, 404)

        request = self.rf.get("/sensitive_cbv")
        self.assertEqual(CommonMiddleware(get_response_404)(request).status_code, 404)

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_quoted(self):
        """
        Tests that URLs requiring quoting are correctly redirected to their slash version when APPEND_SLASH is True.
        """
        request = self.rf.get(quote("/needsquoting#"))
        r = CommonMiddleware(get_response_404)(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "/needsquoting%23/")

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_leading_slashes(self):
        """
        Tests that the CommonMiddleware correctly handles and escapes paths starting with multiple slashes to prevent open redirects when APPEND_SLASH is enabled.
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
        request = self.rf.get("/slash")
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/slash/")

    # The following tests examine expected behavior given a custom URLconf that
    # overrides the default one through the request object.

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_have_slash_custom_urlconf(self):
        """
        Tests whether URLs containing a trailing slash are handled correctly and left unmodified by the CommonMiddleware when a custom URL configuration is in use.
        """
        request = self.rf.get("/customurlconf/slash/")
        request.urlconf = "middleware.extra_urls"
        self.assertIsNone(CommonMiddleware(get_response_404).process_request(request))
        self.assertEqual(CommonMiddleware(get_response_404)(request).status_code, 404)

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_slashless_resource_custom_urlconf(self):
        """
        Tests that the CommonMiddleware does not append a slash to a slashless URL when a custom URL configuration is in use.
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
        Tests whether APPEND_SLASH functionality correctly handles unknown resources in a custom URL configuration, ensuring it does not redirect and instead returns a 404 status code.
        """
        request = self.rf.get("/customurlconf/unknown")
        request.urlconf = "middleware.extra_urls"
        self.assertIsNone(CommonMiddleware(get_response_404).process_request(request))
        self.assertEqual(CommonMiddleware(get_response_404)(request).status_code, 404)

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_redirect_custom_urlconf(self):
        """
        Tests that APPEND_SLASH setting correctly redirects URLs without a trailing slash to a valid pattern when a custom URL configuration is used.
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

        Tests that a POST request to a URL that would normally be redirected to 
        its slashed version raises an exception in DEBUG mode, rather than 
        redirecting, when using a custom URL configuration.

        """
        request = self.rf.get("/customurlconf/slash")
        request.urlconf = "middleware.extra_urls"
        request.method = "POST"
        with self.assertRaisesMessage(RuntimeError, "end in a slash"):
            CommonMiddleware(get_response_404)(request)

    @override_settings(APPEND_SLASH=False)
    def test_append_slash_disabled_custom_urlconf(self):
        """
        Tests the behavior of the CommonMiddleware when the APPEND_SLASH setting is disabled, ensuring that URLs without a trailing slash are not modified and return a 404 status code.
        """
        request = self.rf.get("/customurlconf/slash")
        request.urlconf = "middleware.extra_urls"
        self.assertIsNone(CommonMiddleware(get_response_404).process_request(request))
        self.assertEqual(CommonMiddleware(get_response_404)(request).status_code, 404)

    @override_settings(APPEND_SLASH=True)
    def test_append_slash_quoted_custom_urlconf(self):
        """
        Tests if the CommonMiddleware properly appends a slash to custom URL confs that require quoting, verifying the redirect response.
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
        Tests that the CommonMiddleware correctly prepends 'www' to a custom URL configuration when the PREPEND_WWW setting is enabled.
        """
        request = self.rf.get("/customurlconf/path/")
        request.urlconf = "middleware.extra_urls"
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/customurlconf/path/")

    @override_settings(APPEND_SLASH=True, PREPEND_WWW=True)
    def test_prepend_www_append_slash_have_slash_custom_urlconf(self):
        """
        Tests that the CommonMiddleware correctly prepends 'www' to the URL and appends a slash when the URL already has a trailing slash and a custom URL configuration is in use, resulting in a 301 redirect to the modified URL.
        """
        request = self.rf.get("/customurlconf/slash/")
        request.urlconf = "middleware.extra_urls"
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/customurlconf/slash/")

    @override_settings(APPEND_SLASH=True, PREPEND_WWW=True)
    def test_prepend_www_append_slash_slashless_custom_urlconf(self):
        """
        Tests the behavior of the CommonMiddleware when the APPEND_SLASH and PREPEND_WWW settings are enabled and a custom URL configuration is used, ensuring that a slash is appended to the URL and 'www' is prepended to the domain in a 301 redirect response.
        """
        request = self.rf.get("/customurlconf/slash")
        request.urlconf = "middleware.extra_urls"
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/customurlconf/slash/")

    # Tests for the Content-Length header

    def test_content_length_header_added(self):
        """

        Verifies that the Content-Length header is added to an HTTP response when using the CommonMiddleware.

        Tests that the middleware correctly calculates and includes the Content-Length header in the response,
        ensuring that the length matches the actual content length.

        """
        def get_response(req):
            response = HttpResponse("content")
            self.assertNotIn("Content-Length", response)
            return response

        response = CommonMiddleware(get_response)(self.rf.get("/"))
        self.assertEqual(int(response.headers["Content-Length"]), len(response.content))

    def test_content_length_header_not_added_for_streaming_response(self):
        """
        Ensures the 'Content-Length' header is not added to responses when using a streaming HTTP response.
        """
        def get_response(req):
            response = StreamingHttpResponse("content")
            self.assertNotIn("Content-Length", response)
            return response

        response = CommonMiddleware(get_response)(self.rf.get("/"))
        self.assertNotIn("Content-Length", response)

    def test_content_length_header_not_changed(self):
        """
        Tests that the Content-Length header set by the application is not modified by the CommonMiddleware.
        """
        bad_content_length = 500

        def get_response(req):
            response = HttpResponse()
            response.headers["Content-Length"] = bad_content_length
            return response

        response = CommonMiddleware(get_response)(self.rf.get("/"))
        self.assertEqual(int(response.headers["Content-Length"]), bad_content_length)

    # Other tests

    @override_settings(DISALLOWED_USER_AGENTS=[re.compile(r"foo")])
    def test_disallowed_user_agents(self):
        request = self.rf.get("/slash")
        request.META["HTTP_USER_AGENT"] = "foo"
        with self.assertRaisesMessage(PermissionDenied, "Forbidden user agent"):
            CommonMiddleware(get_response_empty).process_request(request)

    def test_non_ascii_query_string_does_not_crash(self):
        """
        Tests that the application correctly handles non-ASCII characters in query strings, verifying a fix for a previous crash issue.
        """
        request = self.rf.get("/slash")
        request.META["QUERY_STRING"] = "drink=café"
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertIsNone(r)
        response = HttpResponseNotFound()
        r = CommonMiddleware(get_response_empty).process_response(request, response)
        self.assertEqual(r.status_code, 301)

    def test_response_redirect_class(self):
        """
        Tests that a GET request to a URL without a trailing slash receives a permanent redirect to the same URL with a trailing slash.
        """
        request = self.rf.get("/slash")
        r = CommonMiddleware(get_response_404)(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "/slash/")
        self.assertIsInstance(r, HttpResponsePermanentRedirect)

    def test_response_redirect_class_subclass(self):
        """

        Tests that a subclass of CommonMiddleware correctly redirects to a URL with a trailing slash.

        This test case verifies that the response_redirect_class attribute can be overridden
        to return an instance of the specified redirect class.

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
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 0)

    def test_404_error_reporting_ignored_url(self):
        self.req.path = self.req.path_info = "foo_url/that/does/not/exist"
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 0)

    def test_custom_request_checker(self):
        """
        Tests the custom request checking functionality of the BrokenLinkEmailsMiddleware by subclassing it with additional user-agent patterns, simulating ignorable and non-ignorable requests, and verifying the expected email sending behavior.
        """
        class SubclassedMiddleware(BrokenLinkEmailsMiddleware):
            ignored_user_agent_patterns = (
                re.compile(r"Spider.*"),
                re.compile(r"Robot.*"),
            )

            def is_ignorable_request(self, request, uri, domain, referer):
                """
                Determines whether an incoming request should be ignored based on the user's user-agent, in addition to standard ignorable request checks.
                """
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
        Tests that BrokenLinkEmailsMiddleware does not send emails when the referer is equal to the requested URL, even when the request is made over HTTPS via a proxy.
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
        Tests the ConditionalGetMiddleware when the If-None-Match header matches the ETag and a redirect is returned. 
        Verifies that the middleware correctly handles this scenario and returns a 301 status code.
        """
        def get_response(req):
            """
            Generate a redirect response by sending a request to the client.

             The function builds a response object, applies a custom ETag, redirects the user to the root page,
             and returns the response object with a 301 status code (Moved Permanently).
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
        Tests if ConditionalGetMiddleware returns a 400 status code when the If-None-Match header matches the ETag, but the underlying response is a client error.
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
        self.resp_headers["Last-Modified"] = "Sat, 12 Feb 2011 17:38:44 GMT"
        resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(resp.status_code, 200)

    def test_if_modified_since_and_same_last_modified(self):
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
        Tests the ConditionalGetMiddleware when 'If-Modified-Since' header is present, 
        verifying it honors the 301 redirect even if the requested resource has not been modified since the specified date.
        """
        def get_response(req):
            """
            Return a HTTP response object with a 301 redirect status code, 
            redirecting to the root URL and specifying a fixed Last-Modified header.
            """
            resp = self.client.get(req.path_info)
            resp["Last-Modified"] = "Sat, 12 Feb 2011 17:35:44 GMT"
            resp["Location"] = "/"
            resp.status_code = 301
            return resp

        self.req.META["HTTP_IF_MODIFIED_SINCE"] = "Sat, 12 Feb 2011 17:38:44 GMT"
        resp = ConditionalGetMiddleware(get_response)(self.req)
        self.assertEqual(resp.status_code, 301)

    def test_if_modified_since_and_client_error(self):
        """

        Tests if the ConditionalGetMiddleware handles the 'If-Modified-Since' header correctly 
        when the client makes an invalid request, resulting in a 400 error response.

        """
        def get_response(req):
            resp = self.client.get(req.path_info)
            resp["Last-Modified"] = "Sat, 12 Feb 2011 17:35:44 GMT"
            resp.status_code = 400
            return resp

        self.req.META["HTTP_IF_MODIFIED_SINCE"] = "Sat, 12 Feb 2011 17:38:44 GMT"
        resp = ConditionalGetMiddleware(get_response)(self.req)
        self.assertEqual(resp.status_code, 400)

    def test_not_modified_headers(self):
        """
        Tests that a 304 Not Modified response from the ConditionalGetMiddleware includes only the required headers and cookies, as specified by RFC 9110.
        """

        def get_response(req):
            """
            Returns a response object with predefined HTTP headers for a given request.

            The response includes various headers such as Date, Last-Modified, Expires, and Cache-Control,
            as well as a set cookie. It appears to be a mocked or standardized response for testing purposes.
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
        Tests that ConditionalGetMiddleware does not return a conditional response 
        for an unsafe request, returning a standard 200 response instead.
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
        Tests that ConditionalGetMiddleware does not compute an ETag for a HEAD request, as it cannot be determined accurately without the corresponding GET response body.
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
        Tests that the XFrameOptionsMiddleware correctly sets the X-Frame-Options HTTP header to 'SAMEORIGIN' when the X_FRAME_OPTIONS setting is set to 'SAMEORIGIN' or 'sameorigin'.
        """
        with override_settings(X_FRAME_OPTIONS="SAMEORIGIN"):
            r = XFrameOptionsMiddleware(get_response_empty)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "SAMEORIGIN")

        with override_settings(X_FRAME_OPTIONS="sameorigin"):
            r = XFrameOptionsMiddleware(get_response_empty)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "SAMEORIGIN")

    def test_deny(self):
        """
        Tests the XFrameOptionsMiddleware with the X_FRAME_OPTIONS setting set to 'DENY', verifying the middleware correctly sets the 'X-Frame-Options' HTTP header to 'DENY' in a case-insensitive manner.
        """
        with override_settings(X_FRAME_OPTIONS="DENY"):
            r = XFrameOptionsMiddleware(get_response_empty)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "DENY")

        with override_settings(X_FRAME_OPTIONS="deny"):
            r = XFrameOptionsMiddleware(get_response_empty)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "DENY")

    def test_defaults_sameorigin(self):
        """
        Tests that the X_FRAME_OPTIONS header defaults to 'DENY' when the setting is not explicitly configured.
        """
        with override_settings(X_FRAME_OPTIONS=None):
            del settings.X_FRAME_OPTIONS  # restored by override_settings
            r = XFrameOptionsMiddleware(get_response_empty)(HttpRequest())
            self.assertEqual(r.headers["X-Frame-Options"], "DENY")

    def test_dont_set_if_set(self):
        """
        Tests that the XFrameOptionsMiddleware does not override the X-Frame-Options header if it has already been set.
        """

        def same_origin_response(request):
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
        Tests that the X-Frame-Options header is correctly set or absent based on the xframe_options_exempt attribute of the response.
        """

        def xframe_exempt_response(request):
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
        Tests that the X-Frame-Options header value can be dynamically overridden based on attributes of the request or response.
        """

        class OtherXFrameOptionsMiddleware(XFrameOptionsMiddleware):
            # This is just an example for testing purposes...
            def get_xframe_options_value(self, request, response):
                """
                Determines the X-Frame-Options header value based on the request and response.
                Returns 'SAMEORIGIN' if either the request or response has the sameorigin attribute set,
                otherwise returns 'DENY'.
                """
                if getattr(request, "sameorigin", False):
                    return "SAMEORIGIN"
                if getattr(response, "sameorigin", False):
                    return "SAMEORIGIN"
                return "DENY"

        def same_origin_response(request):
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
        Sets up a test request and response with default metadata and content for testing purposes.
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
        with gzip.GzipFile(mode="rb", fileobj=BytesIO(gzipped_string)) as f:
            return f.read()

    @staticmethod
    def get_mtime(gzipped_string):
        with gzip.GzipFile(mode="rb", fileobj=BytesIO(gzipped_string)) as f:
            f.read()  # must read the data before accessing the header
            return f.mtime

    def test_compress_response(self):
        """

        Tests that HTTP responses with compressible content are properly compressed using gzip.

        Verifies that the compressed response content matches the original string after decompression,
        and that the correct 'Content-Encoding' and 'Content-Length' headers are set.

        """
        r = GZipMiddleware(self.get_response)(self.req)
        self.assertEqual(self.decompress(r.content), self.compressible_string)
        self.assertEqual(r.get("Content-Encoding"), "gzip")
        self.assertEqual(r.get("Content-Length"), str(len(r.content)))

    def test_compress_streaming_response(self):
        """

        Tests that a streaming response is successfully compressed by the GZip middleware.
        Verifies that the compressed response is correctly decompressed and that the 'Content-Encoding' header is set to 'gzip'.

        """

        def get_stream_response(request):
            resp = StreamingHttpResponse(self.sequence)
            resp["Content-Type"] = "text/html; charset=UTF-8"
            return resp

        r = GZipMiddleware(get_stream_response)(self.req)
        self.assertEqual(self.decompress(b"".join(r)), b"".join(self.sequence))
        self.assertEqual(r.get("Content-Encoding"), "gzip")
        self.assertFalse(r.has_header("Content-Length"))

    async def test_compress_async_streaming_response(self):
        """

        Tests that the GZipMiddleware correctly compresses async streaming responses.
        Verifies that the compressed response is decompressible and that the correct headers are set.

        """

        async def get_stream_response(request):
            """
            Returns a StreamingHttpResponse object that iterates over a sequence of chunks, 
            delivered as a text/html response with UTF-8 encoding.
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
        Tests that GZipMiddleware correctly compresses HTTP responses with streaming Unicode content.
        """

        def get_stream_response_unicode(request):
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
        Tests that the GZipMiddleware correctly compresses a FileResponse, 
         verifying the response content is properly decompressed and the 
         'Content-Encoding' header is set to 'gzip'.
        """
        with open(__file__, "rb") as file1:

            def get_response(req):
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
        Tests that the compression middleware compresses responses with non-200 status codes, such as 404 errors, and verifies that the compressed content is correct and the Content-Encoding header is set to 'gzip'.
        """
        self.resp.status_code = 404
        r = GZipMiddleware(self.get_response)(self.req)
        self.assertEqual(self.decompress(r.content), self.compressible_string)
        self.assertEqual(r.get("Content-Encoding"), "gzip")

    def test_no_compress_short_response(self):
        """
        Tests that the GZip middleware does not compress responses with short content, ensuring that the response remains unchanged and no Content-Encoding header is added.
        """
        self.resp.content = self.short_string
        r = GZipMiddleware(self.get_response)(self.req)
        self.assertEqual(r.content, self.short_string)
        self.assertIsNone(r.get("Content-Encoding"))

    def test_no_compress_compressed_response(self):
        """
        Tests that a response that is already compressed is not re-compressed by the GZipMiddleware.
        """
        self.resp["Content-Encoding"] = "deflate"
        r = GZipMiddleware(self.get_response)(self.req)
        self.assertEqual(r.content, self.compressible_string)
        self.assertEqual(r.get("Content-Encoding"), "deflate")

    def test_no_compress_incompressible_response(self):
        """
        Tests that the response content is not compressed when it contains incompressible data, and that the Content-Encoding header is not set.
        """
        self.resp.content = self.incompressible_string
        r = GZipMiddleware(self.get_response)(self.req)
        self.assertEqual(r.content, self.incompressible_string)
        self.assertIsNone(r.get("Content-Encoding"))

    def test_compress_deterministic(self):
        """
        Verifies that compression results are deterministic and do not include a modification time, ensuring compatibility with ConditionalGetMiddleware for gzipped content.
        """

        class DeterministicGZipMiddleware(GZipMiddleware):
            max_random_bytes = 0

        r1 = DeterministicGZipMiddleware(self.get_response)(self.req)
        r2 = DeterministicGZipMiddleware(self.get_response)(self.req)
        self.assertEqual(r1.content, r2.content)
        self.assertEqual(self.get_mtime(r1.content), 0)
        self.assertEqual(self.get_mtime(r2.content), 0)

    def test_random_bytes(self):
        """
        Tests the GZipMiddleware's response to mitigate the BREACH attack by verifying that a random number of bytes is added to the response and that the compressed content is correct.
        """
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
        """
        测试中间件对HTTP响应进行GZip压缩的功能，特别是在使用流媒体方式发送响应时。该测试确保对带有随机字节的响应进行正确压缩和解压缩，确保中间件正常工作并能够抵御BREACH攻击。
        """

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
        Tests that GZipMiddleware correctly converts a strong ETag to a weak ETag when gzip compression is enabled.
        """

        def get_response(req):
            response = HttpResponse(self.compressible_string)
            response.headers["ETag"] = '"eggs"'
            return response

        request = self.rf.get("/", headers={"accept-encoding": "gzip, deflate"})
        gzip_response = GZipMiddleware(get_response)(request)
        self.assertEqual(gzip_response.headers["ETag"], 'W/"eggs"')

    def test_weak_etag_not_modified(self):
        """
        Tests that GZipMiddleware preserves a weak ETag header in the response, ensuring it remains unchanged after compression.
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
        Tests that the ETag header generated by the GZipMiddleware is properly used to trigger a 304 Not Modified response when the client's request includes an If-None-Match header with the same ETag.
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
