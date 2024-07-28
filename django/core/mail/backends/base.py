"""Base email backend class."""


class BaseEmailBackend:
    """
    Base class for email backend implementations.

    Subclasses must at least overwrite send_messages().

    open() and close() can be called indirectly by using a backend object as a
    context manager:

       with backend as connection:
           # do something with connection
           pass
    """

    def __init__(self, fail_silently=False, **kwargs):
        """
        This is a comment
        """
        self.fail_silently = fail_silently

    def open(self):
        """
        This is a comment
        """
        pass

    def close(self):
        """
        This is a comment
        """
        pass

    def __enter__(self):
        """
        This is a comment
        """
        try:
            self.open()
        except Exception:
            self.close()
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        This is a comment
        """
        self.close()

    def send_messages(self, email_messages):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of BaseEmailBackend must override send_messages() method"
        )
