import logging

from django.template import Engine, Variable, VariableDoesNotExist
from django.test import SimpleTestCase


class VariableResolveLoggingTests(SimpleTestCase):
    loglevel = logging.DEBUG

    def test_log_on_variable_does_not_exist_silent(self):
        """
        Tests that a logging message is generated when attempting to log on a variable that does not exist, without raising an exception, when the attribute's exception is marked as silent.
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
        """
        Tests that logging a variable that does not exist raises a VariableDoesNotExist exception and produces an expected log message.
        """
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
        with self.assertNoLogs("django.template", self.loglevel):
            Variable("article.section").resolve({"article": {"section": "News"}})
