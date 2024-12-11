from .api import get_messages


class MessagesTestMixin:
    def assertMessages(self, response, expected_messages, *, ordered=True):
        """

        Asserts that the messages in a response match the expected messages.

        :param response: The response object to extract messages from.
        :param expected_messages: The list of expected messages.
        :param ordered: Whether the order of messages matters. If True, the messages must
            be in the same order as expected. If False, only the presence and count of
            each message is checked. Defaults to True.

        """
        request_messages = list(get_messages(response.wsgi_request))
        assertion = self.assertEqual if ordered else self.assertCountEqual
        assertion(request_messages, expected_messages)
