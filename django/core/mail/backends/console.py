"""
Email backend that writes messages to console instead of sending them.
"""

import sys
import threading

from django.core.mail.backends.base import BaseEmailBackend


class EmailBackend(BaseEmailBackend):
    def __init__(self, *args, **kwargs):
        """
        Initializes a new instance of the class.

        This constructor initializes the object with the provided arguments and keyword arguments.
        It sets the output stream to the value of the 'stream' keyword argument, defaulting to sys.stdout if not provided.
        A reentrant lock is also created to ensure thread safety.
        The parent class constructor is then called with the remaining arguments and keyword arguments to complete the initialization.
        """
        self.stream = kwargs.pop("stream", sys.stdout)
        self._lock = threading.RLock()
        super().__init__(*args, **kwargs)

    def write_message(self, message):
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
