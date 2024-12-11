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
        """

        Tests that the CommonMiddleware correctly prepends 'www' to the start of a URL when the PREPEND_WWW setting is enabled.

        This test case verifies that when a request is made without the 'www' subdomain, the middleware redirects the request to the same URL with 'www' prepended, as specified by the PREPEND_WWW setting.

        The test checks for a successful redirect by verifying the status code of the response is 301 and that the URL of the redirect matches the expected 'www' prefixed URL.

        """
        request = self.rf.get("/path/")
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/path/")

    @override_settings(APPEND_SLASH=True, PREPEND_WWW=True)
    def test_prepend_www_append_slash_have_slash(self):
        """

        Test case for a request that already has a trailing slash and 
        should be redirected with both 'www' prepended to the hostname 
        and the trailing slash preserved.

        The test verifies that a GET request to a URL with a trailing 
        slash is correctly redirected to the corresponding URL with 
        'www' prepended to the hostname and the trailing slash preserved.
        The expected redirect status code is 301 (Moved Permanently).

        """
        request = self.rf.get("/slash/")
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/slash/")

    @override_settings(APPEND_SLASH=True, PREPEND_WWW=True)
    def test_prepend_www_append_slash_slashless(self):
        """
        Tests the behavior of the CommonMiddleware when both APPEND_SLASH and PREPEND_WWW settings are enabled. Verifies that a request to a slashless URL is redirected to its equivalent URL with a trailing slash and the 'www.' subdomain prepended to the host. The expected behavior includes a permanent redirect (301 status code) to the updated URL.
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

        Tests whether the CommonMiddleware correctly prepends 'www' to the URL when a custom URL configuration is used.

        This test case verifies that when a request is made to a path defined in a custom URL configuration, the
        middleware redirects the request to the same path but with 'www' prepended to the domain name.

        The expected behavior is a 301 redirect to the URL with 'www' prepended, indicating that the middleware is
        correctly configured to modify the URL as required.

        """
        request = self.rf.get("/customurlconf/path/")
        request.urlconf = "middleware.extra_urls"
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/customurlconf/path/")

    @override_settings(APPEND_SLASH=True, PREPEND_WWW=True)
    def test_prepend_www_append_slash_have_slash_custom_urlconf(self):
        request = self.rf.get("/customurlconf/slash/")
        request.urlconf = "middleware.extra_urls"
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/customurlconf/slash/")

    @override_settings(APPEND_SLASH=True, PREPEND_WWW=True)
    def test_prepend_www_append_slash_slashless_custom_urlconf(self):
        """

        Tests the behavior of the CommonMiddleware when the APPEND_SLASH and PREPEND_WWW settings are enabled.
        Verifies that a 301 redirect is returned for a slashless custom URL, and that the redirect URL is correctly prepended with 'www' and appended with a slash.

        The test case covers the scenario where the request URL does not have a trailing slash, and the CUSTOM_URLCONF setting points to a custom URL configuration.
        The expected outcome is that the middleware redirects the request to the same URL with a trailing slash, and the 'www' subdomain is prepended to the host.

        """
        request = self.rf.get("/customurlconf/slash")
        request.urlconf = "middleware.extra_urls"
        r = CommonMiddleware(get_response_empty).process_request(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "http://www.testserver/customurlconf/slash/")

    # Tests for the Content-Length header

    def test_content_length_header_added(self):
        """
        :param self: Test case instance
        :returns: None
        :rtype: None

        Tests that the Content-Length header is added to the response when using the CommonMiddleware.

        The Content-Length header is a crucial part of the HTTP protocol, specifying the size of the response body in bytes. This test ensures that when using the CommonMiddleware, the Content-Length header is correctly calculated and added to the response, with its value matching the length of the response content.
        """
        def get_response(req):
            """
            Return a Django HTTP response object with the given content.

            The returned response does not include the 'Content-Length' header.
            This is typically used in situations where the content length is not fixed or known beforehand.

            :returns: A Django HttpResponse object without a 'Content-Length' header
            """
            response = HttpResponse("content")
            self.assertNotIn("Content-Length", response)
            return response

        response = CommonMiddleware(get_response)(self.rf.get("/"))
        self.assertEqual(int(response.headers["Content-Length"]), len(response.content))

    def test_content_length_header_not_added_for_streaming_response(self):
        """

        Tests that the 'Content-Length' header is not added to the response when using a streaming HTTP response.

        This test case verifies that the middleware does not attempt to calculate the content length
        of a streaming response, which would be impossible to determine without consuming the entire stream.
        Instead, it ensures that the middleware leaves the 'Content-Length' header absent, allowing the
        server to handle the response appropriately.

        The test covers the usage of the CommonMiddleware with a custom response handler that returns
        a StreamingHttpResponse, simulating a streaming response scenario.

        """
        def get_response(req):
            response = StreamingHttpResponse("content")
            self.assertNotIn("Content-Length", response)
            return response

        response = CommonMiddleware(get_response)(self.rf.get("/"))
        self.assertNotIn("Content-Length", response)

    def test_content_length_header_not_changed(self):
        """

        Verifies that the Content-Length header of an HTTP response remains unchanged after passing through a middleware.

        This test case checks that the middleware does not modify the Content-Length header in the response, even if it contains an unexpected value.

        :raises: AssertionError if the Content-Length header is modified by the middleware.

        """
        bad_content_length = 500

        def get_response(req):
            """
            Returns an HTTP response object.

            This function constructs an HttpResponse object and modifies its headers to include a custom 'Content-Length' value.
            The returned response is intended for further processing or transmission, allowing for customization of the HTTP response characteristics.

            Args:
                req: The input request object, used as a context for generating the response.

            Returns:
                HttpResponse: The generated HTTP response object with a modified 'Content-Length' header.

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
        Tests the CommonMiddleware's handling of disallowed user agents.

        This test checks that when a request is made with a user agent that matches a pattern
        in the DISALLOWED_USER_AGENTS setting, a PermissionDenied exception is raised with
        a 'Forbidden user agent' message. The test simulates a request with a disallowed
        user agent and verifies that the expected exception is raised.
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
        request = self.rf.get("/slash")
        r = CommonMiddleware(get_response_404)(request)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.url, "/slash/")
        self.assertIsInstance(r, HttpResponsePermanentRedirect)

    def test_response_redirect_class_subclass(self):
        """
        Tests that the response redirect class can be subclassed and overridden.

        This test case verifies that a custom middleware class can extend the base CommonMiddleware
        class and redefine the response redirect class. The test creates a custom middleware class
        (MyCommonMiddleware) that uses HttpResponseRedirect as the response redirect class and then
        checks that the middleware correctly redirects a request to the desired URL.

        The test ensures that the response code is set to 302 (Found), the redirect URL is correct,
        and the response object is an instance of the overridden response redirect class.
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
        """

        Tests that a 404 error is correctly reported via email.

        This test case simulates a request to a non-existent page and verifies that 
        an email notification is sent with the correct subject. It checks that 
        the email is triggered by the BrokenLinkEmailsMiddleware and that the 
        subject of the email contains the expected 'Broken' keyword, indicating 
        a broken link error.

        """
        self.req.META["HTTP_REFERER"] = "/another/url/"
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Broken", mail.outbox[0].subject)

    def test_404_error_reporting_no_referer(self):
        """
        Tests the 404 error reporting functionality when there is no HTTP referer.
        Verifies that no email is sent by the BrokenLinkEmailsMiddleware under these conditions, ensuring that error reporting only occurs when a valid referer is present.
        """
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 0)

    def test_404_error_reporting_ignored_url(self):
        """
        .Tests that the BrokenLinkEmailsMiddleware does not send an email when a 404 error occurs on a URL that is meant to be ignored. 

        This test case simulates a request to a non-existent URL and verifies that no email is triggered by the middleware, ensuring the error reporting mechanism is functioning as expected and ignoring the specified URLs.
        """
        self.req.path = self.req.path_info = "foo_url/that/does/not/exist"
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 0)

    def test_custom_request_checker(self):
        """

        Tests the custom request checker functionality in the BrokenLinkEmailsMiddleware.

        This test case verifies that the middleware correctly ignores requests from specified user agents
        and sends an email when a request is not ignorable. It creates a subclass of the middleware with
        custom ignored user agent patterns, simulates requests with different user agents, and checks the
        email outbox for expected results.

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
        """

        Test that a broken link email is sent when the referer is on a different domain.

        This test checks the functionality of the BrokenLinkEmailsMiddleware when the
        referer URL is from a different domain than the requested URL. It verifies that
        in such cases, an email notification is sent, indicating a broken link.

        """
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
        """

        Test that the Broken Link Emails middleware correctly identifies a broken link
        when the referer URL is equal to the requested URL without a trailing slash and
        the APPEND_SLASH setting is False.

        Verifies that an email notification is sent when a broken link is encountered
        under these specific conditions, ensuring that the middleware behaves as expected
        in this edge case.

        """
        self.req.path = self.req.path_info = "/regular_url/that/does/not/exist/"
        self.req.META["HTTP_REFERER"] = self.req.path_info[:-1]
        BrokenLinkEmailsMiddleware(self.get_response)(self.req)
        self.assertEqual(len(mail.outbox), 1)


@override_settings(ROOT_URLCONF="middleware.cond_get_urls")
class ConditionalGetMiddlewareTest(SimpleTestCase):
    request_factory = RequestFactory()

    def setUp(self):
        """
        Sets up the environment for testing by creating a request object and an empty dictionary to store response headers.

        The request object is created using the request_factory, simulating a GET request to the root URL ('/'). The response headers dictionary is initialized empty, allowing for the storage of headers as needed during testing.

        This method is intended to be used as a setup routine prior to running tests, providing a common starting point for test cases.
        """
        self.req = self.request_factory.get("/")
        self.resp_headers = {}

    def get_response(self, req):
        """
        ..:noindex:
            Retrieves a response based on the provided request.

            :param req: The request object containing the path information.
            :return: A response object with headers populated from the :attr:`resp_headers` dictionary.
            :rtype: Response object

            This function leverages the :attr:`client` object to fetch a response for the given request path.
            It then augments the response with predefined headers, ensuring consistency across responses.
            The resulting response object is then returned, making it suitable for further processing or direct output.
        """
        resp = self.client.get(req.path_info)
        for key, value in self.resp_headers.items():
            resp[key] = value
        return resp

    # Tests for the ETag header

    def test_middleware_calculates_etag(self):
        """
        Tests whether the ConditionalGetMiddleware correctly calculates the ETag header.

        This test verifies that the middleware returns a successful response (200 OK)
        and includes a non-empty ETag header in the response, confirming that it
        properly calculated the ETag value.

        The test assumes a typical request-response flow, where the middleware is
        invoked with a sample request and is expected to produce a valid response
        with the ETag header populated accordingly.
        """
        resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual("", resp["ETag"])

    def test_middleware_wont_overwrite_etag(self):
        """
        Tests that the ConditionalGetMiddleware does not overwrite an existing ETag header.

        This test case verifies that if an ETag header is already present in the response,
        the middleware will not modify or overwrite it. The test checks the status code
        of the response and confirms that the original ETag value is preserved in the
        response headers.
        """
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
        """
        Test that the ConditionalGetMiddleware does not include an ETag header in its response when the Cache-Control header specifies 'No-Cache, No-Store' and the request does not provide an ETag. This ensures that the middleware adheres to standard caching directives and prevents caching of sensitive data.
        """
        self.resp_headers["Cache-Control"] = "No-Cache, No-Store, Max-age=0"
        self.assertFalse(
            ConditionalGetMiddleware(self.get_response)(self.req).has_header("ETag")
        )

    def test_etag_extended_cache_control(self):
        """
        Tests the ConditionalGetMiddleware to verify that it includes an ETag header 
        in the response when the Cache-Control header contains an extended directive, 
        even if the directive would normally prevent caching. 

        This test case checks the middleware's behavior when the Cache-Control header 
        contains a custom directive that would normally prevent caching, and verifies 
        that the ETag header is still included in the response to support conditional 
        GET requests.
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
        """
        Tests the ConditionalGetMiddleware when the If-None-Match header matches the ETag header.

        Verifies that the middleware returns a 304 status code (Not Modified) when the request
        includes an If-None-Match header that matches the ETag of the response, indicating that
        the client has a valid cached copy of the resource and there is no need for a full response.
        """
        self.req.META["HTTP_IF_NONE_MATCH"] = '"spam"'
        self.resp_headers["ETag"] = '"spam"'
        resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(resp.status_code, 304)

    def test_if_none_match_and_different_etag(self):
        """
        Tests the ConditionalGetMiddleware when the 'If-None-Match' request header and the 'ETag' response header have different values, ensuring that the response is returned with a 200 status code, rather than a 304 status code, which would be expected if the 'If-None-Match' header matched the 'ETag' header. This verifies that the middleware correctly handles mismatches between these headers.
        """
        self.req.META["HTTP_IF_NONE_MATCH"] = "spam"
        self.resp_headers["ETag"] = "eggs"
        resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(resp.status_code, 200)

    def test_if_none_match_and_redirect(self):
        def get_response(req):
            """
            Return a response object with a redirect status.

            This function generates a HTTP response with a 301 status code, indicating a permanent redirect.
            The response headers are modified to include a custom ETag and a Location header set to the root URL ('/').
            The function takes a request object as input and uses its path information to construct the response.

            :param req: The request object containing path information.
            :return: A response object with a 301 status code and custom headers.

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

        Tests the behavior of ConditionalGetMiddleware when the If-None-Match header matches the ETag of the response, 
        but the response from the GET request is a client error (4xx status code).

        Verifies that the middleware does not override the client error status code with a 304 Not Modified status code, 
        ensuring that the original error is propagated to the client.

        """
        def get_response(req):
            """
            Return a modified HTTP response object.

            This function takes an incoming request as input and generates a response 
            object. It sends a GET request to the client using the path information 
            from the incoming request, then modifies the response by setting a 
            custom ETag header and an HTTP status code of 400 (Bad Request). The 
            modified response object is then returned.

            :param req: The incoming request object.
            :rtype: A modified HTTP response object.
            """
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
        Tests the ConditionalGetMiddleware when no 'If-Modified-Since' header is provided in the request, 
        but a 'Last-Modified' header is present in the response. Verifies that the response status code 
        is 200, indicating a successful request.
        """
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
        """
        Tests the ConditionalGetMiddleware when If-Modified-Since and Last-Modified headers are set with dates in the past and future, respectively.

        Verifies that the middleware returns a 200 status code when the requested resource has been modified after the date specified in the If-Modified-Since header.

        This test scenario ensures that the middleware correctly handles cases where the client's cached version is outdated and a fresh version of the resource is available on the server.
        """
        self.req.META["HTTP_IF_MODIFIED_SINCE"] = "Sat, 12 Feb 2011 17:38:44 GMT"
        self.resp_headers["Last-Modified"] = "Sat, 12 Feb 2011 17:41:44 GMT"
        self.resp = ConditionalGetMiddleware(self.get_response)(self.req)
        self.assertEqual(self.resp.status_code, 200)

    def test_if_modified_since_and_redirect(self):
        def get_response(req):
            """
            Return a HTTP response for the given request.

            This function generates a response with a 301 status code, indicating a permanent redirect. 
            The response includes headers for 'Last-Modified' and 'Location', where 'Location' is set to the root URL ('/'). 
            The 'Last-Modified' header is set to a fixed date and time, regardless of the request details. 
            The returned response object can be used to redirect the client to the specified location.

            :param req: The incoming request object.
            :rtype: response object
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
        Tests the ConditionalGetMiddleware when the client sends an If-Modified-Since header
        and the backend returns a client error.

        This test verifies that the middleware correctly handles the case where the client
        requests a resource with an If-Modified-Since header, but the backend responds with
        a 4xx status code, indicating an error on the client side. The expected behavior is
        that the middleware returns the backend's error response, rather than attempting to
        process the If-Modified-Since header.

        The test case simulates a backend response with a Last-Modified header and a 400
        status code, and checks that the middleware returns a response with the same status
        code, indicating that the client error takes precedence over any potential caching
        or conditional get logic.
        """
        def get_response(req):
            """

            Retrieves a response object based on the provided request.

            The function sends a GET request to the client using the path information from the input request.
            It then modifies the response by setting a fixed 'Last-Modified' header and a status code of 400 (Bad Request).
            The modified response object is then returned, indicating an error in the request processing.

            Args:
                req: The input request object containing the path information.

            Returns:
                A response object with a status code of 400 and a modified 'Last-Modified' header.

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

            Return a standardized HTTP response object containing common headers and cookie.

            The response is generated based on the provided request object, with additional
            headers such as 'Date', 'Last-Modified', 'Expires', and others set to fixed
            values. A cookie with key 'key' and value 'value' is also set in the response.

            The returned response object is populated with default values for caching,
            language, and other parameters, which can be used as a starting point for
            building a custom response.

            :rtype: HTTP response object

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
            Returns an HTTP response that allows the browser to render the page only if the origin of the request is the same as the origin of the page.

            This function is useful for preventing clickjacking attacks by specifying that the page can only be framed by pages from the same origin.

            :returns: An HTTP response with the X-Frame-Options header set to SAMEORIGIN.
            """
            response = HttpResponse()
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            return response

        def deny_response(request):
            """

            Returns an HTTP response that denies framing of the content.

            This function generates a response with the X-Frame-Options header set to 'DENY',
            preventing the page from being iframed by third-party sites, thus helping to
            prevent clickjacking attacks.

            :rtype: HttpResponse

            """
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

            Returns an HTTP response with the X-Frame-Options header set to exempt,
            allowing the response to be framed by other websites.

            This is useful for pages that need to be embedded in iframes on other sites,
            and is a security feature to prevent clickjacking attacks.

            Note that setting this header can introduce security risks if not used carefully,
            and should only be used when necessary and with proper consideration of the potential risks.

            """
            response = HttpResponse()
            response.xframe_options_exempt = True
            return response

        def xframe_not_exempt_response(request):
            """

            Returns an HTTP response with the X-Frame-Options header set to deny, 
            indicating that the response cannot be iframed by any page. 

            This function is used to prevent clickjacking attacks by ensuring that 
            the response is not embedded in an iframe on a malicious site.

            Args:
                request: The current HTTP request.

            Returns:
                An HttpResponse object with the X-Frame-Options header set.

            """
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
                Returns the value for the X-Frame-Options header based on the provided request and response objects.

                The function checks if the request or response object has a `sameorigin` attribute set to `True`. If either condition is met, it returns `'SAMEORIGIN'`, indicating that the page can only be iframed by the same origin. 

                If neither condition is met, it returns `'DENY'`, indicating that the page cannot be iframed by any site. This header is used to prevent clickjacking attacks by controlling whether a page can be framed by other pages.
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
            Returns a streaming HTTP response to the given request.

            The response contains a sequence of data and is formatted as HTML content with UTF-8 character encoding.

            :returns: A StreamingHttpResponse object containing the response data
            :param request: The incoming HTTP request object
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
            Returns a streaming HTTP response containing chunks of HTML data.

            This function generates a response that is sent to the client in a streaming fashion,
            allowing for large amounts of data to be transferred without having to load the entire
            response into memory. The content type of the response is set to text/html with UTF-8
            character encoding.

            The response is constructed from a sequence of chunks, which are yielded by an internal
            iterator. This allows for efficient handling of large datasets and reduces the memory
            footprint of the application.

            :param request: The incoming HTTP request
            :return: A StreamingHttpResponse object containing the chunked HTML data
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

            Returns a StreamingHttpResponse object containing a sequence of Unicode characters.

            The response is formatted as HTML, using the UTF-8 character encoding to ensure proper display of Unicode characters.
            This allows the response to be streamed to the client, rather than loaded into memory all at once.

            :return: A StreamingHttpResponse object containing the Unicode sequence
            :rtype: StreamingHttpResponse

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
            """
            Returns a StreamingHttpResponse object containing the sequence, with a Content-Type header set to 'text/html; charset=UTF-8', suitable for streaming HTML content to the client.
            """
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
            """

            Returns an HTTP response object containing a compressed string.

            The response includes an ETag header with a fixed value, indicating that the
            response body has not been modified since the last request. This allows
            clients to cache the response and reduces the need for unnecessary
            subsequent requests.

            :return: An HttpResponse object with the compressed string as its body and an ETag header.

            """
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
