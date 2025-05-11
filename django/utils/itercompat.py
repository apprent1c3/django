# RemovedInDjango60Warning: Remove this entire module.

import warnings

from django.utils.deprecation import RemovedInDjango60Warning


def is_iterable(x):
    """
    Checks if an object is iterable, returning True if it can be iterated over and False otherwise. 

    Note: This function is deprecated and should be replaced with isinstance(..., collections.abc.Iterable) for future compatibility.
    """
    warnings.warn(
        "django.utils.itercompat.is_iterable() is deprecated. "
        "Use isinstance(..., collections.abc.Iterable) instead.",
        RemovedInDjango60Warning,
        stacklevel=2,
    )
    try:
        iter(x)
    except TypeError:
        return False
    else:
        return True
