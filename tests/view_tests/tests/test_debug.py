import importlib
import inspect
import os
import re
import sys
import tempfile
import threading
from io import StringIO
from pathlib import Path
from unittest import mock, skipIf, skipUnless

from asgiref.sync import async_to_sync, iscoroutinefunction

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.template import TemplateDoesNotExist
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.test.utils import LoggingCaptureMixin
from django.urls import path, reverse
from django.urls.converters import IntConverter
from django.utils.functional import SimpleLazyObject
from django.utils.regex_helper import _lazy_re_compile
from django.utils.safestring import mark_safe
from django.utils.version import PY311
from django.views.debug import (
    CallableSettingWrapper,
    ExceptionCycleWarning,
    ExceptionReporter,
)
from django.views.debug import Path as DebugPath
from django.views.debug import (
    SafeExceptionReporterFilter,
    default_urlconf,
    get_default_exception_reporter_filter,
    technical_404_response,
    technical_500_response,
)
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

from ..views import (
    async_sensitive_method_view,
    async_sensitive_method_view_nested,
    async_sensitive_view,
    async_sensitive_view_nested,
    custom_exception_reporter_filter_view,
    index_page,
    multivalue_dict_key_error,
    non_sensitive_view,
    paranoid_view,
    sensitive_args_function_caller,
    sensitive_kwargs_function_caller,
    sensitive_method_view,
    sensitive_view,
)


class User:
    def __str__(self):
        return "jacob"


class WithoutEmptyPathUrls:
    urlpatterns = [path("url/", index_page, name="url")]


class CallableSettingWrapperTests(SimpleTestCase):
    """Unittests for CallableSettingWrapper"""

    def test_repr(self):
        """
        Tests the representation of a CallableSettingWrapper object.

        Verifies that the repr method of the CallableSettingWrapper returns the 
        representation of the wrapped callable object, ensuring correct delegation 
        of the __repr__ method to the wrapped object.

        Checks that the returned representation string matches the expected output 
        from the wrapped callable's __repr__ method, confirming proper wrapping and 
        representation of the underlying callable object.
        """
        class WrappedCallable:
            def __repr__(self):
                return "repr from the wrapped callable"

            def __call__(self):
                pass

        actual = repr(CallableSettingWrapper(WrappedCallable()))
        self.assertEqual(actual, "repr from the wrapped callable")


@override_settings(DEBUG=True, ROOT_URLCONF="view_tests.urls")
class DebugViewTests(SimpleTestCase):
    def test_files(self):
        with self.assertLogs("django.request", "ERROR"):
            response = self.client.get("/raises/")
        self.assertEqual(response.status_code, 500)

        data = {
            "file_data.txt": SimpleUploadedFile("file_data.txt", b"haha"),
        }
        with self.assertLogs("django.request", "ERROR"):
            response = self.client.post("/raises/", data)
        self.assertContains(response, "file_data.txt", status_code=500)
        self.assertNotContains(response, "haha", status_code=500)

    def test_400(self):
        # When DEBUG=True, technical_500_template() is called.
        with self.assertLogs("django.security", "WARNING"):
            response = self.client.get("/raises400/")
        self.assertContains(response, '<div class="context" id="', status_code=400)

    def test_400_bad_request(self):
        # When DEBUG=True, technical_500_template() is called.
        """

        Tests that a 400 Bad Request response is correctly returned and logged when the /raises400_bad_request/ URL is accessed.

        The test verifies that the response contains the expected HTML structure and that a warning log message is generated with a message indicating a malformed request syntax.

        Checks the following conditions:
        - The response status code is 400.
        - The response contains a div with class 'context' and id attribute.
        - A warning log message is generated with the expected malformed request syntax message.

        """
        with self.assertLogs("django.request", "WARNING") as cm:
            response = self.client.get("/raises400_bad_request/")
        self.assertContains(response, '<div class="context" id="', status_code=400)
        self.assertEqual(
            cm.records[0].getMessage(),
            "Malformed request syntax: /raises400_bad_request/",
        )

    # Ensure no 403.html template exists to test the default case.
    @override_settings(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
            }
        ]
    )
    def test_403(self):
        """
        Tests that a 403 Forbidden response is correctly handled and displayed.

        This test case simulates a GET request to a URL that intentionally raises a 403 error.
        It verifies that the response contains the expected error message and has the correct HTTP status code.
        The test ensures that the application properly handles and renders the 403 Forbidden page when an authorized user attempts to access a restricted resource.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the response does not contain the expected error message or has an incorrect status code.

        """
        response = self.client.get("/raises403/")
        self.assertContains(response, "<h1>403 Forbidden</h1>", status_code=403)

    # Set up a test 403.html template.
    @override_settings(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "OPTIONS": {
                    "loaders": [
                        (
                            "django.template.loaders.locmem.Loader",
                            {
                                "403.html": (
                                    "This is a test template for a 403 error "
                                    "({{ exception }})."
                                ),
                            },
                        ),
                    ],
                },
            }
        ]
    )
    def test_403_template(self):
        """
        Tests the rendering of a custom 403 error template when an Insufficient Permissions exception is raised.

        This test case verifies that the custom template is correctly loaded and displayed when a 403 error occurs, 
        containing the expected exception message and template content.

        The test checks for the presence of specific text in the response, ensuring that both the custom template 
        and the exception message are correctly rendered with a 403 status code.
        """
        response = self.client.get("/raises403/")
        self.assertContains(response, "test template", status_code=403)
        self.assertContains(response, "(Insufficient Permissions).", status_code=403)

    def test_404(self):
        response = self.client.get("/raises404/")
        self.assertNotContains(
            response,
            '<pre class="exception_value">',
            status_code=404,
        )
        self.assertContains(
            response,
            "<p>The current path, <code>not-in-urls</code>, didn’t match any "
            "of these.</p>",
            status_code=404,
            html=True,
        )

    def test_404_not_in_urls(self):
        response = self.client.get("/not-in-urls")
        self.assertNotContains(response, "Raised by:", status_code=404)
        self.assertNotContains(
            response,
            '<pre class="exception_value">',
            status_code=404,
        )
        self.assertContains(
            response, "Django tried these URL patterns", status_code=404
        )
        self.assertContains(
            response,
            "<code>technical404/ [name='my404']</code>",
            status_code=404,
            html=True,
        )
        self.assertContains(
            response,
            "<p>The current path, <code>not-in-urls</code>, didn’t match any "
            "of these.</p>",
            status_code=404,
            html=True,
        )
        # Pattern and view name of a RegexURLPattern appear.
        self.assertContains(
            response, r"^regex-post/(?P&lt;pk&gt;[0-9]+)/$", status_code=404
        )
        self.assertContains(response, "[name='regex-post']", status_code=404)
        # Pattern and view name of a RoutePattern appear.
        self.assertContains(response, r"path-post/&lt;int:pk&gt;/", status_code=404)
        self.assertContains(response, "[name='path-post']", status_code=404)

    @override_settings(ROOT_URLCONF=WithoutEmptyPathUrls)
    def test_404_empty_path_not_in_urls(self):
        response = self.client.get("/")
        self.assertContains(
            response,
            "<p>The empty path didn’t match any of these.</p>",
            status_code=404,
            html=True,
        )

    def test_technical_404(self):
        """

        Tests the technical 404 page.

        Verifies that a GET request to the /technical404/ URL returns a 404 status code and 
        contains the expected HTML elements, including a header, main section, and footer.
        Additionally, checks that the page displays the exception value, the view that raised 
        the exception, and a message explaining the error.

        The test ensures that the technical 404 page is properly formatted and provides 
        useful information for debugging purposes.

        """
        response = self.client.get("/technical404/")
        self.assertContains(response, '<header id="summary">', status_code=404)
        self.assertContains(response, '<main id="info">', status_code=404)
        self.assertContains(response, '<footer id="explanation">', status_code=404)
        self.assertContains(
            response,
            '<pre class="exception_value">Testing technical 404.</pre>',
            status_code=404,
            html=True,
        )
        self.assertContains(response, "Raised by:", status_code=404)
        self.assertContains(
            response,
            "<td>view_tests.views.technical404</td>",
            status_code=404,
        )
        self.assertContains(
            response,
            "<p>The current path, <code>technical404/</code>, matched the "
            "last one.</p>",
            status_code=404,
            html=True,
        )

    def test_classbased_technical_404(self):
        """
        Tests that a class-based view correctly raises a 404 status code.

        Verifies that the view returns a HTML response containing the expected
        error details, including the view that raised the exception, and that
        the HTTP status code of the response is 404 (Not Found).
        """
        response = self.client.get("/classbased404/")
        self.assertContains(
            response,
            '<th scope="row">Raised by:</th><td>view_tests.views.Http404View</td>',
            status_code=404,
            html=True,
        )

    def test_technical_500(self):
        """

        Tests the technical 500 error page response.

        This test checks that the server correctly raises a 500 error when the /raises500/ URL is accessed,
        and that the error page contains the expected content. The test verifies that the HTML error page
        includes the summary, info, and explanation sections. It also checks that the error page correctly
        displays the view that raised the exception.

        Additionally, this test ensures that the error page works correctly when the client requests plain text
        instead of HTML, by sending an 'Accept: text/plain' header in the request.

        """
        with self.assertLogs("django.request", "ERROR"):
            response = self.client.get("/raises500/")
        self.assertContains(response, '<header id="summary">', status_code=500)
        self.assertContains(response, '<main id="info">', status_code=500)
        self.assertContains(response, '<footer id="explanation">', status_code=500)
        self.assertContains(
            response,
            '<th scope="row">Raised during:</th><td>view_tests.views.raises500</td>',
            status_code=500,
            html=True,
        )
        with self.assertLogs("django.request", "ERROR"):
            response = self.client.get("/raises500/", headers={"accept": "text/plain"})
        self.assertContains(
            response,
            "Raised during: view_tests.views.raises500",
            status_code=500,
        )

    def test_classbased_technical_500(self):
        """

        Tests that a class-based view correctly handles and reports internal server errors.

        This test case simulates a GET request to a view designed to raise a 500 error and verifies 
        that the response contains the expected error information in both HTML and plain text formats.

        The test checks for the presence of log messages at the ERROR level, indicating that the 
        request was correctly flagged as an error. It also verifies that the response contains 
        information about the view that raised the error, confirming that the error was properly 
        handled and reported.

        """
        with self.assertLogs("django.request", "ERROR"):
            response = self.client.get("/classbased500/")
        self.assertContains(
            response,
            '<th scope="row">Raised during:</th>'
            "<td>view_tests.views.Raises500View</td>",
            status_code=500,
            html=True,
        )
        with self.assertLogs("django.request", "ERROR"):
            response = self.client.get(
                "/classbased500/", headers={"accept": "text/plain"}
            )
        self.assertContains(
            response,
            "Raised during: view_tests.views.Raises500View",
            status_code=500,
        )

    def test_non_l10ned_numeric_ids(self):
        """
        Numeric IDs and fancy traceback context blocks line numbers shouldn't
        be localized.
        """
        with self.settings(DEBUG=True):
            with self.assertLogs("django.request", "ERROR"):
                response = self.client.get("/raises500/")
            # We look for a HTML fragment of the form
            # '<div class="context" id="c38123208">',
            # not '<div class="context" id="c38,123,208"'.
            self.assertContains(response, '<div class="context" id="', status_code=500)
            match = re.search(
                b'<div class="context" id="(?P<id>[^"]+)">', response.content
            )
            self.assertIsNotNone(match)
            id_repr = match["id"]
            self.assertFalse(
                re.search(b"[^c0-9]", id_repr),
                "Numeric IDs in debug response HTML page shouldn't be localized "
                "(value: %s)." % id_repr.decode(),
            )

    def test_template_exceptions(self):
        with self.assertLogs("django.request", "ERROR"):
            try:
                self.client.get(reverse("template_exception"))
            except Exception:
                raising_loc = inspect.trace()[-1][-2][0].strip()
                self.assertNotEqual(
                    raising_loc.find('raise Exception("boom")'),
                    -1,
                    "Failed to find 'raise Exception' in last frame of "
                    "traceback, instead found: %s" % raising_loc,
                )

    @skipIf(
        sys.platform == "win32",
        "Raises OSError instead of TemplateDoesNotExist on Windows.",
    )
    def test_safestring_in_exception(self):
        """
        Tests that a Django view handles a SafeString exception correctly when an error occurs.

        The test verifies that the view logs the exception as an error, returns a 500 status code, and escapes any HTML characters in the exception message to prevent cross-site scripting attacks. Specifically, it checks that any malicious script tags are properly encoded and not rendered as executable HTML.

        """
        with self.assertLogs("django.request", "ERROR"):
            response = self.client.get("/safestring_exception/")
            self.assertNotContains(
                response,
                "<script>alert(1);</script>",
                status_code=500,
                html=True,
            )
            self.assertContains(
                response,
                "&lt;script&gt;alert(1);&lt;/script&gt;",
                count=3,
                status_code=500,
                html=True,
            )

    def test_template_loader_postmortem(self):
        """Tests for not existing file"""
        template_name = "notfound.html"
        with tempfile.NamedTemporaryFile(prefix=template_name) as tmpfile:
            tempdir = os.path.dirname(tmpfile.name)
            template_path = os.path.join(tempdir, template_name)
            with (
                override_settings(
                    TEMPLATES=[
                        {
                            "BACKEND": (
                                "django.template.backends.django.DjangoTemplates"
                            ),
                            "DIRS": [tempdir],
                        }
                    ]
                ),
                self.assertLogs("django.request", "ERROR"),
            ):
                response = self.client.get(
                    reverse(
                        "raises_template_does_not_exist", kwargs={"path": template_name}
                    )
                )
            self.assertContains(
                response,
                "%s (Source does not exist)" % template_path,
                status_code=500,
                count=2,
            )
            # Assert as HTML.
            self.assertContains(
                response,
                "<li><code>django.template.loaders.filesystem.Loader</code>: "
                "%s (Source does not exist)</li>"
                % os.path.join(tempdir, "notfound.html"),
                status_code=500,
                html=True,
            )

    def test_no_template_source_loaders(self):
        """
        Make sure if you don't specify a template, the debug view doesn't blow up.
        """
        with self.assertLogs("django.request", "ERROR"):
            with self.assertRaises(TemplateDoesNotExist):
                self.client.get("/render_no_template/")

    @override_settings(ROOT_URLCONF="view_tests.default_urls")
    def test_default_urlconf_template(self):
        """
        Make sure that the default URLconf template is shown instead of the
        technical 404 page, if the user has not altered their URLconf yet.
        """
        response = self.client.get("/")
        self.assertContains(
            response, "<h1>The install worked successfully! Congratulations!</h1>"
        )

    @override_settings(ROOT_URLCONF="view_tests.regression_21530_urls")
    def test_regression_21530(self):
        """
        Regression test for bug #21530.

        If the admin app include is replaced with exactly one url
        pattern, then the technical 404 template should be displayed.

        The bug here was that an AttributeError caused a 500 response.
        """
        response = self.client.get("/")
        self.assertContains(
            response, "Page not found <small>(404)</small>", status_code=404
        )

    def test_template_encoding(self):
        """
        The templates are loaded directly, not via a template loader, and
        should be opened as utf-8 charset as is the default specified on
        template engines.
        """
        with mock.patch.object(DebugPath, "open") as m:
            default_urlconf(None)
            m.assert_called_once_with(encoding="utf-8")
            m.reset_mock()
            technical_404_response(mock.MagicMock(), mock.Mock())
            m.assert_called_once_with(encoding="utf-8")

    def test_technical_404_converter_raise_404(self):
        """

        Tests the technical 404 converter functionality.

        This test case verifies that a 404 error is raised and the correct error message is displayed when the 
        IntConverter's to_python method is mocked to raise an Http404 exception. The test simulates a GET request 
        to the specified path and checks that the response contains the 'Page not found' error message with a 
        status code of 404.

        Checks the following conditions:
        - The IntConverter correctly raises an Http404 exception when its to_python method fails.
        - The view handles the Http404 exception by returning a 404 status code.
        - The response to the request contains the expected 'Page not found' error message.

        """
        with mock.patch.object(IntConverter, "to_python", side_effect=Http404):
            response = self.client.get("/path-post/1/")
            self.assertContains(response, "Page not found", status_code=404)

    def test_exception_reporter_from_request(self):
        with self.assertLogs("django.request", "ERROR"):
            response = self.client.get("/custom_reporter_class_view/")
        self.assertContains(response, "custom traceback text", status_code=500)

    @override_settings(
        DEFAULT_EXCEPTION_REPORTER="view_tests.views.CustomExceptionReporter"
    )
    def test_exception_reporter_from_settings(self):
        with self.assertLogs("django.request", "ERROR"):
            response = self.client.get("/raises500/")
        self.assertContains(response, "custom traceback text", status_code=500)

    @override_settings(
        DEFAULT_EXCEPTION_REPORTER="view_tests.views.TemplateOverrideExceptionReporter"
    )
    def test_template_override_exception_reporter(self):
        with self.assertLogs("django.request", "ERROR"):
            response = self.client.get("/raises500/")
        self.assertContains(
            response,
            "<h1>Oh no, an error occurred!</h1>",
            status_code=500,
            html=True,
        )

        with self.assertLogs("django.request", "ERROR"):
            response = self.client.get("/raises500/", headers={"accept": "text/plain"})
        self.assertContains(response, "Oh dear, an error occurred!", status_code=500)


class DebugViewQueriesAllowedTests(SimpleTestCase):
    # May need a query to initialize MySQL connection
    databases = {"default"}

    def test_handle_db_exception(self):
        """
        Ensure the debug view works when a database exception is raised by
        performing an invalid query and passing the exception to the debug view.
        """
        with connection.cursor() as cursor:
            try:
                cursor.execute("INVALID SQL")
            except DatabaseError:
                exc_info = sys.exc_info()

        rf = RequestFactory()
        response = technical_500_response(rf.get("/"), *exc_info)
        self.assertContains(response, "OperationalError at /", status_code=500)


@override_settings(
    DEBUG=True,
    ROOT_URLCONF="view_tests.urls",
    # No template directories are configured, so no templates will be found.
    TEMPLATES=[
        {
            "BACKEND": "django.template.backends.dummy.TemplateStrings",
        }
    ],
)
class NonDjangoTemplatesDebugViewTests(SimpleTestCase):
    def test_400(self):
        # When DEBUG=True, technical_500_template() is called.
        """

        Test that a 400 Bad Request response is handled correctly.

        This test case checks that when a request is made to a view that raises a 400 status code,
        the response is properly rendered and includes the expected error context.
        The test also verifies that a warning log message is generated by Django's security logging.

        """
        with self.assertLogs("django.security", "WARNING"):
            response = self.client.get("/raises400/")
        self.assertContains(response, '<div class="context" id="', status_code=400)

    def test_400_bad_request(self):
        # When DEBUG=True, technical_500_template() is called.
        """
        Tests the handling of a 400 Bad Request HTTP response.

        This test case sends a GET request to a URL that intentionally raises a 400 Bad Request error and verifies that the response contains the expected error message and has a status code of 400. Additionally, it checks that a warning log message is generated with the correct error message, indicating that the request syntax was malformed.
        """
        with self.assertLogs("django.request", "WARNING") as cm:
            response = self.client.get("/raises400_bad_request/")
        self.assertContains(response, '<div class="context" id="', status_code=400)
        self.assertEqual(
            cm.records[0].getMessage(),
            "Malformed request syntax: /raises400_bad_request/",
        )

    def test_403(self):
        """
        Tests that a 403 Forbidden response is correctly returned when accessing the '/raises403/' URL.

        This test case verifies that the server returns a 403 Forbidden status code and a corresponding HTML response containing the '<h1>403 Forbidden</h1>' header, indicating that the requested resource is forbidden for the user or the request is not allowed.

        The test covers the scenario where a client attempts to access a restricted resource, and the server is expected to respond with a 403 Forbidden error, providing a clear indication of the issue to the client.

        The test is designed to ensure that the server's authentication and authorization mechanisms are functioning correctly, and that the client receives a standard and informative error response when attempting to access a forbidden resource.
        """
        response = self.client.get("/raises403/")
        self.assertContains(response, "<h1>403 Forbidden</h1>", status_code=403)

    def test_404(self):
        """
        Tests the handling of a 404 status code by making a GET request to a URL that is known to raise a 404 error.

        Verifies that the server correctly returns a 404 status code when the requested resource cannot be found, ensuring proper error handling and reporting.

        Returns:
            None

        Raises:
            AssertionError: If the server does not return a 404 status code as expected
        """
        response = self.client.get("/raises404/")
        self.assertEqual(response.status_code, 404)

    def test_template_not_found_error(self):
        # Raises a TemplateDoesNotExist exception and shows the debug view.
        """
        Tests that a TemplateDoesNotExist exception is raised and handled correctly.

        This test case ensures that when a template file is not found, the application
        appropriately logs an error and returns a 500 response with an error message.
        The error response is verified to contain the expected HTML structure.

        The test simulates a GET request to a URL that is configured to raise a 
        TemplateDoesNotExist exception, and checks that the response status code and 
        content match the expected error output.
        """
        url = reverse(
            "raises_template_does_not_exist", kwargs={"path": "notfound.html"}
        )
        with self.assertLogs("django.request", "ERROR"):
            response = self.client.get(url)
        self.assertContains(response, '<div class="context" id="', status_code=500)


class ExceptionReporterTests(SimpleTestCase):
    rf = RequestFactory()

    def test_request_and_exception(self):
        "A simple exception report can be generated"
        try:
            request = self.rf.get("/test_view/")
            request.user = User()
            raise ValueError("Can't find my keys")
        except ValueError:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(request, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertInHTML("<h1>ValueError at /test_view/</h1>", html)
        self.assertIn(
            '<pre class="exception_value">Can&#x27;t find my keys</pre>', html
        )
        self.assertIn('<th scope="row">Request Method:</th>', html)
        self.assertIn('<th scope="row">Request URL:</th>', html)
        self.assertIn('<h3 id="user-info">USER</h3>', html)
        self.assertIn("<p>jacob</p>", html)
        self.assertIn('<th scope="row">Exception Type:</th>', html)
        self.assertIn('<th scope="row">Exception Value:</th>', html)
        self.assertIn("<h2>Traceback ", html)
        self.assertIn("<h2>Request information</h2>", html)
        self.assertNotIn("<p>Request data not supplied</p>", html)
        self.assertIn("<p>No POST data</p>", html)

    def test_no_request(self):
        "An exception report can be generated without request"
        try:
            raise ValueError("Can't find my keys")
        except ValueError:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertInHTML("<h1>ValueError</h1>", html)
        self.assertIn(
            '<pre class="exception_value">Can&#x27;t find my keys</pre>', html
        )
        self.assertNotIn('<th scope="row">Request Method:</th>', html)
        self.assertNotIn('<th scope="row">Request URL:</th>', html)
        self.assertNotIn('<h3 id="user-info">USER</h3>', html)
        self.assertIn('<th scope="row">Exception Type:</th>', html)
        self.assertIn('<th scope="row">Exception Value:</th>', html)
        self.assertIn("<h2>Traceback ", html)
        self.assertIn("<h2>Request information</h2>", html)
        self.assertIn("<p>Request data not supplied</p>", html)

    def test_sharing_traceback(self):
        """

        Tests the sharing functionality of the traceback by simulating an exception and verifying that the HTML output contains a form to share the traceback on dpaste.com.

        This test case covers the scenario where an exception occurs, and the system generates a traceback. It then checks if the generated HTML includes a form that allows users to share the traceback on dpaste.com, which is a code-sharing platform. The test ensures that the traceback can be properly shared and displayed in a user-friendly format.

        """
        try:
            raise ValueError("Oops")
        except ValueError:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertIn(
            '<form action="https://dpaste.com/" name="pasteform" '
            'id="pasteform" method="post">',
            html,
        )

    def test_eol_support(self):
        """The ExceptionReporter supports Unix, Windows and Macintosh EOL markers"""
        LINES = ["print %d" % i for i in range(1, 6)]
        reporter = ExceptionReporter(None, None, None, None)

        for newline in ["\n", "\r\n", "\r"]:
            fd, filename = tempfile.mkstemp(text=False)
            os.write(fd, (newline.join(LINES) + newline).encode())
            os.close(fd)

            try:
                self.assertEqual(
                    reporter._get_lines_from_file(filename, 3, 2),
                    (1, LINES[1:3], LINES[3], LINES[4:]),
                )
            finally:
                os.unlink(filename)

    def test_no_exception(self):
        "An exception report can be generated for just a request"
        request = self.rf.get("/test_view/")
        reporter = ExceptionReporter(request, None, None, None)
        html = reporter.get_traceback_html()
        self.assertInHTML("<h1>Report at /test_view/</h1>", html)
        self.assertIn(
            '<pre class="exception_value">No exception message supplied</pre>', html
        )
        self.assertIn('<th scope="row">Request Method:</th>', html)
        self.assertIn('<th scope="row">Request URL:</th>', html)
        self.assertNotIn('<th scope="row">Exception Type:</th>', html)
        self.assertNotIn('<th scope="row">Exception Value:</th>', html)
        self.assertNotIn("<h2>Traceback ", html)
        self.assertIn("<h2>Request information</h2>", html)
        self.assertNotIn("<p>Request data not supplied</p>", html)

    def test_suppressed_context(self):
        try:
            try:
                raise RuntimeError("Can't find my keys")
            except RuntimeError:
                raise ValueError("Can't find my keys") from None
        except ValueError:
            exc_type, exc_value, tb = sys.exc_info()

        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertInHTML("<h1>ValueError</h1>", html)
        self.assertIn(
            '<pre class="exception_value">Can&#x27;t find my keys</pre>', html
        )
        self.assertIn('<th scope="row">Exception Type:</th>', html)
        self.assertIn('<th scope="row">Exception Value:</th>', html)
        self.assertIn("<h2>Traceback ", html)
        self.assertIn("<h2>Request information</h2>", html)
        self.assertIn("<p>Request data not supplied</p>", html)
        self.assertNotIn("During handling of the above exception", html)

    def test_innermost_exception_without_traceback(self):
        """
        Test the creation of an exception report when an innermost exception is raised without a traceback.

        This function simulates an exception being raised within a nested try-except block, 
        then tests that the exception report accurately reflects the raised exception and its context.
        The test checks that the report includes the expected information, such as the exception type and value, 
        the traceback, and a message indicating that another exception occurred during handling of the original exception.
        It verifies this information is present in both the HTML and text formats of the report.
        """
        try:
            try:
                raise RuntimeError("Oops")
            except Exception as exc:
                new_exc = RuntimeError("My context")
                exc.__context__ = new_exc
                raise
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()

        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        frames = reporter.get_traceback_frames()
        self.assertEqual(len(frames), 2)
        html = reporter.get_traceback_html()
        self.assertInHTML("<h1>RuntimeError</h1>", html)
        self.assertIn('<pre class="exception_value">Oops</pre>', html)
        self.assertIn('<th scope="row">Exception Type:</th>', html)
        self.assertIn('<th scope="row">Exception Value:</th>', html)
        self.assertIn("<h2>Traceback ", html)
        self.assertIn("<h2>Request information</h2>", html)
        self.assertIn("<p>Request data not supplied</p>", html)
        self.assertIn(
            "During handling of the above exception (My context), another "
            "exception occurred",
            html,
        )
        self.assertInHTML('<li class="frame user">None</li>', html)
        self.assertIn("Traceback (most recent call last):\n  None", html)

        text = reporter.get_traceback_text()
        self.assertIn("Exception Type: RuntimeError", text)
        self.assertIn("Exception Value: Oops", text)
        self.assertIn("Traceback (most recent call last):\n  None", text)
        self.assertIn(
            "During handling of the above exception (My context), another "
            "exception occurred",
            text,
        )

    @skipUnless(PY311, "Exception notes were added in Python 3.11.")
    def test_exception_with_notes(self):
        request = self.rf.get("/test_view/")
        try:
            try:
                raise RuntimeError("Oops")
            except Exception as err:
                err.add_note("First Note")
                err.add_note("Second Note")
                err.add_note(mark_safe("<script>alert(1);</script>"))
                raise err
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()

        reporter = ExceptionReporter(request, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertIn(
            '<pre class="exception_value">Oops\nFirst Note\nSecond Note\n'
            "&lt;script&gt;alert(1);&lt;/script&gt;</pre>",
            html,
        )
        self.assertIn(
            "Exception Value: Oops\nFirst Note\nSecond Note\n"
            "&lt;script&gt;alert(1);&lt;/script&gt;",
            html,
        )

        text = reporter.get_traceback_text()
        self.assertIn(
            "Exception Value: Oops\nFirst Note\nSecond Note\n"
            "<script>alert(1);</script>",
            text,
        )

    def test_mid_stack_exception_without_traceback(self):
        """

        Tests the generation of HTML and text exception reports when an exception occurs 
        in the middle of a stack without a traceback. It verifies that the exception 
        report includes the expected headers, exception type, exception value, and 
        traceback information.

        The test case simulates a nested exception scenario where an inner exception 
        ('Inner Oops') is caught and then re-raised with a new exception ('Oops') that 
        has the inner exception as its context. The resulting exception report is then 
        checked for the presence of specific HTML and text elements, including exception 
        headers, exception values, and traceback details.

        """
        try:
            try:
                raise RuntimeError("Inner Oops")
            except Exception as exc:
                new_exc = RuntimeError("My context")
                new_exc.__context__ = exc
                raise RuntimeError("Oops") from new_exc
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertInHTML("<h1>RuntimeError</h1>", html)
        self.assertIn('<pre class="exception_value">Oops</pre>', html)
        self.assertIn('<th scope="row">Exception Type:</th>', html)
        self.assertIn('<th scope="row">Exception Value:</th>', html)
        self.assertIn("<h2>Traceback ", html)
        self.assertInHTML('<li class="frame user">Traceback: None</li>', html)
        self.assertIn(
            "During handling of the above exception (Inner Oops), another "
            "exception occurred:\n  Traceback: None",
            html,
        )

        text = reporter.get_traceback_text()
        self.assertIn("Exception Type: RuntimeError", text)
        self.assertIn("Exception Value: Oops", text)
        self.assertIn("Traceback (most recent call last):", text)
        self.assertIn(
            "During handling of the above exception (Inner Oops), another "
            "exception occurred:\n  Traceback: None",
            text,
        )

    def test_reporting_of_nested_exceptions(self):
        request = self.rf.get("/test_view/")
        try:
            try:
                raise AttributeError(mark_safe("<p>Top level</p>"))
            except AttributeError as explicit:
                try:
                    raise ValueError(mark_safe("<p>Second exception</p>")) from explicit
                except ValueError:
                    raise IndexError(mark_safe("<p>Final exception</p>"))
        except Exception:
            # Custom exception handler, just pass it into ExceptionReporter
            exc_type, exc_value, tb = sys.exc_info()

        explicit_exc = (
            "The above exception ({0}) was the direct cause of the following exception:"
        )
        implicit_exc = (
            "During handling of the above exception ({0}), another exception occurred:"
        )

        reporter = ExceptionReporter(request, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        # Both messages are twice on page -- one rendered as html,
        # one as plain text (for pastebin)
        self.assertEqual(
            2, html.count(explicit_exc.format("&lt;p&gt;Top level&lt;/p&gt;"))
        )
        self.assertEqual(
            2, html.count(implicit_exc.format("&lt;p&gt;Second exception&lt;/p&gt;"))
        )
        self.assertEqual(10, html.count("&lt;p&gt;Final exception&lt;/p&gt;"))

        text = reporter.get_traceback_text()
        self.assertIn(explicit_exc.format("<p>Top level</p>"), text)
        self.assertIn(implicit_exc.format("<p>Second exception</p>"), text)
        self.assertEqual(3, text.count("<p>Final exception</p>"))

    @skipIf(
        sys._xoptions.get("no_debug_ranges", False)
        or os.environ.get("PYTHONNODEBUGRANGES", False),
        "Fine-grained error locations are disabled.",
    )
    @skipUnless(PY311, "Fine-grained error locations were added in Python 3.11.")
    def test_highlight_error_position(self):
        """
        Tests the fine-grained error location highlighting in exception reporting.

        This test simulates a series of exceptions with varying levels of nesting and checks
        that the exception reporter correctly highlights the error positions in both HTML
        and text representations of the traceback. The test ensures that the error
        locations are accurately identified and marked in the traceback output.

        The test covers cases where exceptions are raised directly, as well as exceptions
        that are raised from other exceptions, to verify that the reporting mechanism can
        handle complex error scenarios.

        The expected output includes specific lines from the traceback that contain the
        highlighted error positions, with carets (`^`) pointing to the exact locations
        where the exceptions were raised. The test checks for the presence of these lines
        in both the HTML and text representations of the traceback to ensure that the
        reporting mechanism is working correctly.

        Requires Python 3.11 or later, as fine-grained error locations were introduced in
        this version. Skipped if fine-grained error locations are disabled via the
        `no_debug_ranges` or `PYTHONNODEBUGRANGES` options.
        """
        request = self.rf.get("/test_view/")
        try:
            try:
                raise AttributeError("Top level")
            except AttributeError as explicit:
                try:
                    raise ValueError(mark_safe("<p>2nd exception</p>")) from explicit
                except ValueError:
                    raise IndexError("Final exception")
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()

        reporter = ExceptionReporter(request, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertIn(
            "<pre>                raise AttributeError(&quot;Top level&quot;)\n"
            "                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^</pre>",
            html,
        )
        self.assertIn(
            "<pre>                    raise ValueError(mark_safe("
            "&quot;&lt;p&gt;2nd exception&lt;/p&gt;&quot;)) from explicit\n"
            "                         "
            "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^</pre>",
            html,
        )
        self.assertIn(
            "<pre>                    raise IndexError(&quot;Final exception&quot;)\n"
            "                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^</pre>",
            html,
        )
        # Pastebin.
        self.assertIn(
            "    raise AttributeError(&quot;Top level&quot;)\n"
            "    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
            html,
        )
        self.assertIn(
            "    raise ValueError(mark_safe("
            "&quot;&lt;p&gt;2nd exception&lt;/p&gt;&quot;)) from explicit\n"
            "    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
            html,
        )
        self.assertIn(
            "    raise IndexError(&quot;Final exception&quot;)\n"
            "    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
            html,
        )
        # Text traceback.
        text = reporter.get_traceback_text()
        self.assertIn(
            '    raise AttributeError("Top level")\n'
            "    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
            text,
        )
        self.assertIn(
            '    raise ValueError(mark_safe("<p>2nd exception</p>")) from explicit\n'
            "    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
            text,
        )
        self.assertIn(
            '    raise IndexError("Final exception")\n'
            "    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n",
            text,
        )

    def test_reporting_frames_without_source(self):
        """

        Test that the ExceptionReporter correctly handles reporting frames when the source code is not available.

        This test simulates a scenario where an exception is raised from a dynamically compiled code object.
        The test verifies that the reporter correctly identifies the frame information, including the filename, function name, and line number.
        Additionally, it checks that the reporter's get_traceback_frames, get_traceback_html, and get_traceback_text methods produce the expected output when the source code is not available, using the '<source code not available>' placeholder.

        """
        try:
            source = "def funcName():\n    raise Error('Whoops')\nfuncName()"
            namespace = {}
            code = compile(source, "generated", "exec")
            exec(code, namespace)
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        request = self.rf.get("/test_view/")
        reporter = ExceptionReporter(request, exc_type, exc_value, tb)
        frames = reporter.get_traceback_frames()
        last_frame = frames[-1]
        self.assertEqual(last_frame["context_line"], "<source code not available>")
        self.assertEqual(last_frame["filename"], "generated")
        self.assertEqual(last_frame["function"], "funcName")
        self.assertEqual(last_frame["lineno"], 2)
        html = reporter.get_traceback_html()
        self.assertIn(
            '<span class="fname">generated</span>, line 2, in funcName',
            html,
        )
        self.assertIn(
            '<code class="fname">generated</code>, line 2, in funcName',
            html,
        )
        self.assertIn(
            '"generated", line 2, in funcName\n    &lt;source code not available&gt;',
            html,
        )
        text = reporter.get_traceback_text()
        self.assertIn(
            '"generated", line 2, in funcName\n    <source code not available>',
            text,
        )

    def test_reporting_frames_source_not_match(self):
        try:
            source = "def funcName():\n    raise Error('Whoops')\nfuncName()"
            namespace = {}
            code = compile(source, "generated", "exec")
            exec(code, namespace)
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        with mock.patch(
            "django.views.debug.ExceptionReporter._get_source",
            return_value=["wrong source"],
        ):
            request = self.rf.get("/test_view/")
            reporter = ExceptionReporter(request, exc_type, exc_value, tb)
            frames = reporter.get_traceback_frames()
            last_frame = frames[-1]
            self.assertEqual(last_frame["context_line"], "<source code not available>")
            self.assertEqual(last_frame["filename"], "generated")
            self.assertEqual(last_frame["function"], "funcName")
            self.assertEqual(last_frame["lineno"], 2)
            html = reporter.get_traceback_html()
            self.assertIn(
                '<span class="fname">generated</span>, line 2, in funcName',
                html,
            )
            self.assertIn(
                '<code class="fname">generated</code>, line 2, in funcName',
                html,
            )
            self.assertIn(
                '"generated", line 2, in funcName\n'
                "    &lt;source code not available&gt;",
                html,
            )
            text = reporter.get_traceback_text()
            self.assertIn(
                '"generated", line 2, in funcName\n    <source code not available>',
                text,
            )

    def test_reporting_frames_for_cyclic_reference(self):
        """

        Tests the handling of cyclic references in exception reporting frames.

        This test function simulates an exception being raised with a cyclic reference in its
        cause chain. It then creates an ExceptionReporter instance with the raised exception
        and verifies that a warning is emitted when a cycle is detected in the exception chain.
        The test also checks that the traceback frames are correctly generated despite the cycle.

        The test covers the following scenarios:
        - A cycle is detected in the exception chain and a warning is emitted.
        - The traceback frames are correctly generated even in the presence of a cycle.
        - The last frame of the traceback contains the expected context line, filename, and function name.

        """
        try:

            def test_func():
                try:
                    raise RuntimeError("outer") from RuntimeError("inner")
                except RuntimeError as exc:
                    raise exc.__cause__

            test_func()
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        request = self.rf.get("/test_view/")
        reporter = ExceptionReporter(request, exc_type, exc_value, tb)

        def generate_traceback_frames(*args, **kwargs):
            """
            Generates and updates traceback frames obtained from the reporter.

            This function fetches the traceback frames and stores them in the tb_frames variable, allowing for further analysis or processing of the frames.

            Parameters
            ----------
            *args : variable-length non-keyword arguments
                Not utilized in this function.
            **kwargs : arbitrary keyword arguments
                Not utilized in this function.

            Notes
            -----
            The reporter object is assumed to have a get_traceback_frames method that returns the traceback frames.
            """
            nonlocal tb_frames
            tb_frames = reporter.get_traceback_frames()

        tb_frames = None
        tb_generator = threading.Thread(target=generate_traceback_frames, daemon=True)
        msg = (
            "Cycle in the exception chain detected: exception 'inner' "
            "encountered again."
        )
        with self.assertWarnsMessage(ExceptionCycleWarning, msg):
            tb_generator.start()
        tb_generator.join(timeout=5)
        if tb_generator.is_alive():
            # tb_generator is a daemon that runs until the main thread/process
            # exits. This is resource heavy when running the full test suite.
            # Setting the following values to None makes
            # reporter.get_traceback_frames() exit early.
            exc_value.__traceback__ = exc_value.__context__ = exc_value.__cause__ = None
            tb_generator.join()
            self.fail("Cyclic reference in Exception Reporter.get_traceback_frames()")
        if tb_frames is None:
            # can happen if the thread generating traceback got killed
            # or exception while generating the traceback
            self.fail("Traceback generation failed")
        last_frame = tb_frames[-1]
        self.assertIn("raise exc.__cause__", last_frame["context_line"])
        self.assertEqual(last_frame["filename"], __file__)
        self.assertEqual(last_frame["function"], "test_func")

    def test_request_and_message(self):
        "A message can be provided in addition to a request"
        request = self.rf.get("/test_view/")
        reporter = ExceptionReporter(request, None, "I'm a little teapot", None)
        html = reporter.get_traceback_html()
        self.assertInHTML("<h1>Report at /test_view/</h1>", html)
        self.assertIn(
            '<pre class="exception_value">I&#x27;m a little teapot</pre>', html
        )
        self.assertIn('<th scope="row">Request Method:</th>', html)
        self.assertIn('<th scope="row">Request URL:</th>', html)
        self.assertNotIn('<th scope="row">Exception Type:</th>', html)
        self.assertNotIn('<th scope="row">Exception Value:</th>', html)
        self.assertIn("<h2>Traceback ", html)
        self.assertIn("<h2>Request information</h2>", html)
        self.assertNotIn("<p>Request data not supplied</p>", html)

    def test_message_only(self):
        reporter = ExceptionReporter(None, None, "I'm a little teapot", None)
        html = reporter.get_traceback_html()
        self.assertInHTML("<h1>Report</h1>", html)
        self.assertIn(
            '<pre class="exception_value">I&#x27;m a little teapot</pre>', html
        )
        self.assertNotIn('<th scope="row">Request Method:</th>', html)
        self.assertNotIn('<th scope="row">Request URL:</th>', html)
        self.assertNotIn('<th scope="row">Exception Type:</th>', html)
        self.assertNotIn('<th scope="row">Exception Value:</th>', html)
        self.assertIn("<h2>Traceback ", html)
        self.assertIn("<h2>Request information</h2>", html)
        self.assertIn("<p>Request data not supplied</p>", html)

    def test_non_utf8_values_handling(self):
        "Non-UTF-8 exceptions/values should not make the output generation choke."
        try:

            class NonUtf8Output(Exception):
                def __repr__(self):
                    return b"EXC\xe9EXC"

            somevar = b"VAL\xe9VAL"  # NOQA
            raise NonUtf8Output()
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertIn("VAL\\xe9VAL", html)
        self.assertIn("EXC\\xe9EXC", html)

    def test_local_variable_escaping(self):
        """Safe strings in local variables are escaped."""
        try:
            local = mark_safe("<p>Local variable</p>")
            raise ValueError(local)
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        html = ExceptionReporter(None, exc_type, exc_value, tb).get_traceback_html()
        self.assertIn(
            '<td class="code"><pre>&#x27;&lt;p&gt;Local variable&lt;/p&gt;&#x27;</pre>'
            "</td>",
            html,
        )

    def test_unprintable_values_handling(self):
        "Unprintable values should not make the output generation choke."
        try:

            class OomOutput:
                def __repr__(self):
                    raise MemoryError("OOM")

            oomvalue = OomOutput()  # NOQA
            raise ValueError()
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertIn('<td class="code"><pre>Error in formatting', html)

    def test_too_large_values_handling(self):
        "Large values should not create a large HTML."
        large = 256 * 1024
        repr_of_str_adds = len(repr(""))
        try:

            class LargeOutput:
                def __repr__(self):
                    return repr("A" * large)

            largevalue = LargeOutput()  # NOQA
            raise ValueError()
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertEqual(len(html) // 1024 // 128, 0)  # still fit in 128Kb
        self.assertIn(
            "&lt;trimmed %d bytes string&gt;" % (large + repr_of_str_adds,), html
        )

    def test_encoding_error(self):
        """
        A UnicodeError displays a portion of the problematic string. HTML in
        safe strings is escaped.
        """
        try:
            mark_safe("abcdefghijkl<p>mnὀp</p>qrstuwxyz").encode("ascii")
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertIn("<h2>Unicode error hint</h2>", html)
        self.assertIn("The string that could not be encoded/decoded was: ", html)
        self.assertIn("<strong>&lt;p&gt;mnὀp&lt;/p&gt;</strong>", html)

    def test_unfrozen_importlib(self):
        """
        importlib is not a frozen app, but its loader thinks it's frozen which
        results in an ImportError. Refs #21443.
        """
        try:
            request = self.rf.get("/test_view/")
            importlib.import_module("abc.def.invalid.name")
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(request, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertInHTML("<h1>ModuleNotFoundError at /test_view/</h1>", html)

    def test_ignore_traceback_evaluation_exceptions(self):
        """
        Don't trip over exceptions generated by crafted objects when
        evaluating them while cleansing (#24455).
        """

        class BrokenEvaluation(Exception):
            pass

        def broken_setup():
            raise BrokenEvaluation

        request = self.rf.get("/test_view/")
        broken_lazy = SimpleLazyObject(broken_setup)
        try:
            bool(broken_lazy)
        except BrokenEvaluation:
            exc_type, exc_value, tb = sys.exc_info()

        self.assertIn(
            "BrokenEvaluation",
            ExceptionReporter(request, exc_type, exc_value, tb).get_traceback_html(),
            "Evaluation exception reason not mentioned in traceback",
        )

    @override_settings(ALLOWED_HOSTS="example.com")
    def test_disallowed_host(self):
        "An exception report can be generated even for a disallowed host."
        request = self.rf.get("/", headers={"host": "evil.com"})
        reporter = ExceptionReporter(request, None, None, None)
        html = reporter.get_traceback_html()
        self.assertIn("http://evil.com/", html)

    def test_request_with_items_key(self):
        """
        An exception report can be generated for requests with 'items' in
        request GET, POST, FILES, or COOKIES QueryDicts.
        """
        value = '<td>items</td><td class="code"><pre>&#x27;Oops&#x27;</pre></td>'
        # GET
        request = self.rf.get("/test_view/?items=Oops")
        reporter = ExceptionReporter(request, None, None, None)
        html = reporter.get_traceback_html()
        self.assertInHTML(value, html)
        # POST
        request = self.rf.post("/test_view/", data={"items": "Oops"})
        reporter = ExceptionReporter(request, None, None, None)
        html = reporter.get_traceback_html()
        self.assertInHTML(value, html)
        # FILES
        fp = StringIO("filecontent")
        request = self.rf.post("/test_view/", data={"name": "filename", "items": fp})
        reporter = ExceptionReporter(request, None, None, None)
        html = reporter.get_traceback_html()
        self.assertInHTML(
            '<td>items</td><td class="code"><pre>&lt;InMemoryUploadedFile: '
            "items (application/octet-stream)&gt;</pre></td>",
            html,
        )
        # COOKIES
        rf = RequestFactory()
        rf.cookies["items"] = "Oops"
        request = rf.get("/test_view/")
        reporter = ExceptionReporter(request, None, None, None)
        html = reporter.get_traceback_html()
        self.assertInHTML(
            '<td>items</td><td class="code"><pre>&#x27;Oops&#x27;</pre></td>', html
        )

    def test_exception_fetching_user(self):
        """
        The error page can be rendered if the current user can't be retrieved
        (such as when the database is unavailable).
        """

        class ExceptionUser:
            def __str__(self):
                raise Exception()

        request = self.rf.get("/test_view/")
        request.user = ExceptionUser()

        try:
            raise ValueError("Oops")
        except ValueError:
            exc_type, exc_value, tb = sys.exc_info()

        reporter = ExceptionReporter(request, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertInHTML("<h1>ValueError at /test_view/</h1>", html)
        self.assertIn('<pre class="exception_value">Oops</pre>', html)
        self.assertIn('<h3 id="user-info">USER</h3>', html)
        self.assertIn("<p>[unable to retrieve the current user]</p>", html)

        text = reporter.get_traceback_text()
        self.assertIn("USER: [unable to retrieve the current user]", text)

    def test_template_encoding(self):
        """
        The templates are loaded directly, not via a template loader, and
        should be opened as utf-8 charset as is the default specified on
        template engines.
        """
        reporter = ExceptionReporter(None, None, None, None)
        with mock.patch.object(DebugPath, "open") as m:
            reporter.get_traceback_html()
            m.assert_called_once_with(encoding="utf-8")
            m.reset_mock()
            reporter.get_traceback_text()
            m.assert_called_once_with(encoding="utf-8")

    @override_settings(ALLOWED_HOSTS=["example.com"])
    def test_get_raw_insecure_uri(self):
        """

        Test the _get_raw_insecure_uri method to ensure it correctly constructs an insecure URI 
        from a given request.

        The test simulates requests with various URL patterns and asserts that the resulting 
        insecure URI matches the expected output. This includes tests for absolute URIs, URLs 
        with query parameters, and paths containing special characters.

        The test case uses a RequestFactory to create mock requests with a custom 'Host' header 
        set to 'evil.com', which is not in the ALLOWED_HOSTS setting, and verifies that the 
        _get_raw_insecure_uri method behaves as expected in this scenario.

        """
        factory = RequestFactory(headers={"host": "evil.com"})
        tests = [
            ("////absolute-uri", "http://evil.com//absolute-uri"),
            ("/?foo=bar", "http://evil.com/?foo=bar"),
            ("/path/with:colons", "http://evil.com/path/with:colons"),
        ]
        for url, expected in tests:
            with self.subTest(url=url):
                request = factory.get(url)
                reporter = ExceptionReporter(request, None, None, None)
                self.assertEqual(reporter._get_raw_insecure_uri(), expected)


class PlainTextReportTests(SimpleTestCase):
    rf = RequestFactory()

    def test_request_and_exception(self):
        "A simple exception report can be generated"
        try:
            request = self.rf.get("/test_view/")
            request.user = User()
            raise ValueError("Can't find my keys")
        except ValueError:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(request, exc_type, exc_value, tb)
        text = reporter.get_traceback_text()
        self.assertIn("ValueError at /test_view/", text)
        self.assertIn("Can't find my keys", text)
        self.assertIn("Request Method:", text)
        self.assertIn("Request URL:", text)
        self.assertIn("USER: jacob", text)
        self.assertIn("Exception Type:", text)
        self.assertIn("Exception Value:", text)
        self.assertIn("Traceback (most recent call last):", text)
        self.assertIn("Request information:", text)
        self.assertNotIn("Request data not supplied", text)

    def test_no_request(self):
        "An exception report can be generated without request"
        try:
            raise ValueError("Can't find my keys")
        except ValueError:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        text = reporter.get_traceback_text()
        self.assertIn("ValueError", text)
        self.assertIn("Can't find my keys", text)
        self.assertNotIn("Request Method:", text)
        self.assertNotIn("Request URL:", text)
        self.assertNotIn("USER:", text)
        self.assertIn("Exception Type:", text)
        self.assertIn("Exception Value:", text)
        self.assertIn("Traceback (most recent call last):", text)
        self.assertIn("Request data not supplied", text)

    def test_no_exception(self):
        "An exception report can be generated for just a request"
        request = self.rf.get("/test_view/")
        reporter = ExceptionReporter(request, None, None, None)
        reporter.get_traceback_text()

    def test_request_and_message(self):
        "A message can be provided in addition to a request"
        request = self.rf.get("/test_view/")
        reporter = ExceptionReporter(request, None, "I'm a little teapot", None)
        reporter.get_traceback_text()

    @override_settings(DEBUG=True)
    def test_template_exception(self):
        """

        Tests that a template exception triggers the correct error reporting.

        The test simulates a request to a view that renders a template with an intentional error,
        then verifies that the resulting exception is correctly handled and reported by the 
        ExceptionReporter. Specifically, it checks that the error message includes the 
        path to the problematic template, the line number where the error occurred, and 
        the error message itself, which should indicate that the 'cycle' tag is missing 
        required arguments.

        """
        request = self.rf.get("/test_view/")
        try:
            render(request, "debug/template_error.html")
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(request, exc_type, exc_value, tb)
        text = reporter.get_traceback_text()
        templ_path = Path(
            Path(__file__).parents[1], "templates", "debug", "template_error.html"
        )
        self.assertIn(
            "Template error:\n"
            "In template %(path)s, error at line 2\n"
            "   'cycle' tag requires at least two arguments\n"
            "   1 : Template with error:\n"
            "   2 :  {%% cycle %%} \n"
            "   3 : " % {"path": templ_path},
            text,
        )

    def test_request_with_items_key(self):
        """
        An exception report can be generated for requests with 'items' in
        request GET, POST, FILES, or COOKIES QueryDicts.
        """
        # GET
        request = self.rf.get("/test_view/?items=Oops")
        reporter = ExceptionReporter(request, None, None, None)
        text = reporter.get_traceback_text()
        self.assertIn("items = 'Oops'", text)
        # POST
        request = self.rf.post("/test_view/", data={"items": "Oops"})
        reporter = ExceptionReporter(request, None, None, None)
        text = reporter.get_traceback_text()
        self.assertIn("items = 'Oops'", text)
        # FILES
        fp = StringIO("filecontent")
        request = self.rf.post("/test_view/", data={"name": "filename", "items": fp})
        reporter = ExceptionReporter(request, None, None, None)
        text = reporter.get_traceback_text()
        self.assertIn("items = <InMemoryUploadedFile:", text)
        # COOKIES
        rf = RequestFactory()
        rf.cookies["items"] = "Oops"
        request = rf.get("/test_view/")
        reporter = ExceptionReporter(request, None, None, None)
        text = reporter.get_traceback_text()
        self.assertIn("items = 'Oops'", text)

    def test_message_only(self):
        reporter = ExceptionReporter(None, None, "I'm a little teapot", None)
        reporter.get_traceback_text()

    @override_settings(ALLOWED_HOSTS="example.com")
    def test_disallowed_host(self):
        "An exception report can be generated even for a disallowed host."
        request = self.rf.get("/", headers={"host": "evil.com"})
        reporter = ExceptionReporter(request, None, None, None)
        text = reporter.get_traceback_text()
        self.assertIn("http://evil.com/", text)


class ExceptionReportTestMixin:
    # Mixin used in the ExceptionReporterFilterTests and
    # AjaxResponseExceptionReporterFilter tests below
    breakfast_data = {
        "sausage-key": "sausage-value",
        "baked-beans-key": "baked-beans-value",
        "hash-brown-key": "hash-brown-value",
        "bacon-key": "bacon-value",
    }

    def verify_unsafe_response(
        self, view, check_for_vars=True, check_for_POST_params=True
    ):
        """
        Asserts that potentially sensitive info are displayed in the response.
        """
        request = self.rf.post("/some_url/", self.breakfast_data)
        if iscoroutinefunction(view):
            response = async_to_sync(view)(request)
        else:
            response = view(request)
        if check_for_vars:
            # All variables are shown.
            self.assertContains(response, "cooked_eggs", status_code=500)
            self.assertContains(response, "scrambled", status_code=500)
            self.assertContains(response, "sauce", status_code=500)
            self.assertContains(response, "worcestershire", status_code=500)
        if check_for_POST_params:
            for k, v in self.breakfast_data.items():
                # All POST parameters are shown.
                self.assertContains(response, k, status_code=500)
                self.assertContains(response, v, status_code=500)

    def verify_safe_response(
        self, view, check_for_vars=True, check_for_POST_params=True
    ):
        """
        Asserts that certain sensitive info are not displayed in the response.
        """
        request = self.rf.post("/some_url/", self.breakfast_data)
        if iscoroutinefunction(view):
            response = async_to_sync(view)(request)
        else:
            response = view(request)
        if check_for_vars:
            # Non-sensitive variable's name and value are shown.
            self.assertContains(response, "cooked_eggs", status_code=500)
            self.assertContains(response, "scrambled", status_code=500)
            # Sensitive variable's name is shown but not its value.
            self.assertContains(response, "sauce", status_code=500)
            self.assertNotContains(response, "worcestershire", status_code=500)
        if check_for_POST_params:
            for k in self.breakfast_data:
                # All POST parameters' names are shown.
                self.assertContains(response, k, status_code=500)
            # Non-sensitive POST parameters' values are shown.
            self.assertContains(response, "baked-beans-value", status_code=500)
            self.assertContains(response, "hash-brown-value", status_code=500)
            # Sensitive POST parameters' values are not shown.
            self.assertNotContains(response, "sausage-value", status_code=500)
            self.assertNotContains(response, "bacon-value", status_code=500)

    def verify_paranoid_response(
        self, view, check_for_vars=True, check_for_POST_params=True
    ):
        """
        Asserts that no variables or POST parameters are displayed in the response.
        """
        request = self.rf.post("/some_url/", self.breakfast_data)
        response = view(request)
        if check_for_vars:
            # Show variable names but not their values.
            self.assertContains(response, "cooked_eggs", status_code=500)
            self.assertNotContains(response, "scrambled", status_code=500)
            self.assertContains(response, "sauce", status_code=500)
            self.assertNotContains(response, "worcestershire", status_code=500)
        if check_for_POST_params:
            for k, v in self.breakfast_data.items():
                # All POST parameters' names are shown.
                self.assertContains(response, k, status_code=500)
                # No POST parameters' values are shown.
                self.assertNotContains(response, v, status_code=500)

    def verify_unsafe_email(self, view, check_for_POST_params=True):
        """
        Asserts that potentially sensitive info are displayed in the email report.
        """
        with self.settings(ADMINS=[("Admin", "admin@fattie-breakie.com")]):
            mail.outbox = []  # Empty outbox
            request = self.rf.post("/some_url/", self.breakfast_data)
            if iscoroutinefunction(view):
                async_to_sync(view)(request)
            else:
                view(request)
            self.assertEqual(len(mail.outbox), 1)
            email = mail.outbox[0]

            # Frames vars are never shown in plain text email reports.
            body_plain = str(email.body)
            self.assertNotIn("cooked_eggs", body_plain)
            self.assertNotIn("scrambled", body_plain)
            self.assertNotIn("sauce", body_plain)
            self.assertNotIn("worcestershire", body_plain)

            # Frames vars are shown in html email reports.
            body_html = str(email.alternatives[0].content)
            self.assertIn("cooked_eggs", body_html)
            self.assertIn("scrambled", body_html)
            self.assertIn("sauce", body_html)
            self.assertIn("worcestershire", body_html)

            if check_for_POST_params:
                for k, v in self.breakfast_data.items():
                    # All POST parameters are shown.
                    self.assertIn(k, body_plain)
                    self.assertIn(v, body_plain)
                    self.assertIn(k, body_html)
                    self.assertIn(v, body_html)

    def verify_safe_email(self, view, check_for_POST_params=True):
        """
        Asserts that certain sensitive info are not displayed in the email report.
        """
        with self.settings(ADMINS=[("Admin", "admin@fattie-breakie.com")]):
            mail.outbox = []  # Empty outbox
            request = self.rf.post("/some_url/", self.breakfast_data)
            if iscoroutinefunction(view):
                async_to_sync(view)(request)
            else:
                view(request)
            self.assertEqual(len(mail.outbox), 1)
            email = mail.outbox[0]

            # Frames vars are never shown in plain text email reports.
            body_plain = str(email.body)
            self.assertNotIn("cooked_eggs", body_plain)
            self.assertNotIn("scrambled", body_plain)
            self.assertNotIn("sauce", body_plain)
            self.assertNotIn("worcestershire", body_plain)

            # Frames vars are shown in html email reports.
            body_html = str(email.alternatives[0].content)
            self.assertIn("cooked_eggs", body_html)
            self.assertIn("scrambled", body_html)
            self.assertIn("sauce", body_html)
            self.assertNotIn("worcestershire", body_html)

            if check_for_POST_params:
                for k in self.breakfast_data:
                    # All POST parameters' names are shown.
                    self.assertIn(k, body_plain)
                # Non-sensitive POST parameters' values are shown.
                self.assertIn("baked-beans-value", body_plain)
                self.assertIn("hash-brown-value", body_plain)
                self.assertIn("baked-beans-value", body_html)
                self.assertIn("hash-brown-value", body_html)
                # Sensitive POST parameters' values are not shown.
                self.assertNotIn("sausage-value", body_plain)
                self.assertNotIn("bacon-value", body_plain)
                self.assertNotIn("sausage-value", body_html)
                self.assertNotIn("bacon-value", body_html)

    def verify_paranoid_email(self, view):
        """
        Asserts that no variables or POST parameters are displayed in the email report.
        """
        with self.settings(ADMINS=[("Admin", "admin@fattie-breakie.com")]):
            mail.outbox = []  # Empty outbox
            request = self.rf.post("/some_url/", self.breakfast_data)
            view(request)
            self.assertEqual(len(mail.outbox), 1)
            email = mail.outbox[0]
            # Frames vars are never shown in plain text email reports.
            body = str(email.body)
            self.assertNotIn("cooked_eggs", body)
            self.assertNotIn("scrambled", body)
            self.assertNotIn("sauce", body)
            self.assertNotIn("worcestershire", body)
            for k, v in self.breakfast_data.items():
                # All POST parameters' names are shown.
                self.assertIn(k, body)
                # No POST parameters' values are shown.
                self.assertNotIn(v, body)


@override_settings(ROOT_URLCONF="view_tests.urls")
class ExceptionReporterFilterTests(
    ExceptionReportTestMixin, LoggingCaptureMixin, SimpleTestCase
):
    """
    Sensitive information can be filtered out of error reports (#14614).
    """

    rf = RequestFactory()

    def test_non_sensitive_request(self):
        """
        Everything (request info and frame variables) can bee seen
        in the default error reports for non-sensitive requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(non_sensitive_view)
            self.verify_unsafe_email(non_sensitive_view)

        with self.settings(DEBUG=False):
            self.verify_unsafe_response(non_sensitive_view)
            self.verify_unsafe_email(non_sensitive_view)

    def test_sensitive_request(self):
        """
        Sensitive POST parameters and frame variables cannot be
        seen in the default error reports for sensitive requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(sensitive_view)
            self.verify_unsafe_email(sensitive_view)

        with self.settings(DEBUG=False):
            self.verify_safe_response(sensitive_view)
            self.verify_safe_email(sensitive_view)

    def test_async_sensitive_request(self):
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(async_sensitive_view)
            self.verify_unsafe_email(async_sensitive_view)

        with self.settings(DEBUG=False):
            self.verify_safe_response(async_sensitive_view)
            self.verify_safe_email(async_sensitive_view)

    def test_async_sensitive_nested_request(self):
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(async_sensitive_view_nested)
            self.verify_unsafe_email(async_sensitive_view_nested)

        with self.settings(DEBUG=False):
            self.verify_safe_response(async_sensitive_view_nested)
            self.verify_safe_email(async_sensitive_view_nested)

    def test_paranoid_request(self):
        """
        No POST parameters and frame variables can be seen in the
        default error reports for "paranoid" requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(paranoid_view)
            self.verify_unsafe_email(paranoid_view)

        with self.settings(DEBUG=False):
            self.verify_paranoid_response(paranoid_view)
            self.verify_paranoid_email(paranoid_view)

    def test_multivalue_dict_key_error(self):
        """
        #21098 -- Sensitive POST parameters cannot be seen in the
        error reports for if request.POST['nonexistent_key'] throws an error.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(multivalue_dict_key_error)
            self.verify_unsafe_email(multivalue_dict_key_error)

        with self.settings(DEBUG=False):
            self.verify_safe_response(multivalue_dict_key_error)
            self.verify_safe_email(multivalue_dict_key_error)

    def test_custom_exception_reporter_filter(self):
        """
        It's possible to assign an exception reporter filter to
        the request to bypass the one set in DEFAULT_EXCEPTION_REPORTER_FILTER.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(custom_exception_reporter_filter_view)
            self.verify_unsafe_email(custom_exception_reporter_filter_view)

        with self.settings(DEBUG=False):
            self.verify_unsafe_response(custom_exception_reporter_filter_view)
            self.verify_unsafe_email(custom_exception_reporter_filter_view)

    def test_sensitive_method(self):
        """
        The sensitive_variables decorator works with object methods.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(
                sensitive_method_view, check_for_POST_params=False
            )
            self.verify_unsafe_email(sensitive_method_view, check_for_POST_params=False)

        with self.settings(DEBUG=False):
            self.verify_safe_response(
                sensitive_method_view, check_for_POST_params=False
            )
            self.verify_safe_email(sensitive_method_view, check_for_POST_params=False)

    def test_async_sensitive_method(self):
        """
        The sensitive_variables decorator works with async object methods.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(
                async_sensitive_method_view, check_for_POST_params=False
            )
            self.verify_unsafe_email(
                async_sensitive_method_view, check_for_POST_params=False
            )

        with self.settings(DEBUG=False):
            self.verify_safe_response(
                async_sensitive_method_view, check_for_POST_params=False
            )
            self.verify_safe_email(
                async_sensitive_method_view, check_for_POST_params=False
            )

    def test_async_sensitive_method_nested(self):
        """
        The sensitive_variables decorator works with async object methods.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(
                async_sensitive_method_view_nested, check_for_POST_params=False
            )
            self.verify_unsafe_email(
                async_sensitive_method_view_nested, check_for_POST_params=False
            )

        with self.settings(DEBUG=False):
            self.verify_safe_response(
                async_sensitive_method_view_nested, check_for_POST_params=False
            )
            self.verify_safe_email(
                async_sensitive_method_view_nested, check_for_POST_params=False
            )

    def test_sensitive_function_arguments(self):
        """
        Sensitive variables don't leak in the sensitive_variables decorator's
        frame, when those variables are passed as arguments to the decorated
        function.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(sensitive_args_function_caller)
            self.verify_unsafe_email(sensitive_args_function_caller)

        with self.settings(DEBUG=False):
            self.verify_safe_response(
                sensitive_args_function_caller, check_for_POST_params=False
            )
            self.verify_safe_email(
                sensitive_args_function_caller, check_for_POST_params=False
            )

    def test_sensitive_function_keyword_arguments(self):
        """
        Sensitive variables don't leak in the sensitive_variables decorator's
        frame, when those variables are passed as keyword arguments to the
        decorated function.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(sensitive_kwargs_function_caller)
            self.verify_unsafe_email(sensitive_kwargs_function_caller)

        with self.settings(DEBUG=False):
            self.verify_safe_response(
                sensitive_kwargs_function_caller, check_for_POST_params=False
            )
            self.verify_safe_email(
                sensitive_kwargs_function_caller, check_for_POST_params=False
            )

    def test_callable_settings(self):
        """
        Callable settings should not be evaluated in the debug page (#21345).
        """

        def callable_setting():
            return "This should not be displayed"

        with self.settings(DEBUG=True, FOOBAR=callable_setting):
            response = self.client.get("/raises500/")
            self.assertNotContains(
                response, "This should not be displayed", status_code=500
            )

    def test_callable_settings_forbidding_to_set_attributes(self):
        """
        Callable settings which forbid to set attributes should not break
        the debug page (#23070).
        """

        class CallableSettingWithSlots:
            __slots__ = []

            def __call__(self):
                return "This should not be displayed"

        with self.settings(DEBUG=True, WITH_SLOTS=CallableSettingWithSlots()):
            response = self.client.get("/raises500/")
            self.assertNotContains(
                response, "This should not be displayed", status_code=500
            )

    def test_dict_setting_with_non_str_key(self):
        """
        A dict setting containing a non-string key should not break the
        debug page (#12744).
        """
        with self.settings(DEBUG=True, FOOBAR={42: None}):
            response = self.client.get("/raises500/")
            self.assertContains(response, "FOOBAR", status_code=500)

    def test_sensitive_settings(self):
        """
        The debug page should not show some sensitive settings
        (password, secret key, ...).
        """
        sensitive_settings = [
            "SECRET_KEY",
            "SECRET_KEY_FALLBACKS",
            "PASSWORD",
            "API_KEY",
            "AUTH_TOKEN",
        ]
        for setting in sensitive_settings:
            with self.settings(DEBUG=True, **{setting: "should not be displayed"}):
                response = self.client.get("/raises500/")
                self.assertNotContains(
                    response, "should not be displayed", status_code=500
                )

    def test_settings_with_sensitive_keys(self):
        """
        The debug page should filter out some sensitive information found in
        dict settings.
        """
        sensitive_settings = [
            "SECRET_KEY",
            "SECRET_KEY_FALLBACKS",
            "PASSWORD",
            "API_KEY",
            "AUTH_TOKEN",
        ]
        for setting in sensitive_settings:
            FOOBAR = {
                setting: "should not be displayed",
                "recursive": {setting: "should not be displayed"},
            }
            with self.settings(DEBUG=True, FOOBAR=FOOBAR):
                response = self.client.get("/raises500/")
                self.assertNotContains(
                    response, "should not be displayed", status_code=500
                )

    def test_cleanse_setting_basic(self):
        """

        Tests the basic functionality of the :meth:`cleanse_setting` method.

        Verifies that the method correctly returns the original value for non-sensitive settings
        and replaces sensitive settings with a substitute value to prevent exposure of confidential information.

        """
        reporter_filter = SafeExceptionReporterFilter()
        self.assertEqual(reporter_filter.cleanse_setting("TEST", "TEST"), "TEST")
        self.assertEqual(
            reporter_filter.cleanse_setting("PASSWORD", "super_secret"),
            reporter_filter.cleansed_substitute,
        )

    def test_cleanse_setting_ignore_case(self):
        reporter_filter = SafeExceptionReporterFilter()
        self.assertEqual(
            reporter_filter.cleanse_setting("password", "super_secret"),
            reporter_filter.cleansed_substitute,
        )

    def test_cleanse_setting_recurses_in_dictionary(self):
        """

        Test that the cleanse_setting method recurses into dictionaries to remove sensitive information.

        This test case verifies that when a dictionary is provided to the cleanse_setting method,
        any password or secret values within that dictionary are correctly replaced with a
        cleansed substitute. The test covers the scenario where a dictionary contains a password
        or other sensitive setting that needs to be removed from logging output to prevent
        security vulnerabilities.

        The expected outcome is a dictionary with all sensitive information removed, ensuring
        that log reports do not inadvertently expose secure data.

        """
        reporter_filter = SafeExceptionReporterFilter()
        initial = {"login": "cooper", "password": "secret"}
        self.assertEqual(
            reporter_filter.cleanse_setting("SETTING_NAME", initial),
            {"login": "cooper", "password": reporter_filter.cleansed_substitute},
        )

    def test_cleanse_setting_recurses_in_dictionary_with_non_string_key(self):
        """
        Tests that the cleanse_setting method can handle dictionaries with non-string keys and recursively clean sensitive settings.

        Recursion is performed to traverse nested dictionaries and redact sensitive information, such as passwords. This ensures that all sensitive data is properly cleansed, regardless of the dictionary structure or key types.

        The method is expected to replace sensitive values with a cleansed substitute, while preserving the overall structure of the input dictionary. This test case specifically verifies this behavior for a dictionary with a non-string key, demonstrating the method's ability to handle diverse dictionary configurations.
        """
        reporter_filter = SafeExceptionReporterFilter()
        initial = {("localhost", 8000): {"login": "cooper", "password": "secret"}}
        self.assertEqual(
            reporter_filter.cleanse_setting("SETTING_NAME", initial),
            {
                ("localhost", 8000): {
                    "login": "cooper",
                    "password": reporter_filter.cleansed_substitute,
                },
            },
        )

    def test_cleanse_setting_recurses_in_list_tuples(self):
        reporter_filter = SafeExceptionReporterFilter()
        initial = [
            {
                "login": "cooper",
                "password": "secret",
                "apps": (
                    {"name": "app1", "api_key": "a06b-c462cffae87a"},
                    {"name": "app2", "api_key": "a9f4-f152e97ad808"},
                ),
                "tokens": ["98b37c57-ec62-4e39", "8690ef7d-8004-4916"],
            },
            {"SECRET_KEY": "c4d77c62-6196-4f17-a06b-c462cffae87a"},
        ]
        cleansed = [
            {
                "login": "cooper",
                "password": reporter_filter.cleansed_substitute,
                "apps": (
                    {"name": "app1", "api_key": reporter_filter.cleansed_substitute},
                    {"name": "app2", "api_key": reporter_filter.cleansed_substitute},
                ),
                "tokens": reporter_filter.cleansed_substitute,
            },
            {"SECRET_KEY": reporter_filter.cleansed_substitute},
        ]
        self.assertEqual(
            reporter_filter.cleanse_setting("SETTING_NAME", initial),
            cleansed,
        )
        self.assertEqual(
            reporter_filter.cleanse_setting("SETTING_NAME", tuple(initial)),
            tuple(cleansed),
        )

    def test_request_meta_filtering(self):
        """

        Tests the filtering functionality of the SafeExceptionReporterFilter for request metadata.

        Verifies that sensitive information in the request headers, such as 'secret-header', 
        is properly filtered and replaced with a cleansed substitute in the request metadata.

        Ensures that the filter correctly identifies and redacts sensitive headers to prevent 
        leakage of confidential information.

        """
        request = self.rf.get("/", headers={"secret-header": "super_secret"})
        reporter_filter = SafeExceptionReporterFilter()
        self.assertEqual(
            reporter_filter.get_safe_request_meta(request)["HTTP_SECRET_HEADER"],
            reporter_filter.cleansed_substitute,
        )

    def test_exception_report_uses_meta_filtering(self):
        """

        Tests that exception reports respect meta filtering rules.

        This test case checks that sensitive information, such as secret headers, is not included in exception reports.
        It verifies this behavior by sending requests with secret headers to an endpoint that raises an exception, 
        and then checks the response content to ensure the secret headers are not present.

        The test covers both HTML and JSON response formats, ensuring that meta filtering is applied consistently across different content types.

        """
        response = self.client.get(
            "/raises500/", headers={"secret-header": "super_secret"}
        )
        self.assertNotIn(b"super_secret", response.content)
        response = self.client.get(
            "/raises500/",
            headers={"secret-header": "super_secret", "accept": "application/json"},
        )
        self.assertNotIn(b"super_secret", response.content)

    @override_settings(SESSION_COOKIE_NAME="djangosession")
    def test_cleanse_session_cookie_value(self):
        """
        Tests that session cookie values are properly cleansed and not displayed in error responses.

        This test ensures that potentially sensitive information stored in session cookies
        is not leaked in the event of an internal server error. It verifies that the value
        of the session cookie is not present in the response body when a 500 status code
        is returned, helping to maintain the security and confidentiality of user data.
        """
        self.client.cookies.load({"djangosession": "should not be displayed"})
        response = self.client.get("/raises500/")
        self.assertNotContains(response, "should not be displayed", status_code=500)


class CustomExceptionReporterFilter(SafeExceptionReporterFilter):
    cleansed_substitute = "XXXXXXXXXXXXXXXXXXXX"
    hidden_settings = _lazy_re_compile(
        "API|TOKEN|KEY|SECRET|PASS|SIGNATURE|DATABASE_URL", flags=re.I
    )


@override_settings(
    ROOT_URLCONF="view_tests.urls",
    DEFAULT_EXCEPTION_REPORTER_FILTER="%s.CustomExceptionReporterFilter" % __name__,
)
class CustomExceptionReporterFilterTests(SimpleTestCase):
    def setUp(self):
        """

        Sets up the test environment by clearing the cache of the default exception reporter filter.
        This ensures that any cached filter settings are reset before each test, providing a clean slate.
        Additionally, schedules a cleanup to clear the cache again after the test, guaranteeing that the test environment is restored to its original state.

        """
        get_default_exception_reporter_filter.cache_clear()
        self.addCleanup(get_default_exception_reporter_filter.cache_clear)

    def test_setting_allows_custom_subclass(self):
        self.assertIsInstance(
            get_default_exception_reporter_filter(),
            CustomExceptionReporterFilter,
        )

    def test_cleansed_substitute_override(self):
        reporter_filter = get_default_exception_reporter_filter()
        self.assertEqual(
            reporter_filter.cleanse_setting("password", "super_secret"),
            reporter_filter.cleansed_substitute,
        )

    def test_hidden_settings_override(self):
        """
        Tests that hidden settings are properly overridden when using the default exception reporter filter.

        The function verifies that sensitive information, such as a database URL, is replaced with a substitute value to prevent it from being exposed in exception reports. 

        It checks the functionality of the default exception reporter filter's setting cleansing mechanism, ensuring that it correctly handles hidden settings and maintains the confidentiality of sensitive data.
        """
        reporter_filter = get_default_exception_reporter_filter()
        self.assertEqual(
            reporter_filter.cleanse_setting("database_url", "super_secret"),
            reporter_filter.cleansed_substitute,
        )


class NonHTMLResponseExceptionReporterFilter(
    ExceptionReportTestMixin, LoggingCaptureMixin, SimpleTestCase
):
    """
    Sensitive information can be filtered out of error reports.

    The plain text 500 debug-only error page is served when it has been
    detected the request doesn't accept HTML content. Don't check for
    (non)existence of frames vars in the traceback information section of the
    response content because they're not included in these error pages.
    Refs #14614.
    """

    rf = RequestFactory(headers={"accept": "application/json"})

    def test_non_sensitive_request(self):
        """
        Request info can bee seen in the default error reports for
        non-sensitive requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(non_sensitive_view, check_for_vars=False)

        with self.settings(DEBUG=False):
            self.verify_unsafe_response(non_sensitive_view, check_for_vars=False)

    def test_sensitive_request(self):
        """
        Sensitive POST parameters cannot be seen in the default
        error reports for sensitive requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(sensitive_view, check_for_vars=False)

        with self.settings(DEBUG=False):
            self.verify_safe_response(sensitive_view, check_for_vars=False)

    def test_async_sensitive_request(self):
        """
        Sensitive POST parameters cannot be seen in the default
        error reports for sensitive requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(async_sensitive_view, check_for_vars=False)

        with self.settings(DEBUG=False):
            self.verify_safe_response(async_sensitive_view, check_for_vars=False)

    def test_async_sensitive_request_nested(self):
        """
        Sensitive POST parameters cannot be seen in the default
        error reports for sensitive requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(
                async_sensitive_view_nested, check_for_vars=False
            )

        with self.settings(DEBUG=False):
            self.verify_safe_response(async_sensitive_view_nested, check_for_vars=False)

    def test_paranoid_request(self):
        """
        No POST parameters can be seen in the default error reports
        for "paranoid" requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(paranoid_view, check_for_vars=False)

        with self.settings(DEBUG=False):
            self.verify_paranoid_response(paranoid_view, check_for_vars=False)

    def test_custom_exception_reporter_filter(self):
        """
        It's possible to assign an exception reporter filter to
        the request to bypass the one set in DEFAULT_EXCEPTION_REPORTER_FILTER.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(
                custom_exception_reporter_filter_view, check_for_vars=False
            )

        with self.settings(DEBUG=False):
            self.verify_unsafe_response(
                custom_exception_reporter_filter_view, check_for_vars=False
            )

    @override_settings(DEBUG=True, ROOT_URLCONF="view_tests.urls")
    def test_non_html_response_encoding(self):
        """

        Tests that a non-HTML response from a view is properly encoded.

        This test case sends a GET request to a URL that is expected to raise a 500 error,
        with an Accept header set to 'application/json'. It then checks that the response
        has a Content-Type header indicating that the body is encoded in UTF-8, despite the
        client requesting JSON. This ensures that the server correctly handles encoding
        for non-HTML responses.

        The test is run with DEBUG mode enabled to ensure accurate error reporting.

        """
        response = self.client.get(
            "/raises500/", headers={"accept": "application/json"}
        )
        self.assertEqual(response.headers["Content-Type"], "text/plain; charset=utf-8")


class DecoratorsTests(SimpleTestCase):
    def test_sensitive_variables_not_called(self):
        """

        Tests that the sensitive_variables decorator is called with parentheses.

        This test case verifies that the sensitive_variables function is used correctly as a decorator.
        It checks that calling sensitive_variables without parentheses raises a TypeError with a specific error message.
        The test ensures that users are informed to use the decorator in the correct syntax, i.e., @sensitive_variables(), rather than @sensitive_variables.

        """
        msg = (
            "sensitive_variables() must be called to use it as a decorator, "
            "e.g., use @sensitive_variables(), not @sensitive_variables."
        )
        with self.assertRaisesMessage(TypeError, msg):

            @sensitive_variables
            def test_func(password):
                pass

    def test_sensitive_post_parameters_not_called(self):
        msg = (
            "sensitive_post_parameters() must be called to use it as a "
            "decorator, e.g., use @sensitive_post_parameters(), not "
            "@sensitive_post_parameters."
        )
        with self.assertRaisesMessage(TypeError, msg):

            @sensitive_post_parameters
            def test_func(request):
                return index_page(request)

    def test_sensitive_post_parameters_http_request(self):
        """

        Tests that the sensitive_post_parameters decorator correctly handles HTTP requests.

        The function verifies that the decorator raises a TypeError when it does not receive an HttpRequest object.
        It checks the scenario where the decorator is applied to a class method, ensuring that the correct usage
        of @method_decorator is enforced to avoid potential bugs.

        The test case includes a sample view function 'a_view' decorated with @sensitive_post_parameters and
        attempts to call this view with an HttpRequest object, validating the expected error message.

        """
        class MyClass:
            @sensitive_post_parameters()
            def a_view(self, request):
                return HttpResponse()

        msg = (
            "sensitive_post_parameters didn't receive an HttpRequest object. "
            "If you are decorating a classmethod, make sure to use "
            "@method_decorator."
        )
        with self.assertRaisesMessage(TypeError, msg):
            MyClass().a_view(HttpRequest())
