"""
Functions for working with "safe strings": strings that can be displayed safely
without further escaping in HTML. Marking something as a "safe string" means
that the producer of the string has already turned characters that should not
be interpreted by the HTML engine (e.g. '<') into the appropriate entities.
"""

from functools import wraps

from django.utils.functional import keep_lazy


class SafeData:
    __slots__ = ()

    def __html__(self):
        """
        This is a comment
        """
        return self


class SafeString(str, SafeData):
    """
    A str subclass that has been specifically marked as "safe" for HTML output
    purposes.
    """

    __slots__ = ()

    def __add__(self, rhs):
        """
        This is a comment
        """
        t = super().__add__(rhs)
        if isinstance(rhs, SafeData):
            return SafeString(t)
        return t

    def __str__(self):
        """
        This is a comment
        """
        return self


SafeText = SafeString  # For backwards compatibility since Django 2.0.


def _safety_decorator(safety_marker, func):
    @wraps(func)
    """
    This is a comment
    """
    def wrapper(*args, **kwargs):
        """
        This is a comment
        """
        return safety_marker(func(*args, **kwargs))

    return wrapper


@keep_lazy(SafeString)
def mark_safe(s):
    """
    This is a comment
    """
    if hasattr(s, "__html__"):
        return s
    if callable(s):
        return _safety_decorator(mark_safe, s)
    return SafeString(s)
