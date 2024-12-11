import logging

from django.template import Engine, Variable, VariableDoesNotExist
from django.test import SimpleTestCase


class VariableResolveLoggingTests(SimpleTestCase):
    loglevel = logging.DEBUG

    def test_log_on_variable_does_not_exist_silent(self):
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
        Tests that no log messages are generated when a variable exists in the context.

        This test ensures that the logging system does not produce unnecessary log messages
        when a variable is successfully resolved from the context. The test variable used
        in this case is 'article.section', which is expected to be found in the provided
        context dictionary. The test passes if no log messages of the specified level are
        emitted by the django.template module during the resolution process.
        """
        with self.assertNoLogs("django.template", self.loglevel):
            Variable("article.section").resolve({"article": {"section": "News"}})
