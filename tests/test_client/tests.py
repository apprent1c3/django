"""
Testing using the Test Client

The test client is a class that can act like a simple
browser for testing purposes.

It allows the user to compose GET and POST requests, and
obtain the response that the server gave to those requests.
The server Response objects are annotated with the details
of the contexts and templates that were rendered during the
process of serving the request.

``Client`` objects are stateful - they will retain cookie (and
thus session) details for the lifetime of the ``Client`` instance.

This is not intended as a replacement for Twill, Selenium, or
other browser automation frameworks - it is here to allow
testing against the contexts and templates produced by a view,
rather than the HTML rendered to the end-user.

"""

import copy
import itertools
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.http import HttpResponse, HttpResponseNotAllowed
from django.test import (
    AsyncRequestFactory,
    Client,
    RequestFactory,
    SimpleTestCase,
    TestCase,
    modify_settings,
    override_settings,
)
from django.urls import reverse_lazy
from django.utils.decorators import async_only_middleware
from django.views.generic import RedirectView

from .views import TwoArgException, get_view, post_view, trace_view


def middleware_urlconf(get_response):
    def middleware(request):
        request.urlconf = "test_client.urls_middleware_urlconf"
        return get_response(request)

    return middleware


@async_only_middleware
def async_middleware_urlconf(get_response):
    async def middleware(request):
        request.urlconf = "test_client.urls_middleware_urlconf"
        return await get_response(request)

    return middleware


@override_settings(ROOT_URLCONF="test_client.urls")
class ClientTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.u1 = User.objects.create_user(username="testclient", password="password")
        cls.u2 = User.objects.create_user(
            username="inactive", password="password", is_active=False
        )

    def test_get_view(self):
        """
        Tests the GET view by verifying its response content and context
        """
        # The data is ignored, but let's check it doesn't crash the system
        # anyway.
        data = {"var": "\xf2"}
        response = self.client.get("/get_view/", data)

        # Check some response details
        self.assertContains(response, "This is a test")
        self.assertEqual(response.context["var"], "\xf2")
        self.assertEqual(response.templates[0].name, "GET Template")

    def test_copy_response(self):
        """
        Tests that copying a response object preserves its key attributes.

        Verifies that the copy has the same representation and maintains references to its associated client, resolver match, and WSGI request.
        """
        tests = ["/cbv_view/", "/get_view/"]
        for url in tests:
            with self.subTest(url=url):
                response = self.client.get(url)
                response_copy = copy.copy(response)
                self.assertEqual(repr(response), repr(response_copy))
                self.assertIs(response_copy.client, response.client)
                self.assertIs(response_copy.resolver_match, response.resolver_match)
                self.assertIs(response_copy.wsgi_request, response.wsgi_request)

    async def test_copy_response_async(self):
        """
        Tests the copying of asynchronous response objects to ensure the original and copied responses have identical representations and share the same client, resolver match, and ASGI request instances.
        """
        response = await self.async_client.get("/async_get_view/")
        response_copy = copy.copy(response)
        self.assertEqual(repr(response), repr(response_copy))
        self.assertIs(response_copy.client, response.client)
        self.assertIs(response_copy.resolver_match, response.resolver_match)
        self.assertIs(response_copy.asgi_request, response.asgi_request)

    def test_query_string_encoding(self):
        # WSGI requires latin-1 encoded strings.
        response = self.client.get("/get_view/?var=1\ufffd")
        self.assertEqual(response.context["var"], "1\ufffd")

    def test_get_data_none(self):
        msg = (
            "Cannot encode None for key 'value' in a query string. Did you "
            "mean to pass an empty string or omit the value?"
        )
        with self.assertRaisesMessage(TypeError, msg):
            self.client.get("/get_view/", {"value": None})

    def test_get_post_view(self):
        """
        Tests that a view which normally expects POST requests can handle GET requests correctly, verifying the response status code and template used.
        """
        response = self.client.get("/post_view/", {})

        # Check some response details
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "Empty GET Template")
        self.assertTemplateUsed(response, "Empty GET Template")
        self.assertTemplateNotUsed(response, "Empty POST Template")

    def test_empty_post(self):
        """
        Tests the behavior of a view when a POST request is made with an empty dictionary, verifying a successful response and correct template usage.
        """
        response = self.client.post("/post_view/", {})

        # Check some response details
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "Empty POST Template")
        self.assertTemplateNotUsed(response, "Empty GET Template")
        self.assertTemplateUsed(response, "Empty POST Template")

    def test_post(self):
        """
        Tests sending a POST request to a view, verifying the response contains the expected data and template.
        """
        post_data = {"value": 37}
        response = self.client.post("/post_view/", post_data)

        # Check some response details
        self.assertContains(response, "Data received")
        self.assertEqual(response.context["data"], "37")
        self.assertEqual(response.templates[0].name, "POST Template")

    def test_post_data_none(self):
        msg = (
            "Cannot encode None for key 'value' as POST data. Did you mean "
            "to pass an empty string or omit the value?"
        )
        with self.assertRaisesMessage(TypeError, msg):
            self.client.post("/post_view/", {"value": None})

    def test_json_serialization(self):
        """
        Tests that the client correctly serializes JSON data for various HTTP methods.

        Verifies that JSON serialization works as expected for POST, PUT, PATCH, and DELETE requests,
        with different types of data, including dictionaries, lists, and tuples.
        """
        methods = ("post", "put", "patch", "delete")
        tests = (
            ({"value": 37}, {"value": 37}),
            ([37, True], [37, True]),
            ((37, False), [37, False]),
        )
        for method in methods:
            with self.subTest(method=method):
                for data, expected in tests:
                    with self.subTest(data):
                        client_method = getattr(self.client, method)
                        method_name = method.upper()
                        response = client_method(
                            "/json_view/", data, content_type="application/json"
                        )
                        self.assertContains(response, "Viewing %s page." % method_name)
                        self.assertEqual(response.context["data"], expected)

    def test_json_encoder_argument(self):
        """

        Verifies that the Client can utilize a custom JSON encoder.

        Ensures that the provided json_encoder is called when sending a request 
        and that the encoding result is used as the request body.

        """
        mock_encoder = mock.MagicMock()
        mock_encoding = mock.MagicMock()
        mock_encoder.return_value = mock_encoding
        mock_encoding.encode.return_value = '{"value": 37}'

        client = self.client_class(json_encoder=mock_encoder)
        # Vendored tree JSON content types are accepted.
        client.post(
            "/json_view/", {"value": 37}, content_type="application/vnd.api+json"
        )
        self.assertTrue(mock_encoder.called)
        self.assertTrue(mock_encoding.encode.called)

    def test_put(self):
        """
        Tests the PUT request to '/put_view/' by verifying the response status code, template name, and context data.
        """
        response = self.client.put("/put_view/", {"foo": "bar"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "PUT Template")
        self.assertEqual(response.context["data"], "{'foo': 'bar'}")
        self.assertEqual(response.context["Content-Length"], "14")

    def test_trace(self):
        """
        Tests that a TRACE request to the trace view returns a successful response with the correct context and template.
        """
        response = self.client.trace("/trace_view/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["method"], "TRACE")
        self.assertEqual(response.templates[0].name, "TRACE Template")

    def test_response_headers(self):
        "Check the value of HTTP headers returned in a response"
        response = self.client.get("/header_view/")

        self.assertEqual(response.headers["X-DJANGO-TEST"], "Slartibartfast")

    def test_response_attached_request(self):
        """
        Tests that a response object from the client has a 'request' attribute containing the original environ dictionary and a 'wsgi_request' attribute, and verifies that the environ dictionary is correctly mapped to the WSGIRequest.
        """
        response = self.client.get("/header_view/")

        self.assertTrue(hasattr(response, "request"))
        self.assertTrue(hasattr(response, "wsgi_request"))
        for key, value in response.request.items():
            self.assertIn(key, response.wsgi_request.environ)
            self.assertEqual(response.wsgi_request.environ[key], value)

    def test_response_resolver_match(self):
        """
        The response contains a ResolverMatch instance.
        """
        response = self.client.get("/header_view/")
        self.assertTrue(hasattr(response, "resolver_match"))

    def test_response_resolver_match_redirect_follow(self):
        """
        The response ResolverMatch instance contains the correct
        information when following redirects.
        """
        response = self.client.get("/redirect_view/", follow=True)
        self.assertEqual(response.resolver_match.url_name, "get_view")

    def test_response_resolver_match_regular_view(self):
        """
        The response ResolverMatch instance contains the correct
        information when accessing a regular view.
        """
        response = self.client.get("/get_view/")
        self.assertEqual(response.resolver_match.url_name, "get_view")

    def test_response_resolver_match_class_based_view(self):
        """
        The response ResolverMatch instance can be used to access the CBV view
        class.
        """
        response = self.client.get("/accounts/")
        self.assertIs(response.resolver_match.func.view_class, RedirectView)

    @modify_settings(MIDDLEWARE={"prepend": "test_client.tests.middleware_urlconf"})
    def test_response_resolver_match_middleware_urlconf(self):
        response = self.client.get("/middleware_urlconf_view/")
        self.assertEqual(response.resolver_match.url_name, "middleware_urlconf_view")

    def test_raw_post(self):
        """
        Tests posting raw XML data to a view, verifying it returns a 200 status code and the correct template and content.
        """
        test_doc = """<?xml version="1.0" encoding="utf-8"?>
        <library><book><title>Blink</title><author>Malcolm Gladwell</author></book>
        </library>
        """
        response = self.client.post(
            "/raw_post_view/", test_doc, content_type="text/xml"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.templates[0].name, "Book template")
        self.assertEqual(response.content, b"Blink - Malcolm Gladwell")

    def test_insecure(self):
        "GET a URL through http"
        response = self.client.get("/secure_view/", secure=False)
        self.assertFalse(response.test_was_secure_request)
        self.assertEqual(response.test_server_port, "80")

    def test_secure(self):
        "GET a URL through https"
        response = self.client.get("/secure_view/", secure=True)
        self.assertTrue(response.test_was_secure_request)
        self.assertEqual(response.test_server_port, "443")

    def test_redirect(self):
        "GET a URL that redirects elsewhere"
        response = self.client.get("/redirect_view/")
        self.assertRedirects(response, "/get_view/")

    def test_redirect_with_query(self):
        "GET a URL that redirects with given GET parameters"
        response = self.client.get("/redirect_view/", {"var": "value"})
        self.assertRedirects(response, "/get_view/?var=value")

    def test_redirect_with_query_ordering(self):
        """assertRedirects() ignores the order of query string parameters."""
        response = self.client.get("/redirect_view/", {"var": "value", "foo": "bar"})
        self.assertRedirects(response, "/get_view/?var=value&foo=bar")
        self.assertRedirects(response, "/get_view/?foo=bar&var=value")

    def test_permanent_redirect(self):
        "GET a URL that redirects permanently elsewhere"
        response = self.client.get("/permanent_redirect_view/")
        self.assertRedirects(response, "/get_view/", status_code=301)

    def test_temporary_redirect(self):
        "GET a URL that does a non-permanent redirect"
        response = self.client.get("/temporary_redirect_view/")
        self.assertRedirects(response, "/get_view/", status_code=302)

    def test_redirect_to_strange_location(self):
        "GET a URL that redirects to a non-200 page"
        response = self.client.get("/double_redirect_view/")
        # The response was a 302, and that the attempt to get the redirection
        # location returned 301 when retrieved
        self.assertRedirects(
            response, "/permanent_redirect_view/", target_status_code=301
        )

    def test_follow_redirect(self):
        "A URL that redirects can be followed to termination."
        response = self.client.get("/double_redirect_view/", follow=True)
        self.assertRedirects(
            response, "/get_view/", status_code=302, target_status_code=200
        )
        self.assertEqual(len(response.redirect_chain), 2)

    def test_follow_relative_redirect(self):
        "A URL with a relative redirect can be followed."
        response = self.client.get("/accounts/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request["PATH_INFO"], "/accounts/login/")

    def test_follow_relative_redirect_no_trailing_slash(self):
        "A URL with a relative redirect with no trailing slash can be followed."
        response = self.client.get("/accounts/no_trailing_slash", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request["PATH_INFO"], "/accounts/login/")

    def test_redirect_to_querystring_only(self):
        """
        Verifies that a URL comprising only a query string can be successfully redirected to, ensuring correct HTTP response status and content.
        """
        response = self.client.post("/post_then_get_view/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request["PATH_INFO"], "/post_then_get_view/")
        self.assertEqual(response.content, b"The value of success is true.")

    def test_follow_307_and_308_redirect(self):
        """
        Tests HTTP client behavior for 307 and 308 redirects, verifying that the request method is preserved after the redirect.
        """
        methods = ("get", "post", "head", "options", "put", "patch", "delete", "trace")
        codes = (307, 308)
        for method, code in itertools.product(methods, codes):
            with self.subTest(method=method, code=code):
                req_method = getattr(self.client, method)
                response = req_method(
                    "/redirect_view_%s/" % code, data={"value": "test"}, follow=True
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.request["PATH_INFO"], "/post_view/")
                self.assertEqual(response.request["REQUEST_METHOD"], method.upper())

    def test_follow_307_and_308_preserves_query_string(self):
        """
        Tests that following 307 and 308 redirects preserves the original query string for various HTTP methods, including POST, OPTIONS, PUT, PATCH, DELETE, and TRACE.
        """
        methods = ("post", "options", "put", "patch", "delete", "trace")
        codes = (307, 308)
        for method, code in itertools.product(methods, codes):
            with self.subTest(method=method, code=code):
                req_method = getattr(self.client, method)
                response = req_method(
                    "/redirect_view_%s_query_string/" % code,
                    data={"value": "test"},
                    follow=True,
                )
                self.assertRedirects(
                    response, "/post_view/?hello=world", status_code=code
                )
                self.assertEqual(response.request["QUERY_STRING"], "hello=world")

    def test_follow_307_and_308_get_head_query_string(self):
        """

        Tests if the client correctly follows HTTP 307 and 308 redirects for GET and HEAD requests 
        with query strings, verifying the status code, redirect url, and query string preservation.

        """
        methods = ("get", "head")
        codes = (307, 308)
        for method, code in itertools.product(methods, codes):
            with self.subTest(method=method, code=code):
                req_method = getattr(self.client, method)
                response = req_method(
                    "/redirect_view_%s_query_string/" % code,
                    data={"value": "test"},
                    follow=True,
                )
                self.assertRedirects(
                    response, "/post_view/?hello=world", status_code=code
                )
                self.assertEqual(response.request["QUERY_STRING"], "value=test")

    def test_follow_307_and_308_preserves_post_data(self):
        for code in (307, 308):
            with self.subTest(code=code):
                response = self.client.post(
                    "/redirect_view_%s/" % code, data={"value": "test"}, follow=True
                )
                self.assertContains(response, "test is the value")

    def test_follow_307_and_308_preserves_put_body(self):
        for code in (307, 308):
            with self.subTest(code=code):
                response = self.client.put(
                    "/redirect_view_%s/?to=/put_view/" % code, data="a=b", follow=True
                )
                self.assertContains(response, "a=b is the body")

    def test_follow_307_and_308_preserves_get_params(self):
        """
        Tests that HTTP 307 and 308 redirects preserve GET parameters when following the redirect, ensuring correct data transmission.
        """
        data = {"var": 30, "to": "/get_view/"}
        for code in (307, 308):
            with self.subTest(code=code):
                response = self.client.get(
                    "/redirect_view_%s/" % code, data=data, follow=True
                )
                self.assertContains(response, "30 is the value")

    def test_redirect_http(self):
        """GET a URL that redirects to an HTTP URI."""
        response = self.client.get("/http_redirect_view/", follow=True)
        self.assertFalse(response.test_was_secure_request)

    def test_redirect_https(self):
        """GET a URL that redirects to an HTTPS URI."""
        response = self.client.get("/https_redirect_view/", follow=True)
        self.assertTrue(response.test_was_secure_request)

    def test_notfound_response(self):
        "GET a URL that responds as '404:Not Found'"
        response = self.client.get("/bad_view/")
        self.assertContains(response, "MAGIC", status_code=404)

    def test_valid_form(self):
        """
        Tests a form view with valid user input to ensure a successful HTTP response.
        """
        post_data = {
            "text": "Hello World",
            "email": "foo@example.com",
            "value": 37,
            "single": "b",
            "multi": ("b", "c", "e"),
        }
        response = self.client.post("/form_view/", post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "Valid POST Template")

    def test_valid_form_with_hints(self):
        """
        Tests a GET request to the form view with hint data, verifying the response contains no error messages related to the hints and uses the correct template for rendering the form.
        """
        hints = {"text": "Hello World", "multi": ("b", "c", "e")}
        response = self.client.get("/form_view/", data=hints)
        # The multi-value data has been rolled out ok
        self.assertContains(response, "Select a valid choice.", 0)
        self.assertTemplateUsed(response, "Form GET Template")

    def test_incomplete_data_form(self):
        """

        Tests the handling of an incomplete data form submission.

        Verifies that a POST request with missing required fields returns an error response,
        including the 'This field is required.' error message for each missing field.

        """
        post_data = {"text": "Hello World", "value": 37}
        response = self.client.post("/form_view/", post_data)
        self.assertContains(response, "This field is required.", 3)
        self.assertTemplateUsed(response, "Invalid POST Template")
        form = response.context["form"]
        self.assertFormError(form, "email", "This field is required.")
        self.assertFormError(form, "single", "This field is required.")
        self.assertFormError(form, "multi", "This field is required.")

    def test_form_error(self):
        """
        Tests the behavior of a form when invalid data is submitted, verifying that a 200 status code is returned, the correct error template is rendered, and a specific validation error message is displayed for an invalid email address.
        """
        post_data = {
            "text": "Hello World",
            "email": "not an email address",
            "value": 37,
            "single": "b",
            "multi": ("b", "c", "e"),
        }
        response = self.client.post("/form_view/", post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "Invalid POST Template")

        self.assertFormError(
            response.context["form"], "email", "Enter a valid email address."
        )

    def test_valid_form_with_template(self):
        """
        Tests that a form view handles valid form data correctly when using multiple templates, verifying that the expected templates are used and the response contains the expected success message.
        """
        post_data = {
            "text": "Hello World",
            "email": "foo@example.com",
            "value": 37,
            "single": "b",
            "multi": ("b", "c", "e"),
        }
        response = self.client.post("/form_view_with_template/", post_data)
        self.assertContains(response, "POST data OK")
        self.assertTemplateUsed(response, "form_view.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateNotUsed(response, "Valid POST Template")

    def test_incomplete_data_form_with_template(self):
        """
        Tests that a form view using multiple templates correctly handles incomplete POST data, 
        rendering the expected templates and displaying the relevant form validation errors.
        """
        post_data = {"text": "Hello World", "value": 37}
        response = self.client.post("/form_view_with_template/", post_data)
        self.assertContains(response, "POST data has errors")
        self.assertTemplateUsed(response, "form_view.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateNotUsed(response, "Invalid POST Template")
        form = response.context["form"]
        self.assertFormError(form, "email", "This field is required.")
        self.assertFormError(form, "single", "This field is required.")
        self.assertFormError(form, "multi", "This field is required.")

    def test_form_error_with_template(self):
        """
        Tests a form view with multiple templates by submitting invalid data and verifying the response contains error messages, the correct templates are used, and the form error is correctly reported.
        """
        post_data = {
            "text": "Hello World",
            "email": "not an email address",
            "value": 37,
            "single": "b",
            "multi": ("b", "c", "e"),
        }
        response = self.client.post("/form_view_with_template/", post_data)
        self.assertContains(response, "POST data has errors")
        self.assertTemplateUsed(response, "form_view.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateNotUsed(response, "Invalid POST Template")

        self.assertFormError(
            response.context["form"], "email", "Enter a valid email address."
        )

    def test_unknown_page(self):
        "GET an invalid URL"
        response = self.client.get("/unknown_view/")

        # The response was a 404
        self.assertEqual(response.status_code, 404)

    def test_url_parameters(self):
        "Make sure that URL ;-parameters are not stripped."
        response = self.client.get("/unknown_view/;some-parameter")

        # The path in the response includes it (ignore that it's a 404)
        self.assertEqual(response.request["PATH_INFO"], "/unknown_view/;some-parameter")

    def test_view_with_login(self):
        """
        Verify that a view protected by the login_required decorator correctly redirects to the login page for unauthenticated users and allows access to authenticated users.
        """

        # Get the page without logging in. Should result in 302.
        response = self.client.get("/login_protected_view/")
        self.assertRedirects(response, "/accounts/login/?next=/login_protected_view/")

        # Log in
        login = self.client.login(username="testclient", password="password")
        self.assertTrue(login, "Could not log in")

        # Request a page that requires a login
        response = self.client.get("/login_protected_view/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"].username, "testclient")

    @override_settings(
        INSTALLED_APPS=["django.contrib.auth"],
        SESSION_ENGINE="django.contrib.sessions.backends.file",
    )
    def test_view_with_login_when_sessions_app_is_not_installed(self):
        self.test_view_with_login()

    def test_view_with_force_login(self):
        """
        Tests that a view protected by @login_required redirects to the login page for unauthenticated users and allows access for authenticated users.
        """
        # Get the page without logging in. Should result in 302.
        response = self.client.get("/login_protected_view/")
        self.assertRedirects(response, "/accounts/login/?next=/login_protected_view/")

        # Log in
        self.client.force_login(self.u1)

        # Request a page that requires a login
        response = self.client.get("/login_protected_view/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"].username, "testclient")

    def test_view_with_method_login(self):
        """

         Tests a view that requires a user to be logged in, verifying the login redirect and successful page access after authentication.

        """

        # Get the page without logging in. Should result in 302.
        response = self.client.get("/login_protected_method_view/")
        self.assertRedirects(
            response, "/accounts/login/?next=/login_protected_method_view/"
        )

        # Log in
        login = self.client.login(username="testclient", password="password")
        self.assertTrue(login, "Could not log in")

        # Request a page that requires a login
        response = self.client.get("/login_protected_method_view/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"].username, "testclient")

    def test_view_with_method_force_login(self):
        """
        Tests that a view decorated with @login_required correctly redirects unauthenticated users to the login page and allows access to authenticated users.
        """
        # Get the page without logging in. Should result in 302.
        response = self.client.get("/login_protected_method_view/")
        self.assertRedirects(
            response, "/accounts/login/?next=/login_protected_method_view/"
        )

        # Log in
        self.client.force_login(self.u1)

        # Request a page that requires a login
        response = self.client.get("/login_protected_method_view/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"].username, "testclient")

    def test_view_with_login_and_custom_redirect(self):
        """

        Tests a protected view with a custom redirect after successful login.
        Verifies that an unauthenticated user is redirected to the login page,
        and that after logging in, the user is granted access to the protected view.

        """

        # Get the page without logging in. Should result in 302.
        response = self.client.get("/login_protected_view_custom_redirect/")
        self.assertRedirects(
            response,
            "/accounts/login/?redirect_to=/login_protected_view_custom_redirect/",
        )

        # Log in
        login = self.client.login(username="testclient", password="password")
        self.assertTrue(login, "Could not log in")

        # Request a page that requires a login
        response = self.client.get("/login_protected_view_custom_redirect/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"].username, "testclient")

    def test_view_with_force_login_and_custom_redirect(self):
        """
        Tests the behavior of a view that requires login, using a custom redirect URL. Verifies that an unauthenticated user is redirected to the login page with the correct redirect URL, and that an authenticated user can access the view successfully.
        """
        # Get the page without logging in. Should result in 302.
        response = self.client.get("/login_protected_view_custom_redirect/")
        self.assertRedirects(
            response,
            "/accounts/login/?redirect_to=/login_protected_view_custom_redirect/",
        )

        # Log in
        self.client.force_login(self.u1)

        # Request a page that requires a login
        response = self.client.get("/login_protected_view_custom_redirect/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"].username, "testclient")

    def test_view_with_bad_login(self):
        "Request a page that is protected with @login, but use bad credentials"

        login = self.client.login(username="otheruser", password="nopassword")
        self.assertFalse(login)

    def test_view_with_inactive_login(self):
        """

        Tests that an inactive user can or cannot log in depending on the authentication backend configuration.

        """
        credentials = {"username": "inactive", "password": "password"}
        self.assertFalse(self.client.login(**credentials))

        with self.settings(
            AUTHENTICATION_BACKENDS=[
                "django.contrib.auth.backends.AllowAllUsersModelBackend"
            ]
        ):
            self.assertTrue(self.client.login(**credentials))

    @override_settings(
        AUTHENTICATION_BACKENDS=[
            "django.contrib.auth.backends.ModelBackend",
            "django.contrib.auth.backends.AllowAllUsersModelBackend",
        ]
    )
    def test_view_with_inactive_force_login(self):
        """
        Tests the behavior of a login-protected view when attempting to access it with an inactive user account, ensuring the correct login redirect and subsequent access after force login.
        """

        # Get the page without logging in. Should result in 302.
        response = self.client.get("/login_protected_view/")
        self.assertRedirects(response, "/accounts/login/?next=/login_protected_view/")

        # Log in
        self.client.force_login(
            self.u2, backend="django.contrib.auth.backends.AllowAllUsersModelBackend"
        )

        # Request a page that requires a login
        response = self.client.get("/login_protected_view/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"].username, "inactive")

    def test_logout(self):
        """
        Tests the logout functionality by logging in, accessing a protected view, logging out, and verifying redirect to the login page after attempting to access the protected view again.
        """
        # Log in
        self.client.login(username="testclient", password="password")

        # Request a page that requires a login
        response = self.client.get("/login_protected_view/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"].username, "testclient")

        # Log out
        self.client.logout()

        # Request a page that requires a login
        response = self.client.get("/login_protected_view/")
        self.assertRedirects(response, "/accounts/login/?next=/login_protected_view/")

    def test_logout_with_force_login(self):
        """
        Tests the logout functionality by simulating a forced login, 
        accessing a login-protected view, then logging out and verifying 
        the user is redirected to the login page when attempting to access 
        the protected view again.
        """
        # Log in
        self.client.force_login(self.u1)

        # Request a page that requires a login
        response = self.client.get("/login_protected_view/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"].username, "testclient")

        # Log out
        self.client.logout()

        # Request a page that requires a login
        response = self.client.get("/login_protected_view/")
        self.assertRedirects(response, "/accounts/login/?next=/login_protected_view/")

    @override_settings(
        AUTHENTICATION_BACKENDS=[
            "django.contrib.auth.backends.ModelBackend",
            "test_client.auth_backends.TestClientBackend",
        ],
    )
    def test_force_login_with_backend(self):
        """
        Tests the force_login functionality with a custom authentication backend, ensuring that a user is successfully logged in and can access protected pages.
        """
        # Get the page without logging in. Should result in 302.
        response = self.client.get("/login_protected_view/")
        self.assertRedirects(response, "/accounts/login/?next=/login_protected_view/")

        # Log in
        self.client.force_login(
            self.u1, backend="test_client.auth_backends.TestClientBackend"
        )
        self.assertEqual(self.u1.backend, "test_client.auth_backends.TestClientBackend")

        # Request a page that requires a login
        response = self.client.get("/login_protected_view/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"].username, "testclient")

    @override_settings(
        AUTHENTICATION_BACKENDS=[
            "django.contrib.auth.backends.ModelBackend",
            "test_client.auth_backends.TestClientBackend",
        ],
    )
    def test_force_login_without_backend(self):
        """
        Tests that the force_login functionality uses the first authentication backend by default when multiple backends are configured and none are explicitly specified.
        """
        self.client.force_login(self.u1)
        response = self.client.get("/login_protected_view/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"].username, "testclient")
        self.assertEqual(self.u1.backend, "django.contrib.auth.backends.ModelBackend")

    @override_settings(
        AUTHENTICATION_BACKENDS=[
            "test_client.auth_backends.BackendWithoutGetUserMethod",
            "django.contrib.auth.backends.ModelBackend",
        ]
    )
    def test_force_login_with_backend_missing_get_user(self):
        """
        force_login() skips auth backends without a get_user() method.
        """
        self.client.force_login(self.u1)
        self.assertEqual(self.u1.backend, "django.contrib.auth.backends.ModelBackend")

    @override_settings(SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies")
    def test_logout_cookie_sessions(self):
        self.test_logout()

    def test_view_with_permissions(self):
        """
        Tests that a view protected by the @permission_required decorator correctly redirects to the login page when accessed by an unauthenticated user and still redirects to the login page when accessed by an authenticated user without the required permission.
        """

        # Get the page without logging in. Should result in 302.
        response = self.client.get("/permission_protected_view/")
        self.assertRedirects(
            response, "/accounts/login/?next=/permission_protected_view/"
        )

        # Log in
        login = self.client.login(username="testclient", password="password")
        self.assertTrue(login, "Could not log in")

        # Log in with wrong permissions. Should result in 302.
        response = self.client.get("/permission_protected_view/")
        self.assertRedirects(
            response, "/accounts/login/?next=/permission_protected_view/"
        )

        # TODO: Log in with right permissions and request the page again

    def test_view_with_permissions_exception(self):
        """

        Tests the behavior of a view protected by the @permission_required decorator that raises an exception, 
        ensuring it correctly returns a 403 Forbidden response code both before and after login.
        """

        # Get the page without logging in. Should result in 403.
        response = self.client.get("/permission_protected_view_exception/")
        self.assertEqual(response.status_code, 403)

        # Log in
        login = self.client.login(username="testclient", password="password")
        self.assertTrue(login, "Could not log in")

        # Log in with wrong permissions. Should result in 403.
        response = self.client.get("/permission_protected_view_exception/")
        self.assertEqual(response.status_code, 403)

    def test_view_with_method_permissions(self):
        """
        Tests that a view protected with a @permission_required method decorator redirects unauthenticated users to the login page, and that an authenticated user without the required permission is also redirected.
        """

        # Get the page without logging in. Should result in 302.
        response = self.client.get("/permission_protected_method_view/")
        self.assertRedirects(
            response, "/accounts/login/?next=/permission_protected_method_view/"
        )

        # Log in
        login = self.client.login(username="testclient", password="password")
        self.assertTrue(login, "Could not log in")

        # Log in with wrong permissions. Should result in 302.
        response = self.client.get("/permission_protected_method_view/")
        self.assertRedirects(
            response, "/accounts/login/?next=/permission_protected_method_view/"
        )

        # TODO: Log in with right permissions and request the page again

    def test_external_redirect(self):
        response = self.client.get("/django_project_redirect/")
        self.assertRedirects(
            response, "https://www.djangoproject.com/", fetch_redirect_response=False
        )

    @override_settings(ALLOWED_HOSTS=["hostname1", "hostname2"])
    def test_redirect_with_http_host(self):
        response = self.client.get(
            "/redirect_to_different_hostname/", follow=True, HTTP_HOST="hostname1"
        )
        self.assertEqual(response.content, b"hostname2")

    def test_external_redirect_without_trailing_slash(self):
        """
        Client._handle_redirects() with an empty path.
        """
        response = self.client.get("/no_trailing_slash_external_redirect/", follow=True)
        self.assertRedirects(response, "https://testserver")

    def test_external_redirect_with_fetch_error_msg(self):
        """
        Tests that the assertRedirects method raises a ValueError with a descriptive message when attempting to fetch a redirect response from an external URL without setting fetch_redirect_response=False.
        """
        response = self.client.get("/django_project_redirect/")
        msg = (
            "The test client is unable to fetch remote URLs (got "
            "https://www.djangoproject.com/). If the host is served by Django, "
            "add 'www.djangoproject.com' to ALLOWED_HOSTS. "
            "Otherwise, use assertRedirects(..., fetch_redirect_response=False)."
        )
        with self.assertRaisesMessage(ValueError, msg):
            self.assertRedirects(response, "https://www.djangoproject.com/")

    def test_session_modifying_view(self):
        """
        Tests a view that modifies the session by posting a request to it and verifying the session contents before and after the modification, ensuring that the desired key is added with the expected value.
        """
        # Session value isn't set initially
        with self.assertRaises(KeyError):
            self.client.session["tobacconist"]

        self.client.post("/session_view/")
        # The session was modified
        self.assertEqual(self.client.session["tobacconist"], "hovercraft")

    @override_settings(
        INSTALLED_APPS=[],
        SESSION_ENGINE="django.contrib.sessions.backends.file",
    )
    def test_sessions_app_is_not_installed(self):
        self.test_session_modifying_view()

    @override_settings(
        INSTALLED_APPS=[],
        SESSION_ENGINE="django.contrib.sessions.backends.nonexistent",
    )
    def test_session_engine_is_invalid(self):
        with self.assertRaisesMessage(ImportError, "nonexistent"):
            self.test_session_modifying_view()

    def test_view_with_exception(self):
        "Request a page that is known to throw an error"
        with self.assertRaises(KeyError):
            self.client.get("/broken_view/")

    def test_exc_info(self):
        """
        Tests error handling for a broken view, verifying that a 500 status code is returned and the correct exception information is stored in the response.
        """
        client = Client(raise_request_exception=False)
        response = client.get("/broken_view/")
        self.assertEqual(response.status_code, 500)
        exc_type, exc_value, exc_traceback = response.exc_info
        self.assertIs(exc_type, KeyError)
        self.assertIsInstance(exc_value, KeyError)
        self.assertEqual(str(exc_value), "'Oops! Looks like you wrote some bad code.'")
        self.assertIsNotNone(exc_traceback)

    def test_exc_info_none(self):
        response = self.client.get("/get_view/")
        self.assertIsNone(response.exc_info)

    def test_mail_sending(self):
        """
        Tests if mail sending is functioning correctly by verifying a test email is successfully sent and stored in the outbox with expected subject, body, sender, and recipient addresses.
        """
        response = self.client.get("/mail_sending_view/")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Test message")
        self.assertEqual(mail.outbox[0].body, "This is a test email")
        self.assertEqual(mail.outbox[0].from_email, "from@example.com")
        self.assertEqual(mail.outbox[0].to[0], "first@example.com")
        self.assertEqual(mail.outbox[0].to[1], "second@example.com")

    def test_reverse_lazy_decodes(self):
        "reverse_lazy() works in the test client"
        data = {"var": "data"}
        response = self.client.get(reverse_lazy("get_view"), data)

        # Check some response details
        self.assertContains(response, "This is a test")

    def test_relative_redirect(self):
        response = self.client.get("/accounts/")
        self.assertRedirects(response, "/accounts/login/")

    def test_relative_redirect_no_trailing_slash(self):
        response = self.client.get("/accounts/no_trailing_slash")
        self.assertRedirects(response, "/accounts/login/")

    def test_mass_mail_sending(self):
        """

        Tests mass mail sending functionality by verifying the correct number of emails are sent and their content.

        """
        response = self.client.get("/mass_mail_sending_view/")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].subject, "First Test message")
        self.assertEqual(mail.outbox[0].body, "This is the first test email")
        self.assertEqual(mail.outbox[0].from_email, "from@example.com")
        self.assertEqual(mail.outbox[0].to[0], "first@example.com")
        self.assertEqual(mail.outbox[0].to[1], "second@example.com")

        self.assertEqual(mail.outbox[1].subject, "Second Test message")
        self.assertEqual(mail.outbox[1].body, "This is the second test email")
        self.assertEqual(mail.outbox[1].from_email, "from@example.com")
        self.assertEqual(mail.outbox[1].to[0], "second@example.com")
        self.assertEqual(mail.outbox[1].to[1], "third@example.com")

    def test_exception_following_nested_client_request(self):
        """
        A nested test client request shouldn't clobber exception signals from
        the outer client request.
        """
        with self.assertRaisesMessage(Exception, "exception message"):
            self.client.get("/nesting_exception_view/")

    def test_response_raises_multi_arg_exception(self):
        """A request may raise an exception with more than one required arg."""
        with self.assertRaises(TwoArgException) as cm:
            self.client.get("/two_arg_exception/")
        self.assertEqual(cm.exception.args, ("one", "two"))

    def test_uploading_temp_file(self):
        with tempfile.TemporaryFile() as test_file:
            response = self.client.post("/upload_view/", data={"temp_file": test_file})
        self.assertEqual(response.content, b"temp_file")

    def test_uploading_named_temp_file(self):
        with tempfile.NamedTemporaryFile() as test_file:
            response = self.client.post(
                "/upload_view/",
                data={"named_temp_file": test_file},
            )
        self.assertEqual(response.content, b"named_temp_file")

    def test_query_params(self):
        """

        Tests that query parameters are properly passed to views for all HTTP methods.

        Verifies that the 'example' query parameter is correctly set for each of the 
        supported HTTP methods: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS, and TRACE.

        """
        tests = (
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "head",
            "options",
            "trace",
        )
        for method in tests:
            with self.subTest(method=method):
                client_method = getattr(self.client, method)
                response = client_method("/get_view/", query_params={"example": "data"})
                self.assertEqual(response.wsgi_request.GET["example"], "data")

    def test_cannot_use_data_and_query_params_together(self):
        """
        Checks that query parameters and data cannot be used together in GET and HEAD client requests.
        """
        tests = ["get", "head"]
        msg = "query_params and data arguments are mutually exclusive."
        for method in tests:
            with self.subTest(method=method):
                client_method = getattr(self.client, method)
                with self.assertRaisesMessage(ValueError, msg):
                    client_method(
                        "/get_view/",
                        data={"example": "data"},
                        query_params={"q": "terms"},
                    )


@override_settings(
    MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"],
    ROOT_URLCONF="test_client.urls",
)
class CSRFEnabledClientTests(SimpleTestCase):
    def test_csrf_enabled_client(self):
        """
        Tests that a client instantiated with CSRF checks enabled correctly blocks requests without CSRF tokens, while allowing requests without CSRF checks to succeed.
        """
        csrf_client = Client(enforce_csrf_checks=True)
        # The normal client allows the post
        response = self.client.post("/post_view/", {})
        self.assertEqual(response.status_code, 200)
        # The CSRF-enabled client rejects it
        response = csrf_client.post("/post_view/", {})
        self.assertEqual(response.status_code, 403)


class CustomTestClient(Client):
    i_am_customized = "Yes"


class CustomTestClientTest(SimpleTestCase):
    client_class = CustomTestClient

    def test_custom_test_client(self):
        """A test case can specify a custom class for self.client."""
        self.assertIs(hasattr(self.client, "i_am_customized"), True)


def _generic_view(request):
    return HttpResponse(status=200)


@override_settings(ROOT_URLCONF="test_client.urls")
class RequestFactoryTest(SimpleTestCase):
    """Tests for the request factory."""

    # A mapping between names of HTTP/1.1 methods and their test views.
    http_methods_and_views = (
        ("get", get_view),
        ("post", post_view),
        ("put", _generic_view),
        ("patch", _generic_view),
        ("delete", _generic_view),
        ("head", _generic_view),
        ("options", _generic_view),
        ("trace", trace_view),
    )
    request_factory = RequestFactory()

    def test_request_factory(self):
        """

        Tests the request factory's implementation of HTTP/1.1 methods by creating requests 
        with each supported method and verifying that the corresponding view returns a 200 status code.

        """
        for method_name, view in self.http_methods_and_views:
            method = getattr(self.request_factory, method_name)
            request = method("/somewhere/")
            response = view(request)
            self.assertEqual(response.status_code, 200)

    def test_get_request_from_factory(self):
        """
        The request factory returns a templated response for a GET request.
        """
        request = self.request_factory.get("/somewhere/")
        response = get_view(request)
        self.assertContains(response, "This is a test")

    def test_trace_request_from_factory(self):
        """
        Tests that the request factory correctly handles TRACE requests by verifying the response contains the echoed request line.
        """
        url_path = "/somewhere/"
        request = self.request_factory.trace(url_path)
        response = trace_view(request)
        protocol = request.META["SERVER_PROTOCOL"]
        echoed_request_line = "TRACE {} {}".format(url_path, protocol)
        self.assertContains(response, echoed_request_line)

    def test_request_factory_default_headers(self):
        """
        Tests that the RequestFactory correctly sets request headers, including case-insensitivity and conversion to HTTP_* format in the request's META dictionary.
        """
        request = RequestFactory(
            headers={
                "authorization": "Bearer faketoken",
                "x-another-header": "some other value",
            }
        ).get("/somewhere/")
        self.assertEqual(request.headers["authorization"], "Bearer faketoken")
        self.assertIn("HTTP_AUTHORIZATION", request.META)
        self.assertEqual(request.headers["x-another-header"], "some other value")
        self.assertIn("HTTP_X_ANOTHER_HEADER", request.META)

        request = RequestFactory(
            headers={
                "Authorization": "Bearer faketoken",
                "X-Another-Header": "some other value",
            }
        ).get("/somewhere/")
        self.assertEqual(request.headers["authorization"], "Bearer faketoken")
        self.assertIn("HTTP_AUTHORIZATION", request.META)
        self.assertEqual(request.headers["x-another-header"], "some other value")
        self.assertIn("HTTP_X_ANOTHER_HEADER", request.META)

    def test_request_factory_sets_headers(self):
        """

        Tests that the request factory sets headers correctly.

        Verifies that the request factory properly handles custom headers, including
        case sensitivity, and ensures they are added to the request's headers and META
        dictionary.

        """
        for method_name, view in self.http_methods_and_views:
            method = getattr(self.request_factory, method_name)
            request = method(
                "/somewhere/",
                headers={
                    "authorization": "Bearer faketoken",
                    "x-another-header": "some other value",
                },
            )
            self.assertEqual(request.headers["authorization"], "Bearer faketoken")
            self.assertIn("HTTP_AUTHORIZATION", request.META)
            self.assertEqual(request.headers["x-another-header"], "some other value")
            self.assertIn("HTTP_X_ANOTHER_HEADER", request.META)

            request = method(
                "/somewhere/",
                headers={
                    "Authorization": "Bearer faketoken",
                    "X-Another-Header": "some other value",
                },
            )
            self.assertEqual(request.headers["authorization"], "Bearer faketoken")
            self.assertIn("HTTP_AUTHORIZATION", request.META)
            self.assertEqual(request.headers["x-another-header"], "some other value")
            self.assertIn("HTTP_X_ANOTHER_HEADER", request.META)

    def test_request_factory_query_params(self):
        """
        Tests that the request factory correctly handles query parameters for different HTTP methods.

        Verifies that query parameters are properly set in the resulting request object for all supported HTTP methods.
        """
        tests = (
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "head",
            "options",
            "trace",
        )
        for method in tests:
            with self.subTest(method=method):
                factory = getattr(self.request_factory, method)
                request = factory("/somewhere", query_params={"example": "data"})
                self.assertEqual(request.GET["example"], "data")


@override_settings(ROOT_URLCONF="test_client.urls")
class AsyncClientTest(TestCase):
    async def test_response_resolver_match(self):
        response = await self.async_client.get("/async_get_view/")
        self.assertTrue(hasattr(response, "resolver_match"))
        self.assertEqual(response.resolver_match.url_name, "async_get_view")

    @modify_settings(
        MIDDLEWARE={"prepend": "test_client.tests.async_middleware_urlconf"},
    )
    async def test_response_resolver_match_middleware_urlconf(self):
        response = await self.async_client.get("/middleware_urlconf_view/")
        self.assertEqual(response.resolver_match.url_name, "middleware_urlconf_view")

    async def test_redirect(self):
        response = await self.async_client.get("/redirect_view/")
        self.assertEqual(response.status_code, 302)

    async def test_follow_redirect(self):
        """
        Test that HTTP requests follow redirects successfully.

        Checks that all supported HTTP methods (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS, TRACE)
        correctly follow redirects to their target views, verifying the final response status code and view name.
        """
        tests = (
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "head",
            "options",
            "trace",
        )
        for method_name in tests:
            with self.subTest(method=method_name):
                method = getattr(self.async_client, method_name)
                response = await method("/redirect_view/", follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.resolver_match.url_name, "get_view")

    async def test_follow_double_redirect(self):
        response = await self.async_client.get("/double_redirect_view/", follow=True)
        self.assertRedirects(
            response, "/get_view/", status_code=302, target_status_code=200
        )
        self.assertEqual(len(response.redirect_chain), 2)

    async def test_get_data(self):
        response = await self.async_client.get("/get_view/", {"var": "val"})
        self.assertContains(response, "This is a test. val is the value.")

    async def test_post_data(self):
        response = await self.async_client.post("/post_view/", {"value": 37})
        self.assertContains(response, "Data received: 37 is the value.")

    async def test_body_read_on_get_data(self):
        response = await self.async_client.get("/post_view/")
        self.assertContains(response, "Viewing GET page.")

    async def test_query_params(self):
        """
        Tests that query parameters are properly passed to the asynchronous client for various HTTP methods.
        """
        tests = (
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "head",
            "options",
            "trace",
        )
        for method in tests:
            with self.subTest(method=method):
                client_method = getattr(self.async_client, method)
                response = await client_method(
                    "/async_get_view/", query_params={"example": "data"}
                )
                self.assertEqual(response.asgi_request.GET["example"], "data")


@override_settings(ROOT_URLCONF="test_client.urls")
class AsyncRequestFactoryTest(SimpleTestCase):
    request_factory = AsyncRequestFactory()

    async def test_request_factory(self):
        """
        Tests the request factory's support for various HTTP methods by creating a request for each method and verifying that it is handled correctly by a generic view.
        """
        tests = (
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "head",
            "options",
            "trace",
        )
        for method_name in tests:
            with self.subTest(method=method_name):

                async def async_generic_view(request):
                    if request.method.lower() != method_name:
                        return HttpResponseNotAllowed(method_name)
                    return HttpResponse(status=200)

                method = getattr(self.request_factory, method_name)
                request = method("/somewhere/")
                response = await async_generic_view(request)
                self.assertEqual(response.status_code, 200)

    async def test_request_factory_data(self):
        """
        Tests the request factory's ability to generate a POST request with JSON data and verifies that the request is properly handled by a generic async view, returning a 200 status code with the request body as content.
        """
        async def async_generic_view(request):
            return HttpResponse(status=200, content=request.body)

        request = self.request_factory.post(
            "/somewhere/",
            data={"example": "data"},
            content_type="application/json",
        )
        self.assertEqual(request.headers["content-length"], "19")
        self.assertEqual(request.headers["content-type"], "application/json")
        response = await async_generic_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'{"example": "data"}')

    async def test_request_limited_read(self):
        """
        Tests that limited read operations return empty bytes for HTTP requests with no body.
        """
        tests = ["GET", "POST"]
        for method in tests:
            with self.subTest(method=method):
                request = self.request_factory.generic(
                    method,
                    "/somewhere",
                )
                self.assertEqual(request.read(200), b"")

    def test_request_factory_sets_headers(self):
        """
        Tests that the request factory correctly sets headers for a request.

         Verifies that both keyword arguments and a headers dictionary can be used to set 
         'Authorization' and custom headers, and that these are properly converted to 
         their corresponding HTTP header names and stored in the request's META dictionary.
        """
        request = self.request_factory.get(
            "/somewhere/",
            AUTHORIZATION="Bearer faketoken",
            X_ANOTHER_HEADER="some other value",
        )
        self.assertEqual(request.headers["authorization"], "Bearer faketoken")
        self.assertIn("HTTP_AUTHORIZATION", request.META)
        self.assertEqual(request.headers["x-another-header"], "some other value")
        self.assertIn("HTTP_X_ANOTHER_HEADER", request.META)

        request = self.request_factory.get(
            "/somewhere/",
            headers={
                "Authorization": "Bearer faketoken",
                "X-Another-Header": "some other value",
            },
        )
        self.assertEqual(request.headers["authorization"], "Bearer faketoken")
        self.assertIn("HTTP_AUTHORIZATION", request.META)
        self.assertEqual(request.headers["x-another-header"], "some other value")
        self.assertIn("HTTP_X_ANOTHER_HEADER", request.META)

    def test_request_factory_query_string(self):
        request = self.request_factory.get("/somewhere/", {"example": "data"})
        self.assertNotIn("Query-String", request.headers)
        self.assertEqual(request.GET["example"], "data")

    def test_request_factory_query_params(self):
        """

        Tests the request factory's ability to create requests with query parameters for various HTTP methods.

        Verifies that the query parameters are correctly added to the request for each method.

        """
        tests = (
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "head",
            "options",
            "trace",
        )
        for method in tests:
            with self.subTest(method=method):
                factory = getattr(self.request_factory, method)
                request = factory("/somewhere", query_params={"example": "data"})
                self.assertEqual(request.GET["example"], "data")

    def test_cannot_use_data_and_query_params_together(self):
        """
        Tests that data and query_params cannot be used together in HTTP requests.

        Verifies that attempting to combine data and query parameters in a single request
        raises a ValueError with an informative error message.
        """
        tests = ["get", "head"]
        msg = "query_params and data arguments are mutually exclusive."
        for method in tests:
            with self.subTest(method=method):
                factory = getattr(self.request_factory, method)
                with self.assertRaisesMessage(ValueError, msg):
                    factory(
                        "/somewhere",
                        data={"example": "data"},
                        query_params={"q": "terms"},
                    )
