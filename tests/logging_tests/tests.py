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
        """

        Sets up the class for testing by configuring the logging settings.

        This method is called once before running all tests in the class. It sets the logging configuration to the default settings defined in :data:`DEFAULT_LOGGING`.
        After all tests have finished, the logging configuration is reset to the settings defined in :data:`settings.LOGGING` to ensure cleanup.

        """
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
        """
        Tests the Django logger to ensure it correctly outputs a warning message.

        This test case verifies that when a warning is logged using the logger's warning method,
        the expected warning message is properly written to the log output.

        :raises AssertionError: if the logged warning message does not match the expected output
        """
        self.logger.warning("warning")
        self.assertEqual(self.logger_output.getvalue(), "warning\n")

    @override_settings(DEBUG=True)
    def test_django_logger_info(self):
        self.logger.info("info")
        self.assertEqual(self.logger_output.getvalue(), "info\n")

    @override_settings(DEBUG=True)
    def test_django_logger_debug(self):
        """
        Tests that Django logger does not output debug messages when running in debug mode.

        This test case verifies the functionality of the Django logger when the DEBUG setting is enabled.
        It checks if a debug message is correctly logged and if it appears in the logger output as expected.
        The test ensures that the logger behaves as intended in a debug environment, providing a basis for troubleshooting and debugging purposes.
        """
        self.logger.debug("debug")
        self.assertEqual(self.logger_output.getvalue(), "")


class LoggingAssertionMixin:
    def assertLogsRequest(
        self, url, level, msg, status_code, logger="django.request", exc_class=None
    ):
        """
        Asserts that a GET request to the given URL logs a message at the specified level.

        Parameters
        ----------
        url : str
            The URL to send the GET request to.
        level : int
            The logging level at which the message should be logged.
        msg : str
            The expected log message.
        status_code : int
            The expected status code associated with the log record.
        logger : str, optional
            The name of the logger to check (default is 'django.request').
        exc_class : type, optional
            The expected exception class associated with the log record, if any.

        This function verifies that the log message matches the expected message and that the log record contains the correct status code and exception information, if applicable.

        Raises
        ------
        AssertionError
            If the log message does not match the expected message, or if the log record does not contain the correct status code or exception information.

        """
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
        """
        Tests that a redirect occurs without triggering any warnings.

        This test case checks the functionality of a redirect by sending a GET request
        to the '/redirect/' endpoint and verifying that no warnings are logged during
        the process. It ensures that the redirect operation does not produce any
        unexpected warnings, providing confidence in the reliability of the system.
        """
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
        """
        Tests that no warnings are emitted when an i18n page is found.

        This test scenario simulates requests to existing pages with and without 
        locale prefix, verifying that the logging output remains empty, indicating 
        no warnings were generated during the page requests.
        """
        self.client.get("/exists/")
        self.client.get("/en/exists/")
        self.assertEqual(self.logger_output.getvalue(), "")

    def test_i18n_page_not_found_warning(self):
        """
        Tests whether the proper warning messages are logged when an I18N page is not found.

        Verifies that a 'Not Found' warning is correctly emitted for both non-translated and translated pages that do not exist.

        Checks the logged output to ensure the expected warnings are present for the given non-existent page URLs.
        """
        self.client.get("/this_does_not/")
        self.client.get("/en/nor_this/")
        self.assertEqual(
            self.logger_output.getvalue(),
            "Not Found: /this_does_not/\nNot Found: /en/nor_this/\n",
        )


class CallbackFilterTest(SimpleTestCase):
    def test_sense(self):
        f_false = CallbackFilter(lambda r: False)
        f_true = CallbackFilter(lambda r: True)

        self.assertFalse(f_false.filter("record"))
        self.assertTrue(f_true.filter("record"))

    def test_passes_on_record(self):
        collector = []

        def _callback(record):
            """
            Callback function to collect log records.

            This function is used to process log records, appending them to a collector for further processing.
            It takes a log record as input and returns a boolean value indicating success.

            :param record: The log record to be collected
            :rtype: bool
            :return: True to indicate successful collection of the log record
            """
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
            Send a notification email to administrators.

            This function facilitates sending emails to administrators using a predefined 
            email backend. It checks if the provided connection is an instance of 
            MyEmailBackend before proceeding.

            Args:
                *args: Variable number of arguments
                **kwargs: Keyword arguments, including 'connection' which is required

            Note:
                The 'connection' keyword argument must be an instance of MyEmailBackend.

            This function does not return any value but triggers an internal flag 
            indicating that the mail admins functionality has been called.
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
        """

        Tests the customization of the send mail method for sending error emails to managers.

        This test case verifies that the customized email handler successfully sends an email
        to the specified manager's email address when an error occurs. It ensures that the email
        is sent to the correct recipient and that the email outbox is updated correctly.

        The test uses a customized AdminEmailHandler that overrides the send mail method to
        use the mail_managers function, which sends emails to the managers listed in the
        MANAGERS setting.

        """
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
        Tests that an invalid host header does not cause the application to crash.

        This test checks the application's behavior when a request is made with a host header
        that is not in the ALLOWED_HOSTS setting. It verifies that the application handles this
        scenario without crashing, both when HTML emails are included and when they are not.

        The test overrides the ALLOWED_HOSTS setting to 'example.com' and then makes a request
        to the root URL with a host header set to 'evil.com', which is not in the allowed hosts.
        It checks that the application behaves as expected in both cases, ensuring that the
        admin email handler functions correctly and does not cause any crashes.
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
        """
        Tests whether the default exception reporter class is correctly assigned to the admin email handler.

        Verifies that the admin email handler, responsible for sending exception reports,
        utilizes the standard exception reporting class provided by the system, ensuring
        consistent and reliable error reporting to administrators.

        Only the assignment of the exception reporter class is verified, without 
        considering the actual functionality of the reporter or the email handler. 

        Checks the default configuration, ensuring that the correct reporter class is 
        selected and used for error reporting purposes when no specific configuration 
        is provided.
        """
        admin_email_handler = self.get_admin_email_handler(self.logger)
        self.assertEqual(admin_email_handler.reporter_class, ExceptionReporter)

    @override_settings(ADMINS=[("A.N.Admin", "admin@example.com")])
    def test_custom_exception_reporter_is_used(self):
        """

        Tests if a custom exception reporter is used when an error is logged.

        This test case verifies that the custom exception reporter class is utilized when 
        an error occurs and an email notification is sent to administrators. It checks if 
        the email contains the expected error message and custom traceback text.

        The test uses a mock request, sets up an AdminEmailHandler with the custom 
        reporter class, and then emits a log record with an error level. It then asserts 
        that an email is sent and that its content matches the expected output.

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
        Check for circular dependencies in the system.

        This test method verifies that the system configuration does not contain any circular dependencies.
        It runs the system check command and then asserts that no errors are reported and the expected success message is displayed.
        The test passes if no issues are identified by the system check, indicating a clean and properly configured system.

        Returns:
            None

        Raises:
            AssertionError: If the system check reports any issues or errors.
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
        Tests whether the initial configuration of the application properly sets up logging.

        This test case verifies that the logging configuration is initialized as expected
        when the application is set up. It checks if the dictConfig function is called,
        which is responsible for configuring the logging system based on a dictionary
        configuration. The test ensures that the logging is correctly configured at the
        start of the application.
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
        self.client.get("/suspicious/")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("SuspiciousOperation at /suspicious/", mail.outbox[0].body)


class SettingsCustomLoggingTest(AdminScriptTestCase):
    """
    Using a logging defaults are still applied when using a custom
    callable in LOGGING_CONFIG (i.e., logging.config.fileConfig).
    """

    def setUp(self):
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
        Tests custom logging functionality by running the system check command.

        Verifies that the system check command executes successfully, producing no error output.
        Checks that the command produces the expected output, indicating that no issues were identified during the system check.

        :returns: None
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
            """

            Context manager to patch the Django server logger stream.

            This function allows you to capture log messages from the Django server logger.
            It temporarily redirects the logger's output to a StringIO object, yielding it to the caller.
            After the context manager exits, the original logger stream is restored.

            Use this context manager when you need to test or inspect log messages produced by the Django server logger.
            The yielded StringIO object will contain the log messages produced during the execution of the code within the context manager.

            """
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
