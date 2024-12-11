import logging

from django.template import Engine, Variable, VariableDoesNotExist
from django.test import SimpleTestCase


class VariableResolveLoggingTests(SimpleTestCase):
    loglevel = logging.DEBUG

    def test_log_on_variable_does_not_exist_silent(self):
        """
        Tests that resolving a variable that does not exist on an object raises a silent exception and logs an error message at the specified log level.

        The test case verifies that the log message correctly identifies the variable and template involved, and that the exception is properly recorded in the log record.
        """
        class TestObject:
            class SilentDoesNotExist(Exception):
                silent_variable_failure = True

            @property
            def template_name(self):
                return "template_name"

            @property
            def template(self):
                return Engine().from_string("")

            @property
            def article(self):
                raise TestObject.SilentDoesNotExist("Attribute does not exist.")

            def __iter__(self):
                return (attr for attr in dir(TestObject) if attr[:2] != "__")

            def __getitem__(self, item):
                return self.__dict__[item]

        with self.assertLogs("django.template", self.loglevel) as cm:
            Variable("article").resolve(TestObject())

        self.assertEqual(len(cm.records), 1)
        log_record = cm.records[0]
        self.assertEqual(
            log_record.getMessage(),
            "Exception while resolving variable 'article' in template 'template_name'.",
        )
        self.assertIsNotNone(log_record.exc_info)
        raised_exception = log_record.exc_info[1]
        self.assertEqual(str(raised_exception), "Attribute does not exist.")

    def test_log_on_variable_does_not_exist_not_silent(self):
        with self.assertLogs("django.template", self.loglevel) as cm:
            with self.assertRaises(VariableDoesNotExist):
                Variable("article.author").resolve({"article": {"section": "News"}})

        self.assertEqual(len(cm.records), 1)
        log_record = cm.records[0]
        self.assertEqual(
            log_record.getMessage(),
            "Exception while resolving variable 'author' in template 'unknown'.",
        )
        self.assertIsNotNone(log_record.exc_info)
        raised_exception = log_record.exc_info[1]
        self.assertEqual(
            str(raised_exception),
            "Failed lookup for key [author] in {'section': 'News'}",
        )

    def test_no_log_when_variable_exists(self):
        """
        Tests that no log messages are emitted when a Variable is resolved and the variable exists in the context.

        This test case ensures that the templating engine does not generate unnecessary log output when a variable is successfully resolved from the provided context. The test verifies that the 'django.template' logger at the specified log level remains silent during the resolution process.
        """
        with self.assertNoLogs("django.template", self.loglevel):
            Variable("article.section").resolve({"article": {"section": "News"}})
