"""
This module contains generic exceptions used by template backends. Although,
due to historical reasons, the Django template language also internally uses
these exceptions, other exceptions specific to the DTL should not be added
here.
"""


class TemplateDoesNotExist(Exception):
    """
    The exception used when a template does not exist. Optional arguments:

    backend
        The template backend class used when raising this exception.

    tried
        A list of sources that were tried when finding the template. This
        is formatted as a list of tuples containing (origin, status), where
        origin is an Origin object or duck type and status is a string with the
        reason the template wasn't found.

    chain
        A list of intermediate TemplateDoesNotExist exceptions. This is used to
        encapsulate multiple exceptions when loading templates from multiple
        engines.
    """

    def __init__(self, msg, tried=None, backend=None, chain=None):
        """
        Initializes a new instance of the exception class, providing a message and optional indicators of attempted recovery efforts and a call chain.

         :param msg: The message describing the exception.
         :param tried: A list of previous attempts made to recover from the exception, defaults to an empty list.
         :param backend: The backend associated with the exception, defaults to None.
         :param chain: A list representing the call chain leading to the exception, defaults to an empty list.
        """
        self.backend = backend
        if tried is None:
            tried = []
        self.tried = tried
        if chain is None:
            chain = []
        self.chain = chain
        super().__init__(msg)


class TemplateSyntaxError(Exception):
    """
    The exception used for syntax errors during parsing or rendering.
    """

    pass
