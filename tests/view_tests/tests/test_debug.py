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
        """

        Tests that a 400 bad request is handled correctly.

        Verifies that a warning is logged when a 400 response is generated, and that the 
        response contains the expected HTML elements and has a status code of 400.

        """
        with self.assertLogs("django.security", "WARNING"):
            response = self.client.get("/raises400/")
        self.assertContains(response, '<div class="context" id="', status_code=400)

    def test_400_bad_request(self):
        # When DEBUG=True, technical_500_template() is called.
        """

        Tests that a 400 Bad Request response is returned when a malformed request is made.

        This test case verifies that the application correctly handles invalid requests and returns
        a 400 status code with an informative error message. The test also checks that the error
        is logged with a warning level and that the response contains the expected error context.

        It covers the scenario where a request is made to a URL that is designed to raise a 400
        Bad Request error, ensuring that the application behaves as expected in this situation.

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
        """

        Tests the HTTP 404 response when accessing a non-existent URL.

        Verifies that the 404 response does not contain certain exception-related HTML
        elements and instead provides helpful information about the attempted URL and
        the URL patterns that Django tried to match.

        Specifically, checks that the response contains a list of attempted URL patterns
        and an indication that the current path did not match any of them.

        """
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
        """
        Tests the handling of an empty path in URL resolution, verifying that a 404 error is raised and the correct error message is displayed when the empty path does not match any defined URL patterns.
        """
        response = self.client.get("/")
        self.assertContains(
            response,
            "<p>The empty path didn’t match any of these.</p>",
            status_code=404,
            html=True,
        )

    def test_technical_404(self):
        """

        Tests the rendering of a technical 404 error page.

        This test case simulates a GET request to a URL that triggers a 404 error and verifies that the response
        contains the expected elements, including header, main content, footer, and exception details.
        It also checks that the correct view function is identified as the source of the error and that the
        error message includes information about the unmatched URL path.

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
        Tests that a class-based view correctly raises a 404 Not Found error and includes the expected information in the HTML response, specifically the name of the view that raised the exception.
        """
        response = self.client.get("/classbased404/")
        self.assertContains(
            response,
            '<th scope="row">Raised by:</th><td>view_tests.views.Http404View</td>',
            status_code=404,
            html=True,
        )

    def test_technical_500(self):
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
        Tests that a class-based view correctly raises a 500 Internal Server Error.

        Verifies that the error is logged and that the response contains the expected error message,
        both when the client accepts HTML and when it accepts plain text. Ensures that the view's
        name is correctly reported in the error message.

        The test covers the case where the client requests HTML and the case where it requests plain text,
        confirming that the error response is correctly formatted in both scenarios.
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
        Tests that the technical 404 converter correctly raises a 404 status code.

        This test case simulates a scenario where the IntConverter's to_python method
        raises an Http404 exception. It verifies that the HTTP response contains the
        'Page not found' message and has a status code of 404, as expected in such cases.

        The test focuses on ensuring that the converter properly handles the error and
        returns the expected HTTP response, providing a solid foundation for error handling
        in the application.\"\"\"
         desetños
        """
        with mock.patch.object(IntConverter, "to_python", side_effect=Http404):
            response = self.client.get("/path-post/1/")
            self.assertContains(response, "Page not found", status_code=404)

    def test_exception_reporter_from_request(self):
        """

        Tests the custom exception reporter by simulating a GET request to a view 
        that triggers an error and verifying the response contains the expected 
        custom traceback text and returns a 500 status code. 

        The test confirms that the exception is properly logged as an ERROR in 
        the django.request logger and that the custom reporter class correctly 
        includes the desired text in the error response.

        """
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
        with self.assertLogs("django.security", "WARNING"):
            response = self.client.get("/raises400/")
        self.assertContains(response, '<div class="context" id="', status_code=400)

    def test_400_bad_request(self):
        # When DEBUG=True, technical_500_template() is called.
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

        Verifies that the response contains the expected HTML header and status code, ensuring that the
        forbidden access is properly handled and communicated to the client.

        """
        response = self.client.get("/raises403/")
        self.assertContains(response, "<h1>403 Forbidden</h1>", status_code=403)

    def test_404(self):
        response = self.client.get("/raises404/")
        self.assertEqual(response.status_code, 404)

    def test_template_not_found_error(self):
        # Raises a TemplateDoesNotExist exception and shows the debug view.
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

        Tests the sharing of a traceback by generating an exception, creating an ExceptionReporter, 
        and verifying that the generated HTML traceback contains a form for sharing the exception on dpaste.com.

        The test simulates a ValueError, captures the exception information, and uses the ExceptionReporter 
        to generate an HTML representation of the traceback. It then asserts that the resulting HTML 
        includes a form for submitting the traceback to dpaste.com, ensuring that the sharing functionality 
        is correctly implemented.

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
        """
        Tests that suppressed exception context is correctly handled by the ExceptionReporter.

        This function simulates a situation where an exception is raised within another exception,
        with the inner exception's context suppressed. It then uses an ExceptionReporter to generate
        an HTML representation of the exception traceback and verifies that the resulting HTML meets
        expected criteria, including the presence of key exception information and the absence of
        suppressed context details.

        The test checks for the inclusion of the exception type, value, and traceback in the HTML,
        as well as the presence of a request information section (even if no request data is provided).
        It also verifies that the 'During handling of the above exception' message, which indicates
        suppressed context, is not present in the HTML output.
        """
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
        Tests the handling of a RuntimeError exception without a traceback in the mid-stack.

        Verifies that the ExceptionReporter correctly generates HTML and text representations of the exception, 
        including the exception type, value, and traceback information. 

        Specifically, checks for the presence of key elements such as exception type, value, and traceback headers 
        in the generated HTML and text, and ensures that the context of the original exception is properly included 
        in the exception message.

        The test simulates a nested exception scenario where an inner exception ('Inner Oops') is raised and 
        handled, but in the process of handling it, another exception ('Oops') is raised, creating a mid-stack 
        exception without a traceback. The resulting exception report is then verified to contain the expected 
        information in the correct format.
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
        Tests the reporting of frames in the exception handler when source code is not available.

        This test case simulates an exception occurrence and verifies that the exception reporter 
        correctly handles frames when the source code is not provided. It checks that the reporter 
        sets the 'context_line' to a default value, correctly identifies the filename, function 
        name, and line number, and that these values are correctly displayed in both HTML and text 
        representations of the traceback.
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
        """
        Tests the exception reporter's handling of traceback frames when the source code does not match the expected source.

        Verifies that the reporter correctly generates the traceback frames and HTML/text representations when the source code is not available.
        The test scenario simulates an exception being raised in a dynamically compiled code block and checks the following:

        * The last frame in the traceback has the correct filename, function name, and line number.
        * The context line is marked as '<source code not available>'.
        * The HTML and text representations of the traceback contain the correct information, including the filename, line number, and function name.
        The test ensures that the exception reporter behaves correctly when the source code is not available, providing a useful error message instead of attempting to display the non-existent source code.
        """
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
            Generates traceback frames using the reporter module.

            This function utilizes the reporter's capabilities to retrieve traceback frames, 
            which can be useful for error handling, debugging, and logging purposes.

            The generated frames are stored in the tb_frames variable for further use.

            The function accepts variable arguments (*args) and keyword arguments (**kwargs) 
            to provide flexibility in handling different scenarios or configurations. 

            Returns:
                None

            Note:
                The tb_frames variable is updated in-place, and its new value can be accessed 
                after calling this function.
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
        """

        Tests the async sensitive nested request functionality under different settings.

        This test case checks the behavior of the async sensitive view when nested requests 
        are made, verifying that the response and email sent are handled correctly. 

        The test covers two scenarios:
            - When DEBUG mode is enabled, it verifies that the response and email are marked as unsafe.
            - When DEBUG mode is disabled, it verifies that the response and email are marked as safe.

        """
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
        reporter_filter = SafeExceptionReporterFilter()
        initial = {"login": "cooper", "password": "secret"}
        self.assertEqual(
            reporter_filter.cleanse_setting("SETTING_NAME", initial),
            {"login": "cooper", "password": reporter_filter.cleansed_substitute},
        )

    def test_cleanse_setting_recurses_in_dictionary_with_non_string_key(self):
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
        """

        Tests that the :meth:`~SafeExceptionReporterFilter.cleanse_setting` method correctly 
        removes sensitive information from a setting when the setting value is a list or tuple 
        that contains nested lists, tuples, and dictionaries.

        This test ensures that the method can handle nested data structures, replacing 
        sensitive information such as passwords, API keys, and tokens with a cleansed 
        substitute, regardless of whether the input is a list or a tuple.

        """
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
        Tests the filtering of sensitive information in request metadata.

        This function verifies that the SafeExceptionReporterFilter correctly removes
        sensitive headers from a request's metadata, replacing them with a cleansed
        substitute. The test simulates a request with a secret header and checks that
        the filtered metadata contains the expected substitute value instead of the
        original sensitive information.
        """
        request = self.rf.get("/", headers={"secret-header": "super_secret"})
        reporter_filter = SafeExceptionReporterFilter()
        self.assertEqual(
            reporter_filter.get_safe_request_meta(request)["HTTP_SECRET_HEADER"],
            reporter_filter.cleansed_substitute,
        )

    def test_exception_report_uses_meta_filtering(self):
        """

        Tests the exception report functionality to ensure it correctly applies meta filtering.

        This test case verifies that sensitive information, such as secret headers, is not included in the exception report.
        It covers two scenarios: when the response content type is not specified and when it is set to JSON.
        The test passes if the secret header value is not present in the response content in both cases.

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
        get_default_exception_reporter_filter.cache_clear()
        self.addCleanup(get_default_exception_reporter_filter.cache_clear)

    def test_setting_allows_custom_subclass(self):
        self.assertIsInstance(
            get_default_exception_reporter_filter(),
            CustomExceptionReporterFilter,
        )

    def test_cleansed_substitute_override(self):
        """
        Tests that the cleanse_setting function correctly substitutes sensitive information.

        This test case verifies that the default exception reporter filter replaces a sensitive value, 
        such as a password, with a cleansed substitute to prevent it from being exposed.
        The test ensures that the substitution occurs as expected, maintaining the confidentiality of sensitive data.
        """
        reporter_filter = get_default_exception_reporter_filter()
        self.assertEqual(
            reporter_filter.cleanse_setting("password", "super_secret"),
            reporter_filter.cleansed_substitute,
        )

    def test_hidden_settings_override(self):
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
        response = self.client.get(
            "/raises500/", headers={"accept": "application/json"}
        )
        self.assertEqual(response.headers["Content-Type"], "text/plain; charset=utf-8")


class DecoratorsTests(SimpleTestCase):
    def test_sensitive_variables_not_called(self):
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
