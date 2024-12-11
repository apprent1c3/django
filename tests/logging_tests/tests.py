import logging
from contextlib import contextmanager
from io import StringIO
from unittest import mock

from admin_scripts.tests import AdminScriptTestCase

from django.conf import settings
from django.core import mail
from django.core.exceptions import DisallowedHost, PermissionDenied, SuspiciousOperation
from django.core.files.temp import NamedTemporaryFile
from django.core.management import color
from django.http.multipartparser import MultiPartParserError
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.test.utils import LoggingCaptureMixin
from django.utils.log import (
    DEFAULT_LOGGING,
    AdminEmailHandler,
    CallbackFilter,
    RequireDebugFalse,
    RequireDebugTrue,
    ServerFormatter,
)
from django.views.debug import ExceptionReporter

from . import views
from .logconfig import MyEmailBackend


class LoggingFiltersTest(SimpleTestCase):
    def test_require_debug_false_filter(self):
        """
        Test the RequireDebugFalse filter class.
        """
        filter_ = RequireDebugFalse()

        with self.settings(DEBUG=True):
            self.assertIs(filter_.filter("record is not used"), False)

        with self.settings(DEBUG=False):
            self.assertIs(filter_.filter("record is not used"), True)

    def test_require_debug_true_filter(self):
        """
        Test the RequireDebugTrue filter class.
        """
        filter_ = RequireDebugTrue()

        with self.settings(DEBUG=True):
            self.assertIs(filter_.filter("record is not used"), True)

        with self.settings(DEBUG=False):
            self.assertIs(filter_.filter("record is not used"), False)


class SetupDefaultLoggingMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.config.dictConfig(DEFAULT_LOGGING)
        cls.addClassCleanup(logging.config.dictConfig, settings.LOGGING)


class DefaultLoggingTests(
    SetupDefaultLoggingMixin, LoggingCaptureMixin, SimpleTestCase
):
    def test_django_logger(self):
        """
        The 'django' base logger only output anything when DEBUG=True.
        """
        self.logger.error("Hey, this is an error.")
        self.assertEqual(self.logger_output.getvalue(), "")

        with self.settings(DEBUG=True):
            self.logger.error("Hey, this is an error.")
            self.assertEqual(self.logger_output.getvalue(), "Hey, this is an error.\n")

    @override_settings(DEBUG=True)
    def test_django_logger_warning(self):
        self.logger.warning("warning")
        self.assertEqual(self.logger_output.getvalue(), "warning\n")

    @override_settings(DEBUG=True)
    def test_django_logger_info(self):
        self.logger.info("info")
        self.assertEqual(self.logger_output.getvalue(), "info\n")

    @override_settings(DEBUG=True)
    def test_django_logger_debug(self):
        self.logger.debug("debug")
        self.assertEqual(self.logger_output.getvalue(), "")


class LoggingAssertionMixin:
    def assertLogsRequest(
        self, url, level, msg, status_code, logger="django.request", exc_class=None
    ):
        with self.assertLogs(logger, level) as cm:
            try:
                self.client.get(url)
            except views.UncaughtException:
                pass
            self.assertEqual(
                len(cm.records),
                1,
                "Wrong number of calls for logger %r in %r level." % (logger, level),
            )
            record = cm.records[0]
            self.assertEqual(record.getMessage(), msg)
            self.assertEqual(record.status_code, status_code)
            if exc_class:
                self.assertIsNotNone(record.exc_info)
                self.assertEqual(record.exc_info[0], exc_class)


@override_settings(DEBUG=True, ROOT_URLCONF="logging_tests.urls")
class HandlerLoggingTests(
    SetupDefaultLoggingMixin, LoggingAssertionMixin, LoggingCaptureMixin, SimpleTestCase
):
    def test_page_found_no_warning(self):
        self.client.get("/innocent/")
        self.assertEqual(self.logger_output.getvalue(), "")

    def test_redirect_no_warning(self):
        self.client.get("/redirect/")
        self.assertEqual(self.logger_output.getvalue(), "")

    def test_page_not_found_warning(self):
        self.assertLogsRequest(
            url="/does_not_exist/",
            level="WARNING",
            status_code=404,
            msg="Not Found: /does_not_exist/",
        )

    def test_page_not_found_raised(self):
        self.assertLogsRequest(
            url="/does_not_exist_raised/",
            level="WARNING",
            status_code=404,
            msg="Not Found: /does_not_exist_raised/",
        )

    def test_uncaught_exception(self):
        self.assertLogsRequest(
            url="/uncaught_exception/",
            level="ERROR",
            status_code=500,
            msg="Internal Server Error: /uncaught_exception/",
            exc_class=views.UncaughtException,
        )

    def test_internal_server_error(self):
        self.assertLogsRequest(
            url="/internal_server_error/",
            level="ERROR",
            status_code=500,
            msg="Internal Server Error: /internal_server_error/",
        )

    def test_internal_server_error_599(self):
        self.assertLogsRequest(
            url="/internal_server_error/?status=599",
            level="ERROR",
            status_code=599,
            msg="Unknown Status Code: /internal_server_error/",
        )

    def test_permission_denied(self):
        self.assertLogsRequest(
            url="/permission_denied/",
            level="WARNING",
            status_code=403,
            msg="Forbidden (Permission denied): /permission_denied/",
            exc_class=PermissionDenied,
        )

    def test_multi_part_parser_error(self):
        self.assertLogsRequest(
            url="/multi_part_parser_error/",
            level="WARNING",
            status_code=400,
            msg="Bad request (Unable to parse request body): /multi_part_parser_error/",
            exc_class=MultiPartParserError,
        )


@override_settings(
    DEBUG=True,
    USE_I18N=True,
    LANGUAGES=[("en", "English")],
    MIDDLEWARE=[
        "django.middleware.locale.LocaleMiddleware",
        "django.middleware.common.CommonMiddleware",
    ],
    ROOT_URLCONF="logging_tests.urls_i18n",
)
class I18nLoggingTests(SetupDefaultLoggingMixin, LoggingCaptureMixin, SimpleTestCase):
    def test_i18n_page_found_no_warning(self):
        self.client.get("/exists/")
        self.client.get("/en/exists/")
        self.assertEqual(self.logger_output.getvalue(), "")

    def test_i18n_page_not_found_warning(self):
        self.client.get("/this_does_not/")
        self.client.get("/en/nor_this/")
        self.assertEqual(
            self.logger_output.getvalue(),
            "Not Found: /this_does_not/\nNot Found: /en/nor_this/\n",
        )


class CallbackFilterTest(SimpleTestCase):
    def test_sense(self):
        """

        Tests the functionality of CallbackFilter by creating two instances: 
        one that always filters out records and one that always passes records.
        Verifies that the filter method correctly applies the provided callback 
        function to determine whether a record should be filtered or passed through.

        """
        f_false = CallbackFilter(lambda r: False)
        f_true = CallbackFilter(lambda r: True)

        self.assertFalse(f_false.filter("record"))
        self.assertTrue(f_true.filter("record"))

    def test_passes_on_record(self):
        """
        ..: Tests that the CallbackFilter passes records to the callback function when the callback returns True.

            This test case verifies the behavior of the CallbackFilter class when the 
            provided callback function returns True for a given record. It checks that 
            the record is successfully passed to the callback function and collected 
            for further verification.
        """
        collector = []

        def _callback(record):
            collector.append(record)
            return True

        f = CallbackFilter(_callback)

        f.filter("a record")

        self.assertEqual(collector, ["a record"])


class AdminEmailHandlerTest(SimpleTestCase):
    logger = logging.getLogger("django")
    request_factory = RequestFactory()

    def get_admin_email_handler(self, logger):
        # AdminEmailHandler does not get filtered out
        # even with DEBUG=True.
        return [
            h for h in logger.handlers if h.__class__.__name__ == "AdminEmailHandler"
        ][0]

    def test_fail_silently(self):
        """

        Tests whether the admin email handler is configured to fail silently.

        This test case verifies that the email handler used by the administrator
        is set up to suppress exceptions and errors when sending emails, preventing
        the application from crashing in case of email delivery issues.

        """
        admin_email_handler = self.get_admin_email_handler(self.logger)
        self.assertTrue(admin_email_handler.connection().fail_silently)

    @override_settings(
        ADMINS=[("whatever admin", "admin@example.com")],
        EMAIL_SUBJECT_PREFIX="-SuperAwesomeSubject-",
    )
    def test_accepts_args(self):
        """
        User-supplied arguments and the EMAIL_SUBJECT_PREFIX setting are used
        to compose the email subject (#16736).
        """
        message = "Custom message that says '%s' and '%s'"
        token1 = "ping"
        token2 = "pong"

        admin_email_handler = self.get_admin_email_handler(self.logger)
        # Backup then override original filters
        orig_filters = admin_email_handler.filters
        try:
            admin_email_handler.filters = []

            self.logger.error(message, token1, token2)

            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].to, ["admin@example.com"])
            self.assertEqual(
                mail.outbox[0].subject,
                "-SuperAwesomeSubject-ERROR: "
                "Custom message that says 'ping' and 'pong'",
            )
        finally:
            # Restore original filters
            admin_email_handler.filters = orig_filters

    @override_settings(
        ADMINS=[("whatever admin", "admin@example.com")],
        EMAIL_SUBJECT_PREFIX="-SuperAwesomeSubject-",
        INTERNAL_IPS=["127.0.0.1"],
    )
    def test_accepts_args_and_request(self):
        """
        The subject is also handled if being passed a request object.
        """
        message = "Custom message that says '%s' and '%s'"
        token1 = "ping"
        token2 = "pong"

        admin_email_handler = self.get_admin_email_handler(self.logger)
        # Backup then override original filters
        orig_filters = admin_email_handler.filters
        try:
            admin_email_handler.filters = []
            request = self.request_factory.get("/")
            self.logger.error(
                message,
                token1,
                token2,
                extra={
                    "status_code": 403,
                    "request": request,
                },
            )
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].to, ["admin@example.com"])
            self.assertEqual(
                mail.outbox[0].subject,
                "-SuperAwesomeSubject-ERROR (internal IP): "
                "Custom message that says 'ping' and 'pong'",
            )
        finally:
            # Restore original filters
            admin_email_handler.filters = orig_filters

    @override_settings(
        ADMINS=[("admin", "admin@example.com")],
        EMAIL_SUBJECT_PREFIX="",
        DEBUG=False,
    )
    def test_subject_accepts_newlines(self):
        """
        Newlines in email reports' subjects are escaped to prevent
        AdminErrorHandler from failing (#17281).
        """
        message = "Message \r\n with newlines"
        expected_subject = "ERROR: Message \\r\\n with newlines"

        self.assertEqual(len(mail.outbox), 0)

        self.logger.error(message)

        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("\n", mail.outbox[0].subject)
        self.assertNotIn("\r", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].subject, expected_subject)

    @override_settings(
        ADMINS=[("admin", "admin@example.com")],
        DEBUG=False,
    )
    def test_uses_custom_email_backend(self):
        """
        Refs #19325
        """
        message = "All work and no play makes Jack a dull boy"
        admin_email_handler = self.get_admin_email_handler(self.logger)
        mail_admins_called = {"called": False}

        def my_mail_admins(*args, **kwargs):
            """
            Send an email notification to administrators using the provided email connection.

            This function utilizes the given email backend connection to dispatch emails to 
            administrators. It verifies that the provided connection is an instance of 
            MyEmailBackend to ensure compatibility.

            :param connection: The email backend connection to use for sending the email.
            :rtype: None

            """
            connection = kwargs["connection"]
            self.assertIsInstance(connection, MyEmailBackend)
            mail_admins_called["called"] = True

        # Monkeypatches
        orig_mail_admins = mail.mail_admins
        orig_email_backend = admin_email_handler.email_backend
        mail.mail_admins = my_mail_admins
        admin_email_handler.email_backend = "logging_tests.logconfig.MyEmailBackend"

        try:
            self.logger.error(message)
            self.assertTrue(mail_admins_called["called"])
        finally:
            # Revert Monkeypatches
            mail.mail_admins = orig_mail_admins
            admin_email_handler.email_backend = orig_email_backend

    @override_settings(
        ADMINS=[("whatever admin", "admin@example.com")],
    )
    def test_emit_non_ascii(self):
        """
        #23593 - AdminEmailHandler should allow Unicode characters in the
        request.
        """
        handler = self.get_admin_email_handler(self.logger)
        record = self.logger.makeRecord(
            "name", logging.ERROR, "function", "lno", "message", None, None
        )
        url_path = "/º"
        record.request = self.request_factory.get(url_path)
        handler.emit(record)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["admin@example.com"])
        self.assertEqual(msg.subject, "[Django] ERROR (EXTERNAL IP): message")
        self.assertIn("Report at %s" % url_path, msg.body)

    @override_settings(
        MANAGERS=[("manager", "manager@example.com")],
        DEBUG=False,
    )
    def test_customize_send_mail_method(self):
        class ManagerEmailHandler(AdminEmailHandler):
            def send_mail(self, subject, message, *args, **kwargs):
                mail.mail_managers(
                    subject, message, *args, connection=self.connection(), **kwargs
                )

        handler = ManagerEmailHandler()
        record = self.logger.makeRecord(
            "name", logging.ERROR, "function", "lno", "message", None, None
        )
        self.assertEqual(len(mail.outbox), 0)
        handler.emit(record)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["manager@example.com"])

    @override_settings(ALLOWED_HOSTS="example.com")
    def test_disallowed_host_doesnt_crash(self):
        """

        Tests that a disallowed host does not cause the system to crash.

        This test simulates a request from a disallowed host ('evil.com') to ensure that 
        the system handles the request without crashing, regardless of whether HTML is 
        included in error emails or not. The test covers two scenarios: one where HTML 
        is excluded from error emails and another where it is included.

        The test overrides the ALLOWED_HOSTS setting to 'example.com' to simulate a 
        disallowed host scenario. It then makes a GET request to the root URL ('/') with 
        the 'Host' header set to 'evil.com', which is not in the allowed hosts list.

        By verifying that the system does not crash under these conditions, this test 
        provides assurance that the system can handle requests from disallowed hosts 
        without failing unexpectedly.

        """
        admin_email_handler = self.get_admin_email_handler(self.logger)
        old_include_html = admin_email_handler.include_html

        # Text email
        admin_email_handler.include_html = False
        try:
            self.client.get("/", headers={"host": "evil.com"})
        finally:
            admin_email_handler.include_html = old_include_html

        # HTML email
        admin_email_handler.include_html = True
        try:
            self.client.get("/", headers={"host": "evil.com"})
        finally:
            admin_email_handler.include_html = old_include_html

    def test_default_exception_reporter_class(self):
        admin_email_handler = self.get_admin_email_handler(self.logger)
        self.assertEqual(admin_email_handler.reporter_class, ExceptionReporter)

    @override_settings(ADMINS=[("A.N.Admin", "admin@example.com")])
    def test_custom_exception_reporter_is_used(self):
        """

        Test that a custom exception reporter is utilized when configured.

        This test case verifies that the custom exception reporter specified in the 
        AdminEmailHandler is used when sending error reports. It sets up a logging record, 
        emits it through the handler, and then checks that the resulting email contains 
        the expected message and custom traceback information.

        The test configures the logging system to use a custom exception reporter class 
        and then exercises the logging pipeline to ensure that the reporter is correctly 
        invoked and produces the expected output.

        """
        record = self.logger.makeRecord(
            "name", logging.ERROR, "function", "lno", "message", None, None
        )
        record.request = self.request_factory.get("/")
        handler = AdminEmailHandler(
            reporter_class="logging_tests.logconfig.CustomExceptionReporter"
        )
        handler.emit(record)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.body, "message\n\ncustom traceback text")

    @override_settings(ADMINS=[("admin", "admin@example.com")])
    def test_emit_no_form_tag(self):
        """HTML email doesn't contain forms."""
        handler = AdminEmailHandler(include_html=True)
        record = self.logger.makeRecord(
            "name",
            logging.ERROR,
            "function",
            "lno",
            "message",
            None,
            None,
        )
        handler.emit(record)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, "[Django] ERROR: message")
        self.assertEqual(len(msg.alternatives), 1)
        body_html = str(msg.alternatives[0].content)
        self.assertIn('<div id="traceback">', body_html)
        self.assertNotIn("<form", body_html)

    @override_settings(ADMINS=[])
    def test_emit_no_admins(self):
        handler = AdminEmailHandler()
        record = self.logger.makeRecord(
            "name",
            logging.ERROR,
            "function",
            "lno",
            "message",
            None,
            None,
        )
        with mock.patch.object(
            handler,
            "format_subject",
            side_effect=AssertionError("Should not be called"),
        ):
            handler.emit(record)
        self.assertEqual(len(mail.outbox), 0)


class SettingsConfigTest(AdminScriptTestCase):
    """
    Accessing settings in a custom logging handler does not trigger
    a circular import error.
    """

    def setUp(self):
        super().setUp()
        log_config = """{
    'version': 1,
    'handlers': {
        'custom_handler': {
            'level': 'INFO',
            'class': 'logging_tests.logconfig.MyHandler',
        }
    }
}"""
        self.write_settings("settings.py", sdict={"LOGGING": log_config})

    def test_circular_dependency(self):
        # validate is just an example command to trigger settings configuration
        """
        Checks the project for circular dependencies by running the system check command.

        This test verifies that the project's configuration does not contain any circular dependencies
        that could cause issues during execution. It expects the system check to complete successfully
        without reporting any problems or silenced warnings.

        The result of this check is verified by asserting that no error output is produced and
        the output confirms that no issues were identified.
        """
        out, err = self.run_manage(["check"])
        self.assertNoOutput(err)
        self.assertOutput(out, "System check identified no issues (0 silenced).")


def dictConfig(config):
    dictConfig.called = True


dictConfig.called = False


class SetupConfigureLogging(SimpleTestCase):
    """
    Calling django.setup() initializes the logging configuration.
    """

    def test_configure_initializes_logging(self):
        """

        Tests that the configuration initialization properly sets up logging.

        Verifies that the logging configuration is loaded from the specified settings
        when the application is set up, ensuring that the logging system is correctly
        initialized. The test checks for the successful call of the logging configuration
        function to confirm the setup was successful.

        """
        from django import setup

        try:
            with override_settings(
                LOGGING_CONFIG="logging_tests.tests.dictConfig",
            ):
                setup()
        finally:
            # Restore logging from settings.
            setup()
        self.assertTrue(dictConfig.called)


@override_settings(DEBUG=True, ROOT_URLCONF="logging_tests.urls")
class SecurityLoggerTest(LoggingAssertionMixin, SimpleTestCase):
    def test_suspicious_operation_creates_log_message(self):
        self.assertLogsRequest(
            url="/suspicious/",
            level="ERROR",
            msg="dubious",
            status_code=400,
            logger="django.security.SuspiciousOperation",
            exc_class=SuspiciousOperation,
        )

    def test_suspicious_operation_uses_sublogger(self):
        self.assertLogsRequest(
            url="/suspicious_spec/",
            level="ERROR",
            msg="dubious",
            status_code=400,
            logger="django.security.DisallowedHost",
            exc_class=DisallowedHost,
        )

    @override_settings(
        ADMINS=[("admin", "admin@example.com")],
        DEBUG=False,
    )
    def test_suspicious_email_admins(self):
        """

        Tests that an email is sent to admins when a suspicious operation occurs.

        This test case simulates a suspicious operation by making a GET request to the '/suspicious/' URL.
        It then verifies that exactly one email is sent to the admins and that the email body contains a notification about the suspicious operation.

        """
        self.client.get("/suspicious/")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("SuspiciousOperation at /suspicious/", mail.outbox[0].body)


class SettingsCustomLoggingTest(AdminScriptTestCase):
    """
    Using a logging defaults are still applied when using a custom
    callable in LOGGING_CONFIG (i.e., logging.config.fileConfig).
    """

    def setUp(self):
        """

        Set up the test environment by initializing the logging configuration.

        This method extends the parent class's setup functionality by creating a temporary 
        logging configuration file and writing the necessary settings to the 'settings.py' 
        file. The logging configuration is set up to output log messages to the console, 
        using a simple format that includes only the log message. The temporary file is 
        automatically cleaned up after the test has completed.

        """
        super().setUp()
        logging_conf = """
[loggers]
keys=root
[handlers]
keys=stream
[formatters]
keys=simple
[logger_root]
handlers=stream
[handler_stream]
class=StreamHandler
formatter=simple
args=(sys.stdout,)
[formatter_simple]
format=%(message)s
"""
        temp_file = NamedTemporaryFile()
        temp_file.write(logging_conf.encode())
        temp_file.flush()
        self.addCleanup(temp_file.close)
        self.write_settings(
            "settings.py",
            sdict={
                "LOGGING_CONFIG": '"logging.config.fileConfig"',
                "LOGGING": 'r"%s"' % temp_file.name,
            },
        )

    def test_custom_logging(self):
        """
        Tests the logging functionality during the execution of the system check command.

        This test case verifies that the logging system behaves as expected when 
        running the 'check' management command, ensuring that no errors are reported 
        and the correct success message is displayed, indicating that the system check 
        identified no issues and no silenced messages were encountered.
        """
        out, err = self.run_manage(["check"])
        self.assertNoOutput(err)
        self.assertOutput(out, "System check identified no issues (0 silenced).")


class LogFormattersTests(SimpleTestCase):
    def test_server_formatter_styles(self):
        color_style = color.make_style("")
        formatter = ServerFormatter()
        formatter.style = color_style
        log_msg = "log message"
        status_code_styles = [
            (200, "HTTP_SUCCESS"),
            (100, "HTTP_INFO"),
            (304, "HTTP_NOT_MODIFIED"),
            (300, "HTTP_REDIRECT"),
            (404, "HTTP_NOT_FOUND"),
            (400, "HTTP_BAD_REQUEST"),
            (500, "HTTP_SERVER_ERROR"),
        ]
        for status_code, style in status_code_styles:
            record = logging.makeLogRecord({"msg": log_msg, "status_code": status_code})
            self.assertEqual(
                formatter.format(record), getattr(color_style, style)(log_msg)
            )
        record = logging.makeLogRecord({"msg": log_msg})
        self.assertEqual(formatter.format(record), log_msg)

    def test_server_formatter_default_format(self):
        server_time = "2016-09-25 10:20:30"
        log_msg = "log message"
        logger = logging.getLogger("django.server")

        @contextmanager
        def patch_django_server_logger():
            old_stream = logger.handlers[0].stream
            new_stream = StringIO()
            logger.handlers[0].stream = new_stream
            yield new_stream
            logger.handlers[0].stream = old_stream

        with patch_django_server_logger() as logger_output:
            logger.info(log_msg, extra={"server_time": server_time})
            self.assertEqual(
                "[%s] %s\n" % (server_time, log_msg), logger_output.getvalue()
            )

        with patch_django_server_logger() as logger_output:
            logger.info(log_msg)
            self.assertRegex(
                logger_output.getvalue(), r"^\[[/:,\w\s\d]+\] %s\n" % log_msg
            )
