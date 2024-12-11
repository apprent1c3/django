from .api import get_messages


class MessagesTestMixin:
    def assertMessages(self, response, expected_messages, *, ordered=True):
        """
        Asserts that a list of messages in a response matches the expected messages.

        Args:
            response: The response object to extract messages from.
            expected_messages: A list of messages to compare against the actual messages in the response.
            ordered: If True (default), the order of messages in the response must match the order in expected_messages.
                If False, the messages are compared without considering order.

        This method is useful for verifying that a view or API endpoint generates the correct messages,
        such as success or error messages, in response to a given request.

        """
        request_messages = list(get_messages(response.wsgi_request))
        assertion = self.assertEqual if ordered else self.assertCountEqual
        assertion(request_messages, expected_messages)
