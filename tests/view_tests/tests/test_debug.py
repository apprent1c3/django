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
        Tests that the repr method of a CallableSettingWrapper instance returns the repr of the wrapped callable.
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
        """
        Tests the error handling for file uploads on the '/raises/' endpoint.

        Verifies that a 500 error is raised when making both GET and POST requests to the endpoint,
        and checks the response content for the presence of the uploaded file name, while ensuring the 
        file contents are not exposed in the error response.
        """
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

        Tests that a 404 error page is correctly displayed when a URL is not found in the URL patterns.
        Verifies the error page contains the expected content, including the URL patterns that were tried.

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
        response = self.client.get("/")
        self.assertContains(
            response,
            "<p>The empty path didn’t match any of these.</p>",
            status_code=404,
            html=True,
        )

    def test_technical_404(self):
        """
        Tests the rendering of a custom 404 error page for technical purposes, verifying that it contains the expected HTML structure and content when accessed via a specific URL.
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
        response = self.client.get("/classbased404/")
        self.assertContains(
            response,
            '<th scope="row">Raised by:</th><td>view_tests.views.Http404View</td>',
            status_code=404,
            html=True,
        )

    def test_technical_500(self):
        """
        Tests the technical 500 error page, verifying its structure and content 
        in both HTML and plain text formats, including the display of error information 
        such as the view that raised the exception.
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
        Tests that a 500 error is raised and handled correctly in a class-based view, with both HTML and plain text error responses.
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
        Tests that numeric IDs in error pages are not localized, ensuring they remain numeric for debugging purposes.
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
        """
        Tests that template exceptions are correctly logged and raised.

        Verifies that an error is logged at the 'ERROR' level when a template exception occurs, 
        and checks the source of the exception in the traceback to ensure it originated from the expected location.
        """
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
        """
        Tests the behavior of the template loader when a requested template file does not exist, verifying that an error is logged and the expected error message is displayed in the response.
        """
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

        Tests the encoding used when opening template files, verifying that it defaults to 'utf-8'.

        """
        with mock.patch.object(DebugPath, "open") as m:
            default_urlconf(None)
            m.assert_called_once_with(encoding="utf-8")
            m.reset_mock()
            technical_404_response(mock.MagicMock(), mock.Mock())
            m.assert_called_once_with(encoding="utf-8")

    def test_technical_404_converter_raise_404(self):
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
        """
        Tests the TemplateOverrideExceptionReporter by simulating a 500 error and verifying the error page and plain text error message.
        """
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
        Tests the debug view's handling of database exceptions by simulating an invalid query and verifying the correct error response is returned.
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
        """
        Tests the generation of an exception report for a given request, verifying the inclusion of essential information such as the exception type, value, and request details in the generated HTML traceback.
        """
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
        """
        Tests that an exception report can be generated without a request, verifying the generated HTML includes the exception type, value, and traceback, while omitting request-related information.
        """
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
        Tests that the ExceptionReporter correctly generates a HTML traceback with a form to share the error on a pastebin service.
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
        """
        Tests that the ExceptionReporter class supports different End Of Line (EOL) markers, including Unix, Windows, and Macintosh styles, when reading lines from a file.
        """
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
        """
        Tests that an exception report can be generated for a request without an exception, verifying that the report contains the correct request information and does not include unnecessary exception details.
        """
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
        Tests that an exception with a suppressed context is correctly reported.

        Verifies that the exception reporter generates HTML output without including
        information about the suppressed exception context, while still displaying
        the exception type, value, and traceback information.
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
        """
        Tests if the innermost exception without traceback is properly handled and represented in the exception report.

        Verifies the correctness of the traceback frames, HTML, and text representations of the exception report, ensuring that the exception type, value, and context are correctly displayed.
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
        """
        Tests the generation of an exception report with notes, verifying that the notes are properly included and escaped in both HTML and text formats.
        """
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
        Tests the ExceptionReporter class for rendering a traceback HTML and text when a mid-stack exception without a traceback occurs, ensuring that the original exception, its context, and the final exception are properly displayed.
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
        """
        Tests the reporting of nested exceptions, ensuring that explicit and implicit causes are correctly identified and displayed in both HTML and text representations of the exception traceback.
        """
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
        Tests that error positions in the traceback are correctly highlighted.

        This test case checks that the ExceptionReporter correctly identifies and highlights the lines 
        where exceptions were raised in both HTML and text formats, ensuring accurate error location 
        information for debugging purposes.
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
        Tests the ExceptionReporter's ability to handle and report exceptions that occur in frames without a source code file. Verifies that the reporter correctly identifies the frame details, including filename, function, and line number, and that the traceback HTML and text output contains the expected information.
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
        Tests that the ExceptionReporter generates the correct traceback frames and HTML/text output when the source code for a frame cannot be retrieved, indicating that the 'source code not available' message is displayed in the traceback.
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
        """
        Tests that the ExceptionReporter correctly handles cyclic references in exception chains when generating traceback frames.
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
        """
        Tests that a message can be provided in addition to a request when reporting an exception, and that this message is correctly displayed in the traceback HTML.
        """
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
        """
        Test that a message-only exception report is rendered correctly, including a report header, traceback, and request information sections, but excluding request details and exception type information.
        """
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
        """
        Tests the handling of non-UTF-8 encoded exception values and messages to ensure they do not cause the output generation to fail, verifying that these values are correctly escaped in the generated HTML traceback.
        """
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
        """
        Tests that safe strings stored in local variables are properly escaped when included in exception reports.
        """
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
        """
        Tests the ability of the ExceptionReporter to handle unprintable values when generating HTML tracebacks, ensuring that the output process does not fail when encountering values that cannot be printed.
        """
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
        """
        Tests that large values are handled properly by the exception reporter, 
        preventing the generation of excessively large HTML output. Verifies that large 
        strings are trimmed and represented as such in the traceback HTML.
        """
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
        Tests the handling of Unicode encoding errors in HTML-safe strings, verifying that error messages provide context about the problematic string and escape any HTML content.
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
        Tests importlib to ensure it correctly handles import errors when its loader incorrectly identifies it as a frozen application, resulting in a ModuleNotFoundError rather than an ImportError.
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
        Test that exceptions raised during evaluation of crafted objects are properly handled and reported in the traceback, without causing the system to fail.
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
        """
        Tests the ability to generate an exception report for a request originating from a disallowed host, verifying the report includes the disallowed host's URL.
        """
        request = self.rf.get("/", headers={"host": "evil.com"})
        reporter = ExceptionReporter(request, None, None, None)
        html = reporter.get_traceback_html()
        self.assertIn("http://evil.com/", html)

    def test_request_with_items_key(self):
        """

        Tests the generation of exception reports when 'items' key is present in a request's GET, POST, FILES, or COOKIES dictionaries.

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
        Tests that an error page can be rendered when the current user cannot be retrieved, such as when the database is unavailable, and that the error message includes a placeholder for the unavailable user information.
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
        Tests that the template encoding used by the ExceptionReporter is utf-8, 
        as specified by default in template engines, for both HTML and text tracebacks.
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

        Tests the construction of an insecure URI from a request object, ensuring that 
        absolute URIs and URIs with query parameters or special characters are handled correctly.

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
        """
        Tests that an exception report can be correctly generated when a request is made and an exception is raised, 
        verifying that the report includes relevant information such as the request method, URL, user, and exception details.
        """
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
        """
        Tests that an exception report can be generated without an associated request, 
        including the exception type, value, and traceback, while excluding request-related information.
        """
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
        Tests the handling of template exceptions, ensuring the correct error message is reported when a template error occurs.
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
        ibile to generate an exception report for requests containing 'items' in their GET, POST, FILES, or COOKIES dictionaries, testing that the ExceptionReporter correctly captures and represents these values in the error traceback.
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
        """
        Tests that an exception report can be generated for a request originating from a disallowed host, ensuring relevant information is included in the report.
        """
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

        Verifies that a view's response does not expose potentially sensitive information.
        Checks for the presence of certain variables and POST parameters in the response.

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

        Verifies that a view's response does not contain sensitive information.

        Args:
            view: The view to be tested.
            check_for_vars (bool): Whether to check for specific variables in the response. Defaults to True.
            check_for_POST_params (bool): Whether to check for POST parameters in the response. Defaults to True.

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
        Verifies that a view's response does not leak sensitive information, specifically variables and POST parameters, under error conditions.
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

        Verifies that email reports do not contain potentially sensitive information 
        in plaintext, but include it in HTML format. If specified, also checks that 
        POST request parameters are included in both plaintext and HTML email bodies.

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

        Verify that sensitive information is not displayed in email reports.

        Checks that a view does not expose sensitive data in the email body,
        both in plain text and HTML formats, and optionally verifies that
        certain POST parameters are included or excluded from the email content.

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

            Verifies that sensitive information from the POST parameters is not leaked 
            into the email report generated by the specified view.

            Validates that the email body contains variable names but not their 
            respective values, ensuring a secure and controlled disclosure of data.

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
        Tests the behavior of non-sensitive requests when error reports are generated, verifying that all relevant information is included in error responses and emails, both in debug and production modes.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(non_sensitive_view)
            self.verify_unsafe_email(non_sensitive_view)

        with self.settings(DEBUG=False):
            self.verify_unsafe_response(non_sensitive_view)
            self.verify_unsafe_email(non_sensitive_view)

    def test_sensitive_request(self):
        """
        Tests the handling of sensitive requests to ensure that sensitive information is not exposed in error reports.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(sensitive_view)
            self.verify_unsafe_email(sensitive_view)

        with self.settings(DEBUG=False):
            self.verify_safe_response(sensitive_view)
            self.verify_safe_email(sensitive_view)

    def test_async_sensitive_request(self):
        """

        Tests the async_sensitive_view function under different Django debug settings.

        Checks that the view returns an unsafe response and sends an unsafe email when DEBUG is True,
        and a safe response and email when DEBUG is False.

        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(async_sensitive_view)
            self.verify_unsafe_email(async_sensitive_view)

        with self.settings(DEBUG=False):
            self.verify_safe_response(async_sensitive_view)
            self.verify_safe_email(async_sensitive_view)

    def test_async_sensitive_nested_request(self):
        """
        Tests the async sensitive nested request view under different debug settings.

        Verifies that the view returns an unsafe response and sends an unsafe email when DEBUG is True,
        and a safe response and email when DEBUG is False.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(async_sensitive_view_nested)
            self.verify_unsafe_email(async_sensitive_view_nested)

        with self.settings(DEBUG=False):
            self.verify_safe_response(async_sensitive_view_nested)
            self.verify_safe_email(async_sensitive_view_nested)

    def test_paranoid_request(self):
        """
        Tests the behavior of \"paranoid\" requests, verifying that sensitive information is not included in error reports under different debug settings.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(paranoid_view)
            self.verify_unsafe_email(paranoid_view)

        with self.settings(DEBUG=False):
            self.verify_paranoid_response(paranoid_view)
            self.verify_paranoid_email(paranoid_view)

    def test_multivalue_dict_key_error(self):
        """
        Tests that a KeyError in a multivalue dictionary does not reveal sensitive POST parameters in error reports. Verifies safe and unsafe responses and emails in both debug and non-debug modes.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(multivalue_dict_key_error)
            self.verify_unsafe_email(multivalue_dict_key_error)

        with self.settings(DEBUG=False):
            self.verify_safe_response(multivalue_dict_key_error)
            self.verify_safe_email(multivalue_dict_key_error)

    def test_custom_exception_reporter_filter(self):
        """
        Tests that a custom exception reporter filter can be applied to a request, overriding the default filter, in both debug and non-debug modes.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(custom_exception_reporter_filter_view)
            self.verify_unsafe_email(custom_exception_reporter_filter_view)

        with self.settings(DEBUG=False):
            self.verify_unsafe_response(custom_exception_reporter_filter_view)
            self.verify_unsafe_email(custom_exception_reporter_filter_view)

    def test_sensitive_method(self):
        """
        Tests the behavior of the sensitive_variables decorator when applied to object methods, verifying its effectiveness in debug and non-debug modes.
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
        Tests the handling of sensitive variables in asynchronous object methods when the DEBUG setting is enabled and disabled, verifying the response and email content for both cases.
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
        Tests the functionality of the sensitive_variables decorator with asynchronous object methods, ensuring it correctly handles sensitive data in both debug and production modes.
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
        Tests that sensitive function arguments are not leaked when passed to a function decorated with the sensitive_variables decorator, under both debug and non-debug settings.
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
        Tests that sensitive information is not leaked when passed as keyword arguments to a function decorated with the sensitive_variables decorator, covering both debug and non-debug modes.
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
        Verifies that callable settings are not evaluated on the debug page, ensuring they do not leak sensitive information or cause unintended behavior.
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
        Tests that callable settings which forbid setting attributes via the use of __slots__ do not cause errors on the debug page, specifically ensuring that the callable setting's output is not unnecessarily displayed.
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

        Verify that sensitive settings are not exposed in the debug page.

        Checks that settings like passwords, secret keys, and API tokens are not displayed
        when the debug page is shown, even when their values are set.

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

        Checks that sensitive settings information is filtered out of debug pages.

        Verifies that specific sensitive keys (e.g. SECRET_KEY, PASSWORD, API_KEY) are not 
        displayed in debug responses, even when recursive settings are present.

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
        Tests that the cleanse_setting function correctly recurses into lists and tuples to redact sensitive information from settings
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
        request = self.rf.get("/", headers={"secret-header": "super_secret"})
        reporter_filter = SafeExceptionReporterFilter()
        self.assertEqual(
            reporter_filter.get_safe_request_meta(request)["HTTP_SECRET_HEADER"],
            reporter_filter.cleansed_substitute,
        )

    def test_exception_report_uses_meta_filtering(self):
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
        Tests that non-sensitive request information is visible in default error reports when debug mode is enabled, and remains inaccessible when debug mode is disabled.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(non_sensitive_view, check_for_vars=False)

        with self.settings(DEBUG=False):
            self.verify_unsafe_response(non_sensitive_view, check_for_vars=False)

    def test_sensitive_request(self):
        """
        Tests that sensitive POST parameters are not visible in error reports for sensitive requests, regardless of debug mode.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(sensitive_view, check_for_vars=False)

        with self.settings(DEBUG=False):
            self.verify_safe_response(sensitive_view, check_for_vars=False)

    def test_async_sensitive_request(self):
        """
        Tests that sensitive POST parameters are not included in default error reports for asynchronous sensitive requests, both in debug and non-debug modes.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(async_sensitive_view, check_for_vars=False)

        with self.settings(DEBUG=False):
            self.verify_safe_response(async_sensitive_view, check_for_vars=False)

    def test_async_sensitive_request_nested(self):
        """
        Tests that sensitive POST parameters in async views with nested requests are not logged in error reports, regardless of debug mode.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(
                async_sensitive_view_nested, check_for_vars=False
            )

        with self.settings(DEBUG=False):
            self.verify_safe_response(async_sensitive_view_nested, check_for_vars=False)

    def test_paranoid_request(self):
        """
        Tests that \"paranoid\" requests do not expose POST parameters in error reports, under both debug and non-debug modes.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(paranoid_view, check_for_vars=False)

        with self.settings(DEBUG=False):
            self.verify_paranoid_response(paranoid_view, check_for_vars=False)

    def test_custom_exception_reporter_filter(self):
        """

        Tests that a custom exception reporter filter can be assigned to a request,
        overriding the default filter, and functions correctly in both debug and non-debug modes.

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
        """
        Checks that the sensitive_variables decorator is used correctly by verifying it raises an error when called as a decorator without parentheses.
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
        """
        Verifies that sensitive_post_parameters decorator is used correctly.

        This test ensures that the sensitive_post_parameters function is called when used as a decorator, preventing incorrect usage that could lead to errors.
        """
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
        Tests that the sensitive_post_parameters decorator correctly raises a TypeError when not given an HttpRequest object, ensuring proper usage and handling of HTTP requests in decorated views.
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
