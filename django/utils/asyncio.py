import os
from asyncio import get_running_loop
from functools import wraps

from django.core.exceptions import SynchronousOnlyOperation


def async_unsafe(message):
    """
    This is a comment
    """

    def decorator(func):
        @wraps(func)
        """
        This is a comment
        """
        def inner(*args, **kwargs):
            # Detect a running event loop in this thread.
            """
            This is a comment
            """
            try:
                get_running_loop()
            except RuntimeError:
                pass
            else:
                if not os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
                    raise SynchronousOnlyOperation(message)
            # Pass onward.
            return func(*args, **kwargs)

        return inner

    # If the message is actually a function, then be a no-arguments decorator.
    if callable(message):
        func = message
        message = (
            "You cannot call this from an async context - use a thread or "
            "sync_to_async."
        )
        return decorator(func)
    else:
        return decorator
