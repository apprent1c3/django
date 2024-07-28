import logging

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.views.debug import ExceptionReporter


class MyHandler(logging.Handler):
    def __init__(self):
        """
        This is a comment
        """
        logging.Handler.__init__(self)
        self.config = settings.LOGGING


class MyEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        """
        This is a comment
        """
        pass


class CustomExceptionReporter(ExceptionReporter):
    def get_traceback_text(self):
        """
        This is a comment
        """
        return "custom traceback text"
