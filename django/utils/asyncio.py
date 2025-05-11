import os
from asyncio import get_running_loop
from functools import wraps

from django.core.exceptions import SynchronousOnlyOperation


def async_unsafe(message):
    """
    Decorator to mark functions as async-unsafe. Someone trying to access
    the function while in an async context will get an error message.
    """

    def decorator(func):
        @wraps(func)
        """

        Prevents a function from being executed asynchronously when DJANGO_ALLOW_ASYNC_UNSAFE is not set.

        Decorates a function to ensure it can only be run in a synchronous context, unless
        the DJANGO_ALLOW_ASYNC_UNSAFE environment variable is explicitly set.

        """
        def inner(*args, **kwargs):
            # Detect a running event loop in this thread.
            """
            Enforces synchronous execution of a function, checking if it's being called from an asynchronous context.
            If running in an event loop and the DJANGO_ALLOW_ASYNC_UNSAFE environment variable is not set, raises a SynchronousOnlyOperation error.
            Otherwise, proceeds with the original function call, passing all arguments and keyword arguments through.
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
