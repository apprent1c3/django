"""A custom backend for testing."""

from django.core.mail.backends.base import BaseEmailBackend


class EmailBackend(BaseEmailBackend):
    def __init__(self, *args, **kwargs):
        """
        Initializes the object, inheriting from its parent class and setting up an instance variable to store test outbox data. 

        The test outbox is a list used to hold and manage test-related output. This allows for further processing or verification of the test results in subsequent methods. 

        :param args: Variable number of non-keyword arguments passed to the parent class
        :param kwargs: Variable number of keyword arguments passed to the parent class 
        :ivar test_outbox: List to store test output data 
        :return: None
        """
        super().__init__(*args, **kwargs)
        self.test_outbox = []

    def send_messages(self, email_messages):
        # Messages are stored in an instance variable for testing.
        self.test_outbox.extend(email_messages)
        return len(email_messages)
