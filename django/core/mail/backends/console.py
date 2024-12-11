"""
Email backend that writes messages to console instead of sending them.
"""

import sys
import threading

from django.core.mail.backends.base import BaseEmailBackend


class EmailBackend(BaseEmailBackend):
    def __init__(self, *args, **kwargs):
        self.stream = kwargs.pop("stream", sys.stdout)
        self._lock = threading.RLock()
        super().__init__(*args, **kwargs)

    def write_message(self, message):
        """
        Writes a formatted message to the output stream.

        This method takes a message object, extracts its content, and encodes it to a string using the message's specified charset or 'utf-8' by default.
        The message content is then written to the stream, followed by a line of hyphens to visually separate it from subsequent output.
        The output is formatted with a newline character after each message and separator line for better readability.

        """
        msg = message.message()
        msg_data = msg.as_bytes()
        charset = (
            msg.get_charset().get_output_charset() if msg.get_charset() else "utf-8"
        )
        msg_data = msg_data.decode(charset)
        self.stream.write("%s\n" % msg_data)
        self.stream.write("-" * 79)
        self.stream.write("\n")

    def send_messages(self, email_messages):
        """Write all messages to the stream in a thread-safe way."""
        if not email_messages:
            return
        msg_count = 0
        with self._lock:
            try:
                stream_created = self.open()
                for message in email_messages:
                    self.write_message(message)
                    self.stream.flush()  # flush after each message
                    msg_count += 1
                if stream_created:
                    self.close()
            except Exception:
                if not self.fail_silently:
                    raise
        return msg_count
